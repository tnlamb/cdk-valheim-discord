"""
DNS updater Lambda.

Triggered by an EventBridge rule on ECS task state transitions to RUNNING.
Steps:
  1. Extract the ENI ID from the task's attachments.
  2. Look up the ENI's public IP via ec2:DescribeNetworkInterfaces.
  3. UPSERT an A record `RECORD_FQDN` → publicIp with TTL `RECORD_TTL` in hosted zone `HOSTED_ZONE_ID`.

No external pip deps — boto3 is included in the Lambda Python 3.12 runtime.
"""
import logging
import os

import boto3

HOSTED_ZONE_ID = os.environ["HOSTED_ZONE_ID"]
RECORD_FQDN = os.environ["RECORD_FQDN"]
RECORD_TTL = int(os.environ["RECORD_TTL"])

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_ec2 = boto3.client("ec2")
_route53 = boto3.client("route53")


def _extract_eni_id(detail: dict) -> str | None:
    """
    ECS task attachments look like:
        "attachments": [
          {"type": "eni", "details": [
            {"name": "networkInterfaceId", "value": "eni-abc123"},
            ...
          ]}
        ]

    AWS ECS Task State Change events use type="eni" (not "ElasticNetworkInterface"
    as the docs sometimes suggest). Accept both to be resilient to any future change.
    """
    eni_types = {"eni", "ElasticNetworkInterface"}
    for attachment in detail.get("attachments", []):
        if attachment.get("type") not in eni_types:
            continue
        for entry in attachment.get("details", []):
            if entry.get("name") == "networkInterfaceId":
                return entry.get("value")
    return None


def _lookup_public_ip(eni_id: str) -> str | None:
    resp = _ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
    enis = resp.get("NetworkInterfaces") or []
    if not enis:
        return None
    association = enis[0].get("Association") or {}
    return association.get("PublicIp")


def _upsert_record(public_ip: str) -> None:
    _route53.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
            "Comment": f"valheim-dns-updater: point {RECORD_FQDN} at task public IP",
            "Changes": [{
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": RECORD_FQDN,
                    "Type": "A",
                    "TTL": RECORD_TTL,
                    "ResourceRecords": [{"Value": public_ip}],
                },
            }],
        },
    )


def handler(event, _context):
    logger.info("Received event: %s", event)
    detail = event.get("detail") or {}
    # Extra safety check — the EventBridge rule already filters on lastStatus=RUNNING,
    # but double-check in case the rule ever widens.
    if detail.get("lastStatus") != "RUNNING":
        logger.info("Skipping: lastStatus=%s", detail.get("lastStatus"))
        return {"skipped": True, "reason": "not running"}

    eni_id = _extract_eni_id(detail)
    if not eni_id:
        logger.warning("No ENI found in task attachments")
        return {"skipped": True, "reason": "no eni"}

    public_ip = _lookup_public_ip(eni_id)
    if not public_ip:
        logger.warning("No public IP on ENI %s (task may not be in a public subnet)", eni_id)
        return {"skipped": True, "reason": "no public ip", "eni": eni_id}

    _upsert_record(public_ip)
    logger.info("UPSERT %s -> %s (ttl=%d)", RECORD_FQDN, public_ip, RECORD_TTL)
    return {"updated": True, "fqdn": RECORD_FQDN, "ip": public_ip}
