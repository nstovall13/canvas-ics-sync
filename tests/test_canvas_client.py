from unittest.mock import MagicMock, patch

import pytest
import requests

from src.canvas_client import CanvasClient


def _response(status_code, text="", json_data=None, links=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else []
    resp.links = links or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} error", response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_sets_identifying_user_agent():
    client = CanvasClient("https://example.instructure.com", "tok")
    assert "canvas-ics-sync" in client._session.headers["User-Agent"]


def test_401_raises_clear_token_error():
    client = CanvasClient("https://example.instructure.com", "tok")
    with patch.object(client._session, "get", return_value=_response(401)):
        with pytest.raises(RuntimeError, match="CANVAS_TOKEN is expired"):
            client.get_active_courses()


@patch("src.canvas_client.time.sleep")
def test_403_rate_limit_retries_then_succeeds(mock_sleep):
    client = CanvasClient("https://example.instructure.com", "tok")
    responses = [_response(403, text="Rate Limit Exceeded"), _response(200, json_data=[{"id": 1}])]
    with patch.object(client._session, "get", side_effect=responses):
        courses = client.get_active_courses()
    assert courses == [{"id": 1}]
    mock_sleep.assert_called_once()


@patch("src.canvas_client.time.sleep")
def test_403_rate_limit_raises_if_still_failing_after_retry(mock_sleep):
    client = CanvasClient("https://example.instructure.com", "tok")
    responses = [_response(403, text="Rate Limit Exceeded"), _response(403, text="Rate Limit Exceeded")]
    with patch.object(client._session, "get", side_effect=responses):
        with pytest.raises(RuntimeError, match="rate limit exceeded even after retrying"):
            client.get_active_courses()


@patch("src.canvas_client.time.sleep")
def test_406_retries_then_succeeds(mock_sleep):
    """Real incident: Canvas returned 406 only from GitHub Actions' runner IPs,
    not from a residential IP, on the identical request -- consistent with a
    transient bot-protection challenge rather than a real client error."""
    client = CanvasClient("https://example.instructure.com", "tok")
    responses = [_response(406), _response(200, json_data=[{"id": 1}])]
    with patch.object(client._session, "get", side_effect=responses):
        courses = client.get_active_courses()
    assert courses == [{"id": 1}]
    mock_sleep.assert_called_once()


@patch("src.canvas_client.time.sleep")
def test_406_raises_clear_error_if_still_failing_after_retry(mock_sleep):
    client = CanvasClient("https://example.instructure.com", "tok")
    responses = [_response(406), _response(406)]
    with patch.object(client._session, "get", side_effect=responses):
        with pytest.raises(RuntimeError, match="406 Not Acceptable even after retrying"):
            client.get_active_courses()


def test_network_error_wrapped_in_clear_runtime_error():
    client = CanvasClient("https://example.instructure.com", "tok")
    with patch.object(client._session, "get", side_effect=requests.exceptions.ConnectionError("boom")):
        with pytest.raises(RuntimeError, match="Network error calling Canvas API"):
            client.get_active_courses()


def test_pagination_follows_link_header():
    client = CanvasClient("https://example.instructure.com", "tok")
    page1 = _response(200, json_data=[{"id": 1}], links={"next": {"url": "https://example.instructure.com/api/v1/courses?page=2"}})
    page2 = _response(200, json_data=[{"id": 2}])
    with patch.object(client._session, "get", side_effect=[page1, page2]):
        courses = client.get_active_courses()
    assert courses == [{"id": 1}, {"id": 2}]
