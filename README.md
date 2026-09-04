# checkbox-jira-bugger

File Jira bugs from checkbox test-submission reports, with an opt-in
rerun-before-filing step to filter out flaky/transient failures on the
device-under-test (DUT).

## Setup

Config/secrets files (git-ignored, create these yourself):

- `~/.checkbox-jira-bugger/secrets/jira_secrets.ini`
- `~/.checkbox-jira-bugger/jira_project_config/jira_project_config.json`
- `~/.checkbox-jira-bugger/secrets/c3_config.ini`
- `~/.checkbox-jira-bugger/secrets/dut_ssh_config.ini` (only needed for `--rerun-on-fail`)

See `docs/superpowers/specs/2026-09-02-checkbox-jira-bugger-design.md` in
the `bughamster` repo for the exact schema of each file.

## Usage

```bash
checkbox-jira-bugger -p <project> -u <sku> -a <assignee> -m <FC|GM> \
  [--rerun-on-fail] submission.tar.xz
```

You will be prompted interactively for the DUT's CID (Canonical ID); the
tool resolves the platform tag (`canonical_label`) and DUT IP via the C3 API.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest pytest-mock
.venv/bin/pytest tests/ -v
```
