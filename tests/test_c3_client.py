import pytest
from unittest.mock import patch, MagicMock
from checkbox_jira_bugger.c3_client import C3Client, DeviceInfo, DeviceNotFoundError


def _mock_token_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"access_token": "fake-token"}
    resp.raise_for_status.return_value = None
    return resp


@patch("checkbox_jira_bugger.c3_client.requests.post")
def test_client_fetches_access_token_on_init(mock_post):
    mock_post.return_value = _mock_token_response()
    client = C3Client(client_id="cid", client_secret="secret")
    assert client.access_token == "fake-token"
    mock_post.assert_called_once()
    called_url = mock_post.call_args[0][0]
    assert called_url == "https://certification.canonical.com/oauth2/token/"


@patch("checkbox_jira_bugger.c3_client.requests.get")
@patch("checkbox_jira_bugger.c3_client.requests.post")
def test_get_device_host_success(mock_post, mock_get):
    mock_post.return_value = _mock_token_response()

    machine_resp = MagicMock()
    machine_resp.status_code = 200
    machine_resp.raise_for_status.return_value = None
    machine_resp.json.return_value = {"canonical_label": "some-machine-label"}

    labresources_resp = MagicMock()
    labresources_resp.status_code = 200
    labresources_resp.raise_for_status.return_value = None
    labresources_resp.json.return_value = {
        "202102-28691": {"id": 1, "ip_address": "10.1.2.3"}
    }

    mock_get.side_effect = [machine_resp, labresources_resp]

    client = C3Client(client_id="cid", client_secret="secret")
    info = client.get_device_host("202102-28691")

    assert info == DeviceInfo(canonical_label="some-machine-label", ip_address="10.1.2.3")


@patch("checkbox_jira_bugger.c3_client.requests.get")
@patch("checkbox_jira_bugger.c3_client.requests.post")
def test_get_device_host_no_linked_labresource_raises(mock_post, mock_get):
    mock_post.return_value = _mock_token_response()

    machine_resp = MagicMock()
    machine_resp.status_code = 200
    machine_resp.raise_for_status.return_value = None
    machine_resp.json.return_value = {"canonical_label": "some-machine-label"}

    labresources_resp = MagicMock()
    labresources_resp.status_code = 200
    labresources_resp.raise_for_status.return_value = None
    labresources_resp.json.return_value = {}

    mock_get.side_effect = [machine_resp, labresources_resp]

    client = C3Client(client_id="cid", client_secret="secret")
    with pytest.raises(DeviceNotFoundError):
        client.get_device_host("no-such-cid")


@patch("checkbox_jira_bugger.c3_client.requests.get")
@patch("checkbox_jira_bugger.c3_client.requests.post")
def test_get_device_host_empty_ip_raises(mock_post, mock_get):
    mock_post.return_value = _mock_token_response()

    machine_resp = MagicMock()
    machine_resp.status_code = 200
    machine_resp.raise_for_status.return_value = None
    machine_resp.json.return_value = {"canonical_label": "some-machine-label"}

    labresources_resp = MagicMock()
    labresources_resp.status_code = 200
    labresources_resp.raise_for_status.return_value = None
    labresources_resp.json.return_value = {
        "202102-28691": {"id": 1, "ip_address": ""}
    }

    mock_get.side_effect = [machine_resp, labresources_resp]

    client = C3Client(client_id="cid", client_secret="secret")
    with pytest.raises(DeviceNotFoundError):
        client.get_device_host("202102-28691")


@patch("checkbox_jira_bugger.c3_client.requests.post")
def test_from_config_file(mock_post, tmp_path):
    mock_post.return_value = _mock_token_response()
    ini_path = tmp_path / "c3_config.ini"
    ini_path.write_text("[c3 secret]\nclient_id = cid\nclient_secret = secret\n")

    client = C3Client.from_config_file(str(ini_path))
    assert client.access_token == "fake-token"
