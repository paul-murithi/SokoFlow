from datetime import datetime, timezone
from pathlib import Path

from app.chaos.models import ChaosReport


def generate_html_report(report: ChaosReport) -> str:
    """Generates a comprehensive HTML report from a ChaosReport object."""
    results_html = ""
    for res in report.results:
        status_badge = (
            '<span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">PASSED</span>'
            if res.passed
            else '<span style="background-color: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">FAILED</span>'
        )

        steps_html = "".join([f"<li>{step}</li>" for step in res.steps])
        validations_html = ""
        for v in res.validations:
            v_status = "✓" if v.passed else "✗"
            v_color = "#28a745" if v.passed else "#dc3545"
            validations_html += f"""
            <div style="margin-left: 15px; font-size: 0.9em; margin-bottom: 4px;">
                <span style="color: {v_color}; font-weight: bold;">[{v_status}]</span>
                <strong>{v.component}:</strong> {v.details}
                {f'<br/><em style="color: #dc3545;">Reason: {v.failure_reason}</em>' if v.failure_reason else ""}
            </div>
            """

        results_html += f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; background-color: #fff;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                <h3 style="margin: 0;">{res.scenario_name}</h3>
                <div>{status_badge} <span style="color: #666; font-size: 0.9em; margin-left: 10px;">({res.duration}s)</span></div>
            </div>
            <p style="color: #555; margin-top: 8px;"><em>{res.description}</em></p>
            <p style="font-size: 0.85em; color: #777;"><strong>Correlation ID:</strong> <code>{res.correlation_id}</code></p>

            <h4 style="margin-bottom: 6px;">Execution Steps:</h4>
            <ul style="font-size: 0.9em; color: #444;">{steps_html}</ul>

            <h4 style="margin-bottom: 6px;">Validations:</h4>
            {validations_html}

            {f'<div style="margin-top: 10px; padding: 8px; background: #fff0f0; border-left: 4px solid #dc3545; color: #a94442;"><strong>Error:</strong> {res.error_message}</div>' if res.error_message else ""}
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{report.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f8f9fa; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{ background-color: #1a252f; color: white; padding: 24px; border-radius: 8px; margin-bottom: 20px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }}
        .stat-card {{ background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px; text-align: center; }}
        .stat-value {{ font-size: 1.6em; font-weight: bold; }}
        .stat-label {{ font-size: 0.8em; opacity: 0.8; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin:0;">🧪 SokoFlow Chaos Testing Suite</h1>
            <p style="margin: 4px 0 0 0; opacity: 0.8;">Environment: {report.environment} | Started: {report.started_at}</p>

            <div class="summary-grid">
                <div class="stat-card">
                    <div class="stat-value">{report.passed_count}/{report.total_scenarios}</div>
                    <div class="stat-label">Scenarios Passed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{report.pass_rate:.1f}%</div>
                    <div class="stat-label">Pass Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{report.total_duration:.2f}s</div>
                    <div class="stat-label">Total Duration</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{report.coverage:.0f}%</div>
                    <div class="stat-label">Coverage</div>
                </div>
            </div>
        </div>

        <h2>Detailed Scenario Results</h2>
        {results_html}
    </div>
</body>
</html>
"""
    return html_template


def save_report(
    report: ChaosReport, output_dir: str = "chaos_reports", custom_filename: str | None = None
) -> tuple[Path, Path]:
    """Saves report as both HTML and JSON files in output_dir."""
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    if custom_filename:
        base_name = custom_filename.replace(".html", "").replace(".json", "")
    else:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        base_name = f"chaos_{timestamp_str}"

    html_path = dir_path / f"{base_name}.html"
    json_path = dir_path / f"{base_name}.json"

    html_content = generate_html_report(report)
    html_path.write_text(html_content, encoding="utf-8")

    json_content = report.model_dump_json(indent=2)
    json_path.write_text(json_content, encoding="utf-8")

    return html_path, json_path
