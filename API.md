# API Reference <a name="API Reference" id="api-reference"></a>

## Constructs <a name="Constructs" id="Constructs"></a>

### DiscordValheimController <a name="DiscordValheimController" id="cdk-valheim-discord.DiscordValheimController"></a>

Lambda + API Gateway that handles Discord Interactions (slash commands) and scales the Valheim Fargate service between desiredCount 0 and 1.

Registers a `/vh {status|start|stop}` slash command flow. Use
`scripts/register_bot.py` to register the command with Discord the first time.

Discord POSTs to `<apiEndpointUrl>/discord`. The Lambda:
  1. Verifies the Ed25519 signature using the application public key.
  2. Responds to PING (type=1) with PONG for Discord's endpoint verification.
  3. Dispatches slash command sub-options to `ecs:DescribeServices` / `ecs:UpdateService`.

IAM is scoped to the specific service ARN (no `AmazonECS_FullAccess`).

#### Initializers <a name="Initializers" id="cdk-valheim-discord.DiscordValheimController.Initializer"></a>

```typescript
import { DiscordValheimController } from 'cdk-valheim-discord'

new DiscordValheimController(scope: Construct, id: string, props: DiscordValheimControllerProps)
```

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.Initializer.parameter.scope">scope</a></code> | <code>constructs.Construct</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.Initializer.parameter.id">id</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.Initializer.parameter.props">props</a></code> | <code><a href="#cdk-valheim-discord.DiscordValheimControllerProps">DiscordValheimControllerProps</a></code> | *No description.* |

---

##### `scope`<sup>Required</sup> <a name="scope" id="cdk-valheim-discord.DiscordValheimController.Initializer.parameter.scope"></a>

- *Type:* constructs.Construct

---

##### `id`<sup>Required</sup> <a name="id" id="cdk-valheim-discord.DiscordValheimController.Initializer.parameter.id"></a>

- *Type:* string

---

##### `props`<sup>Required</sup> <a name="props" id="cdk-valheim-discord.DiscordValheimController.Initializer.parameter.props"></a>

- *Type:* <a href="#cdk-valheim-discord.DiscordValheimControllerProps">DiscordValheimControllerProps</a>

---

#### Methods <a name="Methods" id="Methods"></a>

| **Name** | **Description** |
| --- | --- |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.toString">toString</a></code> | Returns a string representation of this construct. |

---

##### `toString` <a name="toString" id="cdk-valheim-discord.DiscordValheimController.toString"></a>

```typescript
public toString(): string
```

Returns a string representation of this construct.


#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.property.api">api</a></code> | <code>aws-cdk-lib.aws_apigateway.RestApi</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.property.discordEndpointUrl">discordEndpointUrl</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.DiscordValheimController.property.handler">handler</a></code> | <code>aws-cdk-lib.aws_lambda.Function</code> | *No description.* |

---

##### `api`<sup>Required</sup> <a name="api" id="cdk-valheim-discord.DiscordValheimController.property.api"></a>

```typescript
public readonly api: RestApi;
```

- *Type:* aws-cdk-lib.aws_apigateway.RestApi

---

##### `discordEndpointUrl`<sup>Required</sup> <a name="discordEndpointUrl" id="cdk-valheim-discord.DiscordValheimController.property.discordEndpointUrl"></a>

```typescript
public readonly discordEndpointUrl: string;
```

- *Type:* string

---

##### `handler`<sup>Required</sup> <a name="handler" id="cdk-valheim-discord.DiscordValheimController.property.handler"></a>

```typescript
public readonly handler: Function;
```

- *Type:* aws-cdk-lib.aws_lambda.Function

---


### Route53DnsUpdater <a name="Route53DnsUpdater" id="cdk-valheim-discord.Route53DnsUpdater"></a>

Watches ECS task state changes on the given cluster;

when a task transitions to RUNNING,
a Lambda looks up the task's ENI, extracts the auto-assigned public IP, and UPSERTs
a Route53 A record pointing `<recordName>.<zone>` at that IP.

Motivation: Fargate tasks get a fresh public IP on every restart. Friends connect to a
stable DNS name instead of chasing IPs.

#### Initializers <a name="Initializers" id="cdk-valheim-discord.Route53DnsUpdater.Initializer"></a>

