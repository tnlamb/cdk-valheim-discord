"""
Idle monitor for the Valheim server — auto-stops the Fargate service after
IDLE_TIMEOUT_SECONDS of zero players.

Triggered on a schedule (e.g. every 5 minutes) by EventBridge.

Signal source: Steam A2S_INFO UDP query to VALHEIM_HOSTNAME:VALHEIM_QUERY_PORT.
Modern Source servers require a challenge/response handshake, which this
handler implements.

State: a single SSM Parameter stores the Unix epoch of the last observation
with >0 players. The idle baseline used for the stop decision is
    max(last_active_at, task_started_at + GRACE_PERIOD)
so a server that just booted gets a grace window before auto-stop can fire,
regardless of what last_active_at was on previous runs.

Failure behavior: if A2S returns nothing, the run is treated as inconclusive
and the timer is left untouched. That biases toward "don't stop" over
"aggressively stop" — the user can always /vh stop manually.
"""
import logging
import os
import socket
import time
from datetime import datetime, timezone

import boto3

ECS_CLUSTER_ARN = os.environ["ECS_CLUSTER_ARN"]
ECS_SERVICE_NAME = os.environ["ECS_SERVICE_NAME"]
VALHEIM_HOSTNAME = os.environ["VALHEIM_HOSTNAME"]
VALHEIM_QUERY_PORT = int(os.environ.get("VALHEIM_QUERY_PORT", "2457"))
IDLE_TIMEOUT_SECONDS = int(os.environ.get("IDLE_TIMEOUT_SECONDS", "1800"))  # 30 min
GRACE_PERIOD_SECONDS = int(os.environ.get("GRACE_PERIOD_SECONDS", "600"))  # 10 min
STATE_PARAM_NAME = os.environ["STATE_PARAM_NAME"]

# A2S protocol constants
A2S_INFO_REQUEST = b"\xff\xff\xff\xff\x54Source Engine Query\x00"
A2S_HEADER = b"\xff\xff\xff\xff"
A2S_CHALLENGE_RESPONSE = 0x41  # 'A' — server wants a challenge-response
A2S_INFO_RESPONSE = 0x49       # 'I' — the actual info payload

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_ecs = boto3.client("ecs")
_ssm = boto3.client("ssm")


def _query_player_count(host: str, port: int, timeout: float = 3.0) -> int | None:
    """
    Send A2S_INFO and return the player count, or None if inconclusive.

    Implements the challenge-response handshake required by modern Source
    servers: a 0x41 response carries a 4-byte challenge which must be echoed
    back appended to the original A2S_INFO request.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(A2S_INFO_REQUEST, (host, port))
        data, _ = sock.recvfrom(1400)

        # Challenge-response: resend with the echoed challenge appended.
        if len(data) >= 9 and data[:4] == A2S_HEADER and data[4] == A2S_CHALLENGE_RESPONSE:
            challenge = data[5:9]
            sock.sendto(A2S_INFO_REQUEST + challenge, (host, port))
            data, _ = sock.recvfrom(1400)

        if len(data) < 6 or data[:4] != A2S_HEADER or data[4] != A2S_INFO_RESPONSE:
            logger.warning("Unexpected A2S response header: %s", data[:8].hex())
            return None

        # Skip 4-byte header + 1-byte response type + 1-byte protocol version.
        pos = 6
        # Server name, map, folder, game — four null-terminated c-strings.
        for _ in range(4):
            end = data.index(b"\x00", pos)
            pos = end + 1
        # Skip 2-byte appid (little-endian short).
        pos += 2
        # Next byte is the player count.
        return data[pos]
    except socket.timeout:
        logger.warning("A2S query timed out against %s:%d", host, port)
        return None
    except Exception as exc:  # noqa: BLE001 — any parse error = inconclusive
        logger.exception("A2S query failed: %s", exc)
        return None
    finally:
        sock.close()


def _get_running_task_started_at() -> datetime | None:
    """Return startedAt of the oldest RUNNING task, or None if none found."""
    arns = _ecs.list_tasks(
        cluster=ECS_CLUSTER_ARN,
        serviceName=ECS_SERVICE_NAME,
        desiredStatus="RUNNING",
    ).get("taskArns", [])
    if not arns:
        return None
    tasks = _ecs.describe_tasks(cluster=ECS_CLUSTER_ARN, tasks=arns).get("tasks", [])
    started_ats = [t["startedAt"] for t in tasks if t.get("startedAt")]
    return min(started_ats) if started_ats else None


def _get_last_active_epoch() -> int:
    """Read last_active_at from SSM. Returns 0 on first-ever run."""
    try:
        val = _ssm.get_parameter(Name=STATE_PARAM_NAME)["Parameter"]["Value"]
        return int(val)
    except (_ssm.exceptions.ParameterNotFound, ValueError):
        return 0


def _put_last_active_epoch(epoch: int) -> None:
    _ssm.put_parameter(
        Name=STATE_PARAM_NAME,
        Value=str(epoch),
        Type="String",
        Overwrite=True,
    )


def _stop_service() -> None:
    _ecs.update_service(
        cluster=ECS_CLUSTER_ARN,
        service=ECS_SERVICE_NAME,
        desiredCount=0,
    )


def handler(event, _context):
    now = int(time.time())
    logger.info("Idle check starting at epoch=%d", now)

    # 1. Is the service up? If desiredCount=0, nothing to do.
    svc = _ecs.describe_services(
        cluster=ECS_CLUSTER_ARN,
        services=[ECS_SERVICE_NAME],
    )["services"][0]
    if svc["desiredCount"] == 0:
        logger.info("Service already stopped (desiredCount=0). Nothing to do.")
        return {"action": "noop", "reason": "service_stopped"}

    # 2. Is there a RUNNING task? During startup/shutdown there may not be.
    started_at = _get_running_task_started_at()
    if started_at is None:
        logger.info("No RUNNING task found — skipping this cycle.")
        return {"action": "noop", "reason": "no_running_task"}

    task_started_epoch = int(started_at.replace(tzinfo=timezone.utc).timestamp())
    age = now - task_started_epoch
    logger.info("Task startedAt=%s (age=%ds)", started_at.isoformat(), age)

    # 3. Query the server for player count.
    players = _query_player_count(VALHEIM_HOSTNAME, VALHEIM_QUERY_PORT)
    if players is None:
        logger.info("A2S query inconclusive — leaving state untouched.")
        return {"action": "noop", "reason": "query_inconclusive"}
    logger.info("Observed player count: %d", players)

    # 4. If players > 0, bump the activity timestamp and exit.
    if players > 0:
        _put_last_active_epoch(now)
        return {"action": "noop", "reason": "active", "players": players}

    # 5. Idle. Compute baseline, decide whether to stop.
    last_active = _get_last_active_epoch()
    idle_baseline = max(last_active, task_started_epoch + GRACE_PERIOD_SECONDS)
    idle_for = now - idle_baseline
    logger.info(
        "Idle: last_active=%d, grace_end=%d, baseline=%d, idle_for=%ds, threshold=%ds",
        last_active, task_started_epoch + GRACE_PERIOD_SECONDS, idle_baseline,
        idle_for, IDLE_TIMEOUT_SECONDS,
    )

    if idle_for >= IDLE_TIMEOUT_SECONDS:
        logger.info("Idle threshold exceeded — stopping service.")
        _stop_service()
        # Reset the activity timestamp so the next start has a clean slate.
        _put_last_active_epoch(0)
        return {"action": "stopped", "idle_for_seconds": idle_for}

    return {"action": "noop", "reason": "idle_within_threshold", "idle_for_seconds": idle_for}
