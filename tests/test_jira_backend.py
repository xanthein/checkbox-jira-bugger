import json
import os
from unittest.mock import patch, MagicMock

import pytest

from checkbox_jira_bugger.config import DutSshConfig
from checkbox_jira_bugger.c3_client import DeviceInfo
from checkbox_jira_bugger.rerun import RerunResult
from checkbox_jira_bugger.jira_backend import (
    jira_api,
    is_valid_email_address,
    restrict_log_msg,
    bh_get_jira_project_key,
    bh_get_jira_platform_initial_key,
    bh_get_jira_target_objective,
    bh_get_bug_parent_issue_type,
    bh_read_jira_config_file,
    bh_get_jira_account_info,
    compose_jira_issue_dict,
    deal_with_failed_test_cases_common_test,
    deal_with_passed_test_cases_common_test,
    description_to_plain_text,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
JIRA_SECRETS_INI = os.path.join(FIXTURES, "jira_secrets.ini")
JIRA_CONFIG_JSON = os.path.join(FIXTURES, "jira_project_config.json")


def _load_jira_config():
    with open(JIRA_CONFIG_JSON) as f:
        return json.load(f)


def test_is_valid_email_address_true():
    assert is_valid_email_address("someone@canonical.com")


def test_is_valid_email_address_false():
    assert not is_valid_email_address("not-an-email")
    assert not is_valid_email_address(None)


def test_restrict_log_msg_truncates_long_log():
    long_log = "x" * 40000
    result = restrict_log_msg(long_log)
    assert len(result) < len(long_log)


def test_restrict_log_msg_short_log_unchanged():
    short_log = "hello"
    assert restrict_log_msg(short_log) == short_log


def test_description_to_plain_text_passes_through_plain_string():
    assert description_to_plain_text("SKU: sku1 sku2") == "SKU: sku1 sku2"


def test_description_to_plain_text_returns_empty_string_for_none():
    assert description_to_plain_text(None) == ""


def test_description_to_plain_text_converts_adf_dict():
    """
    Regression test: Jira Cloud can return `description` as an Atlassian
    Document Format (ADF) dict instead of a plain string, even with
    api_version=2 pinned. Every description-parsing method needs this
    normalized to plain text (one line per paragraph block) so downstream
    `.split("\\n")`/`in` checks keep working.
    """
    adf_description = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "[Additional Information]"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Manifest: "},
                    {"type": "text", "text": "somerville-jellyfish 20260901-458"},
                ],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "SKU: sku1 sku2"}],
            },
        ],
    }
    plain_text = description_to_plain_text(adf_description)
    assert "[Additional Information]" in plain_text
    assert "Manifest: somerville-jellyfish 20260901-458" in plain_text
    assert "SKU: sku1 sku2" in plain_text
    lines = plain_text.split("\n")
    assert any("SKU:" in line for line in lines)


def test_description_to_plain_text_converts_hard_break_to_newline():
    """
    Regression test confirmed against a real Jira Cloud issue (STELLA-4127):
    a single ADF paragraph can contain multiple `text` nodes separated by
    `hardBreak` nodes (Jira's actual rendering of a "\\n" within one
    paragraph), e.g.:
        [Summary]... <hardBreak> [I/O log]...
    The v2 (string) REST API renders each hardBreak as a single "\\n" when
    it returns description as plain text, so the ADF converter must match
    that behavior -- previously hardBreak nodes were silently dropped
    (contributing no separator at all), incorrectly merging two lines into
    one with zero space between them.
    """
    adf_description = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "[Summary]usb/storage-detect failed"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "[I/O log]nothing found"},
                ],
            }
        ],
    }
    plain_text = description_to_plain_text(adf_description)
    assert plain_text == "[Summary]usb/storage-detect failed\n[I/O log]nothing found"


def test_bh_get_jira_project_key():
    conf = _load_jira_config()
    assert bh_get_jira_project_key(conf, "somerville") == "CASC"


def test_bh_get_jira_project_key_missing_raises():
    conf = _load_jira_config()
    with pytest.raises(KeyError):
        bh_get_jira_project_key(conf, "nonexistent-project")


def test_bh_get_jira_platform_initial_key():
    conf = _load_jira_config()
    key = bh_get_jira_platform_initial_key(conf, "somerville", "jellyfish-gogogo")
    assert key == "CASC-1"


def test_bh_get_jira_platform_initial_key_missing_returns_empty():
    conf = _load_jira_config()
    assert bh_get_jira_platform_initial_key(conf, "somerville", "no-such-component") == ""


def test_bh_get_jira_target_objective():
    conf = _load_jira_config()
    assert bh_get_jira_target_objective(conf, "somerville", "22.04") == "CASC-207"


def test_bh_get_bug_parent_issue_type():
    conf = _load_jira_config()
    assert bh_get_bug_parent_issue_type(conf, "somerville") == "Epic"


