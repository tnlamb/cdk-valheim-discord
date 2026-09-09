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
import socket
from datetime import datetime, timezone

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

APPLICATION_PUBLIC_KEY = os.environ["APPLICATION_PUBLIC_KEY"]
ECS_CLUSTER_ARN = os.environ["ECS_CLUSTER_ARN"]
ECS_SERVICE_NAME = os.environ["ECS_SERVICE_NAME"]
START_DESIRED_COUNT = int(os.environ.get("START_DESIRED_COUNT", "1"))
# Public hostname players connect to (e.g. "valheim.chipsgaming.click").
# Used to build the connect string shown in /vh status replies and as the A2S probe target.
VALHEIM_HOSTNAME = os.environ.get("VALHEIM_HOSTNAME", "")
# Valheim default game port. 2456 UDP is the join port; query is 2457.
VALHEIM_PORT = int(os.environ.get("VALHEIM_PORT", "2456"))
VALHEIM_QUERY_PORT = int(os.environ.get("VALHEIM_QUERY_PORT", "2457"))
# A2S probe must complete well within Discord's 3s interaction response window.
A2S_TIMEOUT_SECONDS = float(os.environ.get("A2S_TIMEOUT_SECONDS", "1.5"))

# Snapshot/rollback configuration
SNAPSHOT_BUCKET = os.environ.get("SNAPSHOT_BUCKET", "")
SNAPSHOT_PREFIX = os.environ.get("SNAPSHOT_PREFIX", "snapshots/")
WORLD_NAME = os.environ.get("WORLD_NAME", "Alfheim")
# Import task configuration for rollback
IMPORT_TASK_FAMILY = os.environ.get("IMPORT_TASK_FAMILY", "valheim-save-import")
IMPORT_SUBNET = os.environ.get("IMPORT_SUBNET", "")
IMPORT_SECURITY_GROUP = os.environ.get("IMPORT_SECURITY_GROUP", "")

# A2S protocol constants — used to probe whether Valheim is actually listening
# yet, since ECS "RUNNING" just means the container started, not that Valheim
# has finished loading the world and opened the game port.
A2S_INFO_REQUEST = b"\xff\xff\xff\xff\x54Source Engine Query\x00"
A2S_HEADER = b"\xff\xff\xff\xff"
A2S_CHALLENGE_RESPONSE = 0x41  # 'A' — server requires challenge/response
A2S_INFO_RESPONSE = 0x49       # 'I' — actual info payload

# Discord interaction types
PING = 1
APPLICATION_COMMAND = 2

# Discord interaction response types
PONG = 1
CHANNEL_MESSAGE_WITH_SOURCE = 4
DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))
_ecs = boto3.client("ecs")
_s3 = boto3.client("s3")


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


def _probe_player_count() -> int | None:
    """
    Send A2S_INFO to the server and return the player count.

    Returns None if the probe is inconclusive (timeout, parse error, or
    Valheim not yet listening). A None result from _status() callers means
    "server is booting, not yet ready for players".
    """
    if not VALHEIM_HOSTNAME:
        return None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(A2S_TIMEOUT_SECONDS)
    try:
        sock.sendto(A2S_INFO_REQUEST, (VALHEIM_HOSTNAME, VALHEIM_QUERY_PORT))
        data, _ = sock.recvfrom(1400)

        # Challenge-response: modern Source servers respond with a 4-byte
        # challenge on the first request that must be echoed back.
        if len(data) >= 9 and data[:4] == A2S_HEADER and data[4] == A2S_CHALLENGE_RESPONSE:
            challenge = data[5:9]
            sock.sendto(A2S_INFO_REQUEST + challenge, (VALHEIM_HOSTNAME, VALHEIM_QUERY_PORT))
            data, _ = sock.recvfrom(1400)

        if len(data) < 6 or data[:4] != A2S_HEADER or data[4] != A2S_INFO_RESPONSE:
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
    except (socket.timeout, OSError, ValueError, IndexError):
        return None
    finally:
        sock.close()


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
    if desired == 0 and running > 0:
        return "🔴 Shutting down — saving game progress."
    if running < desired or pending > 0:
        return "⏳ Starting up — container is coming up. Try `/vh status` again in ~60s."

    # ECS says the task is running; probe whether Valheim itself is listening.
    uptime_s = _running_task_uptime_seconds()
    uptime_str = f" — up {_format_uptime(uptime_s)}" if uptime_s is not None else ""
    players = _probe_player_count()
    if players is None:
        return (
            "⏳ Starting up — game engine is loading the world. "
            "Try `/vh status` again in ~30–60s."
        )
    player_str = (
        " No players online." if players == 0
        else f" {players} player online." if players == 1
        else f" {players} players online."
    )
    return f"✅ Server is ONLINE{uptime_str}.{player_str}{_connect_string()}"


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


def _list_snapshots() -> list[dict]:
    """List snapshot .db files from S3, return sorted newest-first with epoch and size."""
    if not SNAPSHOT_BUCKET:
        return []
    resp = _s3.list_objects_v2(
        Bucket=SNAPSHOT_BUCKET,
        Prefix=SNAPSHOT_PREFIX,
    )
    snapshots = []
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if not key.endswith(f"_{WORLD_NAME}.db"):
            continue
        filename = key.split("/")[-1]
        epoch_str = filename.split("_")[0]
        try:
            epoch = int(epoch_str)
        except ValueError:
            continue
        snapshots.append({"epoch": epoch, "size_mb": round(obj["Size"] / 1048576, 1), "key": key})
    snapshots.sort(key=lambda s: s["epoch"], reverse=True)
    return snapshots


def _rollback_list() -> str:
    """Show available snapshots with Discord timestamps."""
    if not SNAPSHOT_BUCKET:
        return "⚠️ Snapshot bucket not configured."
    snapshots = _list_snapshots()
    if not snapshots:
        return "⚠️ No snapshots found. The server needs to run and autosave at least once."
    lines = ["🔄 **Available saves to restore:**\n"]
    for i, snap in enumerate(snapshots):
        lines.append(f"{i+1}. <t:{snap['epoch']}:f> (<t:{snap['epoch']}:R>) — {snap['size_mb']} MiB")
    lines.append(f"\nTo restore, run: `/vh rollback` with target `<number>`\ne.g. `/vh rollback` target: `1` for the most recent")
    return "\n".join(lines)


def _rollback_restore(choice_str: str) -> str:
    """Restore a specific snapshot by index (1-based) or epoch."""
    if not SNAPSHOT_BUCKET:
        return "⚠️ Snapshot bucket not configured."
    snapshots = _list_snapshots()
    if not snapshots:
        return "⚠️ No snapshots found."

    # Accept 1-based index or raw epoch
    try:
        choice_int = int(choice_str)
    except ValueError:
        return f"⚠️ Invalid choice `{choice_str}`. Use a number (1–{len(snapshots)})."

    if 1 <= choice_int <= len(snapshots):
        snap = snapshots[choice_int - 1]
    else:
        # Try as raw epoch
        snap = next((s for s in snapshots if s["epoch"] == choice_int), None)
        if not snap:
            return f"⚠️ No snapshot found for `{choice_str}`. Run `/vh rollback` to see options."

    # Copy selected snapshot to the import prefix (worlds_local/) so the import task picks it up
    db_key = snap["key"]
    fwl_key = db_key.replace(".db", ".fwl")
    _s3.copy_object(
        Bucket=SNAPSHOT_BUCKET,
        CopySource={"Bucket": SNAPSHOT_BUCKET, "Key": db_key},
        Key=f"worlds_local/{WORLD_NAME}.db",
    )
    _s3.copy_object(
        Bucket=SNAPSHOT_BUCKET,
        CopySource={"Bucket": SNAPSHOT_BUCKET, "Key": fwl_key},
        Key=f"worlds_local/{WORLD_NAME}.fwl",
    )

    # Stop the server (SIGTERM → server flushes final save → exits within 60s)
    _ecs.update_service(
        cluster=ECS_CLUSTER_ARN,
        service=ECS_SERVICE_NAME,
        desiredCount=0,
    )

    # Invoke ourselves asynchronously to wait for stop, run import, wait for
    # import completion, then restart. This avoids Discord's 3s response timeout.
    _lambda = boto3.client("lambda")
    _lambda.invoke(
        FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
        InvocationType="Event",  # async fire-and-forget
        Payload=json.dumps({
            "_rollback_async": True,
            "snapshot_epoch": snap["epoch"],
        }).encode(),
    )

    return (
        f"🔄 Restoring save from <t:{snap['epoch']}:f> (<t:{snap['epoch']}:R>).\n"
        "Server is stopping → importing save → restarting.\n"
        "The ReadyNotifier will ping when the server is back online."
    )


