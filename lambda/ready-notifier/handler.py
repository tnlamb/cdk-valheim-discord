"""
Server-ready notifier.

Triggered by an EventBridge rule when a Valheim Fargate task reaches
`lastStatus=RUNNING`. Polls the server's Steam A2S query port until it
answers (meaning the world has finished loading and the game port is open),
then posts a ready message to a Discord channel using a bot token.

Fires once per task start. Skips rolling deployments by checking if another
task was already RUNNING in the service (cold starts go from 0 → 1 tasks).
"""
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request

import boto3

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = os.environ["DISCORD_CHANNEL_ID"]
VALHEIM_HOSTNAME = os.environ["VALHEIM_HOSTNAME"]
VALHEIM_QUERY_PORT = int(os.environ.get("VALHEIM_QUERY_PORT", "2457"))
# Total wall-clock budget to wait for A2S to answer before giving up.
READY_TIMEOUT_SECONDS = int(os.environ.get("READY_TIMEOUT_SECONDS", "300"))  # 5 min
# Interval between A2S probes while polling.
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "15"))
A2S_SOCKET_TIMEOUT_SECONDS = float(os.environ.get("A2S_SOCKET_TIMEOUT_SECONDS", "3"))

A2S_INFO_REQUEST = b"\xff\xff\xff\xff\x54Source Engine Query\x00"
A2S_HEADER = b"\xff\xff\xff\xff"
A2S_CHALLENGE_RESPONSE = 0x41
A2S_INFO_RESPONSE = 0x49

DISCORD_API_BASE = "https://discord.com/api/v10"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _probe_a2s() -> bool:
    """One-shot A2S probe. Returns True if the server answered with an info response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(A2S_SOCKET_TIMEOUT_SECONDS)
    try:
        sock.sendto(A2S_INFO_REQUEST, (VALHEIM_HOSTNAME, VALHEIM_QUERY_PORT))
        data, _ = sock.recvfrom(1400)

        if len(data) >= 9 and data[:4] == A2S_HEADER and data[4] == A2S_CHALLENGE_RESPONSE:
            challenge = data[5:9]
            sock.sendto(A2S_INFO_REQUEST + challenge, (VALHEIM_HOSTNAME, VALHEIM_QUERY_PORT))
            data, _ = sock.recvfrom(1400)

        return len(data) >= 6 and data[:4] == A2S_HEADER and data[4] == A2S_INFO_RESPONSE
    except (socket.timeout, OSError):
        return False
    finally:
        sock.close()


def _post_discord_message(content: str) -> None:
    """POST a plain-text message to the configured Discord channel as the bot."""
    url = f"{DISCORD_API_BASE}/channels/{DISCORD_CHANNEL_ID}/messages"
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "ValheimReadyNotifier (https://github.com/tnlamb/cdk-valheim-discord, 1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Discord API response status=%s", resp.status)
    except urllib.error.HTTPError as exc:
        logger.error("Discord API HTTP %s: %s", exc.code, exc.read().decode("utf-8", "replace"))
        raise


def handler(event, _context):
    """
    EventBridge delivers an ECS Task State Change event here. We only care about
    tasks reaching `lastStatus=RUNNING` — the rule already filters to that, but
    we double-check in case of unexpected deliveries.

    To avoid spurious notifications during rolling deployments, we check if
    multiple tasks are RUNNING in the service. A user-initiated start goes from
    0 → 1 tasks; a deployment briefly has 2 tasks running.
    """
    logger.info("Received event: %s", json.dumps(event)[:500])
    detail = event.get("detail") or {}
    if detail.get("lastStatus") != "RUNNING":
        logger.info("Ignoring event: lastStatus=%s", detail.get("lastStatus"))
        return {"action": "noop", "reason": "not_running"}

    # Check if this is a rolling deployment (multiple tasks running)
    cluster_arn = detail.get("clusterArn", "")
    service_name = detail.get("group", "").removeprefix("service:")
    if cluster_arn and service_name:
        ecs = boto3.client("ecs")
        running_tasks = ecs.list_tasks(
            cluster=cluster_arn, serviceName=service_name, desiredStatus="RUNNING"
        )
        task_count = len(running_tasks.get("taskArns", []))
        if task_count > 1:
            logger.info("Skipping notification: %d tasks running (rolling deployment)", task_count)
            return {"action": "skipped", "reason": "rolling_deployment", "task_count": task_count}

    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        if _probe_a2s():
            elapsed = int(READY_TIMEOUT_SECONDS - (deadline - time.monotonic()))
            logger.info("A2S responded after %d attempts (~%ds)", attempts, elapsed)
            _post_discord_message("⚡️ Valheim server is ready!")
            return {"action": "notified", "attempts": attempts}
        logger.info("A2S probe %d failed, sleeping %ds", attempts, POLL_INTERVAL_SECONDS)
        time.sleep(POLL_INTERVAL_SECONDS)

    logger.warning("A2S never answered within %ds", READY_TIMEOUT_SECONDS)
    _post_discord_message(
        f"⚠️ Valheim server didn't become ready within "
        f"{READY_TIMEOUT_SECONDS // 60} minutes. Try `/vh status`, or "
        f"`/vh stop` + `/vh start` to try again."
    )
    return {"action": "timeout", "attempts": attempts}
