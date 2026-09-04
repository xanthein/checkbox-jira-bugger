"""Load and validate config/secrets ini files for checkbox-jira-bugger."""
import configparser
from dataclasses import dataclass, field


@dataclass
class JiraSecrets:
    jira_email: str
    jira_apitoken: str
    mt_token: str


@dataclass
class C3Config:
    client_id: str
    client_secret: str


@dataclass
class DutSshConfig:
    user: str
    ssh_key: str
    timeout: int
    env: dict
    rerun_job_patterns: list = field(default_factory=list)


def load_jira_secrets(path: str) -> JiraSecrets:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise FileNotFoundError(f"Could not read jira secrets file: {path}")
    return JiraSecrets(
        jira_email=parser["jira account"]["jira_email"],
        jira_apitoken=parser["jira account"]["jira_apitoken"],
        mt_token=parser["mattermost token"]["mt_token"],
    )


def load_c3_config(path: str) -> C3Config:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise FileNotFoundError(f"Could not read c3 config file: {path}")
    return C3Config(
        client_id=parser["c3 secret"]["client_id"],
        client_secret=parser["c3 secret"]["client_secret"],
    )


def load_dut_ssh_config(path: str) -> DutSshConfig:
    parser = configparser.ConfigParser()
    parser.optionxform = str
    if not parser.read(path):
        raise FileNotFoundError(f"Could not read dut ssh config file: {path}")

    dut_section = parser["dut"]
    env = dict(parser["env"]) if parser.has_section("env") else {}

    rerun_job_patterns = []
    if parser.has_section("rerun"):
        raw = parser["rerun"].get("job_patterns", "")
        rerun_job_patterns = [line.strip() for line in raw.splitlines() if line.strip()]

    return DutSshConfig(
        user=dut_section["user"],
        ssh_key=dut_section["ssh_key"],
        timeout=int(dut_section["timeout"]),
        env=env,
        rerun_job_patterns=rerun_job_patterns,
    )
