import {
  CfnOutput,
  Duration,
  Stack,
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_efs as efs,
  aws_logs as logs,
  aws_s3 as s3,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

export interface SaveImportProps {
  /** ECS cluster (reused from ValheimWorld). */
  readonly cluster: ecs.ICluster;

  /** EFS filesystem that holds the Valheim save data (reused from ValheimWorld). */
  readonly fileSystem: efs.FileSystem;

  /**
   * Path inside the container where EFS is mounted.
   *
   * @default '/config'
   */
  readonly containerPath?: string;

  /**
   * S3 prefix within the import bucket to sync from.
   *
   * @default 'worlds_local/'
   */
  readonly s3Prefix?: string;
}

/**
 * SaveImport provides a way to copy Valheim world files from S3 into EFS.
 *
 * Creates:
 *   - An S3 bucket for user uploads (with 7-day lifecycle on old versions)
 *   - A one-shot Fargate task using `amazon/aws-cli` that mounts the same EFS
 *     and `aws s3 sync`s objects from the bucket into /config/worlds_local/
 *   - A CFN output with the exact `aws ecs run-task` command to trigger the copy
 *
 * Typical usage flow:
 *   1. `aws s3 cp MyWorld.db s3://<bucket>/worlds_local/`
 *   2. `aws s3 cp MyWorld.fwl s3://<bucket>/worlds_local/`
 *   3. Paste the `aws ecs run-task ...` command from the stack output
 *   4. `/vh start` in Discord — server boots with the imported world
 */
export class SaveImport extends Construct {
  public readonly bucket: s3.Bucket;
  public readonly taskDefinition: ecs.FargateTaskDefinition;

  constructor(scope: Construct, id: string, props: SaveImportProps) {
    super(scope, id);

    const containerPath = props.containerPath ?? '/config';
    const s3Prefix = props.s3Prefix ?? 'worlds_local/';

    this.bucket = new s3.Bucket(this, 'ImportBucket', {
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      lifecycleRules: [
        {
          id: 'expire-imports',
          enabled: true,
          expiration: Duration.days(30), // plenty of time to run the import
        },
      ],
    });

    // Task definition using amazon/aws-cli so we have `aws` + coreutils out of the box.
    this.taskDefinition = new ecs.FargateTaskDefinition(this, 'ImportTaskDef', {
      family: 'valheim-save-import',
      cpu: 256,
      memoryLimitMiB: 512,
      volumes: [
        {
          name: 'valheim-save-data',
          efsVolumeConfiguration: {
            fileSystemId: props.fileSystem.fileSystemId,
          },
        },
      ],
    });

    // Grant the task read access to the import bucket.
    this.bucket.grantRead(this.taskDefinition.taskRole);

    const container = this.taskDefinition.addContainer('ImportContainer', {
      image: ecs.ContainerImage.fromRegistry('amazon/aws-cli:latest'),
      entryPoint: ['/bin/sh', '-c'],
      command: [
        [
          'set -eux',
          'mkdir -p ' + containerPath + '/worlds_local',
          'echo "Syncing s3://' + this.bucket.bucketName + '/' + s3Prefix + ' -> ' + containerPath + '/worlds_local/"',
          'aws s3 sync s3://' + this.bucket.bucketName + '/' + s3Prefix + ' ' + containerPath + '/worlds_local/',
          'echo "--- Contents of ' + containerPath + '/worlds_local/ after sync ---"',
          'ls -la ' + containerPath + '/worlds_local/',
        ].join(' && '),
      ],
      logging: new ecs.AwsLogDriver({
        streamPrefix: 'save-import',
        logRetention: logs.RetentionDays.ONE_WEEK,
      }),
    });

    container.addMountPoints({
      containerPath,
      sourceVolume: 'valheim-save-data',
      readOnly: false,
    });

    // Security group for the one-off import task's ENI. Must be able to egress
    // to S3 (HTTPS) and reach EFS (NFS 2049).
    const importSg = new ec2.SecurityGroup(this, 'ImportTaskSG', {
      vpc: props.cluster.vpc,
      description: 'Allow Valheim save-import task to reach EFS and S3',
      allowAllOutbound: true,
    });
    props.fileSystem.connections.allowDefaultPortFrom(importSg);

    const region = Stack.of(this).region;
    const publicSubnetIds = props.cluster.vpc.publicSubnets.map((s) => s.subnetId);

    new CfnOutput(this, 'ImportBucketName', {
      description: 'S3 bucket — upload world files under the "worlds_local/" prefix here',
      value: this.bucket.bucketName,
    });

    new CfnOutput(this, 'ImportUploadCommand', {
      description: 'Example: upload a world pair to S3 (replace the source paths)',
      value:
        'aws s3 cp "<LOCAL_DIR>/MyWorld.db" s3://' +
        this.bucket.bucketName +
        '/worlds_local/ && aws s3 cp "<LOCAL_DIR>/MyWorld.fwl" s3://' +
        this.bucket.bucketName +
        '/worlds_local/',
    });

    new CfnOutput(this, 'ImportRunCommand', {
      description: 'Run this after uploading to S3 — copies files from S3 into the Valheim EFS',
      value: [
        'aws ecs run-task',
        '--cluster ' + props.cluster.clusterName,
        '--launch-type FARGATE',
        '--task-definition ' + this.taskDefinition.family,
        '--network-configuration \'{"awsvpcConfiguration":{"subnets":[' +
          publicSubnetIds.map((subnetId) => '"' + subnetId + '"').join(',') +
          '],"securityGroups":["' +
          importSg.securityGroupId +
          '"],"assignPublicIp":"ENABLED"}}\'',
        '--region ' + region,
      ].join(' '),
    });

    new CfnOutput(this, 'ImportLogsCommand', {
      description: 'Tail import task logs',
      value:
        'aws logs tail /aws/ecs/' +
        // log group name is autogen; we use the container log prefix instead
        'SaveImportImportTaskDef --follow --region ' +
        region +
        ' # or check CloudWatch Logs for streams starting with "save-import/"',
    });
  }
}
