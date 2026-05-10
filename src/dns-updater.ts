import * as path from 'path';
import {
  Duration,
  CfnOutput,
  aws_ecs as ecs,
  aws_events as events,
  aws_events_targets as targets,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  aws_route53 as route53,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Properties for {@link Route53DnsUpdater}.
 */
export interface Route53DnsUpdaterProps {
  /**
   * The ECS cluster whose task state changes should trigger DNS updates.
   */
  readonly cluster: ecs.ICluster;

  /**
   * The Route53 hosted zone to update (e.g. chipsgaming.click).
   */
  readonly hostedZone: route53.IHostedZone;

  /**
   * The record name to upsert. Combined with hostedZone.zoneName.
   *
   * Example: recordName="valheim" + zone "chipsgaming.click" => valheim.chipsgaming.click
   *
   * @default 'valheim'
   */
  readonly recordName?: string;

  /**
   * TTL for the A record. Kept short so friends reconnect fast when the task restarts.
   *
   * @default Duration.seconds(30)
   */
  readonly ttl?: Duration;
}

/**
 * Watches ECS task state changes on the given cluster; when a task transitions to RUNNING,
 * a Lambda looks up the task's ENI, extracts the auto-assigned public IP, and UPSERTs
 * a Route53 A record pointing `<recordName>.<zone>` at that IP.
 *
 * Motivation: Fargate tasks get a fresh public IP on every restart. Friends connect to a
 * stable DNS name instead of chasing IPs.
 */
export class Route53DnsUpdater extends Construct {
  public readonly handler: lambda.Function;
  public readonly rule: events.Rule;
  public readonly recordFqdn: string;

  constructor(scope: Construct, id: string, props: Route53DnsUpdaterProps) {
    super(scope, id);

    const recordName = props.recordName ?? 'valheim';
    const ttlSeconds = (props.ttl ?? Duration.seconds(30)).toSeconds();
    this.recordFqdn = `${recordName}.${props.hostedZone.zoneName}`;

    this.handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      // No external pip deps — pure boto3 (included in runtime). No Docker bundling needed.
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'dns-updater')),
      timeout: Duration.seconds(30),
      memorySize: 128,
      logRetention: logs.RetentionDays.ONE_WEEK,
      environment: {
        HOSTED_ZONE_ID: props.hostedZone.hostedZoneId,
        RECORD_FQDN: this.recordFqdn,
        RECORD_TTL: ttlSeconds.toString(),
      },
    });

    // IAM: describe ENIs (can't scope by specific ENI — they're ephemeral), and
    // change record sets only on this hosted zone.
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ec2:DescribeNetworkInterfaces'],
      resources: ['*'],
    }));
    this.handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['route53:ChangeResourceRecordSets'],
      resources: [`arn:aws:route53:::hostedzone/${props.hostedZone.hostedZoneId}`],
    }));

    // EventBridge: fire on ECS task transitions to RUNNING in this cluster only.
    this.rule = new events.Rule(this, 'TaskRunningRule', {
      description: `Update ${this.recordFqdn} when a Valheim task reaches RUNNING`,
      eventPattern: {
        source: ['aws.ecs'],
        detailType: ['ECS Task State Change'],
        detail: {
          clusterArn: [props.cluster.clusterArn],
          lastStatus: ['RUNNING'],
          desiredStatus: ['RUNNING'],
        },
      },
    });
    this.rule.addTarget(new targets.LambdaFunction(this.handler));

    new CfnOutput(this, 'ServerDnsName', {
      value: this.recordFqdn,
      description: 'Share this with friends — the Valheim server hostname',
    });
  }
}
