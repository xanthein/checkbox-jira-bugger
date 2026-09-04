import json
import os
from unittest.mock import patch

from checkbox_jira_bugger.jira_project_config_generator import JiraConfigGenerator


def test_generate_config_for_project_reads_json_files(tmp_path):
    platform_dir = tmp_path / "somerville"
    platform_dir.mkdir()

    (platform_dir / "numbat-abc.json").write_text(
        json.dumps({"metabug": "SOMERVILLE-123"})
    )
    (platform_dir / "notallowed-xyz.json").write_text(
        json.dumps({"metabug": "SOMERVILLE-456"})
    )

    generator = JiraConfigGenerator(allowed_series=["numbat"])
    generator.generate_config_for_project(str(platform_dir))

    conf = generator.config_data["OEM_X86_JIRA_CONF"]
    assert "somerville" in conf
    assert conf["somerville"]["jira_project"] == "SOMERVILLE"
    components = conf["somerville"]["jira_components"]
    assert len(components) == 1
    assert components[0]["component_name"] == "numbat-abc"
    assert components[0]["jira_enable_platform_card"] == "SOMERVILLE-123"


def test_save_config_writes_sorted_json(tmp_path):
    generator = JiraConfigGenerator()
    generator._add_component_to_project("somerville", "numbat-b", "SOMERVILLE-2")
    generator._add_component_to_project("somerville", "numbat-a", "SOMERVILLE-1")

    output_path = tmp_path / "out" / "jira_project_config.json"
    generator.save_config(str(output_path))

    assert output_path.exists()
    with open(output_path) as f:
        data = json.load(f)

    components = data["OEM_X86_JIRA_CONF"]["somerville"]["jira_components"]
    assert [c["component_name"] for c in components] == ["numbat-a", "numbat-b"]


def test_default_output_config_path_uses_new_default():
    from checkbox_jira_bugger import jira_project_config_generator as mod

    expected_base = os.path.expanduser(
        "~/.checkbox-jira-bugger/jira_project_config"
    )
    assert mod.OUTPUT_CONFIG_PATH.startswith(expected_base)


@patch("checkbox_jira_bugger.jira_project_config_generator.git")
def test_clone_or_pull_hw_info_clones_when_missing(mock_git, tmp_path, monkeypatch):
    from checkbox_jira_bugger import jira_project_config_generator as mod

    fake_local_path = str(tmp_path / "oem-hw-info")
    monkeypatch.setattr(mod, "HW_INFO_LOCAL_PATH", fake_local_path)

    mod.clone_or_pull_hw_info()

    mock_git.Repo.clone_from.assert_called_once_with(
        mod.HW_INFO_REPO, fake_local_path
    )
