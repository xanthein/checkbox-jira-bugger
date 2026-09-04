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


class MattermostClient:
    def __init__(self, token: str):
        self.mt_token = token
        self.mt_session = requests.Session()
        self.mt_session.headers.update(
            {"Authorization": "Bearer {}".format(self.mt_token)}
        )
        response = self.mt_session.get(MATTERMOSTURL + "/users/me")
        log.info("Hello %s", response.json()["username"])

    def mt_get_user_email(self, mt_user_name: str) -> str:
        response = self.mt_session.get(
            MATTERMOSTURL + "/users/username/{}".format(mt_user_name)
        )
        mt_user_email = response.json()["email"]
        log.info("%s: %s", mt_user_name, mt_user_email)
        return mt_user_email
