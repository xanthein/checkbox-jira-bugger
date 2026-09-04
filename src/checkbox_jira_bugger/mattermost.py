"""Mattermost REST API client: username -> email lookup only.

Ported from BugHamster/BugHamsterMatterMost.py's mattermost_rest_api class,
keeping only the user-lookup functionality (no daemon/CLI component). Token
loading is the caller's responsibility (see config.load_jira_secrets), so
this client takes a token directly rather than parsing an ini file itself.
"""
import logging

import requests

MATTERMOSTURL = "https://chat.canonical.com/api/v4"
REQUEST_TIMEOUT = 30

log = logging.getLogger(__name__)


class MattermostApiError(Exception):
    """Raised when a network/HTTP error occurs while talking to the Mattermost API."""


class MattermostClient:
    def __init__(self, token: str):
        self.mt_token = token
        self.mt_session = requests.Session()
        self.mt_session.headers.update(
            {"Authorization": "Bearer {}".format(self.mt_token)}
        )

    def mt_get_user_email(self, mt_user_name: str) -> str:
        try:
            response = self.mt_session.get(
                MATTERMOSTURL + "/users/username/{}".format(mt_user_name),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise MattermostApiError(
                f"Mattermost API request for user {mt_user_name} failed: {exc}"
            ) from exc

        if response.status_code == 404:
            raise MattermostApiError(f"No such Mattermost user: {mt_user_name}")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise MattermostApiError(
                f"Mattermost API request for user {mt_user_name} failed: {exc}"
            ) from exc

        body = response.json()
        if "email" not in body:
            raise MattermostApiError(f"No such Mattermost user: {mt_user_name}")

        mt_user_email = body["email"]
        log.debug("Resolved email for user %s", mt_user_name)
        return mt_user_email
