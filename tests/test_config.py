import os
from checkbox_jira_bugger import config

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_load_jira_secrets():
    secrets = config.load_jira_secrets(os.path.join(FIXTURES, "jira_secrets.ini"))
    assert secrets.jira_email == "bot@example.com"
    assert secrets.jira_apitoken == "fake-jira-token"
    assert secrets.mt_token == "fake-mm-token"


def test_load_c3_config():
    c3_config = config.load_c3_config(os.path.join(FIXTURES, "c3_config.ini"))
    assert c3_config.client_id == "fake-client-id"
    assert c3_config.client_secret == "fake-client-secret"


def test_load_dut_ssh_config():
    dut_config = config.load_dut_ssh_config(os.path.join(FIXTURES, "dut_ssh_config.ini"))
    assert dut_config.user == "ubuntu"
    assert dut_config.ssh_key == "/home/ubuntu/.ssh/id_rsa"
    assert dut_config.timeout == 30
    assert dut_config.env == {"CHECKBOX_ENV": "1", "LANG": "C.UTF-8"}
    assert dut_config.rerun_job_patterns == [
        "com.canonical.certification::audio/*",
        "com.canonical.certification::bluetooth/*",
    ]


def test_load_dut_ssh_config_no_rerun_section(tmp_path):
    ini_path = tmp_path / "no_rerun.ini"
    ini_path.write_text(
        "[dut]\nuser = ubuntu\nssh_key = /key\ntimeout = 10\n\n[env]\n"
    )
    dut_config = config.load_dut_ssh_config(str(ini_path))
    assert dut_config.rerun_job_patterns == []
