#!/usr/bin/python3
"""
jira_project_config_generator.py

Generate jira_project_config.json from Jira. For each selected Jira project,
every "Enable ... Platform" Theme (any status) is a platform enablement card,
and its single Jira component is the platform tag (component_name).
"""
import argparse
import json
import logging
import os
import re
import sys

from atlassian import Jira

from checkbox_jira_bugger import config

BH_DEFAULT_JIRA_PROJECT_CONF_PATH = "~/.checkbox-jira-bugger/jira_project_config"
OUTPUT_CONFIG_PATH = os.path.join(
    os.path.expanduser(BH_DEFAULT_JIRA_PROJECT_CONF_PATH), "jira_project_config.json"
)
DEFAULT_JIRA_SECRETS = "~/.config/secrets/jira_secrets.ini"
JIRA_URL = "https://warthogs.atlassian.net/"
JQL_ENABLE_PLATFORM_THEMES = (
    'project = "{project}" AND issuetype = Theme AND status != "Rejected" '
    'AND summary ~ "Enable" ORDER BY key'
)
PAGE_SIZE = 50

PROJECTS = ("stella", "somerville", "sutton")

_ENABLE_PLATFORM_RE = re.compile(r"^enable\b.*\bplatform$", re.IGNORECASE)


def is_enable_platform_summary(summary):
    return bool(_ENABLE_PLATFORM_RE.match(summary.strip()))


def build_project_entry(project, issues):
    """Build the OEM_X86_JIRA_CONF entry for one project from Jira Theme issues."""
    cards = {}
    for issue in issues:
        key = issue["key"]
        fields = issue.get("fields", {})
        if not is_enable_platform_summary(fields.get("summary") or ""):
            continue
        components = [c["name"] for c in fields.get("components") or []]
        if len(components) != 1:
            logging.warning(
                f"Skipping {key}: expected exactly one component, found {components}"
            )
            continue
        component = components[0]
        if component in cards:
            raise ValueError(
                f"Component '{component}' is claimed by both {cards[component]} and {key}; "
                f"set the duplicate card's status to Rejected in Jira and re-run"
            )
        cards[component] = key

    return {
        "jira_project": project.upper(),
        "jira_components": [
            {"component_name": name, "jira_enable_platform_card": cards[name]}
            for name in sorted(cards)
        ],
    }


def merge_config(existing, entries):
    """Return a copy of existing with OEM_X86_JIRA_CONF[project] replaced for each entry."""
    merged = dict(existing)
    conf = dict(merged.get("OEM_X86_JIRA_CONF", {}))
    conf.update(entries)
    merged["OEM_X86_JIRA_CONF"] = conf
    return merged


def fetch_enable_platform_themes(jira, project):
    """Return every Theme in project whose summary contains "Enable", across all pages."""
    jql = JQL_ENABLE_PLATFORM_THEMES.format(project=project.upper())
    issues = []
    token = None
    while True:
        page = jira.enhanced_jql(
            jql, fields="summary,components", nextPageToken=token, limit=PAGE_SIZE
        )
        issues.extend(page.get("issues", []))
        token = page.get("nextPageToken")
        if page.get("isLast", True) or not token:
            return issues


def load_existing_config(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Existing config {path} is not valid JSON: {e}") from e


def save_config(data, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=4)
            f.write("\n")
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    logging.info(f"Config file saved to {path}")


def generate_jira_config(jira, projects, output_path):
    """Query Jira for the selected projects and merge them into output_path."""
    entries = {}
    for project in projects:
        logging.info(f"Fetching Enable Platform Themes for {project.upper()}")
        issues = fetch_enable_platform_themes(jira, project)
        entries[project] = build_project_entry(project, issues)
        logging.info(
            f"{project.upper()}: {len(entries[project]['jira_components'])} components"
        )
    merged = merge_config(load_existing_config(output_path), entries)
    save_config(merged, output_path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate jira_project_config.json from Jira Enable Platform Themes"
    )
    parser.add_argument(
        "--project", action="append", choices=PROJECTS, default=None,
        help="Project to scan; repeatable (default: all)",
    )
    parser.add_argument("--output", default=OUTPUT_CONFIG_PATH)
    parser.add_argument("--jira-secrets", default=DEFAULT_JIRA_SECRETS)
    args = parser.parse_args(argv)
    if not args.project:
        args.project = list(PROJECTS)
    return args


def main(argv=None):
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
    args = parse_args(argv)
    try:
        secrets = config.load_jira_secrets(os.path.expanduser(args.jira_secrets))
        jira = Jira(url=JIRA_URL, username=secrets.jira_email,
                    password=secrets.jira_apitoken, cloud=True, api_version=2)
        generate_jira_config(jira, args.project, os.path.expanduser(args.output))
    except Exception as e:
        logging.error(f"Error generating Jira config: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
