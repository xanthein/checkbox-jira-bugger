# checkbox-jira-bugger

File Jira bugs from checkbox test-submission reports, with an opt-in
rerun-before-filing step to filter out flaky/transient failures on the
device-under-test (DUT).

## Setup

Config/secrets files (git-ignored, create these yourself). All paths are
overridable via CLI flags; no secrets are hardcoded or committed.

### `~/.checkbox-jira-bugger/secrets/jira_secrets.ini`

Jira account credentials and the Mattermost bot token (used to resolve a
Mattermost username into an email address for bug assignment).

```ini
[jira account]
jira_email = bot@example.com
jira_apitoken = your-jira-api-token

[mattermost token]
mt_token = your-mattermost-bot-token
```

### `~/.checkbox-jira-bugger/secrets/c3_config.ini`

OAuth2 client-credentials used to obtain a bearer token from
`https://certification.canonical.com/oauth2/token/`. Used to resolve
`canonical_label` and the DUT's current host/IP via the C3 API, given the
CID entered interactively at startup.

```ini
[c3 secret]
client_id = your-c3-client-id
client_secret = your-c3-client-secret
```

### `~/.checkbox-jira-bugger/secrets/dut_ssh_config.ini`

Only needed when running with `--rerun-on-fail`. Controls how the tool SSHes
into the DUT to rerun a failed job before filing a bug.

```ini
[dut]
user = ubuntu
ssh_key = /home/ubuntu/.ssh/id_rsa
timeout = 30

[env]
CHECKBOX_ENV = 1
LANG = C.UTF-8

[rerun]
job_patterns =
    com.canonical.certification::audio/*
    com.canonical.certification::bluetooth/*
```

- `[dut]`: `user`/`ssh_key`/`timeout` (seconds) used to build the
  `ssh -i <ssh_key> -o ConnectTimeout=10 <user>@<host>` command.
- `[env]`: arbitrary `KEY = value` pairs passed as environment variables to
  `checkbox-cli` on the DUT (case-sensitive keys; literal `%` characters are
  supported).
- `[rerun].job_patterns`: one `fnmatch`-style glob pattern per line, matched
  against a failed job's `full_id`. A job is only eligible for rerun if it
  matches at least one pattern. If this section is missing or empty, **no**
  jobs are eligible for rerun, even with `--rerun-on-fail` set.

### `~/.checkbox-jira-bugger/jira_project_config/jira_project_config.json`

Maps Canonical project names to Jira project keys, components, and
objective/epic hierarchy. Consumed by `jira_backend.py`'s
`bh_read_jira_config_file`/`bh_get_jira_project_key`/
`bh_get_jira_platform_initial_key`/`bh_get_jira_target_objective`. Can be
generated from the `oem-hw-info` repo via
`jira_project_config_generator.py`.

```json
{
    "OEM_X86_JIRA_CONF": {
        "somerville": {
            "jira_project": "CASC",
            "jira_components": [
                {
                    "component_name": "jellyfish-gogogo",
                    "jira_enable_platform_card": "CASC-1"
                }
            ]
        }
    },
    "somerville": {
        "objectives": {
            "22.04": "CASC-207"
        },
        "hierarchy": ["theme", "objective", "epic", "bug"]
    }
}
```

- Top-level `OEM_X86_JIRA_CONF.<project>`: maps a Canonical project name
  (e.g. `somerville`) to its Jira project key (`jira_project`) and a list of
  `jira_components`, each mapping a platform tag/`component_name` (matched
  against the C3-resolved `canonical_label`) to its enablement epic key
  (`jira_enable_platform_card`).
- Top-level `<project>.objectives`: maps an Ubuntu version string (e.g.
  `22.04`) to the Jira objective/epic key bugs should be filed under for
  that release.
- `<project>.hierarchy`: the Jira issue-type hierarchy used when resolving
  parent issues for a new bug.

See `tests/fixtures/jira_project_config.json` for a working example used in
the test suite, and
`docs/superpowers/specs/2026-09-02-checkbox-jira-bugger-design.md` in the
`bughamster` repo for the full design rationale.

## Usage

```bash
checkbox-jira-bugger -p <project> -l <platform-label> -a <assignee> -m <FC|GM> \
  --cid <cid> [--rerun-on-fail] submission.tar.xz
```

`--cid` (Canonical ID of this submission's DUT) is required. It is resolved
via the C3 API to a device SKU (`canonical_label`, used wherever the old
`-u/--sku` flag was used) and the DUT's current IP (used by
`--rerun-on-fail`). `-l/--label` is required and is used as the Jira
platform tag (used wherever the old `-t/--tag` flag was used).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest pytest-mock
.venv/bin/pytest tests/ -v
```
