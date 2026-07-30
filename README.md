# LoanBuddy: Amazon Bedrock AgentCore Workshop

A hands-on workshop that takes a complete multi-agent loan-origination
application and makes it production-real on Amazon Bedrock AgentCore.

You are the platform engineer. The application code is written; your job is to
deploy and wire every AgentCore primitive: Runtime, Identity, Memory, Gateway,
Code Interpreter, Browser, and Observability.

## The application

LoanBuddy is a loan-origination assistant for a fictional bank:

- Applicants log in and chat with a **supervisor** agent (the loan officer)
- The supervisor delegates to two specialists behind an AgentCore **Gateway**:
  - **doc-coordinator** — collects and validates documents (ID, paystub, bank
    statement) with per-doc-type in-process specialist agents, and verifies
    employers against a business registry using **Browser**
  - **credit-analyst** — pulls a (mocked) Experian credit report, applies
    lending policy, and runs underwriting math in **Code Interpreter**
- Application state lives in DynamoDB; documents live in S3; conversational
  continuity lives in AgentCore **Memory** — so an applicant can leave and
  return days later
- Auth boundaries at every level, anchored on the Cognito identity claim

## Architecture

```
User ──> UI (S3 + CloudFront) ──JWT──> supervisor (Runtime)
                                          │  one MCP client connection
                                          ▼
                                       Gateway
                                          ├──> doc-coordinator (Runtime, MCP)
                                          │       └── Browser
                                          ├──> credit-analyst (Runtime, MCP)
                                          │       └── Code Interpreter
                                          └──> experian-mock (Lambda)
```

## Labs

| Lab | Focus | Time |
|-----|-------|------|
| 0 | Bootstrap the environment | 15 min |
| 1 | Runtime + inbound Identity (JWT) | 25 min |
| 2 | Memory | 25 min |
| 3 | Gateway + outbound Identity | 25 min |
| 4 | Subagent runtimes as MCP targets | 30 min |
| 5 | Built-in tools: Code Interpreter + Browser | 20 min |
| 6 | Observability | 25 min |

Start with [labs/lab-0-bootstrap.md](labs/lab-0-bootstrap.md).

## Repo layout

```
infra/            CloudFormation stack + seed assets (docs, registry site)
agents/           Complete agent code (you configure, not write)
  supervisor/       loan officer: conversation, ledger, gateway client
  doc-coordinator/  MCP server: analyze_document, check_docs_complete
  credit-analyst/   MCP server: assess_credit
ui/               Pre-built single-page app
scripts/          bootstrap, token helper, per-lab checkpoints
labs/             Lab guides 0-6
```

## Pinned versions

| Component | Version |
|-----------|---------|
| AgentCore CLI (`@aws/agentcore`, npm) | 0.24.1 |
| `bedrock-agentcore` (Python SDK) | 1.18.1 |
| `strands-agents` | 1.48.0 |
| `strands-agents-tools` | 0.8.5 |
| Python | >= 3.10 |

## Prerequisites

- An AWS account you can administer (a fresh account is ideal)
- AWS CLI v2 configured with a profile
- Python 3.10+, Node.js 18+
- Model access enabled in Amazon Bedrock for Anthropic Claude models
  (used by all three agents)
