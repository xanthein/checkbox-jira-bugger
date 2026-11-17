import json
import os
from unittest.mock import MagicMock

import pytest

from checkbox_jira_bugger.jira_project_config_generator import (
    PROJECTS,
    build_project_entry,
    fetch_enable_platform_themes,
    generate_jira_config,
    is_enable_platform_summary,
    merge_config,
    parse_args,
)


def _issue(key, summary, comps):
    return {
        "key": key,
        "fields": {"summary": summary, "components": [{"name": c} for c in comps]},
    }


def test_summary_filter():
    assert is_enable_platform_summary("Enable HP ZBook 8 G2i recert 26.04 Platform")
    assert is_enable_platform_summary("enable foo platform")
    assert not is_enable_platform_summary("Enabled foo Platform")
    assert not is_enable_platform_summary("Platform Execution")


def test_build_entry_sorted_and_filtered():
    entry = build_project_entry("stella", [
        _issue("STELLA-2", "Enable B Platform", ["raccoon-b"]),
        _issue("STELLA-1", "Enable A Platform", ["raccoon-a"]),
        _issue("STELLA-3", "Platform Execution", ["raccoon-c"]),
    ])
    assert entry == {
        "jira_project": "STELLA",
        "jira_components": [
            {"component_name": "raccoon-a", "jira_enable_platform_card": "STELLA-1"},
            {"component_name": "raccoon-b", "jira_enable_platform_card": "STELLA-2"},
        ],
    }


def test_build_entry_skips_zero_and_multi_components(caplog):
    entry = build_project_entry("stella", [
        _issue("STELLA-1", "Enable A Platform", []),
        _issue("STELLA-2", "Enable B Platform", ["x", "y"]),
    ])
    assert entry["jira_components"] == []
    assert "STELLA-1" in caplog.text
    assert "STELLA-2" in caplog.text


def test_build_entry_duplicate_component_raises():
    with pytest.raises(ValueError, match="raccoon-a"):
        build_project_entry("stella", [
            _issue("STELLA-1", "Enable A Platform", ["raccoon-a"]),
            _issue("STELLA-2", "Enable A2 Platform", ["raccoon-a"]),
        ])


def test_merge_replaces_only_selected():
    existing = {
        "OEM_X86_JIRA_CONF": {
            "stella": {"jira_project": "STELLA", "jira_components": ["old"]},
            "somerville": {"jira_project": "SOMERVILLE", "jira_components": ["keep"]},
        },
        "somerville": {"objectives": {"22.04": "CASC-207"}},
    }
    new = {"jira_project": "STELLA", "jira_components": []}
    out = merge_config(existing, {"stella": new})
    assert out["OEM_X86_JIRA_CONF"]["stella"] == new
    assert out["OEM_X86_JIRA_CONF"]["somerville"]["jira_components"] == ["keep"]
    assert out["somerville"] == {"objectives": {"22.04": "CASC-207"}}


def test_merge_from_empty():
    entry = {"jira_project": "SUTTON", "jira_components": []}
    assert merge_config({}, {"sutton": entry}) == {"OEM_X86_JIRA_CONF": {"sutton": entry}}


def test_projects_constant():
    assert PROJECTS == ("stella", "somerville", "sutton")


def test_default_output_config_path_uses_new_default():
    from checkbox_jira_bugger import jira_project_config_generator as mod

    expected_base = os.path.expanduser("~/.checkbox-jira-bugger/jira_project_config")
    assert mod.OUTPUT_CONFIG_PATH.startswith(expected_base)


