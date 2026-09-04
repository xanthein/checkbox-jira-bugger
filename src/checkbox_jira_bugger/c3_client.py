"""C3 (certification.canonical.com) API client.

OAuth2 client-credentials auth, modeled on transfer_dut/c3_api.py and
documented in certification_v2_api.yaml.
"""
import base64
import logging
from dataclasses import dataclass

import requests

from checkbox_jira_bugger import config

C3_BASE_URL = "https://certification.canonical.com"
REQUEST_TIMEOUT = 30

log = logging.getLogger(__name__)


class DeviceNotFoundError(Exception):
    """Raised when a CID cannot be resolved to a machine and/or lab resource."""


class C3ApiError(Exception):
    """Raised when a network/HTTP error occurs while talking to the C3 API."""


@dataclass(frozen=True)
class DeviceInfo:
    canonical_label: str
    ip_address: str


class C3Client:
    def __init__(self, client_id: str, client_secret: str):
        self.base_url = C3_BASE_URL
        self.access_token = self._get_access_token(client_id, client_secret)

    @classmethod
    def from_config_file(cls, c3_config_file: str) -> "C3Client":
        c3_config = config.load_c3_config(c3_config_file)
        return cls(client_id=c3_config.client_id, client_secret=c3_config.client_secret)

    def _get_access_token(self, client_id: str, client_secret: str) -> str:
        credential = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("utf-8")
        headers = {
            "Authorization": f"Basic {credential}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        params = {"grant_type": "client_credentials", "scope": "read write"}
        try:
            response = requests.post(
                f"{self.base_url}/oauth2/token/",
                headers=headers,
                data=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise C3ApiError(f"Failed to obtain C3 access token: {exc}") from exc
        return response.json()["access_token"]

    def c3_get(self, endpoint: str, **params):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params.setdefault("pagination", "limitoffset")
        params.setdefault("limit", 0)
        try:
            response = requests.get(
                f"{self.base_url}/api/v2/{endpoint}",
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as exc:
            raise C3ApiError(f"C3 API request to {endpoint} failed: {exc}") from exc
        body = response.json()
        return body["results"] if isinstance(body, dict) and "results" in body else body

    def get_device_host(self, cid: str) -> DeviceInfo:
        """Resolve a CID (canonical id) to its canonical_label and current DUT IP.

        Raises DeviceNotFoundError if the machine record or its linked lab
        resource IP address cannot be found.
        """
        machine = self.c3_get(f"machines/{cid}/")
        if not machine or "canonical_label" not in machine:
            raise DeviceNotFoundError(f"No machine record found for CID {cid}")
        canonical_label = machine["canonical_label"]

        linked = self.c3_get("linked-labresources/", canonical_ids=cid)
        if not linked or cid not in linked:
            raise DeviceNotFoundError(f"No linked lab resource found for CID {cid}")

        ip_address = linked[cid].get("ip_address")
        if not ip_address:
            raise DeviceNotFoundError(f"Linked lab resource for CID {cid} has no ip_address")

        return DeviceInfo(canonical_label=canonical_label, ip_address=ip_address)
