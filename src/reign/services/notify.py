"""Out-of-band notifications for price alerts (issue #65).

Two opt-in channels, both stdlib-only (no new dependencies):
- SMTP email: set ALERT_SMTP_HOST (+ optional user/pass/from/to). Off when unset.
- Webhook: POST JSON to ALERT_WEBHOOK_URL (e.g. ntfy, Gotify, Slack webhook).
  Off when unset.

When both are unset, notify_* are no-ops returning False (in-app banner
remains the primary surface). Never raises: failures are logged.
"""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from reign.config import settings

logger = logging.getLogger("reign.notify")

HTTP_OK_MIN = 200
HTTP_OK_MAX = 300


def smtp_configured() -> bool:
    return bool(getattr(settings, "alert_smtp_host", ""))


def webhook_configured() -> bool:
    return bool(getattr(settings, "alert_webhook_url", ""))


def notify_email(subject: str, body: str, timeout_s: int = 10) -> bool:
    """Send an email via configured SMTP. Returns True if attempted+sent."""
    host = getattr(settings, "alert_smtp_host", "")
    if not host:
        return False
    port = int(getattr(settings, "alert_smtp_port", 587) or 587)
    username = getattr(settings, "alert_smtp_user", "") or ""
    password = getattr(settings, "alert_smtp_password", "") or ""
    sender = getattr(settings, "alert_email_from", "") or username or "reign@localhost"
    to = getattr(settings, "alert_email_to", "") or username
    if not to:
        logger.warning("Alert email skipped: no recipient configured")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=timeout_s) as client:
            client.starttls()
            if username:
                client.login(username, password)
            client.send_message(msg)
        return True
    except Exception as e:
        logger.warning("Alert email failed: %s", e)
        return False


def notify_webhook(title: str, body: str, extra: dict | None = None, timeout_s: int = 10) -> bool:
    """POST a JSON payload to the configured webhook URL (http/https only)."""
    url = getattr(settings, "alert_webhook_url", "")
    if not url:
        return False
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        logger.warning("Alert webhook skipped: URL must be http(s)")
        return False
    payload = {"title": title, "message": body, **(extra or {})}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.urlopen
        with opener(req, timeout=timeout_s) as resp:
            return HTTP_OK_MIN <= resp.status < HTTP_OK_MAX
    except Exception as e:
        logger.warning("Alert webhook failed: %s", e)
        return False


def notify_alert_fired(
    symbol: str, direction: str, price: object, target: object, holding_id: int
) -> dict:
    """Fan out one alert to all configured channels. Never raises."""
    arrow = ">=" if direction == "above" else "<="
    title = f"Reign alert: {symbol} {arrow} {target}"
    body = f"{symbol} hit {price} ({direction} target {target}, holding #{holding_id})."
    extra = {"symbol": symbol, "direction": direction, "holding_id": holding_id}
    return {
        "email": notify_email(title, body),
        "webhook": notify_webhook(title, body, extra),
    }
