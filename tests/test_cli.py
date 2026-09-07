import pytest
from unittest.mock import patch, MagicMock
from checkbox_jira_bugger.cli import build_arg_parser, run
from checkbox_jira_bugger.c3_client import DeviceInfo, DeviceNotFoundError


CID_ARGS = ["--cid", "202102-28691"]


def test_arg_parser_has_no_tag_flag():
    parser = build_arg_parser()
    help_text = parser.format_help()
    assert "--tag" not in help_text
    assert "--rerun-on-fail" in help_text
    assert "--cid" in help_text


def test_arg_parser_requires_project_sku_assignee_milestone():
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["submission.tar.xz"])  # missing required args


def test_arg_parser_requires_cid():
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([
            "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
            "-m", "FC", "submission.tar.xz",
        ])  # missing --cid


@patch("checkbox_jira_bugger.cli.C3Client")
@patch("checkbox_jira_bugger.cli.jira_backend")
@patch("checkbox_jira_bugger.cli.checkbox_report")
def test_run_resolves_device_info_from_cid_flag(
    mock_checkbox_report, mock_jira_backend, mock_c3_client_cls, tmp_path
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
        "-3", "c3.ini", "-d", "dut.ini", *CID_ARGS, "submission.tar.xz",
    ])

    run(args)

    mock_client.get_device_host.assert_called_once_with("202102-28691")
    # canonical_label must be used as the platform tag passed into jira_backend
    called_args = mock_jira_backend.jira_api.call_args[0]
    assert "resolved-label" in called_args


@patch("checkbox_jira_bugger.cli.C3Client")
def test_run_aborts_if_cid_not_resolvable(mock_c3_client_cls, tmp_path, capsys):
    mock_client = MagicMock()
    mock_client.get_device_host.side_effect = DeviceNotFoundError("no such CID")
    mock_c3_client_cls.from_config_file.return_value = mock_client

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", "--cid", "bad-cid", "submission.tar.xz",
    ])

    with pytest.raises(SystemExit):
        run(args)


def test_run_aborts_on_empty_cid(tmp_path):
    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", "--cid", "   ", "submission.tar.xz",
    ])

    with pytest.raises(SystemExit):
        run(args)


@patch("checkbox_jira_bugger.cli.C3Client")
@patch("checkbox_jira_bugger.cli.jira_backend")
@patch("checkbox_jira_bugger.cli.checkbox_report")
def test_run_raises_systemexit_on_malformed_submission_json(
    mock_checkbox_report, mock_jira_backend, mock_c3_client_cls, tmp_path
):
    mock_checkbox_report.extract_submission_tarball.return_value = str(tmp_path)

    (tmp_path / "submission.json").write_text("not valid json")

    mock_client = MagicMock()
    mock_client.get_device_host.return_value = DeviceInfo(
        canonical_label="resolved-label", ip_address="10.1.2.3"
    )
    mock_c3_client_cls.from_config_file.return_value = mock_client

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", *CID_ARGS, "submission.tar.xz",
    ])

    with pytest.raises(SystemExit):
        run(args)


@patch("checkbox_jira_bugger.cli.C3Client")
@patch("checkbox_jira_bugger.cli.config")
@patch("checkbox_jira_bugger.cli.jira_backend")
@patch("checkbox_jira_bugger.cli.checkbox_report")
def test_run_loads_dut_ssh_config_and_passes_rerun_on_fail(
    mock_checkbox_report, mock_jira_backend, mock_config, mock_c3_client_cls, tmp_path
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

    mock_jira_backend.is_valid_email_address.return_value = True

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "assignee@example.com",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", *CID_ARGS, "--rerun-on-fail", "submission.tar.xz",
    ])

    run(args)

    mock_config.load_dut_ssh_config.assert_called_once_with("dut.ini")
    called_kwargs = mock_jira_backend.deal_with_failed_test_cases_common_test.call_args[1]
    assert called_kwargs["rerun_on_fail"] is True


@patch("checkbox_jira_bugger.cli.MattermostClient")
@patch("checkbox_jira_bugger.cli.C3Client")
@patch("checkbox_jira_bugger.cli.config")
@patch("checkbox_jira_bugger.cli.jira_backend")
@patch("checkbox_jira_bugger.cli.checkbox_report")
def test_run_resolves_username_assignee_via_mattermost(
    mock_checkbox_report, mock_jira_backend, mock_config, mock_c3_client_cls,
    mock_mattermost_client_cls, tmp_path
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

    mock_jira_backend.is_valid_email_address.return_value = False

    mock_config.load_jira_secrets.return_value = MagicMock(mt_token="tok123")
    mock_mm_client = MagicMock()
    mock_mm_client.mt_get_user_email.return_value = "resolved@example.com"
    mock_mattermost_client_cls.return_value = mock_mm_client

    parser = build_arg_parser()
    args = parser.parse_args([
        "-p", "somerville", "-u", "sku1", "-a", "someusername",
        "-m", "FC", "-s", "secrets.ini", "-c", "config.json",
        "-3", "c3.ini", "-d", "dut.ini", *CID_ARGS, "submission.tar.xz",
    ])

    run(args)

    mock_config.load_jira_secrets.assert_called_once_with("secrets.ini")
    mock_mattermost_client_cls.assert_called_once_with("tok123")
    mock_mm_client.mt_get_user_email.assert_called_once_with("someusername")
    called_args = mock_jira_backend.deal_with_failed_test_cases_common_test.call_args[0]
    assert "resolved@example.com" in called_args
