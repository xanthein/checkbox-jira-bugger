"""Tests for the Mattermost username -> email lookup client."""
from unittest.mock import patch, MagicMock

from checkbox_jira_bugger.mattermost import MattermostClient, MATTERMOSTURL


@patch("checkbox_jira_bugger.mattermost.requests.Session")
def test_get_user_email_resolves_username(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    me_response = MagicMock()
    me_response.json.return_value = {"username": "botuser"}

    user_response = MagicMock()
    user_response.json.return_value = {"email": "cyrus.lien@canonical.com"}

    mock_session.get.side_effect = [me_response, user_response]

    client = MattermostClient(token="fake-token")
    email = client.mt_get_user_email("cyruslien")

    assert email == "cyrus.lien@canonical.com"
    mock_session.get.assert_any_call(MATTERMOSTURL + "/users/username/cyruslien")
