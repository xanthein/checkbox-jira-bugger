"""Rerun-before-filing: job eligibility, SSH rerun, output parsing."""
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from checkbox_jira_bugger.config import DutSshConfig


@dataclass
class RerunResult:
    status: Optional[str] = None
    io_log: Optional[str] = None
    error: Optional[str] = None


_STATUS_RE = re.compile(r"^(?P<job_id>\S+):\s*(?P<status>pass|fail|skip|crash)\s*$", re.MULTILINE)


def is_job_eligible_for_rerun(job_full_id: str, patterns: list) -> bool:
    """Return True if job_full_id matches any glob pattern in patterns."""
    return any(fnmatch.fnmatch(job_full_id, pattern) for pattern in patterns)


def parse_rerun_output(job_id: str, stdout: str, stderr: str, returncode: int) -> RerunResult:
    """Regex-parse checkbox-cli stdout to find job_id's pass/fail/skip/crash status."""
    for match in _STATUS_RE.finditer(stdout):
        if match.group("job_id") == job_id:
            return RerunResult(status=match.group("status"), io_log=stdout, error=None)
    return RerunResult(
        status=None,
        io_log=stdout,
        error=f"Could not parse status for {job_id} from checkbox-cli output "
        f"(returncode={returncode}, stderr={stderr!r})",
    )


def rerun_job(job_id: str, host: str, ssh_config: DutSshConfig) -> RerunResult:
    """SSH into host and rerun job_id via checkbox-cli, returning the parsed result."""
    env_prefix = " ".join(f"{key}={value}" for key, value in ssh_config.env.items())
    remote_cmd = f"{env_prefix} checkbox-cli run {job_id}".strip()

    cmd = [
        "ssh",
        "-i", ssh_config.ssh_key,
        "-o", "ConnectTimeout=10",
        f"{ssh_config.user}@{host}",
        remote_cmd,
    ]

    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=ssh_config.timeout
        )
    except subprocess.TimeoutExpired:
        return RerunResult(status=None, io_log=None, error=f"SSH rerun of {job_id} timed out")
    except OSError as exc:
        return RerunResult(status=None, io_log=None, error=f"SSH rerun of {job_id} failed: {exc}")

    return parse_rerun_output(job_id, completed.stdout, completed.stderr, completed.returncode)
