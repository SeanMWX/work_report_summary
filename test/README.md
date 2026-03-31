# Local Test Environment

This directory is local-only and is not part of the packaged runtime `.skill`.

## Commands

- `python test/run_smoke.py`
- `python test/run_cli_tests.py`

## Test Rules

- Resolve paths from the file location instead of assuming the current working
  directory.
- Use `WORK_REPORT_SUMMARY_HOME` or `--db-path` so tests never touch the real
  home-directory database.
- Keep coverage focused on the deterministic runtime layer.
