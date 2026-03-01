from __future__ import annotations

import json
from typing import Any

from django.http import HttpResponse


def _parse_hx_trigger_header(raw_header: str) -> dict[str, Any]:
    if not raw_header:
        return {}

    try:
        parsed = json.loads(raw_header)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError):
        pass

    event_map: dict[str, Any] = {}
    for item in raw_header.split(","):
        event_name = item.strip()
        if event_name:
            event_map[event_name] = True
    return event_map


def attach_ui_feedback(
    response: HttpResponse,
    toast: dict[str, Any] | None = None,
    inline: dict[str, Any] | None = None,
) -> HttpResponse:
    payload: dict[str, Any] = {}
    if toast:
        payload["toast"] = toast
    if inline:
        payload["inline"] = inline
    if not payload:
        return response

    existing = _parse_hx_trigger_header(response.headers.get("HX-Trigger", ""))
    existing["ui:feedback"] = payload
    response.headers["HX-Trigger"] = json.dumps(existing)
    return response
