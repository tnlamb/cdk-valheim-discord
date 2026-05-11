import * as path from 'path';
import {
  Duration,
  aws_ecs as ecs,
  aws_events as events,
  aws_events_targets as targets,
  aws_lambda as lambda,
  aws_logs as logs,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Properties for {@link ReadyNotifier}.
 */
export interface ReadyNotifierProps {
  /**
   * The Valheim Fargate service whose task start events we watch.
   */
  readonly service: ecs.FargateService;

  /**
   * Public hostname used for the A2S probe and the "Connect:" string in the
   * ready message.
   */
  readonly hostname: string;

  /**
   * Discord bot token used to post messages as the bot. Must be set to the
   * token from the Discord developer portal → Bot tab.
   *
   * This is a secret. Store it in an env var passed to `cdk deploy`; it will
   * end up as a Lambda environment variable (encrypted at rest by default).
   * For stronger isolation, swap to Secrets Manager later.
   */
  readonly discordBotToken: string;

  /**
   * Discord channel ID where the ready message will be posted. Enable
   * Developer Mode in Discord, right-click the channel, choose "Copy Channel ID".
   */
  readonly discordChannelId: string;

  /**
   * UDP port used for A2S probes.
   *
   * @default 2457
   */
  readonly valheimQueryPort?: number;

  /**
   * Total time to wait for A2S to answer before giving up and posting a
   * warning. Must be <= the Lambda's timeout.
   *
   * @default Duration.minutes(5)
   */
  readonly readyTimeout?: Duration;

  /**
   * How often the Lambda probes A2S while waiting.
   *
   * @default Duration.seconds(15)
   */
  readonly pollInterval?: Duration;
}

/**
 * EventBridge + Lambda: on every Valheim Fargate task transition to RUNNING,
 * poll A2S until the server answers (i.e. the world finished loading and the
 * game port is open) and post "Server is ready!" to a Discord channel via the
 * bot API.
 *
 * Note on task filtering: ECS fires Task State Change events for every task
 * in the cluster — including save-import one-shots. The EventBridge rule
 * scopes to tasks in our valheim-world service via the `group` field which
 * ECS populates as `service:<serviceName>` for service-spawned tasks.
 */
export class ReadyNotifier extends Construct {
  public readonly handler: lambda.Function;
  public readonly rule: events.Rule;

  constructor(scope: Construct, id: string, props: ReadyNotifierProps) {
    super(scope, id);

    const valheimQueryPort = props.valheimQueryPort ?? 2457;
    const readyTimeout = props.readyTimeout ?? Duration.minutes(5);
    const pollInterval = props.pollInterval ?? Duration.seconds(15);

    this.handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      // Pure stdlib — no bundling needed.
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'ready-notifier')),
      // Lambda must outlive the readiness poll loop; add a small buffer.
      timeout: Duration.seconds(readyTimeout.toSeconds() + 30),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
      environment: {
        DISCORD_BOT_TOKEN: props.discordBotToken,
        DISCORD_CHANNEL_ID: props.discordChannelId,
        VALHEIM_HOSTNAME: props.hostname,
        VALHEIM_QUERY_PORT: valheimQueryPort.toString(),
        READY_TIMEOUT_SECONDS: readyTimeout.toSeconds().toString(),
        POLL_INTERVAL_SECONDS: pollInterval.toSeconds().toString(),
      },
    });

    // Fire on every ECS task state change where the task is a member of our
    // Fargate service AND the new lastStatus is RUNNING. The `group` field is
    // the service-qualified group name ECS uses for service-spawned tasks;
    // standalone run-task invocations (e.g. save-import) use `family:<name>`
    // and won't match.
    this.rule = new events.Rule(this, 'Rule', {
      description: 'Post "Server ready" to Discord when a Valheim task reaches RUNNING',
      eventPattern: {
        source: ['aws.ecs'],
        detailType: ['ECS Task State Change'],
        detail: {
          clusterArn: [props.service.cluster.clusterArn],
          lastStatus: ['RUNNING'],
          desiredStatus: ['RUNNING'],
          group: [`service:${props.service.serviceName}`],
        },
      },
    });
    this.rule.addTarget(new targets.LambdaFunction(this.handler));
  }
}
