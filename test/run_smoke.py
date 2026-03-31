#!/usr/bin/env python3
"""
Local smoke test for work_report_summary.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run_cli(script_path: Path, env: dict, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(script_path), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "work_report_summary.py"

    with tempfile.TemporaryDirectory() as tmp_dir:
        env = os.environ.copy()
        env["WORK_REPORT_SUMMARY_HOME"] = str(Path(tmp_dir) / ".work_report_summary")

        run_cli(
            script_path,
            env,
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Closed release checklist", {"task":"Investigated flaky test","status":"blocked","details":"Waiting for logs"}]',
        )
        run_cli(
            script_path,
            env,
            "replace-day",
            "--date",
            "2026-03-31",
            "--items-json",
            '[{"task":"Closed release checklist"},{"task":"Retested login flow","status":"in_progress"}]',
        )
        initial_day_report = run_cli(
            script_path,
            env,
            "day-report",
            "--date",
            "2026-03-31",
        )
        target_entry_id = str(initial_day_report["entries"][1]["id"])
        run_cli(
            script_path,
            env,
            "update-entry",
            "--entry-id",
            target_entry_id,
            "--status",
            "done",
            "--details",
            "Retest completed",
        )
        history_report = run_cli(
            script_path,
            env,
            "entry-history",
            "--entry-id",
            target_entry_id,
        )
        day_history_report = run_cli(
            script_path,
            env,
            "day-history",
            "--date",
            "2026-03-31",
        )
        delete_entry_id = str(initial_day_report["entries"][0]["id"])
        run_cli(
            script_path,
            env,
            "delete-entry",
            "--entry-id",
            delete_entry_id,
        )
        day_report = run_cli(
            script_path,
            env,
            "day-report",
            "--date",
            "2026-03-31",
        )
        week_report = run_cli(
            script_path,
            env,
            "week-report",
            "--date",
            "2026-03-31",
        )

    if history_report["version_count"] != 2:
        raise SystemExit("Smoke test failed: expected two history versions after update-entry.")
    if day_history_report["version_count"] < 3:
        raise SystemExit("Smoke test failed: expected date history to include recorded changes.")
    if day_report["entry_count"] != 1:
        raise SystemExit("Smoke test failed: expected one day entry after delete-entry.")
    if week_report["entry_count"] != 1:
        raise SystemExit("Smoke test failed: expected one weekly entry after delete-entry.")
    if day_report["status_counts"]["done"] != 1:
        raise SystemExit("Smoke test failed: expected one done item after update-entry and delete-entry.")
    if day_report["entries"][0]["details"] != "Retest completed":
        raise SystemExit("Smoke test failed: expected updated details.")

    print("[OK] Smoke test passed.")


if __name__ == "__main__":
    main()
