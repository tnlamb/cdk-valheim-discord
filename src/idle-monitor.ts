import * as path from 'path';
import {
  Duration,
  Stack,
  aws_ecs as ecs,
  aws_events as events,
  aws_events_targets as targets,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  aws_ssm as ssm,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Properties for {@link IdleMonitor}.
 */
export interface IdleMonitorProps {
  /**
   * The Fargate service to scale to 0 when the server goes idle.
   */
  readonly service: ecs.FargateService;

  /**
   * Public hostname the Lambda queries for player count (e.g. `valheim.chipsgaming.click`).
   *
   * This must resolve to the running task's public IP — the DNS updater in this
   * stack already maintains that record on each task start.
   */
  readonly hostname: string;

  /**
   * UDP port for Steam A2S_INFO queries. For Valheim (lloesche image) this is 2457;
   * 2456 is the game/join port and will NOT answer A2S queries.
   *
   * @default 2457
   */
  readonly queryPort?: number;

  /**
   * Duration of zero-player observations before the server is stopped.
   *
   * @default Duration.minutes(30)
   */
  readonly idleTimeout?: Duration;

  /**
   * Minimum time after a task starts before auto-stop may fire. Prevents the
   * monitor from killing a server that just booted and hasn't had time for
   * players to connect yet.
   *
   * @default Duration.minutes(10)
   */
  readonly gracePeriod?: Duration;

  /**
   * How often the monitor runs. Smaller values = tighter idle detection but
   * more Lambda invocations (all well within the free tier).
   *
   * @default Duration.minutes(5)
   */
  readonly checkInterval?: Duration;
}

/**
 * Scheduled Lambda that polls the Valheim server's Steam A2S query port and
 * scales the Fargate service to 0 after a configurable idle window.
 *
 * State lives in a single SSM Parameter (`last_active_at` as a Unix epoch).
 * Failure modes (timeouts, parse errors) are treated as inconclusive and leave
 * state untouched — the bias is toward NOT stopping a server that might still
 * be active.
 */
export class IdleMonitor extends Construct {
  public readonly handler: lambda.Function;
  public readonly rule: events.Rule;
  public readonly stateParameter: ssm.IStringParameter;

  constructor(scope: Construct, id: string, props: IdleMonitorProps) {
    super(scope, id);

    const queryPort = props.queryPort ?? 2457;
    const idleTimeout = props.idleTimeout ?? Duration.minutes(30);
    const gracePeriod = props.gracePeriod ?? Duration.minutes(10);
    const checkInterval = props.checkInterval ?? Duration.minutes(5);

    this.stateParameter = new ssm.StringParameter(this, 'LastActiveAt', {
      parameterName: `/${Stack.of(this).stackName}/valheim/last-active-at`,
      description: 'Unix epoch of the last observation with >0 players. 0 = reset.',
      stringValue: '0',
      tier: ssm.ParameterTier.STANDARD,
    });

    this.handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      // Pure stdlib + boto3 (included in runtime). No bundling needed.
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'idle-monitor')),
      timeout: Duration.seconds(30),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
      environment: {
        ECS_CLUSTER_ARN: props.service.cluster.clusterArn,
        ECS_SERVICE_NAME: props.service.serviceName,
        VALHEIM_HOSTNAME: props.hostname,
        VALHEIM_QUERY_PORT: queryPort.toString(),
        IDLE_TIMEOUT_SECONDS: idleTimeout.toSeconds().toString(),
        GRACE_PERIOD_SECONDS: gracePeriod.toSeconds().toString(),
        STATE_PARAM_NAME: this.stateParameter.parameterName,
      },
    });

    // Stop the service when idle, describe to check current desired count.
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ecs:DescribeServices', 'ecs:UpdateService'],
      resources: [props.service.serviceArn],
    }));

    // List/Describe tasks for the startedAt timestamp. These APIs don't
    // support per-service resource ARNs, so scope via the ecs:cluster condition.
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ecs:ListTasks', 'ecs:DescribeTasks'],
      resources: ['*'],
      conditions: {
        ArnEquals: { 'ecs:cluster': props.service.cluster.clusterArn },
      },
    }));

    this.stateParameter.grantRead(this.handler);
    this.stateParameter.grantWrite(this.handler);

    this.rule = new events.Rule(this, 'Schedule', {
      description: `Poll Valheim player count every ${checkInterval.toMinutes()}m; stop after ${idleTimeout.toMinutes()}m idle`,
      schedule: events.Schedule.rate(checkInterval),
    });
    this.rule.addTarget(new targets.LambdaFunction(this.handler));
  }
}
