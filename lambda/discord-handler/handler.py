"""
Discord Interactions handler for the Valheim server.

Flow:
  1. API Gateway receives POST /discord from Discord.
  2. VTL template in API Gateway wraps the body + headers into a single JSON event
     (so Lambda sees X-Signature-Ed25519 and X-Signature-Timestamp).
  3. This handler verifies the Ed25519 signature using the app's public key.
  4. Responds to PING (type=1) with PONG for Discord's endpoint verification.
  5. Dispatches slash command sub-options to ecs.describe_services / ecs.update_service.

The slash command shape (registered by scripts/register_bot.py):
  /vh <status|start|stop>
"""
import base64
import json
import logging
import os
from datetime import datetime, timezone

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

APPLICATION_PUBLIC_KEY = os.environ["APPLICATION_PUBLIC_KEY"]
ECS_CLUSTER_ARN = os.environ["ECS_CLUSTER_ARN"]
ECS_SERVICE_NAME = os.environ["ECS_SERVICE_NAME"]
START_DESIRED_COUNT = int(os.environ.get("START_DESIRED_COUNT", "1"))
# Public hostname players connect to (e.g. "valheim.chipsgaming.click").
# Used to build the connect string shown in /vh status replies.
VALHEIM_HOSTNAME = os.environ.get("VALHEIM_HOSTNAME", "")
# Valheim default game port. 2456 UDP is the join port; query is 2457.
VALHEIM_PORT = int(os.environ.get("VALHEIM_PORT", "2456"))

# Discord interaction types
PING = 1
APPLICATION_COMMAND = 2

# Discord interaction response types
PONG = 1
CHANNEL_MESSAGE_WITH_SOURCE = 4

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))
_ecs = boto3.client("ecs")


def _verify_signature(raw_body: str, signature: str, timestamp: str) -> bool:
    try:
        _verify_key.verify(
            f"{timestamp}{raw_body}".encode("utf-8"),
            bytes.fromhex(signature),
        )
        return True
    except BadSignatureError:
        return False


def _reply(content: str) -> dict:
    """Build a Discord CHANNEL_MESSAGE_WITH_SOURCE response."""
    return {
        "type": CHANNEL_MESSAGE_WITH_SOURCE,
        "data": {
            "tts": False,
            "content": content,
            "embeds": [],
            "allowed_mentions": {"parse": []},
        },
    }


def _format_uptime(seconds: int) -> str:
    """Human-readable uptime, e.g. '45s', '7m', '2h 14m', '3d 5h'."""
    if seconds < 60:
        return f"{seconds}s"
    minutes, _ = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m"
    hours, m = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {m}m"
    days, h = divmod(hours, 24)
    return f"{days}d {h}h"


def _running_task_uptime_seconds() -> int | None:
    """Return uptime (seconds) of the currently running task, or None if none found."""
    arns = _ecs.list_tasks(
        cluster=ECS_CLUSTER_ARN,
        serviceName=ECS_SERVICE_NAME,
        desiredStatus="RUNNING",
    ).get("taskArns", [])
    if not arns:
        return None
    tasks = _ecs.describe_tasks(cluster=ECS_CLUSTER_ARN, tasks=arns).get("tasks", [])
    started_ats = [t["startedAt"] for t in tasks if t.get("startedAt")]
    if not started_ats:
        return None
    started = min(started_ats)  # oldest running task = actual server uptime
    return int((datetime.now(timezone.utc) - started).total_seconds())


def _connect_string() -> str:
    """Return ' Connect: host:port' or '' if hostname not configured."""
    if not VALHEIM_HOSTNAME:
        return ""
    return f" Connect: `{VALHEIM_HOSTNAME}:{VALHEIM_PORT}`"


def _status() -> str:
    resp = _ecs.describe_services(
        cluster=ECS_CLUSTER_ARN,
        services=[ECS_SERVICE_NAME],
    )
    svc = resp["services"][0]
    desired = svc["desiredCount"]
    running = svc["runningCount"]
    pending = svc["pendingCount"]
    if desired == 0 and running == 0:
        return "🛑 Server is OFF. Use `/vh start` to bring it up."
    if running == desired and pending == 0:
        uptime_s = _running_task_uptime_seconds()
        uptime_str = f" — up {_format_uptime(uptime_s)}" if uptime_s is not None else ""
        return f"✅ Server is ONLINE{uptime_str}.{_connect_string()}"
    return f"⏳ Server is transitioning — desired: {desired}, running: {running}, pending: {pending}."


def _start() -> str:
    _ecs.update_service(
        cluster=ECS_CLUSTER_ARN,
        service=ECS_SERVICE_NAME,
        desiredCount=START_DESIRED_COUNT,
    )
    return (
        "🟢 Starting the Valheim server… give it 2–4 minutes to boot, mount EFS, and "
        "update DNS. Then use `/vh status` to confirm."
    )


def _stop() -> str:
    _ecs.update_service(
        cluster=ECS_CLUSTER_ARN,
        service=ECS_SERVICE_NAME,
        desiredCount=0,
    )
    return "🔴 Stopping the server. Game progress has been saved."


def _dispatch(interaction: dict) -> dict:
    data = interaction.get("data") or {}
    options = data.get("options") or []
    if not options:
        return _reply("Usage: `/vh <status|start|stop>`")
    choice = (options[0].get("value") or "").lower()
    try:
        if choice == "status":
            return _reply(_status())
        if choice == "start":
            return _reply(_start())
        if choice == "stop":
            return _reply(_stop())
        return _reply(f"Unknown sub-command `{choice}`. Use status, start, or stop.")
    except Exception as exc:  # noqa: BLE001 — surface error back to user
        logger.exception("Dispatch failed for choice=%s", choice)
        return _reply(f"⚠️ Command failed: `{type(exc).__name__}`. Check CloudWatch logs.")


def handler(event, _context):
    """
    Lambda entry point (API Gateway Proxy integration).

    Discord signs the RAW request body bytes concatenated with the timestamp.
    We must verify against those exact bytes — do NOT parse-then-re-serialize
    the body (key order and whitespace won't match, and verification fails).
    """
    logger.info("Event keys: %s", list(event.keys()))
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    signature = headers.get("x-signature-ed25519")
    timestamp = headers.get("x-signature-timestamp")
    if not signature or not timestamp or not _verify_signature(raw_body, signature, timestamp):
        logger.warning("Signature verification failed")
        return {"statusCode": 401, "body": "invalid request signature"}

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Body was not valid JSON after signature check passed")
        return {"statusCode": 400, "body": "invalid json"}

    interaction_type = body.get("type")
    if interaction_type == PING:
        response = {"type": PONG}
    elif interaction_type == APPLICATION_COMMAND:
        response = _dispatch(body)
    else:
        logger.warning("Unhandled interaction type: %s", interaction_type)
        response = _reply("Unsupported interaction.")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }
