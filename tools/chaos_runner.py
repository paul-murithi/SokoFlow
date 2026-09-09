#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chaos.models import ChaosReport, ScenarioResult
from app.chaos.reporting import save_report
from app.chaos.scenarios import SCENARIOS_MAP, run_docker_command
from app.chaos.validators import (
    validate_database_consistency,
    validate_log_correlation,
    validate_message_queue_state,
    validate_redis_session_integrity,
)

logger = logging.getLogger("chaos_runner")


async def recover_infrastructure() -> list[str]:
    """Best-effort cleanup for containers left paused by an interrupted run."""
    messages: list[str] = []
    for container in ("sokoflow_postgres", "sokoflow_redis"):
        succeeded, output = await run_docker_command("unpause", container)
        if succeeded:
            messages.append(f"Unpaused {container}")
        elif "is not paused" in output.lower():
            messages.append(f"{container} was already running")
        else:
            messages.append(f"Could not recover {container}: {output}")
    return messages


async def run_preflight() -> list[str]:
    """Confirm Redis and PostgreSQL are reachable before starting scenarios."""
    await recover_infrastructure()
    failures: list[str] = []
    checks = (
        ("PostgreSQL", validate_database_consistency),
        ("Redis", validate_redis_session_integrity),
    )
    for name, check in checks:
        try:
            result = await asyncio.wait_for(check(), timeout=5.0)
        except asyncio.TimeoutError:
            failures.append(f"{name} preflight timed out after 5 seconds")
            continue
        if not result.passed:
            failures.append(f"{name} preflight failed: {result.details}")
    return failures


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def run_scenarios(
    selected_scenarios: list[str],
    repeat: int = 1,
    verbose: bool = False,
    output_path: str | None = None,
    timeout: int = 30,
) -> ChaosReport:
    print("🧪 SokoFlow Chaos Testing Suite v1.0")
    print("=" * 60)
    print("Environment: local")
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Started: {started_at}\n")

    results: list[ScenarioResult] = []
    suite_start = time.perf_counter()

    preflight_failures = await run_preflight()
    if preflight_failures:
        details = "; ".join(preflight_failures)
        print(f" Environment preflight failed: {details}")
        results.append(
            ScenarioResult(
                scenario_name="ENVIRONMENT_PREFLIGHT",
                description="Verify required infrastructure is reachable before chaos execution",
                passed=False,
                duration=round(time.perf_counter() - suite_start, 3),
                correlation_id="preflight",
                error_message=details,
            )
        )
        html_file, _ = save_report(
            ChaosReport(
                environment="local",
                started_at=started_at,
                total_scenarios=1,
                passed_count=0,
                failed_count=1,
                pass_rate=0.0,
                total_duration=round(time.perf_counter() - suite_start, 2),
                coverage=0.0,
                results=results,
            ),
            custom_filename=output_path,
        )
        print(f"Report saved: {html_file}\n")
        return ChaosReport(
            environment="local",
            started_at=started_at,
            total_scenarios=1,
            passed_count=0,
            failed_count=1,
            pass_rate=0.0,
            total_duration=round(time.perf_counter() - suite_start, 2),
            coverage=0.0,
            results=results,
        )

    for idx, name in enumerate(selected_scenarios, start=1):
        if name not in SCENARIOS_MAP:
            print(f"  Unknown scenario '{name}'. Skipping.")
            continue

        scenario_cls = SCENARIOS_MAP[name]
        scenario = scenario_cls()

        for r in range(repeat):
            repeat_suffix = f" (run {r + 1}/{repeat})" if repeat > 1 else ""
            print(f"Running scenario: {name} ({idx}/{len(selected_scenarios)}){repeat_suffix}")

            try:
                result = await asyncio.wait_for(scenario.execute(), timeout=float(timeout))
            except asyncio.TimeoutError:
                result = ScenarioResult(
                    scenario_name=name,
                    description=scenario.description,
                    passed=False,
                    duration=float(timeout),
                    correlation_id="timeout",
                    error_message=f"Scenario timed out after {timeout} seconds",
                )
            finally:
                await recover_infrastructure()

            results.append(result)

            if verbose:
                for step in result.steps:
                    print(f"  → {step}")
                for val in result.validations:
                    status_icon = "✓" if val.passed else "✗"
                    print(f"  → Validating: {val.component} {status_icon}")

            if result.passed:
                print(f"   PASSED ({result.duration:.2f}s)\n")
            else:
                print(f"   FAILED ({result.duration:.2f}s) - Error: {result.error_message}\n")

    suite_duration = time.perf_counter() - suite_start
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    pass_rate = (passed_count / len(results) * 100.0) if results else 0.0

    report = ChaosReport(
        environment="local",
        started_at=started_at,
        total_scenarios=len(results),
        passed_count=passed_count,
        failed_count=failed_count,
        pass_rate=pass_rate,
        total_duration=round(suite_duration, 2),
        coverage=100.0
        if len(results) == len(SCENARIOS_MAP)
        else round(len(results) / len(SCENARIOS_MAP) * 100.0, 1),
        results=results,
    )

    print("=" * 60)
    print(
        f"Summary: {passed_count}/{len(results)} passed | Duration: {suite_duration:.1f}s | Coverage: {report.coverage}%"
    )

    html_file, _ = save_report(report, custom_filename=output_path)
    print(f"Report saved: {html_file}\n")

    return report


def list_scenarios() -> None:
    print("Available Chaos Scenarios:")
    print("=" * 60)
    for name, cls in SCENARIOS_MAP.items():
        print(f" • {name:<25} - {cls.description}")
    print("=" * 60)


async def run_validations() -> None:
    print("Running System Validation Checks (No Chaos Injected)")
    print("=" * 60)
    v1 = await validate_database_consistency()
    v2 = await validate_redis_session_integrity()
    v3 = await validate_message_queue_state()
    v4 = validate_log_correlation("val-test-123")

    for v in [v1, v2, v3, v4]:
        icon = "" if v.passed else ""
        print(f"{icon} {v.component:<25} : {v.details}")
    print("=" * 60)


def generate_report_from_file(json_file_path: str) -> None:
    path = Path(json_file_path)
    if not path.exists():
        print(f"Error: File '{json_file_path}' does not exist.")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    report = ChaosReport.model_validate(data)
    html_path, _ = save_report(report, custom_filename=str(path.with_suffix(".html")))
    print(f"Report generated: {html_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SokoFlow Chaos Test Runner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 'run' subcommand
    run_parser = subparsers.add_parser("run", help="Execute chaos tests")
    run_parser.add_argument(
        "-s",
        "--scenario",
        action="append",
        dest="scenarios",
        help="Specific scenario(s) to run (can specify multiple)",
    )
    run_parser.add_argument(
        "-r",
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat each scenario",
    )
    run_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output with per-step logging",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        help="Save report to specified file path",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Maximum time per test in seconds (default 30s)",
    )

    # 'list' subcommand
    subparsers.add_parser("list", help="List all available scenarios")

    # 'validate' subcommand
    subparsers.add_parser("validate", help="Run system validation checks without injecting chaos")

    # 'report' subcommand
    report_parser = subparsers.add_parser(
        "report", help="Generate HTML report from JSON test results"
    )
    report_parser.add_argument("file", help="Path to JSON test result file")

    args = parser.parse_args()

    if args.subcommand == "list":
        list_scenarios()
    elif args.subcommand == "validate":
        asyncio.run(run_validations())
    elif args.subcommand == "report":
        generate_report_from_file(args.file)
    elif args.subcommand == "run" or args.subcommand is None:
        setup_logging(getattr(args, "verbose", False))
        selected = (
            args.scenarios if getattr(args, "scenarios", None) else list(SCENARIOS_MAP.keys())
        )
        report = asyncio.run(
            run_scenarios(
                selected_scenarios=selected,
                repeat=getattr(args, "repeat", 1),
                verbose=getattr(args, "verbose", False),
                output_path=getattr(args, "output", None),
                timeout=getattr(args, "timeout", 30),
            )
        )
        if report.failed_count > 0:
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