```typescript
import { Route53DnsUpdater } from 'cdk-valheim-discord'

new Route53DnsUpdater(scope: Construct, id: string, props: Route53DnsUpdaterProps)
```

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.scope">scope</a></code> | <code>constructs.Construct</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.id">id</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.props">props</a></code> | <code><a href="#cdk-valheim-discord.Route53DnsUpdaterProps">Route53DnsUpdaterProps</a></code> | *No description.* |

---

##### `scope`<sup>Required</sup> <a name="scope" id="cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.scope"></a>

- *Type:* constructs.Construct

---

##### `id`<sup>Required</sup> <a name="id" id="cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.id"></a>

- *Type:* string

---

##### `props`<sup>Required</sup> <a name="props" id="cdk-valheim-discord.Route53DnsUpdater.Initializer.parameter.props"></a>

- *Type:* <a href="#cdk-valheim-discord.Route53DnsUpdaterProps">Route53DnsUpdaterProps</a>

---

#### Methods <a name="Methods" id="Methods"></a>

| **Name** | **Description** |
| --- | --- |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.toString">toString</a></code> | Returns a string representation of this construct. |

---

##### `toString` <a name="toString" id="cdk-valheim-discord.Route53DnsUpdater.toString"></a>

```typescript
public toString(): string
```

Returns a string representation of this construct.


#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.property.handler">handler</a></code> | <code>aws-cdk-lib.aws_lambda.Function</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.property.recordFqdn">recordFqdn</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdater.property.rule">rule</a></code> | <code>aws-cdk-lib.aws_events.Rule</code> | *No description.* |

---

##### `handler`<sup>Required</sup> <a name="handler" id="cdk-valheim-discord.Route53DnsUpdater.property.handler"></a>

```typescript
public readonly handler: Function;
```

- *Type:* aws-cdk-lib.aws_lambda.Function

---

##### `recordFqdn`<sup>Required</sup> <a name="recordFqdn" id="cdk-valheim-discord.Route53DnsUpdater.property.recordFqdn"></a>

```typescript
public readonly recordFqdn: string;
```

- *Type:* string

---

##### `rule`<sup>Required</sup> <a name="rule" id="cdk-valheim-discord.Route53DnsUpdater.property.rule"></a>

```typescript
public readonly rule: Rule;
```

- *Type:* aws-cdk-lib.aws_events.Rule

---


### SaveImport <a name="SaveImport" id="cdk-valheim-discord.SaveImport"></a>

SaveImport provides a way to copy Valheim world files from S3 into EFS.

Creates:
   - An S3 bucket for user uploads (with 7-day lifecycle on old versions)
   - A one-shot Fargate task using `amazon/aws-cli` that mounts the same EFS
     and `aws s3 sync`s objects from the bucket into /config/worlds_local/
   - A CFN output with the exact `aws ecs run-task` command to trigger the copy

Typical usage flow:
   1. `aws s3 cp MyWorld.db s3://<bucket>/worlds_local/`
   2. `aws s3 cp MyWorld.fwl s3://<bucket>/worlds_local/`
   3. Paste the `aws ecs run-task ...` command from the stack output
   4. `/vh start` in Discord — server boots with the imported world

#### Initializers <a name="Initializers" id="cdk-valheim-discord.SaveImport.Initializer"></a>

```typescript
import { SaveImport } from 'cdk-valheim-discord'

new SaveImport(scope: Construct, id: string, props: SaveImportProps)
```

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.SaveImport.Initializer.parameter.scope">scope</a></code> | <code>constructs.Construct</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.SaveImport.Initializer.parameter.id">id</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.SaveImport.Initializer.parameter.props">props</a></code> | <code><a href="#cdk-valheim-discord.SaveImportProps">SaveImportProps</a></code> | *No description.* |

---

##### `scope`<sup>Required</sup> <a name="scope" id="cdk-valheim-discord.SaveImport.Initializer.parameter.scope"></a>

- *Type:* constructs.Construct

---

##### `id`<sup>Required</sup> <a name="id" id="cdk-valheim-discord.SaveImport.Initializer.parameter.id"></a>

- *Type:* string

---

##### `props`<sup>Required</sup> <a name="props" id="cdk-valheim-discord.SaveImport.Initializer.parameter.props"></a>

- *Type:* <a href="#cdk-valheim-discord.SaveImportProps">SaveImportProps</a>

---

#### Methods <a name="Methods" id="Methods"></a>

