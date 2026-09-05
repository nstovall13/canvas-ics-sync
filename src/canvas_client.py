"""Thin wrapper around the Canvas LMS REST API (read-only endpoints only)."""
import time
from datetime import datetime, timezone

import requests


class CanvasClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            # Some hosts' bot-protection layers flag the generic "python-requests/x.x"
            # default User-Agent, especially from well-known shared CI IP ranges
            # (confirmed: this exact request succeeds from a residential IP but got a
            # 406 from GitHub Actions' runners). Identifying as a real client helps.
            "User-Agent": "canvas-ics-sync/1.0 (+https://github.com/nstovall13/canvas-ics-sync)",
            "Accept": "application/json",
        })

    def _get_once(self, url: str, params: dict | None) -> requests.Response:
        try:
            return self._session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Network error calling Canvas API ({url}): {exc}") from exc

    def _request(self, url: str, params: dict | None = None) -> requests.Response:
        resp = self._get_once(url, params)

        if resp.status_code == 401:
            raise RuntimeError(
                "Canvas API returned 401 Unauthorized -- CANVAS_TOKEN is expired, "
                "revoked, or invalid. Generate a new token (Canvas -> Account -> "
                "Settings -> New Access Token) and update the CANVAS_TOKEN secret."
            )

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            time.sleep(5)
            resp = self._get_once(url, params)
            if resp.status_code == 403:
                raise RuntimeError("Canvas API rate limit exceeded even after retrying. Try again later.")

        if resp.status_code == 406:
            # Seen intermittently, likely a transient bot-protection challenge rather
            # than a real per-request problem -- one retry after a short pause clears
            # it in practice.
            time.sleep(5)
            resp = self._get_once(url, params)
            if resp.status_code == 406:
                raise RuntimeError(
                    "Canvas API returned 406 Not Acceptable even after retrying -- this "
                    "looks like host-side bot protection rejecting the request rather "
                    "than a problem with CANVAS_TOKEN or the request itself. Try again "
                    "later; if it persists, it may need Canvas/IT to allowlist the "
                    "request source."
                )

        resp.raise_for_status()
        return resp

    def _get_paginated(self, path: str, params: dict | None = None) -> list[dict]:
        url = f"{self.base_url}{path}"
        results = []
        while url:
            resp = self._request(url, params)
            results.extend(resp.json())
            # Canvas paginates via a Link header (RFC 5988).
            url = resp.links.get("next", {}).get("url")
            params = None  # subsequent requests carry params in the "next" url already
        return results

    def get_active_courses(self) -> list[dict]:
        return self._get_paginated(
            "/api/v1/courses",
            params={"enrollment_state": "active", "per_page": 100},
        )

    def get_assignments(self, course_id: int) -> list[dict]:
        return self._get_paginated(
            f"/api/v1/courses/{course_id}/assignments",
            params={"per_page": 100, "order_by": "due_at"},
        )

    def get_calendar_events(self, course_ids) -> list[dict]:
        context_codes = [f"course_{cid}" for cid in course_ids]
        if not context_codes:
            return []
        params = {
            "type": "event",
            "all_events": 1,
            "per_page": 100,
            "context_codes[]": context_codes,
        }
        return self._get_paginated("/api/v1/calendar_events", params=params)


def parse_canvas_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Canvas returns ISO 8601 UTC timestamps like "2026-09-05T20:59:59Z".
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
