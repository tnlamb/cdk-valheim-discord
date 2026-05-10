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
import json
import logging
import os

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

APPLICATION_PUBLIC_KEY = os.environ["APPLICATION_PUBLIC_KEY"]
ECS_CLUSTER_ARN = os.environ["ECS_CLUSTER_ARN"]
ECS_SERVICE_NAME = os.environ["ECS_SERVICE_NAME"]
START_DESIRED_COUNT = int(os.environ.get("START_DESIRED_COUNT", "1"))

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
        return f"✅ Server is ONLINE (running: {running}). Connect via the DNS name."
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
    return "🔴 Stopping the server. Your save is preserved on EFS."


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
    Lambda entry point. `event` comes from the VTL template in API Gateway:
      {"body": <parsed-json>, "headers": {...}}

    The Discord signature is verified over the RAW body bytes + timestamp, so we
    re-serialize the parsed JSON exactly as received. We rely on Python's default
    separators here; Discord's reference servers do the same.
    """
    logger.info("Event keys: %s", list(event.keys()))
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or {}
    # Re-serialize body for signature check. API Gateway parsed it into a dict;
    # we need the exact bytes Discord signed. Using compact separators matches
    # Discord's canonical form.
    raw_body = json.dumps(body, separators=(",", ":"))

    signature = headers.get("x-signature-ed25519")
    timestamp = headers.get("x-signature-timestamp")
    if not signature or not timestamp or not _verify_signature(raw_body, signature, timestamp):
        logger.warning("Signature verification failed")
        # 401 response — API Gateway maps this via integrationResponses selectionPattern.
        return {"statusCode": 401, "body": "invalid request signature"}

    interaction_type = body.get("type")
    if interaction_type == PING:
        return {"type": PONG}
    if interaction_type == APPLICATION_COMMAND:
        return _dispatch(body)
    logger.warning("Unhandled interaction type: %s", interaction_type)
    return _reply("Unsupported interaction.")