def test_bh_read_jira_config_file():
    conf = bh_read_jira_config_file(JIRA_CONFIG_JSON)
    assert conf["OEM_X86_JIRA_CONF"]["somerville"]["jira_project"] == "CASC"


def test_bh_get_jira_account_info_uses_config_loader():
    email, apitoken = bh_get_jira_account_info(JIRA_SECRETS_INI)
    assert email == "bot@example.com"
    assert apitoken == "fake-jira-token"


def test_compose_jira_issue_dict():
    d = compose_jira_issue_dict("CASC", "Bug", "summary", "description", ["tag1"], "High", "a@canonical.com")
    assert d["project"]["key"] == "CASC"
    assert d["issuetype"]["name"] == "Bug"
    assert d["priority"]["name"] == "High"
    assert d["labels"] == ["tag1"]
    assert d["assignee"]["emailAddress"] == "a@canonical.com"


def _make_jira_issue_query_response(issues):
    return {"issues": issues}


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_jira_api_pins_rest_api_v2_for_plain_text_descriptions(mock_jira_cls):
    """
    Regression test: without pinning api_version=2, atlassian-python-api's
    default ("latest") resolves to the Jira Cloud v3 REST API on this site,
    which returns rich-text fields like `description` as an ADF dict instead
    of a plain string. Every description-parsing method in this file
    (get_bug_manifest_version, get_bug_manifest_name, get_bug_skus,
    append_sku_to_bug_description) assumes a plain string and calls
    .split("\\n") on it, so an ADF dict causes:
        AttributeError: 'dict' object has no attribute 'split'
    Pinning api_version=2 restores the plain-text (wiki markup) description
    format these methods require.
    """
    mock_jira = MagicMock()
    mock_jira_cls.return_value = mock_jira
    mock_jira.issue_exists.return_value = True
    mock_jira.get_project_components.return_value = [
        {"id": "10", "name": "jellyfish-gogogo", "description": "desc"}
    ]
    mock_jira.jql.return_value = _make_jira_issue_query_response(
        [{"key": "CASC-99", "fields": {"summary": "Platform Execution Needs to be Fixed Bugs for FC Image Release"}}]
    )

    jira_api(
        JIRA_SECRETS_INI, JIRA_CONFIG_JSON, "somerville", "jellyfish-gogogo", "22.04-label",
        "22.04", False, True, "FC",
    )

    _, kwargs = mock_jira_cls.call_args
    assert kwargs.get("api_version") == 2


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_jira_api_search_bug_calls_jql_and_filters_by_summary(mock_jira_cls):
    mock_jira = MagicMock()
    mock_jira_cls.return_value = mock_jira
    mock_jira.issue_exists.return_value = True
    mock_jira.get_project_components.return_value = [
        {"id": "10", "name": "jellyfish-gogogo", "description": "desc"}
    ]

    # BFS in __init__ calls jql for each hierarchy child; return one matching issue per call.
    def jql_side_effect(jql_query):
        return _make_jira_issue_query_response([{"key": "CASC-99", "fields": {"summary": "Platform Execution Needs to be Fixed Bugs for FC Image Release"}}])

    mock_jira.jql.side_effect = jql_side_effect

    api = jira_api(
        JIRA_SECRETS_INI, JIRA_CONFIG_JSON, "somerville", "jellyfish-gogogo", "22.04-label",
        "22.04", False, True, "FC",
    )

    # Reset the mock call history from __init__'s BFS calls before testing search_bug.
    mock_jira.jql.reset_mock()
    mock_jira.jql.side_effect = None
    mock_jira.jql.return_value = _make_jira_issue_query_response(
        [{"key": "CASC-100", "fields": {"summary": "[Sanity] some/job failed"}}]
    )

    result = api.search_bug("some/job")

    mock_jira.jql.assert_called_once()
    assert len(result) == 1
    assert result[0]["key"] == "CASC-100"


def _make_api(mock_jira_cls):
    mock_jira = MagicMock()
    mock_jira_cls.return_value = mock_jira
    mock_jira.issue_exists.return_value = True
    mock_jira.get_project_components.return_value = [
        {"id": "10", "name": "jellyfish-gogogo", "description": "desc"}
    ]
    mock_jira.jql.return_value = _make_jira_issue_query_response(
        [{"key": "CASC-99", "fields": {"summary": "Platform Execution Needs to be Fixed Bugs for FC Image Release"}}]
    )
    api = jira_api(
        JIRA_SECRETS_INI, JIRA_CONFIG_JSON, "somerville", "jellyfish-gogogo", "22.04-label",
        "22.04", False, True, "FC",
    )
    mock_jira.jql.reset_mock()
    return api, mock_jira


