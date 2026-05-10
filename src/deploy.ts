/**
 * Deploy entry point for the Valheim Discord server.
 *
 * Usage (from the repo root):
 *   # Bootstrap (once per account/region):
 *   AWS_PROFILE=lamda-personal-aws npx cdk -a "npx ts-node src/deploy.ts" bootstrap
 *
 *   # Synth / deploy:
 *   AWS_PROFILE=lamda-personal-aws DISCORD_APPLICATION_PUBLIC_KEY=<hex> SERVER_PASSWORD=<min5chars> \
 *     npx cdk -a "npx ts-node src/deploy.ts" deploy
 *
 * Required env vars at deploy time:
 *   DISCORD_APPLICATION_PUBLIC_KEY  — hex public key from Discord dev portal → General Information
 *   SERVER_PASSWORD                 — min 5 chars (Valheim requirement)
 *
 * Optional env vars (with defaults):
 *   SERVER_NAME      = "Chips Gaming"
 *   WORLD_NAME       = "ChipsWorld"
 *   DOMAIN_NAME      = "chipsgaming.click"
 *   SUBDOMAIN        = "valheim"
 *   CDK_DEFAULT_REGION (from AWS profile) — should resolve to us-west-2
 */
import {
  App,
  Stack,
  StackProps,
  Duration,
  aws_route53 as route53,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { DiscordValheimController } from './discord-controller';
import { Route53DnsUpdater } from './dns-updater';
import { SaveImport } from './save-import';
import { ValheimWorld } from './valheim';

interface ValheimDiscordStackProps extends StackProps {
  readonly applicationPublicKey: string;
  readonly serverName: string;
  readonly worldName: string;
  readonly serverPassword: string;
  readonly domainName: string;
  readonly subdomain: string;
}

class ValheimDiscordStack extends Stack {
  constructor(scope: Construct, id: string, props: ValheimDiscordStackProps) {
    super(scope, id, props);

    // 1) Valheim server (Fargate + EFS + backup), scaled to 0 by default —
    //    Discord controls start/stop. No cron schedules (Discord is the source of truth).
    const valheim = new ValheimWorld(this, 'ValheimWorld', {
      cpu: 2048,
      memoryLimitMiB: 4096,
      desiredCount: 0,
      environment: {
        SERVER_NAME: props.serverName,
        WORLD_NAME: props.worldName,
        SERVER_PASS: props.serverPassword,
        // lloesche/valheim-server internals:
        BACKUPS: 'false', // we use AWS Backup on EFS instead of in-container backups
        UPDATE_CRON: '', // disable in-container update cron; let lloesche's startup handle it
      },
    });

    // 2) Discord slash command controller.
    new DiscordValheimController(this, 'DiscordController', {
      service: valheim.service,
      applicationPublicKey: props.applicationPublicKey,
      startDesiredCount: 1,
      lambdaTimeout: Duration.seconds(10),
    });

    // 3) Route53 dynamic DNS updater.
    //    The hosted zone must already exist (auto-created on domain registration).
    const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
      domainName: props.domainName,
    });
    new Route53DnsUpdater(this, 'DnsUpdater', {
      cluster: valheim.service.cluster,
      hostedZone,
      recordName: props.subdomain,
      ttl: Duration.seconds(30),
    });

    // 4) Save-file import helper — reusable way to restore a world from S3 -> EFS.
    //    Upload files to the output bucket under worlds_local/, then trigger the
    //    task using the CFN-output run-task command.
    new SaveImport(this, 'SaveImport', {
      cluster: valheim.service.cluster,
      fileSystem: valheim.fileSystem,
    });
  }
}

function requireEnv(name: string): string {
  const val = process.env[name];
  if (!val) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return val;
}

const app = new App();
new ValheimDiscordStack(app, 'ValheimDiscordStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? 'us-west-2',
  },
  applicationPublicKey: requireEnv('DISCORD_APPLICATION_PUBLIC_KEY'),
  serverName: process.env.SERVER_NAME ?? 'Chips Gaming',
  worldName: process.env.WORLD_NAME ?? 'ChipsWorld',
  serverPassword: requireEnv('SERVER_PASSWORD'),
  domainName: process.env.DOMAIN_NAME ?? 'chipsgaming.click',
  subdomain: process.env.SUBDOMAIN ?? 'valheim',
});
app.synth();
