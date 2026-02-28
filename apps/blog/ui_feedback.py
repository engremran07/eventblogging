from __future__ import annotations

import json


def _parse_hx_trigger_header(raw_header: str) -> dict:
    if not raw_header:
        return {}

    try:
        parsed = json.loads(raw_header)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError):
        pass

    event_map = {}
    for item in raw_header.split(","):
        event_name = item.strip()
        if event_name:
            event_map[event_name] = True
    return event_map


def attach_ui_feedback(response, toast=None, inline=None):
    payload = {}
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