| **Name** | **Description** |
| --- | --- |
| <code><a href="#cdk-valheim-discord.SaveImport.toString">toString</a></code> | Returns a string representation of this construct. |

---

##### `toString` <a name="toString" id="cdk-valheim-discord.SaveImport.toString"></a>

```typescript
public toString(): string
```

Returns a string representation of this construct.


#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.SaveImport.property.bucket">bucket</a></code> | <code>aws-cdk-lib.aws_s3.Bucket</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.SaveImport.property.taskDefinition">taskDefinition</a></code> | <code>aws-cdk-lib.aws_ecs.FargateTaskDefinition</code> | *No description.* |

---

##### `bucket`<sup>Required</sup> <a name="bucket" id="cdk-valheim-discord.SaveImport.property.bucket"></a>

```typescript
public readonly bucket: Bucket;
```

- *Type:* aws-cdk-lib.aws_s3.Bucket

---

##### `taskDefinition`<sup>Required</sup> <a name="taskDefinition" id="cdk-valheim-discord.SaveImport.property.taskDefinition"></a>

```typescript
public readonly taskDefinition: FargateTaskDefinition;
```

- *Type:* aws-cdk-lib.aws_ecs.FargateTaskDefinition

---


### ValheimWorld <a name="ValheimWorld" id="cdk-valheim-discord.ValheimWorld"></a>

#### Initializers <a name="Initializers" id="cdk-valheim-discord.ValheimWorld.Initializer"></a>

```typescript
import { ValheimWorld } from 'cdk-valheim-discord'

new ValheimWorld(scope: Construct, id: string, props?: ValheimWorldProps)
```

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorld.Initializer.parameter.scope">scope</a></code> | <code>constructs.Construct</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.ValheimWorld.Initializer.parameter.id">id</a></code> | <code>string</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.ValheimWorld.Initializer.parameter.props">props</a></code> | <code><a href="#cdk-valheim-discord.ValheimWorldProps">ValheimWorldProps</a></code> | *No description.* |

---

##### `scope`<sup>Required</sup> <a name="scope" id="cdk-valheim-discord.ValheimWorld.Initializer.parameter.scope"></a>

- *Type:* constructs.Construct

---

##### `id`<sup>Required</sup> <a name="id" id="cdk-valheim-discord.ValheimWorld.Initializer.parameter.id"></a>

- *Type:* string

---

##### `props`<sup>Optional</sup> <a name="props" id="cdk-valheim-discord.ValheimWorld.Initializer.parameter.props"></a>

- *Type:* <a href="#cdk-valheim-discord.ValheimWorldProps">ValheimWorldProps</a>

---

#### Methods <a name="Methods" id="Methods"></a>

| **Name** | **Description** |
| --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorld.toString">toString</a></code> | Returns a string representation of this construct. |

---

##### `toString` <a name="toString" id="cdk-valheim-discord.ValheimWorld.toString"></a>

```typescript
public toString(): string
```

Returns a string representation of this construct.


#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorld.property.backupPlan">backupPlan</a></code> | <code>aws-cdk-lib.aws_backup.BackupPlan</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.ValheimWorld.property.fileSystem">fileSystem</a></code> | <code>aws-cdk-lib.aws_efs.FileSystem</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.ValheimWorld.property.service">service</a></code> | <code>aws-cdk-lib.aws_ecs.FargateService</code> | *No description.* |
| <code><a href="#cdk-valheim-discord.ValheimWorld.property.schedules">schedules</a></code> | <code><a href="#cdk-valheim-discord.ValheimWorldScalingSchedule">ValheimWorldScalingSchedule</a>[]</code> | *No description.* |

---

##### `backupPlan`<sup>Required</sup> <a name="backupPlan" id="cdk-valheim-discord.ValheimWorld.property.backupPlan"></a>

```typescript
public readonly backupPlan: BackupPlan;
```

- *Type:* aws-cdk-lib.aws_backup.BackupPlan

---

##### `fileSystem`<sup>Required</sup> <a name="fileSystem" id="cdk-valheim-discord.ValheimWorld.property.fileSystem"></a>

```typescript
public readonly fileSystem: FileSystem;
```

- *Type:* aws-cdk-lib.aws_efs.FileSystem

---

##### `service`<sup>Required</sup> <a name="service" id="cdk-valheim-discord.ValheimWorld.property.service"></a>