def _dispatch(interaction: dict) -> dict:
    data = interaction.get("data") or {}
    options = data.get("options") or []
    if not options:
        return _reply("Usage: `/vh <status|start|stop|rollback>`")

    # Parse options: {name: value} map
    opts = {o["name"]: o.get("value", "") for o in options}
    choice = opts.get("action", "").lower()
    target = opts.get("target", "").strip()

    try:
        if choice == "status":
            return _reply(_status())
        if choice == "start":
            return _reply(_start())
        if choice == "stop":
            return _reply(_stop())
        if choice == "rollback":
            if not target:
                return _reply(_rollback_list())
            return _reply(_rollback_restore(target))
        return _reply(f"Unknown sub-command `{choice}`. Use status, start, stop, or rollback.")
    except Exception as exc:  # noqa: BLE001 — surface error back to user
        logger.exception("Dispatch failed for choice=%s", choice)
        return _reply(f"⚠️ Command failed: `{type(exc).__name__}`. Check CloudWatch logs.")


def _rollback_async(event: dict) -> None:
    """
    Async rollback orchestration (invoked via Lambda Event invocation).
    Waits for server stop, runs import, waits for import completion, then restarts.
    """
    import time

    logger.info("Rollback async started for epoch %s", event.get("snapshot_epoch"))

    # 1. Wait for server tasks to stop (up to 2 min)
    for _ in range(24):
        time.sleep(5)
        running = _ecs.list_tasks(
            cluster=ECS_CLUSTER_ARN,
            serviceName=ECS_SERVICE_NAME,
            desiredStatus="RUNNING",
        ).get("taskArns", [])
        if not running:
            break
    else:
        logger.error("Server did not stop within 2 minutes, proceeding anyway")

    # 2. Run the import task
    import_task_arn = None
    if IMPORT_SUBNET and IMPORT_SECURITY_GROUP:
        run_resp = _ecs.run_task(
            cluster=ECS_CLUSTER_ARN,
            taskDefinition=IMPORT_TASK_FAMILY,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": [IMPORT_SUBNET],
                    "securityGroups": [IMPORT_SECURITY_GROUP],
                    "assignPublicIp": "ENABLED",
                }
            },
        )
        tasks = run_resp.get("tasks", [])
        if tasks:
            import_task_arn = tasks[0]["taskArn"]

    # 3. Wait for import task to complete (up to 5 min)
    if import_task_arn:
        for _ in range(60):
            time.sleep(5)
            desc = _ecs.describe_tasks(cluster=ECS_CLUSTER_ARN, tasks=[import_task_arn])
            task = desc.get("tasks", [{}])[0]
            if task.get("lastStatus") == "STOPPED":
                containers = task.get("containers", [])
                exit_code = containers[0].get("exitCode", -1) if containers else -1
                if exit_code != 0:
                    logger.error("Import task failed with exit code %d", exit_code)
                    return
                break
        else:
            logger.error("Import task timed out after 5 minutes")
            return

    # 4. Restart the server
    _ecs.update_service(
        cluster=ECS_CLUSTER_ARN,
        service=ECS_SERVICE_NAME,
        desiredCount=START_DESIRED_COUNT,
    )
    logger.info("Rollback complete, server restarting")


def handler(event, _context):
    """
    Lambda entry point (API Gateway Proxy integration).

    Discord signs the RAW request body bytes concatenated with the timestamp.
    We must verify against those exact bytes — do NOT parse-then-re-serialize
    the body (key order and whitespace won't match, and verification fails).
    """
    # Async self-invocation for rollback orchestration
    if event.get("_rollback_async"):
        return _rollback_async(event)

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