def test_fetch_follows_next_page_token_until_is_last():
    jira = MagicMock()
    page1 = [_issue(f"STELLA-{i}", "Enable X Platform", [f"c{i}"]) for i in range(50)]
    page2 = [_issue("STELLA-99", "Enable Y Platform", ["c99"])]
    jira.enhanced_jql.side_effect = [
        {"issues": page1, "nextPageToken": "tok", "isLast": False},
        {"issues": page2, "isLast": True},
    ]
    assert len(fetch_enable_platform_themes(jira, "stella")) == 51
    calls = jira.enhanced_jql.call_args_list
    assert 'project = "STELLA"' in calls[0].args[0]
    assert "issuetype = Theme" in calls[0].args[0]
    assert calls[0].kwargs.get("nextPageToken") is None
    assert calls[1].kwargs["nextPageToken"] == "tok"


def _single_page(issues):
    return {"issues": issues, "isLast": True}


def test_generate_partial_run_preserves_other_projects(tmp_path):
    out = tmp_path / "c.json"
    out.write_text(json.dumps({
        "OEM_X86_JIRA_CONF": {
            "somerville": {"jira_project": "SOMERVILLE", "jira_components": []}},
        "somerville": {"objectives": {}},
    }))
    jira = MagicMock()
    jira.enhanced_jql.return_value = _single_page([_issue("STELLA-1", "Enable A Platform", ["a"])])
    generate_jira_config(jira, ["stella"], str(out))
    text = out.read_text()
    data = json.loads(text)
    stella = data["OEM_X86_JIRA_CONF"]["stella"]
    assert stella["jira_components"][0]["jira_enable_platform_card"] == "STELLA-1"
    assert "somerville" in data["OEM_X86_JIRA_CONF"]
    assert data["somerville"] == {"objectives": {}}
    assert text.endswith("\n")


def test_generate_creates_missing_file(tmp_path):
    out = tmp_path / "sub" / "c.json"
    jira = MagicMock()
    jira.enhanced_jql.return_value = _single_page([])
    generate_jira_config(jira, ["sutton"], str(out))
    assert json.loads(out.read_text()) == {
        "OEM_X86_JIRA_CONF": {"sutton": {"jira_project": "SUTTON", "jira_components": []}}}


def test_generate_jira_error_leaves_file_untouched(tmp_path):
    out = tmp_path / "c.json"
    out.write_text("original")
    jira = MagicMock()
    jira.enhanced_jql.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        generate_jira_config(jira, ["stella"], str(out))
    assert out.read_text() == "original"


def test_parse_args_defaults_and_repeat():
    assert parse_args([]).project == list(PROJECTS)
    assert parse_args(["--project", "stella", "--project", "sutton"]).project == [
        "stella", "sutton"]
    with pytest.raises(SystemExit):
        parse_args(["--project", "delta"])


def test_save_failure_leaves_existing_file_intact(tmp_path, monkeypatch):
    from checkbox_jira_bugger import jira_project_config_generator as mod

    out = tmp_path / "c.json"
    out.write_text('{"keep": 1}')

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(mod.json, "dump", boom)
    with pytest.raises(OSError):
        mod.save_config({"new": 1}, str(out))
    assert out.read_text() == '{"keep": 1}'
    assert [p.name for p in tmp_path.iterdir()] == ["c.json"]


def test_corrupt_existing_file_error_names_the_file(tmp_path):
    from checkbox_jira_bugger import jira_project_config_generator as mod

    out = tmp_path / "c.json"
    out.write_text("not json")
    with pytest.raises(ValueError, match=str(out)):
        mod.load_existing_config(str(out))


def test_fetch_excludes_rejected_themes():
    jira = MagicMock()
    jira.enhanced_jql.return_value = {"issues": [], "isLast": True}
    fetch_enable_platform_themes(jira, "stella")
    assert 'status != "Rejected"' in jira.enhanced_jql.call_args.args[0]


def test_duplicate_error_tells_user_to_reject_one():
    with pytest.raises(ValueError, match="Rejected"):
        build_project_entry("stella", [
            _issue("STELLA-1", "Enable A Platform", ["raccoon-a"]),
            _issue("STELLA-2", "Enable A2 Platform", ["raccoon-a"]),
        ])