```typescript
public readonly service: FargateService;
```

- *Type:* aws-cdk-lib.aws_ecs.FargateService

---

##### `schedules`<sup>Optional</sup> <a name="schedules" id="cdk-valheim-discord.ValheimWorld.property.schedules"></a>

```typescript
public readonly schedules: ValheimWorldScalingSchedule[];
```

- *Type:* <a href="#cdk-valheim-discord.ValheimWorldScalingSchedule">ValheimWorldScalingSchedule</a>[]

---


## Structs <a name="Structs" id="Structs"></a>

### DiscordValheimControllerProps <a name="DiscordValheimControllerProps" id="cdk-valheim-discord.DiscordValheimControllerProps"></a>

Properties for {@link DiscordValheimController}.

#### Initializer <a name="Initializer" id="cdk-valheim-discord.DiscordValheimControllerProps.Initializer"></a>

```typescript
import { DiscordValheimControllerProps } from 'cdk-valheim-discord'

const discordValheimControllerProps: DiscordValheimControllerProps = { ... }
```

#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.DiscordValheimControllerProps.property.applicationPublicKey">applicationPublicKey</a></code> | <code>string</code> | The Discord application public key used to verify signed interaction requests (Ed25519). |
| <code><a href="#cdk-valheim-discord.DiscordValheimControllerProps.property.service">service</a></code> | <code>aws-cdk-lib.aws_ecs.FargateService</code> | The Valheim Fargate service to start/stop via Discord slash commands. |
| <code><a href="#cdk-valheim-discord.DiscordValheimControllerProps.property.lambdaTimeout">lambdaTimeout</a></code> | <code>aws-cdk-lib.Duration</code> | Lambda timeout. |
| <code><a href="#cdk-valheim-discord.DiscordValheimControllerProps.property.startDesiredCount">startDesiredCount</a></code> | <code>number</code> | Desired Fargate task count when a user runs `/vh start`. |

---

##### `applicationPublicKey`<sup>Required</sup> <a name="applicationPublicKey" id="cdk-valheim-discord.DiscordValheimControllerProps.property.applicationPublicKey"></a>

```typescript
public readonly applicationPublicKey: string;
```

- *Type:* string

The Discord application public key used to verify signed interaction requests (Ed25519).

This value is public (not a secret) — it is the counterpart of Discord's private signing key.
Passed as a plain Lambda environment variable.

---

##### `service`<sup>Required</sup> <a name="service" id="cdk-valheim-discord.DiscordValheimControllerProps.property.service"></a>

```typescript
public readonly service: FargateService;
```

- *Type:* aws-cdk-lib.aws_ecs.FargateService

The Valheim Fargate service to start/stop via Discord slash commands.

---

##### `lambdaTimeout`<sup>Optional</sup> <a name="lambdaTimeout" id="cdk-valheim-discord.DiscordValheimControllerProps.property.lambdaTimeout"></a>

```typescript
public readonly lambdaTimeout: Duration;
```

- *Type:* aws-cdk-lib.Duration
- *Default:* Duration.seconds(10)

Lambda timeout.

Discord Interactions require a response within 3 seconds,
but the Lambda can deliver deferred responses — for our ECS API calls 10s is plenty.

---

##### `startDesiredCount`<sup>Optional</sup> <a name="startDesiredCount" id="cdk-valheim-discord.DiscordValheimControllerProps.property.startDesiredCount"></a>

```typescript
public readonly startDesiredCount: number;
```

- *Type:* number
- *Default:* 1

Desired Fargate task count when a user runs `/vh start`.

---

### Route53DnsUpdaterProps <a name="Route53DnsUpdaterProps" id="cdk-valheim-discord.Route53DnsUpdaterProps"></a>

Properties for {@link Route53DnsUpdater}.

#### Initializer <a name="Initializer" id="cdk-valheim-discord.Route53DnsUpdaterProps.Initializer"></a>

```typescript
import { Route53DnsUpdaterProps } from 'cdk-valheim-discord'

const route53DnsUpdaterProps: Route53DnsUpdaterProps = { ... }
```

