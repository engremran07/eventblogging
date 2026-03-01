from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from urllib import request as urllib_request

from django.utils import timezone

from .models import IntegrationSettings

logger = logging.getLogger(__name__)


def emit_platform_webhook(event: str, payload: dict[str, Any] | None = None) -> bool:
    settings = IntegrationSettings.get_solo()
    webhook_url = (settings.webhook_url or "").strip()
    if not webhook_url:
        return False

    body = {
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "payload": payload or {},
    }
    encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DjangoBlog/1.0",
    }
    secret = (settings.webhook_secret or "").strip()
    if secret:
        digest = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
        headers["X-DjangoBlog-Signature"] = f"sha256={digest}"

    req = urllib_request.Request(
        webhook_url,
        data=encoded,
        headers=headers,
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=1.5) as response:
            return 200 <= int(getattr(response, "status", 200)) < 300
    except Exception:
        logger.exception("Webhook dispatch failed for event '%s'", event)
        return False
