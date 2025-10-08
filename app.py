#!/usr/bin/env python3
import os
import subprocess
import aws_cdk as cdk
from infrastructure.fantasy_don_stack import FantasyDonStack

app = cdk.App()

# Get account from environment or AWS CLI
account = os.getenv("CDK_DEFAULT_ACCOUNT")
if not account:
    try:
        # Try to get account from AWS CLI
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            capture_output=True,
            text=True,
            check=True
        )
        account = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If AWS CLI fails, leave as None and CDK will use deployment environment
        account = None

region = os.getenv("CDK_DEFAULT_REGION", "us-east-1")

# Only set env if we have an account, otherwise CDK will use deployment environment
stack_env = cdk.Environment(account=account, region=region) if account else None

FantasyDonStack(
    app,
    "FantasyDonStack",
    env=stack_env,
    description="NFL Stats Data Pipeline - Fetches NFL stats and serves via API Gateway",
)

app.synth()
