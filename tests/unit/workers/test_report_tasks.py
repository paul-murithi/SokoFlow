from app.workers.report_tasks import generate_and_send_daily_report


def test_generate_and_send_daily_report_task_stub():
    assert callable(generate_and_send_daily_report)
