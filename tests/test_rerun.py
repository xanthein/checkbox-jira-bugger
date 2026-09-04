import shlex
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from checkbox_jira_bugger.rerun import (
    is_job_eligible_for_rerun,
    parse_rerun_output,
    rerun_job,
    RerunResult,
)
from checkbox_jira_bugger.config import DutSshConfig


def test_is_job_eligible_matches_pattern():
    patterns = ["com.canonical.certification::audio/*"]
    assert is_job_eligible_for_rerun(
        "com.canonical.certification::audio/playback", patterns
    )


def test_is_job_eligible_no_match():
    patterns = ["com.canonical.certification::audio/*"]
    assert not is_job_eligible_for_rerun(
        "com.canonical.certification::bluetooth/scan", patterns
    )


def test_is_job_eligible_empty_patterns():
    assert not is_job_eligible_for_rerun(
        "com.canonical.certification::audio/playback", []
    )


def test_parse_rerun_output_pass():
    stdout = (
        "job_start: com.canonical.certification::audio/playback\n"
        " job passed\n"
        "com.canonical.certification::audio/playback: pass\n"
    )
    result = parse_rerun_output(
        "com.canonical.certification::audio/playback", stdout, "", 0
    )
    assert result.status == "pass"
    assert result.error is None
    assert result.io_log == stdout


def test_parse_rerun_output_fail():
    stdout = "com.canonical.certification::audio/playback: fail\n"
    result = parse_rerun_output(
        "com.canonical.certification::audio/playback", stdout, "", 0
    )
    assert result.status == "fail"
    assert result.error is None


def test_parse_rerun_output_crash():
    stdout = "com.canonical.certification::audio/playback: crash\n"
    result = parse_rerun_output(
        "com.canonical.certification::audio/playback", stdout, "", 1
    )
    assert result.status == "crash"


def test_parse_rerun_output_unparseable():
    result = parse_rerun_output("com.canonical.certification::audio/playback", "garbage output", "some error", 1)
    assert result.status is None
    assert result.error is not None


@patch("checkbox_jira_bugger.rerun.subprocess.run")
def test_rerun_job_success(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=0,
        stdout="com.canonical.certification::audio/playback: pass\n",
        stderr="",
    )
    ssh_config = DutSshConfig(
        user="ubuntu", ssh_key="/key", timeout=30, env={"FOO": "bar"}, rerun_job_patterns=[]
    )
    result = rerun_job("com.canonical.certification::audio/playback", "10.1.2.3", ssh_config)
    assert result.status == "pass"
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "ssh"
    assert "-i" in called_cmd and "/key" in called_cmd
    assert "ubuntu@10.1.2.3" in called_cmd
    joined = " ".join(called_cmd)
    assert "FOO=bar" in joined
    assert "checkbox-cli run com.canonical.certification::audio/playback" in joined


@patch("checkbox_jira_bugger.rerun.subprocess.run")
def test_rerun_job_timeout_returns_error(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=30)
    ssh_config = DutSshConfig(
        user="ubuntu", ssh_key="/key", timeout=30, env={}, rerun_job_patterns=[]
    )
    result = rerun_job("com.canonical.certification::audio/playback", "10.1.2.3", ssh_config)
    assert result.status is None
    assert "timed out" in result.error.lower()


@patch("checkbox_jira_bugger.rerun.subprocess.run")
def test_rerun_job_escapes_shell_metacharacters(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=0,
        stdout="com.canonical.certification::audio/playback: pass\n",
        stderr="",
    )
    ssh_config = DutSshConfig(
        user="ubuntu",
        ssh_key="/key",
        timeout=30,
        env={"FOO": "bar; rm -rf /tmp/pwned"},
        rerun_job_patterns=[],
    )
    rerun_job("com.canonical.certification::audio/playback", "10.1.2.3", ssh_config)
    called_cmd = mock_run.call_args[0][0]
    remote_cmd = called_cmd[-1]
    # The dangerous substring must appear only inside a quoted token, never as
    # a bare unquoted shell command separator.
    assert "FOO=" + shlex.quote("bar; rm -rf /tmp/pwned") in remote_cmd
    # Re-tokenizing with shlex should yield exactly one arg for FOO=..., not
    # split into separate shell commands.
    tokens = shlex.split(remote_cmd)
    foo_tokens = [t for t in tokens if t.startswith("FOO=")]
    assert foo_tokens == ["FOO=bar; rm -rf /tmp/pwned"]
    assert "rm" not in tokens


@patch("checkbox_jira_bugger.rerun.subprocess.run")
def test_rerun_job_ssh_connection_failure_returncode_255(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=255,
        stdout="",
        stderr="ssh: connect to host 10.1.2.3 port 22: Connection refused\n",
    )
    ssh_config = DutSshConfig(
        user="ubuntu", ssh_key="/key", timeout=30, env={}, rerun_job_patterns=[]
    )
    result = rerun_job("com.canonical.certification::audio/playback", "10.1.2.3", ssh_config)
    assert result.status is None
    assert "ssh connection" in result.error.lower()
    assert "could not parse status" not in result.error.lower()


def test_parse_rerun_output_status_with_trailing_text():
    stdout = "com.canonical.certification::audio/playback: fail (with warnings)\n"
    result = parse_rerun_output(
        "com.canonical.certification::audio/playback", stdout, "", 1
    )
    assert result.status == "fail"
