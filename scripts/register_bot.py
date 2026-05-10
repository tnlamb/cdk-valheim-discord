#!/usr/bin/env python3
"""
One-time registration of the /vh slash command with Discord.

Prereqs (from .env or the shell):
  DISCORD_APPLICATION_ID   — app ID from Discord dev portal → General Information
  DISCORD_BOT_TOKEN        — bot token from Discord dev portal → Bot → Reset Token
  DISCORD_GUILD_ID         — (optional) your server ID for guild-scoped commands (instant).
                             If omitted, registers globally (can take up to 1h to propagate).

Usage:
  source .env  # or export the vars manually
  python3 scripts/register_bot.py

This registers:
  /vh <action:status|start|stop>
"""
import os
import sys
import urllib.request
import urllib.error
import json


APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID")  # optional

if not APPLICATION_ID or not BOT_TOKEN:
    sys.exit("DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN are required")

if GUILD_ID:
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/guilds/{GUILD_ID}/commands"
    scope = f"guild {GUILD_ID}"
else:
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"
    scope = "global (may take up to 1h to propagate)"

command = {
    "name": "vh",
    "description": "Start, stop, or check the Valheim server",
    # Slash command options are typed — 3 = STRING.
    "options": [
        {
            "name": "action",
            "description": "What to do",
            "type": 3,
            "required": True,
            "choices": [
                {"name": "status", "value": "status"},
                {"name": "start", "value": "start"},
                {"name": "stop", "value": "stop"},
            ],
        }
    ],
}

req = urllib.request.Request(
    url,
    data=json.dumps(command).encode("utf-8"),
    headers={
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json",
        # Discord's API sits behind Cloudflare, which returns HTTP 403 code 1010
        # for default Python-urllib User-Agents. Discord requires a UA in the form
        # "DiscordBot (<URL>, <Version>)" — https://discord.com/developers/docs/reference
        "User-Agent": "DiscordBot (https://github.com/tnlamb/cdk-valheim-discord, 0.1.0)",
    },
    method="POST",
)

print(f"Registering /vh command ({scope})...")
try:
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        print(f"HTTP {resp.status}: {body}")
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
    sys.exit(1)