#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdaterProps.property.cluster">cluster</a></code> | <code>aws-cdk-lib.aws_ecs.ICluster</code> | The ECS cluster whose task state changes should trigger DNS updates. |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdaterProps.property.hostedZone">hostedZone</a></code> | <code>aws-cdk-lib.aws_route53.IHostedZone</code> | The Route53 hosted zone to update (e.g. chipsgaming.click). |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdaterProps.property.recordName">recordName</a></code> | <code>string</code> | The record name to upsert. Combined with hostedZone.zoneName. |
| <code><a href="#cdk-valheim-discord.Route53DnsUpdaterProps.property.ttl">ttl</a></code> | <code>aws-cdk-lib.Duration</code> | TTL for the A record. |

---

##### `cluster`<sup>Required</sup> <a name="cluster" id="cdk-valheim-discord.Route53DnsUpdaterProps.property.cluster"></a>

```typescript
public readonly cluster: ICluster;
```

- *Type:* aws-cdk-lib.aws_ecs.ICluster

The ECS cluster whose task state changes should trigger DNS updates.

---

##### `hostedZone`<sup>Required</sup> <a name="hostedZone" id="cdk-valheim-discord.Route53DnsUpdaterProps.property.hostedZone"></a>

```typescript
public readonly hostedZone: IHostedZone;
```

- *Type:* aws-cdk-lib.aws_route53.IHostedZone

The Route53 hosted zone to update (e.g. chipsgaming.click).

---

##### `recordName`<sup>Optional</sup> <a name="recordName" id="cdk-valheim-discord.Route53DnsUpdaterProps.property.recordName"></a>

```typescript
public readonly recordName: string;
```

- *Type:* string
- *Default:* 'valheim'

The record name to upsert. Combined with hostedZone.zoneName.

Example: recordName="valheim" + zone "chipsgaming.click" => valheim.chipsgaming.click

---

##### `ttl`<sup>Optional</sup> <a name="ttl" id="cdk-valheim-discord.Route53DnsUpdaterProps.property.ttl"></a>

```typescript
public readonly ttl: Duration;
```

- *Type:* aws-cdk-lib.Duration
- *Default:* Duration.seconds(30)

TTL for the A record.

Kept short so friends reconnect fast when the task restarts.

---

### SaveImportProps <a name="SaveImportProps" id="cdk-valheim-discord.SaveImportProps"></a>

#### Initializer <a name="Initializer" id="cdk-valheim-discord.SaveImportProps.Initializer"></a>

```typescript
import { SaveImportProps } from 'cdk-valheim-discord'

const saveImportProps: SaveImportProps = { ... }
```

#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.SaveImportProps.property.cluster">cluster</a></code> | <code>aws-cdk-lib.aws_ecs.ICluster</code> | ECS cluster (reused from ValheimWorld). |
| <code><a href="#cdk-valheim-discord.SaveImportProps.property.fileSystem">fileSystem</a></code> | <code>aws-cdk-lib.aws_efs.FileSystem</code> | EFS filesystem that holds the Valheim save data (reused from ValheimWorld). |
| <code><a href="#cdk-valheim-discord.SaveImportProps.property.containerPath">containerPath</a></code> | <code>string</code> | Path inside the container where EFS is mounted. |
| <code><a href="#cdk-valheim-discord.SaveImportProps.property.s3Prefix">s3Prefix</a></code> | <code>string</code> | S3 prefix within the import bucket to sync from. |

---

##### `cluster`<sup>Required</sup> <a name="cluster" id="cdk-valheim-discord.SaveImportProps.property.cluster"></a>

```typescript
public readonly cluster: ICluster;
```

- *Type:* aws-cdk-lib.aws_ecs.ICluster

ECS cluster (reused from ValheimWorld).

---

##### `fileSystem`<sup>Required</sup> <a name="fileSystem" id="cdk-valheim-discord.SaveImportProps.property.fileSystem"></a>

```typescript
public readonly fileSystem: FileSystem;
```

- *Type:* aws-cdk-lib.aws_efs.FileSystem

EFS filesystem that holds the Valheim save data (reused from ValheimWorld).

---

##### `containerPath`<sup>Optional</sup> <a name="containerPath" id="cdk-valheim-discord.SaveImportProps.property.containerPath"></a>

```typescript
public readonly containerPath: string;
```

- *Type:* string
- *Default:* '/config'

Path inside the container where EFS is mounted.

---

##### `s3Prefix`<sup>Optional</sup> <a name="s3Prefix" id="cdk-valheim-discord.SaveImportProps.property.s3Prefix"></a>