_ADF_DESCRIPTION_WITH_SKU = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "[Additional Information]"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "SKU: sku1 sku2"}],
        },
    ],
}


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_get_bug_skus_handles_adf_description(mock_jira_cls):
    """
    Regression test: even with api_version=2 pinned, Jira Cloud can still
    return `description` as an ADF dict for some issues. get_bug_skus must
    not crash on that -- it should normalize to plain text first.
    """
    api, _ = _make_api(mock_jira_cls)
    jira_issue_inst = {"key": "CASC-1", "fields": {"description": _ADF_DESCRIPTION_WITH_SKU}}

    result = api.get_bug_skus(jira_issue_inst)

    assert result == ["sku1", "sku2"]


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_append_sku_to_bug_description_handles_adf_description(mock_jira_cls):
    """
    Regression test for the exact crash observed in production:
        AttributeError: 'dict' object has no attribute 'split'
    append_sku_to_bug_description must normalize an ADF description to
    plain text before splitting on newlines, instead of crashing.
    """
    api, mock_jira = _make_api(mock_jira_cls)
    jira_issue_inst = {
        "key": "CASC-1",
        "fields": {"summary": "some bug", "description": _ADF_DESCRIPTION_WITH_SKU},
    }

    api.append_sku_to_bug_description(jira_issue_inst, "sku3")

    mock_jira.update_issue_field.assert_called_once()
    called_key, called_fields = mock_jira.update_issue_field.call_args[0]
    assert called_key == "CASC-1"
    assert "SKU: sku1 sku2 sku3" in called_fields["description"]


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_append_sku_to_bug_description_rejoins_lines_with_blank_line(mock_jira_cls):
    """
    Regression test confirmed against a real Jira Cloud issue (STELLA-4127):
    when the rewritten description is submitted back to Jira as a plain
    string, a single "\\n" between lines gets silently dropped (merging
    lines together with zero separator) -- only a blank line ("\\n\\n")
    survives as a real line break. append_sku_to_bug_description must
    rejoin lines with a blank line, not a single "\\n", so the updated
    description remains parseable after Jira stores it.
    """
    api, mock_jira = _make_api(mock_jira_cls)
    jira_issue_inst = {
        "key": "CASC-1",
        "fields": {
            "summary": "some bug",
            "description": "[Additional Information]\nSKU: sku1 sku2\nBIOS ID: ABC123",
        },
    }

    api.append_sku_to_bug_description(jira_issue_inst, "sku3")

    called_key, called_fields = mock_jira.update_issue_field.call_args[0]
    new_description = called_fields["description"]
    assert "[Additional Information]\n\nSKU: sku1 sku2 sku3\n\nBIOS ID: ABC123" in new_description


@patch("checkbox_jira_bugger.jira_backend.rerun_job")
@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_deal_with_failed_rerun_pass_skips_bug_filing(mock_jira_cls, mock_rerun_job):
    api, mock_jira = _make_api(mock_jira_cls)
    mock_rerun_job.return_value = RerunResult(status="pass", io_log="new log", error=None)

    with patch.object(api, "search_bug") as mock_search_bug:
        data = {
            "results": [
                {
                    "id": "audio/playback",
                    "full_id": "com.canonical.certification::audio/playback",
                    "status": "fail",
                    "io_log": "old log",
                    "certification_status": "blocker",
                }
            ]
        }
        dut_ssh_config = DutSshConfig(
            user="ubuntu", ssh_key="/key", timeout=30, env={},
            rerun_job_patterns=["com.canonical.certification::audio/*"],
        )
        device_info = DeviceInfo(canonical_label="dev1", ip_address="10.0.0.5")

        deal_with_failed_test_cases_common_test(
            data, api, "submission.tar.xz", "jellyfish-gogogo", "manifest", "1.0", "bios1", "sku1",
            "sku-name", "a@canonical.com", "tester1",
            rerun_on_fail=True, device_info=device_info, dut_ssh_config=dut_ssh_config,
        )

        mock_rerun_job.assert_called_once()
        mock_search_bug.assert_not_called()


