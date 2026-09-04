"""Tests for the Mattermost username -> email lookup client."""
from unittest.mock import patch, MagicMock

import pytest
import requests

from checkbox_jira_bugger.mattermost import (
    MattermostClient,
    MattermostApiError,
    MATTERMOSTURL,
)


@patch("checkbox_jira_bugger.mattermost.requests.Session")
def test_get_user_email_resolves_username(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    user_response = MagicMock()
    user_response.status_code = 200
    user_response.json.return_value = {"email": "cyrus.lien@canonical.com"}
    mock_session.get.return_value = user_response

    client = MattermostClient(token="fake-token")
    email = client.mt_get_user_email("cyruslien")

    assert email == "cyrus.lien@canonical.com"
    mock_session.get.assert_called_once_with(
        MATTERMOSTURL + "/users/username/cyruslien", timeout=30
    )


@patch("checkbox_jira_bugger.mattermost.requests.Session")
def test_get_user_email_passes_timeout(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    user_response = MagicMock()
    user_response.status_code = 200
    user_response.json.return_value = {"email": "cyrus.lien@canonical.com"}
    mock_session.get.return_value = user_response

    client = MattermostClient(token="fake-token")
    client.mt_get_user_email("cyruslien")

    _, kwargs = mock_session.get.call_args
    assert kwargs.get("timeout") is not None


@patch("checkbox_jira_bugger.mattermost.requests.Session")
def test_get_user_email_404_raises_mattermost_api_error(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    user_response = MagicMock()
    user_response.status_code = 404
    mock_session.get.return_value = user_response

    client = MattermostClient(token="fake-token")
    with pytest.raises(MattermostApiError, match="nosuchuser"):
        client.mt_get_user_email("nosuchuser")


@patch("checkbox_jira_bugger.mattermost.requests.Session")
def test_get_user_email_connection_error_raises_mattermost_api_error(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.get.side_effect = requests.exceptions.ConnectionError("boom")

    client = MattermostClient(token="fake-token")
    with pytest.raises(MattermostApiError):
        client.mt_get_user_email("cyruslien")