```typescript
public readonly s3Prefix: string;
```

- *Type:* string
- *Default:* 'worlds_local/'

S3 prefix within the import bucket to sync from.

---

### ValheimWorldProps <a name="ValheimWorldProps" id="cdk-valheim-discord.ValheimWorldProps"></a>

#### Initializer <a name="Initializer" id="cdk-valheim-discord.ValheimWorldProps.Initializer"></a>

```typescript
import { ValheimWorldProps } from 'cdk-valheim-discord'

const valheimWorldProps: ValheimWorldProps = { ... }
```

#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.backupPlan">backupPlan</a></code> | <code>aws-cdk-lib.aws_backup.BackupPlan</code> | AWS Backup plan for EFS. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.containerPath">containerPath</a></code> | <code>string</code> | The path on the container to mount the host volume at. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.cpu">cpu</a></code> | <code>number</code> | The number of cpu units used by the task. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.desiredCount">desiredCount</a></code> | <code>number</code> | Desired count of Fargate container. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.environment">environment</a></code> | <code>{[ key: string ]: string}</code> | The environment variables to pass to the container. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.fileSystem">fileSystem</a></code> | <code>aws-cdk-lib.aws_efs.FileSystem</code> | Persistent storage for save data. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.image">image</a></code> | <code>aws-cdk-lib.aws_ecs.ContainerImage</code> | The image used to start a container. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.logGroup">logGroup</a></code> | <code>aws-cdk-lib.aws_ecs.LogDriver</code> | Valheim Server log Group. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.memoryLimitMiB">memoryLimitMiB</a></code> | <code>number</code> | The amount (in MiB) of memory used by the task. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.schedules">schedules</a></code> | <code><a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps">ValheimWorldScalingScheduleProps</a>[]</code> | Running schedules. |
| <code><a href="#cdk-valheim-discord.ValheimWorldProps.property.vpc">vpc</a></code> | <code>aws-cdk-lib.aws_ec2.IVpc</code> | The VPC where your ECS instances will be running or your ENIs will be deployed. |

---

##### `backupPlan`<sup>Optional</sup> <a name="backupPlan" id="cdk-valheim-discord.ValheimWorldProps.property.backupPlan"></a>

```typescript
public readonly backupPlan: BackupPlan;
```

- *Type:* aws-cdk-lib.aws_backup.BackupPlan
- *Default:* Hourly backup with 3 days retension.

AWS Backup plan for EFS.

---

##### `containerPath`<sup>Optional</sup> <a name="containerPath" id="cdk-valheim-discord.ValheimWorldProps.property.containerPath"></a>

```typescript
public readonly containerPath: string;
```

- *Type:* string
- *Default:* /config/

The path on the container to mount the host volume at.

---

##### `cpu`<sup>Optional</sup> <a name="cpu" id="cdk-valheim-discord.ValheimWorldProps.property.cpu"></a>

```typescript
public readonly cpu: number;
```

- *Type:* number
- *Default:* 1024

The number of cpu units used by the task.

For tasks using the Fargate launch type,
this field is required and you must use one of the following values,
which determines your range of valid values for the memory parameter:

256 (.25 vCPU) - Available memory values: 512 (0.5 GB), 1024 (1 GB), 2048 (2 GB)

512 (.5 vCPU) - Available memory values: 1024 (1 GB), 2048 (2 GB), 3072 (3 GB), 4096 (4 GB)

1024 (1 vCPU) - Available memory values: 2048 (2 GB), 3072 (3 GB), 4096 (4 GB), 5120 (5 GB), 6144 (6 GB), 7168 (7 GB), 8192 (8 GB)

2048 (2 vCPU) - Available memory values: Between 4096 (4 GB) and 16384 (16 GB) in increments of 1024 (1 GB)

4096 (4 vCPU) - Available memory values: Between 8192 (8 GB) and 30720 (30 GB) in increments of 1024 (1 GB)

---

##### `desiredCount`<sup>Optional</sup> <a name="desiredCount" id="cdk-valheim-discord.ValheimWorldProps.property.desiredCount"></a>

```typescript
public readonly desiredCount: number;
```

- *Type:* number
- *Default:* 1

Desired count of Fargate container.

Set 0 for maintenance.

---

##### `environment`<sup>Optional</sup> <a name="environment" id="cdk-valheim-discord.ValheimWorldProps.property.environment"></a>

