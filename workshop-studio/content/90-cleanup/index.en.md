---
title: "Cleanup"
weight: 90
---

::alert[At an AWS-hosted event, the provided account is reclaimed automatically — you can skip this page. In your own account, clean up to stop all charges.]{header="Own-account only"}

Remove resources in this order (AgentCore resources first, CloudFormation
last).

## 1. AgentCore resources (created during labs)

```bash
source workshop-env.sh

# Gateway and its targets
agentcore gateway delete-mcp-gateway --region "$AWS_REGION" \
  --name loanbuddy-gateway --force

# Memory
MEMORY_ID=$(aws bedrock-agentcore-control list-memories \
  --query "memories[?starts_with(id,'loanbuddy_memory')].id | [0]" --output text)
agentcore memory delete "$MEMORY_ID" -r "$AWS_REGION"

# The three agent runtimes
for id in $(aws bedrock-agentcore-control list-agent-runtimes \
  --query "agentRuntimes[?starts_with(agentRuntimeName,'loanbuddy')].agentRuntimeArn" \
  --output text | tr '\t' '\n' | awk -F/ '{print $NF}'); do
  aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$id"
done

# Outbound credential provider
aws bedrock-agentcore-control delete-oauth2-credential-provider \
  --name loanbuddy-gateway-access
```

## 2. Empty the S3 buckets (CloudFormation cannot delete non-empty buckets)

```bash
aws s3 rm "s3://$DOCS_BUCKET" --recursive
aws s3 rm "s3://$(out UiBucket)" --recursive
aws s3 rm "s3://$(out AccessLogsBucket)" --recursive
```

## 3. The CloudFormation stack

```bash
aws cloudformation delete-stack --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --stack-name "$STACK"
```

## 4. Leftovers worth checking

- CloudWatch log groups under `/aws/bedrock-agentcore/` (delete if you want
  a spotless account)
- The toolkit's deployment S3 bucket and any ECR repositories it created
- Bedrock model access (account-level setting; harmless to leave)
