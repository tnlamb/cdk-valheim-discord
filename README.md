# cdk-valheim-discord

Personal fork of [`gotodeploy/cdk-valheim`](https://github.com/gotodeploy/cdk-valheim) that
adds:

- **Discord slash commands** (`/vh status|start|stop`) for on-demand server control
- **Route53 dynamic DNS** so friends connect to a stable hostname (`valheim.chipsgaming.click`)
  even though Fargate gives each task a fresh public IP
- **Save-file import** from S3 → EFS for restoring a world you've played locally

## Architecture

```
Discord "/vh start"                ECS task transitions to RUNNING
        │                                    │
        ▼                                    ▼
API Gateway /discord            EventBridge rule (aws.ecs task state)
        │                                    │
        ▼                                    ▼
Discord Lambda (PyNaCl verify)      DNS updater Lambda
    (ecs:UpdateService)         (ec2:DescribeNetworkInterfaces
        │                        + route53:ChangeResourceRecordSets)
        ▼                                    │
ValheimWorld Fargate service ◄─────mount─────┼──► EFS ◄─── S3 import task
  (lloesche/valheim-server)                  │    (valheim-save-data)   (one-shot Fargate,
        │                                    ▼                           amazon/aws-cli image)
        │                          valheim.chipsgaming.click → publicIp
        ▼                                    (TTL 30s)
EFS save data  +  AWS Backup (hourly, 3d retention)
```

## Cost at rest vs running

- **Idle** (`desiredCount=0`): EFS + Backup storage + Route53 hosted zone ≈ **$0.60/mo**
- **Running**: ~$0.10/hr at 2vCPU/4GB Fargate + a few GB EFS transfer

## Prerequisites

1. **AWS account** with Route53 hosted zone for your domain (e.g. `chipsgaming.click`)
2. **Node 18+** (Node 22 recommended) and **Docker** installed on the dev machine
   (Docker is used to bundle the Python Lambda that verifies Discord signatures)
3. **AWS CLI profile** with Admin access to your account (see below)

### Set up the AWS profile

```bash
# One-time per dev machine:
aws configure --profile lamda-personal-aws
#   AWS Access Key ID:     <paste>
#   AWS Secret Access Key: <paste>
#   Default region:        us-west-2
#   Default output format: json
```

## One-time Discord setup

1. Go to <https://discord.com/developers/applications> → **New Application**
2. Under **General Information**, note:
   - **Application ID** → `DISCORD_APPLICATION_ID`
   - **Public Key** → `DISCORD_APPLICATION_PUBLIC_KEY`
3. Under **Bot** → **Reset Token** → copy the token → `DISCORD_BOT_TOKEN`
   - Turn off **Public Bot** (you don't want anyone adding it to random servers)
4. Under **OAuth2** → **URL Generator** → check **bot** and **applications.commands** →
   copy the URL at the bottom → open it → add the bot to your Discord server
5. Get your Discord server ID: right-click your server → Server Settings → Widget →
   **Server ID** → `DISCORD_GUILD_ID` (optional — enables instant command propagation
   instead of the ~1 hour global wait)

## Deploy

```bash
# 1) Copy the env template and fill in Discord + Valheim values
cp .env.example .env
$EDITOR .env
source .env

# 2) One-time bootstrap of the account for CDK
npx cdk -a "npx ts-node src/deploy.ts" bootstrap --profile lamda-personal-aws

# 3) Synth to verify
npx cdk -a "npx ts-node src/deploy.ts" synth --profile lamda-personal-aws

# 4) Deploy the stack (~15 min — EFS mount targets take a while)
npx cdk -a "npx ts-node src/deploy.ts" deploy --profile lamda-personal-aws

# After deploy, the CDK output prints:
#   DiscordControllerDiscordInteractionsEndpointUrl = https://abc.execute-api.us-west-2.amazonaws.com/prod/discord
#   DnsUpdaterServerDnsName = valheim.chipsgaming.click
```

## Finish Discord hookup

5. **Register the slash command** (reads from `.env`):
   ```bash
   python3 scripts/register_bot.py
   ```
6. Paste the `DiscordInteractionsEndpointUrl` from the CDK output into the Discord dev
   portal → **General Information** → **Interactions Endpoint URL** → **Save**.
   Discord pings the endpoint with a PING (type=1) during save; the Lambda must respond
   with PONG or the save will fail. If it fails, check CloudWatch logs for the Lambda.

## Using it

In any channel on your Discord server where the bot is installed:

- `/vh status` — show current desired/running/pending task count
- `/vh start`  — scale desiredCount to 1 (takes ~5 min to be playable — Fargate task placement + image pull + Valheim's steamcmd download + world load)
- `/vh stop`   — scale desiredCount to 0

Once the task reaches RUNNING, the DNS updater Lambda fires and upserts
`valheim.chipsgaming.click` → task's public IP. Friends add the server in the Valheim
client's **Join Game** → **Join IP** with `valheim.chipsgaming.click:2456` and the
server password you set.

## Importing an existing local save

The stack creates an `S3 + one-shot Fargate` helper for restoring a world you've been
playing locally. The CDK outputs include:

- `SaveImportImportBucketName` — S3 bucket to upload `<World>.db` / `<World>.fwl` to
- `SaveImportImportRunCommand` — ready-to-paste `aws ecs run-task` command that mounts
  the same EFS and runs `aws s3 sync` from the bucket into `/config/worlds_local/`
- `SaveImportImportUploadCommand` — example upload command with the right S3 URI

### Flow

1. **Set `WORLD_NAME`** in `.env` to match your save's basename (e.g. `MyWorld` if your
   files are `MyWorld.db` / `MyWorld.fwl`) and redeploy, OR rename the files to match
   whatever `WORLD_NAME` currently is before uploading.
2. **Upload files** (run locally — paths are OS-specific):
   ```bash
   # macOS:
   VALHEIM_DIR="$HOME/Library/Application Support/IronGate/Valheim/worlds_local"
   # Windows (WSL):
   # VALHEIM_DIR="/mnt/c/Users/$USER/AppData/LocalLow/IronGate/Valheim/worlds_local"
   # Linux:
   # VALHEIM_DIR="$HOME/.config/unity3d/IronGate/Valheim/worlds_local"

   aws s3 cp "$VALHEIM_DIR/MyWorld.db"  s3://$IMPORT_BUCKET/worlds_local/ --profile lamda-personal-aws
   aws s3 cp "$VALHEIM_DIR/MyWorld.fwl" s3://$IMPORT_BUCKET/worlds_local/ --profile lamda-personal-aws
   ```
3. **Trigger the copy** by pasting the `SaveImportImportRunCommand` output from `cdk deploy`
   (takes ~30s). Verify by tailing the task's CloudWatch log group — the container lists
   the files it wrote to EFS before exiting.
4. `/vh start` in Discord — the server boots with your imported world.

The import bucket has a 30-day lifecycle expiration so uploads don't linger.

## Troubleshooting

- **Discord "invalid interactions endpoint url"**: The Lambda's signature verification is
  failing. Check the CloudWatch log group for the handler — common causes are
  `DISCORD_APPLICATION_PUBLIC_KEY` mismatch or the API Gateway VTL template not
  forwarding the `X-Signature-*` headers (the CDK construct sets this up; re-deploy
  if you see missing headers in the event).
- **`/vh status` shows running=1 but can't connect**: DNS may not have updated yet.
  Check `aws route53 list-resource-record-sets --hosted-zone-id <id> --profile lamda-personal-aws`
  — the `valheim.chipsgaming.click` A record should point at the task's current public IP.
  The DNS updater Lambda's logs show each UPSERT.
- **Task keeps restarting**: Check the ECS service's task logs in CloudWatch — likely
  an EFS permission issue or the lloesche/valheim-server container is OOMing on boot.
  Bump `memoryLimitMiB` in `src/deploy.ts` if so.

## Publishing this construct library

This fork has `releaseToNpm` disabled. If you ever want to publish, edit `.projenrc.js`
and run `npx projen`.

## Credits

- Base construct: [gotodeploy/cdk-valheim](https://github.com/gotodeploy/cdk-valheim)
- Discord integration pattern: [briancaffey/valheim-cdk-discord-interactions](https://gitlab.com/briancaffey/valheim-cdk-discord-interactions)
  (CDK v1 original, modernized here to CDK v2 + Python 3.12)
- Container image: [lloesche/valheim-server](https://github.com/lloesche/valheim-server-docker)
