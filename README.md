# work_report_summary

Local OpenClaw skill for recording daily work items into SQLite, correcting a
day's report when needed, editing or deleting one specific logged task by entry
id, tracking entry history, and producing deterministic daily or weekly
summaries.

## Runtime Files

- `SKILL.md`
- `scripts/work_report_summary.py`
- `references/commands.md`
- `references/chat_reference.md`
- `references/chinese_output.md`

## Storage

The runtime script stores data in `~/.work_report_summary/<db_name>.db` by
default. Use `default.db` unless the user asks for a separate database name or
path.

To correct an existing daily report, use `replace-day` to replace the full set
of items for that date.
To edit one specific task without touching the rest of the day, use
`update-entry` with the `id` returned by `day-report`.
To delete one specific task, use `delete-entry`.
To inspect version history for one task, use `entry-history`.
To inspect all historical changes for one report date, use `day-history`.

## Local Verification

- `python test/run_smoke.py`
- `python test/run_cli_tests.py`
- `python skill_creator/scripts/quick_validate.py .`
