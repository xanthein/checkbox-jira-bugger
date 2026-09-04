import pytest
from unittest.mock import patch, MagicMock
from checkbox_jira_bugger.cli import build_arg_parser, run
from checkbox_jira_bugger.c3_client import DeviceInfo, DeviceNotFoundError


def test_arg_parser_has_no_tag_flag():
    parser = build_arg_parser()
    help_text = parser.format_help()
    assert "--tag" not in help_text
    assert "--rerun-on-fail" in help_text


def test_arg_parser_requires_project_sku_assignee_milestone():
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["submission.tar.xz"])  # missing required args


@patch("checkbox_jira_bugger.cli.input", return_value="202102-28691")
@patch("checkbox_jira_bugger.cli.C3Client")
@patch("checkbox_jira_bugger.cli.jira_backend")
@patch("checkbox_jira_bugger.cli.checkbox_report")
def test_run_prompts_for_cid_and_resolves_device_info(
    mock_checkbox_report, mock_jira_backend, mock_c3_client_cls, mock_input, tmp_path
):
    mock_checkbox_report.extract_submission_tarball.return_value = str(tmp_path)
    mock_checkbox_report.get_manifest_and_device_information.return_value = (
        "manifest", "1.0", "bios1", "sku1"
    )
    mock_checkbox_report.get_ubuntu_version.return_value = "24.04"

    (tmp_path / "submission.json").write_text('{"results": []}')

    mock_client = MagicMock()
    mock_client.get_device_host.return_value = DeviceInfo(
        canonical_label="resolved-label", ip_address="10.1.2.3"
    )
    mock_c3_client_cls.from_config_file.return_value = mock_client

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", "submission.tar.xz",
    ])

    run(args)

    mock_input.assert_called_once()
    mock_client.get_device_host.assert_called_once_with("202102-28691")
    # canonical_label must be used as the platform tag passed into jira_backend
    called_args = mock_jira_backend.jira_api.call_args[0]
    assert "resolved-label" in called_args


@patch("checkbox_jira_bugger.cli.input", return_value="bad-cid")
@patch("checkbox_jira_bugger.cli.C3Client")
def test_run_aborts_if_cid_not_resolvable(mock_c3_client_cls, mock_input, tmp_path, capsys):
    mock_client = MagicMock()
    mock_client.get_device_host.side_effect = DeviceNotFoundError("no such CID")
    mock_c3_client_cls.from_config_file.return_value = mock_client

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", "submission.tar.xz",
    ])

    with pytest.raises(SystemExit):
        run(args)
