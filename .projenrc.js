const { awscdk } = require('projen');

const project = new awscdk.AwsCdkConstructLibrary({
  authorName: 'tnlamb',
  authorAddress: 'tnlamb@users.noreply.github.com',
  cdkVersion: '2.178.0',
  projenVersion: '0.71.48',
  defaultReleaseBranch: 'main',
  name: 'cdk-valheim-discord',
  repositoryUrl: 'https://github.com/tnlamb/cdk-valheim-discord.git',
  devDeps: [
    'cdk-dia',
    'aws-cdk@2.178.0',
  ],
  license: 'Apache-2.0',
  gitignore: [
    'cdk.context.json',
    'cdk.out/',
    '*.dot',
    // Lambda build artifacts (created by CDK bundling, not committed)
    'lambda/**/_build/',
    'lambda/**/__pycache__/',
    // Local secrets (Discord tokens, etc.) — see .env.example
    '.env',
  ],
  // This fork is not published — disable release pipelines.
  releaseToNpm: false,
  release: false,
  scripts: {
    dia: 'npx cdk-dia --target-path assets/images/diagram.png',
  },
});

project.synth();
