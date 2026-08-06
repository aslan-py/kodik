"""
DataQualityGate — пятиуровневая система контроля качества данных.

Уровни:
1. SCHEMA — проверка обязательных полей
2. TYPES — проверка типов данных
3. BUSINESS — проверка бизнес-правил
4. VOLUME — мониторинг объёма данных
5. CONSISTENCY — проверка на дубликаты

Проблемные записи помещаются в карантин (Quarantine-паттерн).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from ..schemas import (
    QualityGateLevel,
    QualityGateReport,
    QuarantineRecord,
)

logger = logging.getLogger(__name__)

# Обязательные поля для элемента данных.
_REQUIRED_FIELDS = ('url', 'title')


class DataQualityGate:
    """
    Пятиуровневая система контроля качества данных.

    Каждый уровень возвращает QualityGateReport. Проблемные записи
    сохраняются в карантин для последующего анализа.
    """

    def __init__(
        self,
        source_name: str = 'unknown',
        logger: logging.Logger | None = None,
        quarantine_dir: str | None = None,
    ):
        self._source_name = source_name
        self._logger = logger or logging.getLogger(__name__)
        self._quarantine_store: list[QuarantineRecord] = []

        # Персистентное хранилище карантина на диске (JSON-файлы).
        # Если quarantine_dir задан — записи сохраняются на диск и
        # восстанавливаются при создании экземпляра.
        self._quarantine_dir: Path | None = None
        if quarantine_dir:
            self._quarantine_dir = Path(quarantine_dir)
            self._quarantine_dir.mkdir(parents=True, exist_ok=True)
            self._load_quarantine()

    # ========================================================================
    # Уровень 1: SCHEMA
    # ========================================================================

    def validate_schema(
        self,
        data: dict[str, Any],
        expected_schema: dict[str, type] | None = None,
    ) -> QualityGateReport:
        """Уровень 1: Проверка обязательных полей."""
        errors: list[str] = []
        items = data.get('items', []) if isinstance(data, dict) else data

        for idx, item in enumerate(items):
            for field in _REQUIRED_FIELDS:
                if not item.get(field):
                    errors.append(
                        f'item[{idx}]: missing required field "{field}"'
                    )

            if expected_schema:
                for field, expected_type in expected_schema.items():
                    value = item.get(field)
                    if value is not None and not isinstance(
                        value, expected_type
                    ):
                        errors.append(
                            f'item[{idx}]: field "{field}" has wrong type '
                            f'{type(value).__name__}, expected '
                            f'{expected_type.__name__}'
                        )

        return QualityGateReport(
            level=QualityGateLevel.SCHEMA,
            passed=not errors,
            errors=errors,
            item_count=len(items),
            passed_count=len(items) - len(errors),
        )

    # ========================================================================
    # Уровень 2: TYPES
    # ========================================================================

    def validate_types(
        self,
        items: list[dict[str, Any]],
        type_map: dict[str, tuple[type, ...]] | None = None,
    ) -> QualityGateReport:
        """Уровень 2: Проверка типов данных."""
        type_map = type_map or {
            'url': (str,),
            'title': (str,),
            'text': (str, type(None)),
            'published_at': (str, type(None)),
            'region': (str, type(None)),
            'media_name': (str, type(None)),
        }
        errors: list[str] = []

        for idx, item in enumerate(items):
            for field, allowed_types in type_map.items():
                value = item.get(field)
                if value is not None and not isinstance(value, allowed_types):
                    errors.append(
                        f'item[{idx}]: field "{field}" has type '
                        f'{type(value).__name__}, expected one of '
                        f'{", ".join(t.__name__ for t in allowed_types)}'
                    )

        return QualityGateReport(
            level=QualityGateLevel.TYPES,
            passed=not errors,
            errors=errors,
            item_count=len(items),
            passed_count=len(items) - len(errors),
        )

    # ========================================================================
    # Уровень 3: BUSINESS
    # ========================================================================

    def validate_business_rules(
        self,
        items: list[dict[str, Any]],
        rules: list[dict[str, Any]] | None = None,
    ) -> QualityGateReport:
        """
        Уровень 3: Проверка бизнес-правил.

        Правило: {"field": "text", "min_length": 10}
        """
        rules = rules or []
        errors: list[str] = []

        for idx, item in enumerate(items):
            for rule in rules:
                field = rule.get('field')
                value = item.get(field)
                min_length = rule.get('min_length')
                if min_length is not None and value is not None:
                    if len(str(value)) < min_length:
                        errors.append(
                            f'item[{idx}]: field "{field}" shorter than '
                            f'{min_length} chars'
                        )

        return QualityGateReport(
            level=QualityGateLevel.BUSINESS,
            passed=not errors,
            errors=errors,
            item_count=len(items),
            passed_count=len(items) - len(errors),
        )

    # ========================================================================
    # Уровень 4: VOLUME
    # ========================================================================

    def validate_volume(
        self,
        current_count: int,
        expected_count: int,
        threshold: float = 0.8,
    ) -> QualityGateReport:
        """Уровень 4: Мониторинг объёма (аларм при падении > 20%)."""
        warnings: list[str] = []
        if expected_count > 0:
            ratio = current_count / expected_count
            if ratio < threshold:
                warnings.append(
                    f'volume dropped: {current_count} vs expected '
                    f'{expected_count} (ratio {ratio:.2f} < {threshold})'
                )

        return QualityGateReport(
            level=QualityGateLevel.VOLUME,
            passed=not warnings,
            warnings=warnings,
            item_count=current_count,
            passed_count=current_count,
        )

    # ========================================================================
    # Уровень 5: CONSISTENCY
    # ========================================================================

    def validate_consistency(
        self,
        items: list[dict[str, Any]],
        key_field: str = 'url',
    ) -> QualityGateReport:
        """Уровень 5: Проверка на дубликаты."""
        seen: set[str] = set()
        duplicates: list[str] = []

        for idx, item in enumerate(items):
            key = item.get(key_field)
            if key is None:
                continue
            if key in seen:
                duplicates.append(f'item[{idx}]: duplicate key "{key}"')
            seen.add(key)

        return QualityGateReport(
            level=QualityGateLevel.CONSISTENCY,
            passed=not duplicates,
            errors=duplicates,
            item_count=len(items),
            passed_count=len(items) - len(duplicates),
        )

    # ========================================================================
    # Агрегация
    # ========================================================================

    def validate_all(
        self,
        items: list[dict[str, Any]],
        expected_schema: dict[str, type] | None = None,
        type_map: dict[str, tuple[type, ...]] | None = None,
        business_rules: list[dict[str, Any]] | None = None,
        expected_count: int | None = None,
        volume_threshold: float = 0.8,
        key_field: str = 'url',
    ) -> list[QualityGateReport]:
        """Выполняет все 5 уровней валидации."""
        reports = [
            self.validate_schema(
                {'items': items}, expected_schema=expected_schema
            ),
            self.validate_types(items, type_map=type_map),
            self.validate_business_rules(items, rules=business_rules),
        ]

        if expected_count is not None:
            reports.append(
                self.validate_volume(
                    len(items), expected_count, threshold=volume_threshold
                )
            )

        reports.append(self.validate_consistency(items, key_field=key_field))

        # Помещаем проблемные записи в карантин.
        for report in reports:
            if not report.passed:
                self._quarantine_failed(items, report)

        return reports

    def is_all_passed(self, reports: list[QualityGateReport]) -> bool:
        """Возвращает True, если все отчёты прошли."""
        return all(report.passed for report in reports)

    # ========================================================================
    # Карантин
    # ========================================================================

    def _quarantine_failed(
        self, items: list[dict[str, Any]], report: QualityGateReport
    ) -> None:
        """Помещает записи, связанные с ошибками отчёта, в карантин."""
        for error in report.errors:
            self.quarantine(
                data={'error': error, 'source': self._source_name},
                errors=[error],
            )

    def quarantine(
        self,
        data: dict[str, Any],
        errors: list[str],
    ) -> QuarantineRecord:
        """Сохраняет проблемную запись в карантин.

        Если задан ``quarantine_dir`` — запись дополнительно сохраняется
        на диск (JSON-файл) для персистентности между запусками.
        """
        record = QuarantineRecord(
            id=uuid.uuid4().hex,
            original_data=data,
            errors=errors,
            source=self._source_name,
        )
        self._quarantine_store.append(record)
        self._persist_quarantine(record)
        self._logger.warning(
            'Запись помещена в карантин (источник=%s, id=%s, ошибки=%s)',
            self._source_name,
            record.id,
            errors,
        )
        return record

    # ========================================================================
    # Персистентность карантина (диск)
    # ========================================================================

    def _quarantine_path(self, record_id: str) -> Path:
        """Путь к JSON-файлу записи карантина."""
        return self._quarantine_dir / f'{record_id}.json'

    def _persist_quarantine(self, record: QuarantineRecord) -> None:
        """Сохраняет запись карантина на диск (если каталог задан)."""
        if self._quarantine_dir is None:
            return
        try:
            self._quarantine_path(record.id).write_text(
                record.model_dump_json(),
                encoding='utf-8',
            )
        except Exception as e:
            self._logger.warning(
                'Не удалось сохранить запись карантина %s на диск: %s',
                record.id,
                e,
            )

    def _load_quarantine(self) -> None:
        """Загружает записи карантина с диска при инициализации."""
        if self._quarantine_dir is None:
            return
        for path in sorted(self._quarantine_dir.glob('*.json')):
            try:
                record = QuarantineRecord.model_validate_json(
                    path.read_text(encoding='utf-8')
                )
                self._quarantine_store.append(record)
            except Exception as e:
                self._logger.warning(
                    'Не удалось загрузить запись карантина %s: %s',
                    path.name,
                    e,
                )

    @property
    def quarantine_store(self) -> list[QuarantineRecord]:
        """Возвращает список записей карантина."""
        return list(self._quarantine_store)