@patch("checkbox_jira_bugger.jira_backend.rerun_job")
@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_deal_with_failed_rerun_fail_proceeds_to_bug_filing(mock_jira_cls, mock_rerun_job):
    api, mock_jira = _make_api(mock_jira_cls)
    mock_rerun_job.return_value = RerunResult(status="fail", io_log="FRESH_LOG_MARKER", error=None)

    with patch.object(api, "search_bug", return_value=[]) as mock_search_bug, \
            patch.object(api, "create_newbug") as mock_create_newbug:
        data = {
            "results": [
                {
                    "id": "audio/playback",
                    "full_id": "com.canonical.certification::audio/playback",
                    "status": "fail",
                    "io_log": "STALE_LOG_MARKER",
                    "certification_status": "blocker",
                }
            ]
        }
        dut_ssh_config = DutSshConfig(
            user="ubuntu", ssh_key="/key", timeout=30, env={},
            rerun_job_patterns=["com.canonical.certification::audio/*"],
        )
        device_info = DeviceInfo(canonical_label="dev1", ip_address="10.0.0.5")

        deal_with_failed_test_cases_common_test(
            data, api, "submission.tar.xz", "jellyfish-gogogo", "manifest", "1.0", "bios1", "sku1",
            "sku-name", "a@canonical.com", "tester1",
            rerun_on_fail=True, device_info=device_info, dut_ssh_config=dut_ssh_config,
        )

        mock_rerun_job.assert_called_once()
        mock_search_bug.assert_called_once()
        mock_create_newbug.assert_called_once()

        # The bug description passed to create_newbug must carry the FRESH
        # io_log from the rerun result, not the original (stale) io_log.
        call_args = mock_create_newbug.call_args
        bug_description = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("bug_description")
        assert "FRESH_LOG_MARKER" in bug_description
        assert "STALE_LOG_MARKER" not in bug_description


@patch("checkbox_jira_bugger.jira_backend.rerun_job")
@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_deal_with_failed_rerun_unexpected_exception_does_not_abort_loop(mock_jira_cls, mock_rerun_job):
    api, mock_jira = _make_api(mock_jira_cls)
    mock_rerun_job.side_effect = TypeError("boom")

    with patch.object(api, "search_bug", return_value=[]) as mock_search_bug, \
            patch.object(api, "create_newbug") as mock_create_newbug:
        data = {
            "results": [
                {
                    "id": "audio/playback",
                    "full_id": "com.canonical.certification::audio/playback",
                    "status": "fail",
                    "io_log": "log1",
                    "certification_status": "blocker",
                },
                {
                    "id": "bluetooth/scan",
                    "full_id": "com.canonical.certification::bluetooth/scan",
                    "status": "fail",
                    "io_log": "log2",
                    "certification_status": "blocker",
                },
            ]
        }
        dut_ssh_config = DutSshConfig(
            user="ubuntu", ssh_key="/key", timeout=30, env={},
            rerun_job_patterns=["com.canonical.certification::*"],
        )
        device_info = DeviceInfo(canonical_label="dev1", ip_address="10.0.0.5")

        # Should not raise, despite rerun_job raising TypeError for both jobs.
        deal_with_failed_test_cases_common_test(
            data, api, "submission.tar.xz", "jellyfish-gogogo", "manifest", "1.0", "bios1", "sku1",
            "sku-name", "a@canonical.com", "tester1",
            rerun_on_fail=True, device_info=device_info, dut_ssh_config=dut_ssh_config,
        )

        # Both jobs must have proceeded to normal bug-filing flow using the
        # original item, proving the exception in job 1's rerun did not
        # abort processing of job 2 (no blast radius).
        assert mock_search_bug.call_count == 2
        assert mock_create_newbug.call_count == 2


def _child(key, summary):
    return {"key": key, "fields": {"summary": "HP Platform " + summary}}


def _resolve_with(mock_jira_cls, milestone, execution, epic):
    api, _ = _make_api(mock_jira_cls)
    api.milestone = milestone
    api.platform_initial_bug_key = "X-1"
    epic_summary = "Needs to be Fixed Bugs for %s Image Release" % milestone

    def lookup(parent, summary=None):
        if parent == "X-1":
            return [_child(k, "Platform Execution") for k in execution] + [_child("X-9", "Platform Planning")]
        if parent == "X-2":
            return [_child(k, epic_summary) for k in epic] + [_child("X-8", "Needs to be Fixed Bugs for GM Image Release")]
        return []

    api.get_child_work_items = MagicMock(side_effect=lookup)
    return api


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_resolve_m1(mock_jira_cls):
    api = _resolve_with(mock_jira_cls, "M1", ["X-2"], ["X-5"])
    assert api._resolve_bugs_need_fixing_key() == "X-5"


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_resolve_missing_execution(mock_jira_cls):
    api = _resolve_with(mock_jira_cls, "M1", [], ["X-5"])
    with pytest.raises(ValueError, match="Platform Execution"):
        api._resolve_bugs_need_fixing_key()


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_resolve_missing_epic(mock_jira_cls):
    api = _resolve_with(mock_jira_cls, "M1", ["X-2"], [])
    with pytest.raises(ValueError, match="M1 Image Release"):
        api._resolve_bugs_need_fixing_key()


@patch("checkbox_jira_bugger.jira_backend.Jira")
def test_resolve_multiple_matches(mock_jira_cls):
    api = _resolve_with(mock_jira_cls, "M1", ["X-2"], ["X-5", "X-6"])
    with pytest.raises(ValueError):
        api._resolve_bugs_need_fixing_key()