```typescript
public readonly environment: {[ key: string ]: string};
```

- *Type:* {[ key: string ]: string}
- *Default:* No environment variables.

The environment variables to pass to the container.

---

##### `fileSystem`<sup>Optional</sup> <a name="fileSystem" id="cdk-valheim-discord.ValheimWorldProps.property.fileSystem"></a>

```typescript
public readonly fileSystem: FileSystem;
```

- *Type:* aws-cdk-lib.aws_efs.FileSystem
- *Default:* Amazon EFS for default persistent storage.

Persistent storage for save data.

---

##### `image`<sup>Optional</sup> <a name="image" id="cdk-valheim-discord.ValheimWorldProps.property.image"></a>

```typescript
public readonly image: ContainerImage;
```

- *Type:* aws-cdk-lib.aws_ecs.ContainerImage
- *Default:* [lloesche/valheim-server](https://hub.docker.com/r/lloesche/valheim-server)

The image used to start a container.

This string is passed directly to the Docker daemon.
Images in the Docker Hub registry are available by default.
Other repositories are specified with either repository-url/image:tag or repository-url/image@digest.

---

##### `logGroup`<sup>Optional</sup> <a name="logGroup" id="cdk-valheim-discord.ValheimWorldProps.property.logGroup"></a>

```typescript
public readonly logGroup: LogDriver;
```

- *Type:* aws-cdk-lib.aws_ecs.LogDriver
- *Default:* Create the new AWS Cloudwatch Log Group for Valheim Server.

Valheim Server log Group.

---

##### `memoryLimitMiB`<sup>Optional</sup> <a name="memoryLimitMiB" id="cdk-valheim-discord.ValheimWorldProps.property.memoryLimitMiB"></a>

```typescript
public readonly memoryLimitMiB: number;
```

- *Type:* number
- *Default:* 2048

The amount (in MiB) of memory used by the task.

For tasks using the Fargate launch type,
this field is required and you must use one of the following values, which determines your range of valid values for the cpu parameter:

512 (0.5 GB), 1024 (1 GB), 2048 (2 GB) - Available cpu values: 256 (.25 vCPU)

1024 (1 GB), 2048 (2 GB), 3072 (3 GB), 4096 (4 GB) - Available cpu values: 512 (.5 vCPU)

2048 (2 GB), 3072 (3 GB), 4096 (4 GB), 5120 (5 GB), 6144 (6 GB), 7168 (7 GB), 8192 (8 GB) - Available cpu values: 1024 (1 vCPU)

Between 4096 (4 GB) and 16384 (16 GB) in increments of 1024 (1 GB) - Available cpu values: 2048 (2 vCPU)

Between 8192 (8 GB) and 30720 (30 GB) in increments of 1024 (1 GB) - Available cpu values: 4096 (4 vCPU)

---

##### `schedules`<sup>Optional</sup> <a name="schedules" id="cdk-valheim-discord.ValheimWorldProps.property.schedules"></a>

```typescript
public readonly schedules: ValheimWorldScalingScheduleProps[];
```

- *Type:* <a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps">ValheimWorldScalingScheduleProps</a>[]
- *Default:* Always running.

Running schedules.

---

##### `vpc`<sup>Optional</sup> <a name="vpc" id="cdk-valheim-discord.ValheimWorldProps.property.vpc"></a>

```typescript
public readonly vpc: IVpc;
```

- *Type:* aws-cdk-lib.aws_ec2.IVpc
- *Default:* creates a new VPC with two AZs

The VPC where your ECS instances will be running or your ENIs will be deployed.

---

### ValheimWorldScalingScheduleProps <a name="ValheimWorldScalingScheduleProps" id="cdk-valheim-discord.ValheimWorldScalingScheduleProps"></a>

Options for ValheimWorldScalingSchedule.

#### Initializer <a name="Initializer" id="cdk-valheim-discord.ValheimWorldScalingScheduleProps.Initializer"></a>

```typescript
import { ValheimWorldScalingScheduleProps } from 'cdk-valheim-discord'

const valheimWorldScalingScheduleProps: ValheimWorldScalingScheduleProps = { ... }
```

#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps.property.start">start</a></code> | <code>aws-cdk-lib.aws_applicationautoscaling.CronOptions</code> | Options to configure a cron expression for server for server launching schedule. |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps.property.stop">stop</a></code> | <code>aws-cdk-lib.aws_applicationautoscaling.CronOptions</code> | Options to configure a cron expression for server zero-scale schedule. |

---

##### `start`<sup>Required</sup> <a name="start" id="cdk-valheim-discord.ValheimWorldScalingScheduleProps.property.start"></a>

```typescript
public readonly start: CronOptions;
```

- *Type:* aws-cdk-lib.aws_applicationautoscaling.CronOptions

Options to configure a cron expression for server for server launching schedule.

All fields are strings so you can use complex expressions. Absence of
a field implies '*' or '?', whichever one is appropriate. Only comma
separated numbers and hypens are allowed.

---

##### `stop`<sup>Required</sup> <a name="stop" id="cdk-valheim-discord.ValheimWorldScalingScheduleProps.property.stop"></a>

```typescript
public readonly stop: CronOptions;
```

- *Type:* aws-cdk-lib.aws_applicationautoscaling.CronOptions

Options to configure a cron expression for server zero-scale schedule.

All fields are strings so you can use complex expressions. Absence of
a field implies '*' or '?', whichever one is appropriate. Only comma
separated numbers and hypens are allowed.

---

## Classes <a name="Classes" id="Classes"></a>

### ValheimWorldScalingSchedule <a name="ValheimWorldScalingSchedule" id="cdk-valheim-discord.ValheimWorldScalingSchedule"></a>

Represents the schedule to determine when the server starts or terminates.

#### Initializers <a name="Initializers" id="cdk-valheim-discord.ValheimWorldScalingSchedule.Initializer"></a>

```typescript
import { ValheimWorldScalingSchedule } from 'cdk-valheim-discord'

new ValheimWorldScalingSchedule(schedule: ValheimWorldScalingScheduleProps)
```

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingSchedule.Initializer.parameter.schedule">schedule</a></code> | <code><a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps">ValheimWorldScalingScheduleProps</a></code> | *No description.* |

---

##### `schedule`<sup>Required</sup> <a name="schedule" id="cdk-valheim-discord.ValheimWorldScalingSchedule.Initializer.parameter.schedule"></a>

- *Type:* <a href="#cdk-valheim-discord.ValheimWorldScalingScheduleProps">ValheimWorldScalingScheduleProps</a>

---

#### Methods <a name="Methods" id="Methods"></a>

| **Name** | **Description** |
| --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingSchedule.toCronOptions">toCronOptions</a></code> | Returns the cron options merged properties for both start and stop. |

---

##### `toCronOptions` <a name="toCronOptions" id="cdk-valheim-discord.ValheimWorldScalingSchedule.toCronOptions"></a>

```typescript
public toCronOptions(): CronOptions
```

Returns the cron options merged properties for both start and stop.


#### Properties <a name="Properties" id="Properties"></a>

| **Name** | **Type** | **Description** |
| --- | --- | --- |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingSchedule.property.start">start</a></code> | <code>aws-cdk-lib.aws_applicationautoscaling.CronOptions</code> | Options to configure a cron expression for server for server launching schedule. |
| <code><a href="#cdk-valheim-discord.ValheimWorldScalingSchedule.property.stop">stop</a></code> | <code>aws-cdk-lib.aws_applicationautoscaling.CronOptions</code> | Options to configure a cron expression for server zero-scale schedule. |

---

##### `start`<sup>Required</sup> <a name="start" id="cdk-valheim-discord.ValheimWorldScalingSchedule.property.start"></a>

```typescript
public readonly start: CronOptions;
```

- *Type:* aws-cdk-lib.aws_applicationautoscaling.CronOptions

Options to configure a cron expression for server for server launching schedule.

All fields are strings so you can use complex expressions. Absence of
a field implies '*' or '?', whichever one is appropriate. Only comma
separated numbers and hypens are allowed.

---

##### `stop`<sup>Required</sup> <a name="stop" id="cdk-valheim-discord.ValheimWorldScalingSchedule.property.stop"></a>

```typescript
public readonly stop: CronOptions;
```

- *Type:* aws-cdk-lib.aws_applicationautoscaling.CronOptions

Options to configure a cron expression for server zero-scale schedule.

All fields are strings so you can use complex expressions. Absence of
a field implies '*' or '?', whichever one is appropriate. Only comma
separated numbers and hypens are allowed.

---



