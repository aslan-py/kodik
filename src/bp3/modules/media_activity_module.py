"""Расчёт индекса медиа-активности конкурентов."""

from src.bp3.models_llm import BaseModule, ProjectContext


class MediaActivityModule(BaseModule):
    """Считает, насколько активно конкуренты упоминаются в новостях."""

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Считает индекс медиа-активности для каждого конкурента."""
        news_stats = ctx.news_stats
        unique_sources = ctx.count_sources

        # Защита от деления на ноль
        if unique_sources == 0:
            media_activity_index = [
                {'competitor_id': comp_id, 'media_activity_index': 0.0}
                for comp_id in news_stats.keys()
            ]
        else:
            media_activity_index = [
                {
                    'competitor_id': comp_id,
                    'media_activity_index': (
                        vals['news_count']
                        * vals['source_count']
                        / unique_sources
                    ),
                }
                for comp_id, vals in news_stats.items()
            ]

        ctx.media_activity_index = media_activity_index
        return ctx
