import logging

from core.pipeline.tasks import _pipeline_log, _result_summary


def test_pipeline_log_has_searchable_lifecycle_fields(caplog):
    with caplog.at_level(logging.INFO, logger='core.pipeline.tasks'):
        _pipeline_log(
            'stage_finished',
            run_id='run-123',
            stage=2,
            status='succeeded',
            task_id='celery-456',
        )

    assert (
        'pipeline_event=stage_finished run_id=run-123 stage=2 '
        'status=succeeded task_id=celery-456'
    ) in caplog.text


def test_result_summary_uses_only_safe_counter_fields():
    assert _result_summary({'saved': 2, 'rows': 3, 'secret': 'not logged'}) == (
        'saved:2,rows:3'
    )
