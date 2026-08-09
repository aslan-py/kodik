"""
Сервис персистентности результатов парсинга (BP-1).

Инкапсулирует общую логику сохранения результата парсинга, которая
раньше дублировалась между ``tasks.run_parser_async`` и
``adaptive.integration.runner.AdaptiveRunner.run_task``:

- сериализация ``ParsedResponse`` в канонический словарь;
- вычисление content-хэша (только от items, без meta и file_path);
- сверка с предыдущим хэшем в Redis (дедупликация);
- копирование HTML-файла из временного расположения с retry;
- сохранение raw JSON на диск;
- запись ``RawItem`` в БД;
- обновление ``updated_at`` при неизменном хэше.

Используется классическим BP-1 пайплайном и адаптивным runner'ом,
что гарантирует единообразное поведение (статусы, хэши, жизненный цикл
``RawItem``) во всех режимах сбора.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.models import RawItem

logger = logging.getLogger(__name__)

# Константы копирования HTML с повторными попытками (на Windows файл может
# быть временно заблокирован антивирусом/индексацией).
_COPY_MAX_RETRIES = 3
_COPY_BASE_DELAY = 0.5  # секунды, множится на номер попытки


def calculate_content_hash(data: dict[str, Any]) -> str:
    """Вычислить MD5-хэш от канонического JSON содержимого.

    Хэш считается ТОЛЬКО от ``items`` (смысловое содержимое), так как
    ``meta`` содержит изменяемые поля (``source_request_url``,
    ``search_task_id``, ``fetched_at``). Из ``items`` дополнительно
    исключается ``extra.file_path`` — путь к HTML, меняющийся при каждом
    запуске.
    """
    import hashlib

    items = data.get('items', [])
    clean_items: list[dict[str, Any]] = []
    for item in items:
        item_copy = dict(item)
        if 'extra' in item_copy:
            item_copy['extra'] = dict(item_copy['extra'])
            item_copy['extra'].pop('file_path', None)
        clean_items.append(item_copy)

    json_str = json.dumps(clean_items, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def copy_html_file(parser_file_path: str, dest_dir: str) -> str | None:
    """Скопировать HTML-файл в целевой каталог с повторными попытками.

    На Windows источник может быть временно занят другим процессом
    (не освобождён дескриптор браузера/краулера), из-за чего
    ``shutil.copy2`` бросает ``PermissionError``. При ошибке повторяем
    копирование с растущей задержкой; при исчерпании попыток — пробуем
    скопировать вручную через чтение/запись содержимого.

    Возвращает путь назначения при успехе, иначе ``None`` (не прерывая
    обработку задачи).
    """
    if not parser_file_path or not os.path.exists(parser_file_path):
        return None

    os.makedirs(dest_dir, exist_ok=True)
    html_filename = os.path.basename(parser_file_path)
    dest_path = os.path.join(dest_dir, html_filename)

    # 1. Попытки через shutil.copy2.
    for attempt in range(1, _COPY_MAX_RETRIES + 1):
        try:
            shutil.copy2(parser_file_path, dest_path)
            return dest_path
        except PermissionError as e:
            if attempt < _COPY_MAX_RETRIES:
                delay = _COPY_BASE_DELAY * attempt
                logger.warning(
                    'Copy attempt %d/%d failed: %s. Retrying in %.1fs...',
                    attempt,
                    _COPY_MAX_RETRIES,
                    e,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    'Failed to copy HTML after %d attempts: %s',
                    _COPY_MAX_RETRIES,
                    e,
                )

    # 2. Fallback: копирование содержимого вручную.
    try:
        with (
            open(parser_file_path, 'rb') as f_in,
            open(dest_path, 'wb') as f_out,
        ):
            shutil.copyfileobj(f_in, f_out)
        return dest_path
    except (PermissionError, OSError) as inner:
        logger.error(
            'Failed to save HTML %s -> %s: %s',
            parser_file_path,
            dest_path,
            inner,
        )
        return None


def save_raw_json(data: dict[str, Any], task_id: int, raw_dir: str) -> str:
    """Сохранить raw данные в JSON-файл на диске.

    Возвращает полный путь к сохранённому файлу.
    """
    os.makedirs(raw_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'raw_{task_id}_{ts}.json'
    file_path = os.path.join(raw_dir, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info('Raw data saved to: %s', file_path)
    return file_path


def ensure_directories() -> None:
    """Создать директории для хранения HTML и raw данных."""
    Path(settings.bp1_html_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.bp1_raw_dir).mkdir(parents=True, exist_ok=True)


# ============================================================================
# РЕПОЗИТОРИЙ / СЕРВИС СОХРАНЕНИЯ
# ============================================================================


class RawDataService:
    """Единый сервис сохранения результатов парсинга.

    Скрывает детали записи ``RawItem``, сверки с Redis, копирования HTML
    и сохранения JSON. Оба пайплайна (классический и адаптивный) вызывают
    ``persist()`` и получают единообразный результат.
    """

    def __init__(self, session: AsyncSession, redis_client: Any):
        self.session = session
        self.redis = redis_client

    def _redis_key(self, search_task_id: int) -> str:
        """Ключ Redis для задачи (обратная совместимость с BP-1)."""
        return str(search_task_id)

    async def _get_old_hash(self, search_task_id: int) -> str | None:
        """Вернуть предыдущий хэш задачи из Redis (None — первый сбор)."""
        return await self.redis.get(self._redis_key(search_task_id))

    def _serialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Сериализовать результат, исключив file_path из extra.

        ``file_path`` меняется при каждом запуске и не должен влиять
        на сравнение содержимого/попадать в stored данные.
        """
        out = dict(data)
        items = out.get('items', [])
        clean_items: list[dict[str, Any]] = []
        for item in items:
            item_copy = dict(item)
            if 'extra' in item_copy:
                item_copy['extra'] = dict(item_copy['extra'])
                item_copy['extra'].pop('file_path', None)
            clean_items.append(item_copy)
        out['items'] = clean_items
        return out

    async def save_raw_item(
        self,
        search_task_id: int,
        data: dict[str, Any],
        content_hash: str,
        status: str,
        html_file_path: str | None = None,
        source_request_url: str | None = None,
        error_message: str | None = None,
    ) -> int:
        """Сохранить строку ``RawItem`` в БД."""
        now = datetime.now(UTC)
        raw_item = RawItem(
            search_task_id=search_task_id,
            status=status,
            content_hash=content_hash,
            raw_data=data,
            html_file_path=html_file_path,
            source_request_url=source_request_url,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        self.session.add(raw_item)
        await self.session.commit()
        await self.session.refresh(raw_item)
        return raw_item.id

    async def update_timestamp(self, search_task_id: int) -> None:
        """Обновить ``updated_at`` у последней записи задачи.

        Вызывается, когда хэш совпал: новую строку не создаём, статус
        не трогаем, обновляем только время последней сверки.
        """
        # 1. Получаем ID последней записи.
        select_stmt = (
            select(RawItem.id)
            .where(RawItem.search_task_id == search_task_id)
            .order_by(RawItem.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(select_stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return

        # 2. Обновляем updated_at по ID.
        stmt = (
            update(RawItem)
            .where(RawItem.id == row)
            .values(updated_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def persist_error(
        self,
        search_task_id: int,
        error_message: str,
        source_request_url: str | None = None,
    ) -> int:
        """Сохранить строку ``RawItem`` со статусом error."""
        return await self.save_raw_item(
            search_task_id=search_task_id,
            data={},
            content_hash='',
            status='error',
            source_request_url=source_request_url,
            error_message=error_message,
        )

    async def persist(
        self,
        search_task_id: int,
        response_data: dict[str, Any],
        source_request_url: str | None = None,
        html_source_path: str | None = None,
    ) -> dict[str, Any]:
        """Сохранить успешный результат парсинга целиком.

        Выполняет полный цикл персистентности:

        1. Сериализует ``response_data`` (``model_dump()`` результат).
        2. Вычисляет content-хэш.
        3. Сверяет с Redis — при совпадении обновляет ``updated_at``
           и возвращает ``{'status': 'unchanged', ...}``.
        4. Копирует HTML-файл, сохраняет raw JSON, пишет ``RawItem``.
        5. Обновляет хэш в Redis.

        Args:
            search_task_id: ID задачи.
            response_data: ``ParsedResponse.model_dump()`` словарь.
            source_request_url: Ссылка на оригинальный запрос парсера.
            html_source_path: Путь к HTML-файлу (если парсер его сохранил).

        Returns:
            dict с полями результата (status, hash, raw_item_id и т.д.).
        """
        data_dict = self._serialize(response_data)
        content_hash = calculate_content_hash(data_dict)

        old_hash = await self._get_old_hash(search_task_id)

        # Хэш совпал — ничего не изменилось.
        if old_hash == content_hash:
            logger.info('Content unchanged for task %s', search_task_id)
            await self.update_timestamp(search_task_id)
            return {
                'status': 'unchanged',
                'search_task_id': search_task_id,
                'hash': content_hash,
            }

        status = 'new' if old_hash is None else 'changed'

        # Копируем HTML в каталог html_pages.
        html_file_path = None
        if html_source_path:
            html_file_path = copy_html_file(
                html_source_path, settings.bp1_html_dir
            )
            if html_file_path:
                logger.info('HTML file copied to: %s', html_file_path)

        # Сохраняем raw JSON на диск.
        raw_file_path = save_raw_json(
            data_dict, search_task_id, settings.bp1_raw_dir
        )

        # Записываем RawItem в БД.
        raw_item_id = await self.save_raw_item(
            search_task_id=search_task_id,
            data=data_dict,
            content_hash=content_hash,
            status=status,
            html_file_path=html_file_path,
            source_request_url=source_request_url,
        )

        # Обновляем хэш в Redis.
        await self.redis.set(self._redis_key(search_task_id), content_hash)

        logger.info('Saved raw_item_id=%s with status=%s', raw_item_id, status)

        return {
            'status': 'saved',
            'search_task_id': search_task_id,
            'raw_item_id': raw_item_id,
            'hash': content_hash,
            'status_type': status,
            'html_file_path': html_file_path,
            'raw_file_path': raw_file_path,
        }
