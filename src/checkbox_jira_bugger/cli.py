"""Argparse entry point for checkbox-jira-bugger.

Replaces bin/bughamsterjira.py.

- Drops -u/--sku: the device SKU is now always resolved from the required
  --cid flag via the C3 API (DeviceInfo.canonical_label), not read from the
  user.
- -l/--label (platform_label) is now required and is used as the Jira
  platform tag (previously this role was filled by the C3-resolved
  canonical_label; -l/--label was a separate, optional secondary label).
- The CID is supplied via the required --cid flag (not an interactive
  prompt).
"""
import argparse
import json
import logging
import os

from checkbox_jira_bugger import checkbox_report
from checkbox_jira_bugger import config
from checkbox_jira_bugger import jira_backend
from checkbox_jira_bugger.c3_client import C3Client, C3ApiError, DeviceNotFoundError
from checkbox_jira_bugger.mattermost import MattermostClient, MattermostApiError

BH_DEFAULT_JIRA_SECRET = "~/.checkbox-jira-bugger/secrets/jira_secrets.ini"
BH_DEFAULT_JIRA_PROJECT_CONF = "~/.checkbox-jira-bugger/jira_project_config/jira_project_config.json"
BH_DEFAULT_C3_CONFIG = "~/.checkbox-jira-bugger/secrets/c3_config.ini"
BH_DEFAULT_DUT_SSH_CONFIG = "~/.checkbox-jira-bugger/secrets/dut_ssh_config.ini"

log = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A tool to file failed checkbox test cases on Jira, "
                     "with optional rerun-before-filing on the DUT.",
        epilog="e.g. checkbox-jira-bugger -p somerville -l jellyfish-zygarde "
               "--cid 202102-28691 -a cyrus.lien@canonical.com -m FC submission.tar.xz",
    )
    parser.add_argument("--debug", dest="debugmode", action="store_true", help="debug mode")
    parser.add_argument("-s", "--secret", dest="jira_secrets_ini", action="store",
                         default=os.path.expanduser(BH_DEFAULT_JIRA_SECRET),
                         help="jira user account and apitoken ini file")
    parser.add_argument("-c", "--config", dest="jira_config", action="store",
                         default=os.path.expanduser(BH_DEFAULT_JIRA_PROJECT_CONF),
                         help="jira config file (json)")
    parser.add_argument("-3", "--c3-config", dest="c3_config_ini", action="store",
                         default=os.path.expanduser(BH_DEFAULT_C3_CONFIG),
                         help="c3 api secrets ini file")
    parser.add_argument("-d", "--dut-ssh-config", dest="dut_ssh_config_ini", action="store",
                         default=os.path.expanduser(BH_DEFAULT_DUT_SSH_CONFIG),
                         help="dut ssh config ini file")
    parser.add_argument("-p", "--project", dest="project", action="store",
                         default="oemtest", help="Canonical project name e.g. somerville, stella, sutton")
    parser.add_argument("-m", "--milestone", dest="milestone", action="store",
                         required=True, help="Milestone (FC, GM)")
    parser.add_argument("-l", "--label", dest="platform_label", action="store",
                         required=True, help="platform tag/label (used as the Jira platform tag)")
    parser.add_argument("--cid", dest="cid", action="store",
                         required=True,
                         help="Canonical ID (CID) of this submission's DUT, "
                              "resolved via the C3 API to a device SKU (canonical_label) and IP")
    parser.add_argument("-a", "--assignee", dest="assignee", action="store",
                         required=True, help="assign bug to someone (mattermost username or email address)")
    parser.add_argument("-i", dest="interactive", action="store_true", help="interactive mode")
    parser.add_argument("--tester", dest="tester", action="store",
                         default="auto-sanity-bot", help="the tester")
    parser.add_argument("--dryrun", dest="dryrun", action="store_true", help="dryrun")
    parser.add_argument("--rerun-on-fail", dest="rerun_on_fail", action="store_true",
                         help="rerun failed jobs on the DUT before filing a bug (opt-in)")
    parser.add_argument(dest="submission_tarball", help="the submission tarball")
    return parser


def resolve_device_info(c3_config_ini: str, cid: str):
    client = C3Client.from_config_file(c3_config_ini)
    try:
        device_info = client.get_device_host(cid)
    except DeviceNotFoundError as exc:
        log.error("Could not resolve CID %s via C3: %s", cid, exc)
        raise SystemExit(1)
    log.info("Resolved CID %s -> canonical_label(device_sku)=%s, ip=%s",
              cid, device_info.canonical_label, device_info.ip_address)
    return device_info


def run(args):
    args.milestone = args.milestone.upper()

    cid = args.cid.strip()
    if not cid:
        raise SystemExit("--cid must not be empty")
    device_info = resolve_device_info(args.c3_config_ini, cid)

    submission_dir = checkbox_report.extract_submission_tarball(args.submission_tarball)
    if submission_dir is None:
        raise SystemExit(1)

    submission_json_path = os.path.join(submission_dir, "submission.json")
    try:
        with open(submission_json_path, "rb") as fobj:
            data = json.load(fobj)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.error("Could not read submission.json from %s: %s", submission_dir, exc)
        raise SystemExit(1)

    manifest_name, manifest_version, bios_version, sku_number = (
        checkbox_report.get_manifest_and_device_information(data)
    )
    ubuntu_version = checkbox_report.get_ubuntu_version(data)

    bugmgr = jira_backend.jira_api(
        args.jira_secrets_ini, args.jira_config, args.project,
        args.platform_label, None, ubuntu_version,
        args.interactive, args.dryrun, args.milestone,
    )

    if not jira_backend.is_valid_email_address(args.assignee) and args.assignee is not None:
        jira_secrets = config.load_jira_secrets(args.jira_secrets_ini)
        mm_client = MattermostClient(jira_secrets.mt_token)
        target_assignee = mm_client.mt_get_user_email(args.assignee)
    else:
        target_assignee = args.assignee

    checkbox_report.apply_cve_buffer_rule(data)

    dut_ssh_config = None
    if args.rerun_on_fail:
        dut_ssh_config = config.load_dut_ssh_config(args.dut_ssh_config_ini)

    jira_backend.deal_with_failed_test_cases_common_test(
        data, bugmgr, args.submission_tarball, args.platform_label,
        manifest_name, manifest_version, bios_version, sku_number,
        device_info.canonical_label, target_assignee, args.tester,
        rerun_on_fail=args.rerun_on_fail, device_info=device_info, dut_ssh_config=dut_ssh_config,
    )
    jira_backend.deal_with_passed_test_cases_common_test(
        data, bugmgr, args.submission_tarball, args.platform_label,
        manifest_name, manifest_version, bios_version, sku_number, device_info.canonical_label,
    )

    checkbox_report.clean_up(submission_dir)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("atlassian").setLevel(logging.WARNING)
    logging.basicConfig(
        format="JIRA:%(levelname)7s: %(asctime)s: %(message)s",
        level=logging.DEBUG if args.debugmode else logging.INFO,
    )

    try:
        run(args)
    except (C3ApiError, MattermostApiError) as exc:
        log.error("Error: %s", exc)
        raise SystemExit(1)
    except KeyboardInterrupt:
        log.error("Interrupted by user")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
