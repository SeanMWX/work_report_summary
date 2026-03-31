#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "work_report_summary.py"


class TestWorkReportSummary(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.work_home = Path(self.temp_dir.name) / ".work_report_summary"
        self.env = os.environ.copy()
        self.env["WORK_REPORT_SUMMARY_HOME"] = str(self.work_home)

    def run_cli_raw(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )

    def run_cli(self, *args: str) -> dict:
        result = self.run_cli_raw(*args)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout)

    def assert_tasks(self, report: dict, expected_tasks: list[str]) -> None:
        self.assertEqual(
            [entry["task"] for entry in report["entries"]],
            expected_tasks,
        )

    def test_default_storage_path_and_day_report(self):
        record_result = self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            (
                '[{"task":"Completed API integration"},'
                '{"task":"Reviewed PR 42","status":"blocked","details":"Waiting for QA"}]'
            ),
        )

        self.assertEqual(
            Path(record_result["db_path"]),
            self.work_home / "default.db",
        )
        self.assertEqual(record_result["recorded"], 2)

        day_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(day_report["entry_count"], 2)
        self.assertEqual(day_report["status_counts"]["done"], 1)
        self.assertEqual(day_report["status_counts"]["blocked"], 1)
        self.assert_tasks(day_report, ["Completed API integration", "Reviewed PR 42"])

    def test_record_appends_and_replace_day_overwrites_previous_entries(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Initial release checklist"]',
        )
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '[{"task":"Investigated flaky API test","status":"blocked","details":"Waiting for logs"}]',
        )

        appended_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(appended_report["entry_count"], 2)
        self.assert_tasks(
            appended_report,
            ["Initial release checklist", "Investigated flaky API test"],
        )

        replace_result = self.run_cli(
            "replace-day",
            "--date",
            "2026-03-31",
            "--items-json",
            '[{"task":"Retested release flow"},{"task":"Updated rollback plan","status":"in_progress"}]',
        )
        self.assertEqual(replace_result["previous_entry_count"], 2)
        self.assertEqual(replace_result["recorded"], 2)

        replaced_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(replaced_report["entry_count"], 2)
        self.assertEqual(replaced_report["status_counts"]["blocked"], 0)
        self.assertEqual(replaced_report["status_counts"]["in_progress"], 1)
        self.assert_tasks(
            replaced_report,
            ["Retested release flow", "Updated rollback plan"],
        )

    def test_replace_day_with_empty_array_clears_existing_report(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Closed onboarding checklist"]',
        )

        replace_result = self.run_cli(
            "replace-day",
            "--date",
            "2026-03-31",
            "--items-json",
            "[]",
        )

        self.assertEqual(replace_result["previous_entry_count"], 1)
        self.assertEqual(replace_result["recorded"], 0)

        cleared_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(cleared_report["entry_count"], 0)
        self.assertEqual(cleared_report["entries"], [])

    def test_update_entry_changes_only_targeted_entry(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            (
                '[{"task":"Investigated test failure","status":"blocked","details":"Waiting for logs"},'
                '{"task":"Prepared release note","status":"done"}]'
            ),
        )

        initial_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        target_entry = initial_report["entries"][0]
        untouched_entry = initial_report["entries"][1]

        update_result = self.run_cli(
            "update-entry",
            "--entry-id",
            str(target_entry["id"]),
            "--status",
            "done",
            "--details",
            "Logs reviewed and issue resolved",
        )

        self.assertEqual(update_result["previous_entry"]["status"], "blocked")
        self.assertEqual(update_result["entry"]["status"], "done")
        self.assertEqual(update_result["entry"]["details"], "Logs reviewed and issue resolved")

        updated_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(updated_report["status_counts"]["done"], 2)
        self.assertEqual(updated_report["status_counts"]["blocked"], 0)

        updated_target = next(
            entry for entry in updated_report["entries"] if entry["id"] == target_entry["id"]
        )
        unchanged_entry = next(
            entry for entry in updated_report["entries"] if entry["id"] == untouched_entry["id"]
        )
        self.assertEqual(updated_target["task"], "Investigated test failure")
        self.assertEqual(updated_target["details"], "Logs reviewed and issue resolved")
        self.assertEqual(unchanged_entry["task"], "Prepared release note")
        self.assertEqual(unchanged_entry["status"], "done")

    def test_update_entry_can_move_item_to_another_date(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Misfiled task"]',
        )

        initial_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        entry_id = str(initial_report["entries"][0]["id"])

        self.run_cli(
            "update-entry",
            "--entry-id",
            entry_id,
            "--new-date",
            "2026-04-01",
        )

        old_day_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        new_day_report = self.run_cli(
            "day-report",
            "--date",
            "2026-04-01",
        )

        self.assertEqual(old_day_report["entry_count"], 0)
        self.assertEqual(new_day_report["entry_count"], 1)
        self.assertEqual(new_day_report["entries"][0]["date"], "2026-04-01")

    def test_delete_entry_removes_only_targeted_entry_and_keeps_history(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            (
                '[{"task":"Task to keep","status":"done"},'
                '{"task":"Task to delete","status":"blocked","details":"Wrong item"}]'
            ),
        )

        initial_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        keep_entry = initial_report["entries"][0]
        delete_entry = initial_report["entries"][1]

        delete_result = self.run_cli(
            "delete-entry",
            "--entry-id",
            str(delete_entry["id"]),
        )

        self.assertEqual(delete_result["deleted_entry"]["task"], "Task to delete")
        self.assertEqual(delete_result["history_version"], 2)

        day_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        self.assertEqual(day_report["entry_count"], 1)
        self.assertEqual(day_report["entries"][0]["id"], keep_entry["id"])

        history_report = self.run_cli(
            "entry-history",
            "--entry-id",
            str(delete_entry["id"]),
        )
        self.assertFalse(history_report["current_exists"])
        self.assertEqual(history_report["version_count"], 2)
        self.assertEqual(
            [version["action"] for version in history_report["versions"]],
            ["create", "delete"],
        )

    def test_entry_history_tracks_create_update_and_delete(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '[{"task":"Track me","status":"in_progress","details":"Started"}]',
        )
        initial_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        entry_id = str(initial_report["entries"][0]["id"])

        self.run_cli(
            "update-entry",
            "--entry-id",
            entry_id,
            "--status",
            "done",
            "--details",
            "Finished",
        )
        self.run_cli(
            "delete-entry",
            "--entry-id",
            entry_id,
        )

        history_report = self.run_cli(
            "entry-history",
            "--entry-id",
            entry_id,
        )

        self.assertEqual(history_report["version_count"], 3)
        self.assertEqual(
            [version["action"] for version in history_report["versions"]],
            ["create", "update", "delete"],
        )
        self.assertEqual(
            [version["source_command"] for version in history_report["versions"]],
            ["record", "update-entry", "delete-entry"],
        )
        self.assertEqual(history_report["versions"][-1]["status"], "done")
        self.assertEqual(history_report["versions"][-1]["details"], "Finished")

    def test_day_history_groups_versions_by_entry_for_one_date(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            (
                '[{"task":"Task A","status":"done"},'
                '{"task":"Task B","status":"blocked","details":"Waiting"}]'
            ),
        )
        initial_report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        entry_a = initial_report["entries"][0]
        entry_b = initial_report["entries"][1]

        self.run_cli(
            "update-entry",
            "--entry-id",
            str(entry_b["id"]),
            "--status",
            "done",
            "--details",
            "Unblocked",
        )
        self.run_cli(
            "delete-entry",
            "--entry-id",
            str(entry_a["id"]),
        )

        day_history = self.run_cli(
            "day-history",
            "--date",
            "2026-03-31",
        )

        self.assertEqual(day_history["entry_count"], 2)
        self.assertEqual(day_history["version_count"], 4)
        self.assertEqual(day_history["action_counts"]["create"], 2)
        self.assertEqual(day_history["action_counts"]["update"], 1)
        self.assertEqual(day_history["action_counts"]["delete"], 1)

        deleted_group = next(
            entry for entry in day_history["entries"] if entry["entry_id"] == entry_a["id"]
        )
        updated_group = next(
            entry for entry in day_history["entries"] if entry["entry_id"] == entry_b["id"]
        )

        self.assertFalse(deleted_group["current_exists"])
        self.assertIsNone(deleted_group["current_entry"])
        self.assertEqual(
            [version["action"] for version in deleted_group["versions"]],
            ["create", "delete"],
        )

        self.assertTrue(updated_group["current_exists"])
        self.assertEqual(updated_group["current_entry"]["status"], "done")
        self.assertEqual(
            [version["action"] for version in updated_group["versions"]],
            ["create", "update"],
        )

    def test_day_history_shows_current_entry_when_task_moves_to_another_date(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Move me later"]',
        )
        report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )
        entry_id = str(report["entries"][0]["id"])

        self.run_cli(
            "update-entry",
            "--entry-id",
            entry_id,
            "--new-date",
            "2026-04-01",
        )

        day_history = self.run_cli(
            "day-history",
            "--date",
            "2026-03-31",
        )

        self.assertEqual(day_history["entry_count"], 1)
        history_entry = day_history["entries"][0]
        self.assertTrue(history_entry["current_exists"])
        self.assertEqual(history_entry["current_entry"]["date"], "2026-04-01")
        self.assertEqual(
            [version["action"] for version in history_entry["versions"]],
            ["create"],
        )

    def test_day_history_for_unmodified_date_is_empty(self):
        day_history = self.run_cli(
            "day-history",
            "--date",
            "2026-03-31",
        )

        self.assertEqual(day_history["entry_count"], 0)
        self.assertEqual(day_history["version_count"], 0)
        self.assertEqual(
            day_history["action_counts"],
            {"create": 0, "update": 0, "delete": 0},
        )
        self.assertEqual(day_history["entries"], [])

    def test_entry_history_backfills_legacy_rows(self):
        legacy_db = Path(self.temp_dir.name) / "legacy.db"
        with sqlite3.connect(str(legacy_db)) as connection:
            connection.execute(
                """
                CREATE TABLE work_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_date TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO work_entries (work_date, task, status, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("2026-03-31", "Legacy task", "done", "", "2026-03-31T09:00:00+00:00"),
            )

        history_report = self.run_cli(
            "--db-path",
            str(legacy_db),
            "entry-history",
            "--entry-id",
            "1",
        )

        self.assertTrue(history_report["current_exists"])
        self.assertEqual(history_report["version_count"], 1)
        self.assertEqual(history_report["versions"][0]["source_command"], "schema-backfill")

    def test_week_report_groups_entries_into_monday_sunday_window(self):
        self.run_cli(
            "record",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-03-30",
            "--items-json",
            '["Shipped release candidate"]',
        )
        self.run_cli(
            "record",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-04-01",
            "--items-json",
            '[{"task":"Worked on migration plan","status":"in_progress"}]',
        )
        self.run_cli(
            "record",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-04-03",
            "--items-json",
            '[{"task":"Prod access request","status":"blocked","details":"Waiting for approval"}]',
        )

        week_report = self.run_cli(
            "week-report",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-04-01",
        )

        self.assertEqual(week_report["week_start"], "2026-03-30")
        self.assertEqual(week_report["week_end"], "2026-04-05")
        self.assertEqual(week_report["entry_count"], 3)
        self.assertEqual(week_report["status_counts"]["done"], 1)
        self.assertEqual(week_report["status_counts"]["in_progress"], 1)
        self.assertEqual(week_report["status_counts"]["blocked"], 1)
        self.assertEqual(len(week_report["days"]), 7)
        self.assertEqual(week_report["days"][0]["date"], "2026-03-30")
        self.assertEqual(week_report["days"][-1]["date"], "2026-04-05")

        wednesday = next(day for day in week_report["days"] if day["date"] == "2026-04-01")
        self.assertEqual(wednesday["entries"][0]["status"], "in_progress")

    def test_day_report_for_unrecorded_day_is_empty(self):
        empty_report = self.run_cli(
            "day-report",
            "--date",
            "2026-04-02",
        )

        self.assertEqual(empty_report["entry_count"], 0)
        self.assertEqual(
            empty_report["status_counts"],
            {"done": 0, "in_progress": 0, "blocked": 0},
        )
        self.assertEqual(empty_report["entries"], [])

    def test_separate_database_names_are_isolated(self):
        self.run_cli(
            "record",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Alpha release prep"]',
        )
        self.run_cli(
            "record",
            "--db-name",
            "team_beta",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Beta incident follow-up"]',
        )

        alpha_report = self.run_cli(
            "day-report",
            "--db-name",
            "team_alpha",
            "--date",
            "2026-03-31",
        )
        beta_report = self.run_cli(
            "day-report",
            "--db-name",
            "team_beta",
            "--date",
            "2026-03-31",
        )

        self.assert_tasks(alpha_report, ["Alpha release prep"])
        self.assert_tasks(beta_report, ["Beta incident follow-up"])

    def test_db_path_override_creates_custom_database_file(self):
        custom_db = Path(self.temp_dir.name) / "custom" / "reports.db"
        result = self.run_cli(
            "--db-path",
            str(custom_db),
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Closed release checklist"]',
        )

        self.assertEqual(Path(result["db_path"]), custom_db)
        self.assertTrue(custom_db.exists())

    def test_env_var_db_name_is_used_when_cli_flag_is_missing(self):
        self.env["WORK_REPORT_SUMMARY_DB_NAME"] = "env_selected"

        result = self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Used env var db name"]',
        )

        self.assertEqual(
            Path(result["db_path"]),
            self.work_home / "env_selected.db",
        )

    def test_invalid_db_name_fails_cleanly(self):
        result = self.run_cli_raw(
            "--db-name",
            "..\\bad\\name",
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Task"]',
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Database name", result.stderr)

    def test_invalid_items_json_fails_cleanly(self):
        result = self.run_cli_raw(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '{"task":"not-an-array"}',
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JSON array", result.stderr)

    def test_invalid_status_fails_cleanly(self):
        result = self.run_cli_raw(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '[{"task":"Investigated issue","status":"unknown"}]',
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status must be one of", result.stderr)

    def test_update_entry_requires_at_least_one_change(self):
        self.run_cli(
            "record",
            "--date",
            "2026-03-31",
            "--items-json",
            '["Task to edit"]',
        )
        report = self.run_cli(
            "day-report",
            "--date",
            "2026-03-31",
        )

        result = self.run_cli_raw(
            "update-entry",
            "--entry-id",
            str(report["entries"][0]["id"]),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires at least one change", result.stderr)

    def test_update_entry_for_missing_id_fails_cleanly(self):
        result = self.run_cli_raw(
            "update-entry",
            "--entry-id",
            "99999",
            "--status",
            "done",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was not found", result.stderr)

    def test_delete_entry_for_missing_id_fails_cleanly(self):
        result = self.run_cli_raw(
            "delete-entry",
            "--entry-id",
            "99999",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was not found", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
