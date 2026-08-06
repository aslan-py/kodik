"""
StructuredChunker — умное чанкирование очищенного HTML.

Разбивает очищенный контент на логические чанки с перекрытием
(overlap), чтобы сохранить контекст на границах. Каждый чанк не
превышает ``max_chunk_size`` символов.

Используется в ``LLMClient.analyze_structure_chunked`` для обработки
больших страниц, не помещающихся в контекстное окно модели.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """Структура для хранения чанка."""

    index: int
    content: str
    start_block: int
    end_block: int
    metadata: dict[str, Any] = field(default_factory=dict)
    size: int = 0

    def __post_init__(self) -> None:
        self.size = len(self.content)


class StructuredChunker:
    """Разбивает очищенный HTML на логические чанки с перекрытием."""

    def __init__(
        self,
        max_chunk_size: int = 8000,
        overlap_size: int = 500,
        block_tags: list[str] | None = None,
    ) -> None:
        """
        Args:
            max_chunk_size: Максимальный размер чанка в символах.
            overlap_size: Перекрытие между чанками в символах.
            block_tags: Теги, считающиеся логическими блоками.
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.block_tags = block_tags or ['section', 'article', 'div', 'p']

    def chunk(self, cleaned_content: dict[str, Any]) -> list[Chunk]:
        """
        Разбивает очищенный контент на чанки.

        Args:
            cleaned_content: Результат ``HtmlCleaner.clean()``.

        Returns:
            list[Chunk]: Список чанков с перекрытием.
        """
        blocks = cleaned_content.get('blocks', [])
        if not blocks:
            # Нет структурированных блоков — чанкируем по символам.
            return self._chunk_by_chars(cleaned_content.get('content', ''))

        return self._chunk_by_blocks(blocks)

    def _chunk_by_blocks(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        """Чанкирование по логическим блокам."""
        chunks: list[Chunk] = []
        current: list[dict[str, Any]] = []
        current_size = 0
        start_block = 0

        for i, block in enumerate(blocks):
            block_html = block.get('html', '')
            block_size = len(block_html)

            # Если один блок больше max_chunk_size — режем его по символам.
            if block_size > self.max_chunk_size:
                if current:
                    chunks.append(
                        self._make_chunk(
                            current, start_block, i - 1, len(chunks)
                        )
                    )
                    current = []
                    current_size = 0
                for sub in self._split_text(block_html):
                    chunks.append(
                        Chunk(
                            index=len(chunks),
                            content=sub,
                            start_block=i,
                            end_block=i,
                            metadata={
                                'tag': block.get('tag'),
                                'classes': block.get('classes', []),
                            },
                        )
                    )
                start_block = i + 1
                continue

            if current_size + block_size > self.max_chunk_size and current:
                chunks.append(
                    self._make_chunk(current, start_block, i - 1, len(chunks))
                )
                # Перекрытие: последние блоки предыдущего чанка.
                current = self._overlap_blocks(current)
                current_size = sum(len(b.get('html', '')) for b in current)
                start_block = i - len(current)

            current.append(block)
            current_size += block_size

        if current:
            chunks.append(
                self._make_chunk(
                    current, start_block, len(blocks) - 1, len(chunks)
                )
            )

        return chunks

    def _make_chunk(
        self,
        blocks: list[dict[str, Any]],
        start_block: int,
        end_block: int,
        index: int,
    ) -> Chunk:
        """Собирает Chunk из списка блоков."""
        content = ''.join(b.get('html', '') for b in blocks)
        metadata = {
            'tags': [b.get('tag') for b in blocks],
            'classes': [b.get('classes', []) for b in blocks],
        }
        return Chunk(
            index=index,
            content=content,
            start_block=start_block,
            end_block=end_block,
            metadata=metadata,
        )

    def _overlap_blocks(
        self, blocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Возвращает хвост блоков для перекрытия (по размеру overlap)."""
        overlap: list[dict[str, Any]] = []
        size = 0
        for block in reversed(blocks):
            block_size = len(block.get('html', ''))
            if size + block_size > self.overlap_size and overlap:
                break
            overlap.insert(0, block)
            size += block_size
        return overlap

    def _chunk_by_chars(self, content: str) -> list[Chunk]:
        """Чанкирование по символам (без структурированных блоков)."""
        if not content:
            return []
        if len(content) <= self.max_chunk_size:
            return [
                Chunk(
                    index=0,
                    content=content,
                    start_block=0,
                    end_block=0,
                    metadata={},
                )
            ]

        chunks: list[Chunk] = []
        start = 0
        index = 0
        while start < len(content):
            end = min(start + self.max_chunk_size, len(content))
            chunks.append(
                Chunk(
                    index=index,
                    content=content[start:end],
                    start_block=index,
                    end_block=index,
                    metadata={},
                )
            )
            index += 1
            if end >= len(content):
                break
            start = end - self.overlap_size

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """Режет длинный текст на части по max_chunk_size."""
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chunk_size, len(text))
            parts.append(text[start:end])
            if end >= len(text):
                break
            start = end - self.overlap_size
        return parts
