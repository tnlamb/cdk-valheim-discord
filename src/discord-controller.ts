import * as path from 'path';
import {
  Duration,
  CfnOutput,
  aws_apigateway as apigateway,
  aws_ecs as ecs,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Properties for {@link DiscordValheimController}.
 */
export interface DiscordValheimControllerProps {
  /**
   * The Valheim Fargate service to start/stop via Discord slash commands.
   */
  readonly service: ecs.FargateService;

  /**
   * The Discord application public key used to verify signed interaction requests (Ed25519).
   *
   * This value is public (not a secret) — it is the counterpart of Discord's private signing key.
   * Passed as a plain Lambda environment variable.
   */
  readonly applicationPublicKey: string;

  /**
   * Desired Fargate task count when a user runs `/vh start`.
   *
   * @default 1
   */
  readonly startDesiredCount?: number;

  /**
   * Lambda timeout. Discord Interactions require a response within 3 seconds,
   * but the Lambda can deliver deferred responses — for our ECS API calls 10s is plenty.
   *
   * @default Duration.seconds(10)
   */
  readonly lambdaTimeout?: Duration;

  /**
   * Public hostname players connect to (e.g. `valheim.chipsgaming.click`).
   * When set, `/vh status` includes `Connect: <hostname>:<port>` in the reply.
   *
   * @default - no connect string shown
   */
  readonly valheimHostname?: string;

  /**
   * Valheim game port surfaced in the connect string.
   *
   * @default 2456
   */
  readonly valheimPort?: number;

  /**
   * Valheim Steam A2S query port. `/vh status` probes this port to confirm
   * the game engine has finished loading the world before reporting ONLINE.
   *
   * @default 2457
   */
  readonly valheimQueryPort?: number;
}

/**
 * Lambda + API Gateway that handles Discord Interactions (slash commands) and
 * scales the Valheim Fargate service between desiredCount 0 and 1.
 *
 * Registers a `/vh {status|start|stop}` slash command flow. Use
 * `scripts/register_bot.py` to register the command with Discord the first time.
 *
 * Discord POSTs to `<apiEndpointUrl>/discord`. The Lambda:
 *  1. Verifies the Ed25519 signature using the application public key.
 *  2. Responds to PING (type=1) with PONG for Discord's endpoint verification.
 *  3. Dispatches slash command sub-options to `ecs:DescribeServices` / `ecs:UpdateService`.
 *
 * IAM is scoped to the specific service ARN (no `AmazonECS_FullAccess`).
 */
export class DiscordValheimController extends Construct {
  public readonly handler: lambda.Function;
  public readonly api: apigateway.RestApi;
  public readonly discordEndpointUrl: string;

  constructor(scope: Construct, id: string, props: DiscordValheimControllerProps) {
    super(scope, id);

    const { service } = props;
    const startDesiredCount = props.startDesiredCount ?? 1;

    this.handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '..', 'lambda', 'discord-handler'),
        {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              'bash', '-c',
              [
                'pip install --no-cache-dir -r requirements.txt -t /asset-output',
                'cp -au . /asset-output',
              ].join(' && '),
            ],
          },
        },
      ),
      timeout: props.lambdaTimeout ?? Duration.seconds(10),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_WEEK,
      environment: {
        APPLICATION_PUBLIC_KEY: props.applicationPublicKey,
        ECS_CLUSTER_ARN: service.cluster.clusterArn,
        ECS_SERVICE_NAME: service.serviceName,
        START_DESIRED_COUNT: startDesiredCount.toString(),
        VALHEIM_HOSTNAME: props.valheimHostname ?? '',
        VALHEIM_PORT: (props.valheimPort ?? 2456).toString(),
        VALHEIM_QUERY_PORT: (props.valheimQueryPort ?? 2457).toString(),
      },
    });

    // Tight IAM: only describe + update this specific service.
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ecs:DescribeServices', 'ecs:UpdateService'],
      resources: [service.serviceArn],
    }));

    // List/Describe tasks for uptime reporting. These actions don't support
    // per-service resource ARNs, so scope via the ecs:cluster condition.
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ecs:ListTasks', 'ecs:DescribeTasks'],
      resources: ['*'],
      conditions: {
        ArnEquals: { 'ecs:cluster': service.cluster.clusterArn },
      },
    }));

    // API Gateway REST API using Lambda Proxy integration. Discord signs the
    // raw request body bytes, so the Lambda MUST receive them untouched — any
    // VTL re-serialization (e.g. $input.json("$")) changes key order/whitespace
    // and breaks ed25519 signature verification. Proxy integration also forwards
    // the X-Signature-Ed25519 / X-Signature-Timestamp headers natively.
    this.api = new apigateway.RestApi(this, 'Api', {
      restApiName: `${id}-discord-interactions`,
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.ERROR,
      },
    });

    const discordResource = this.api.root.addResource('discord');
    discordResource.addMethod('POST', new apigateway.LambdaIntegration(this.handler, {
      proxy: true,
    }));

    this.discordEndpointUrl = `${this.api.url}discord`;

    new CfnOutput(this, 'DiscordInteractionsEndpointUrl', {
      value: this.discordEndpointUrl,
      description: 'Paste this into the Discord developer portal → General Information → Interactions Endpoint URL',
    });
  }
}
