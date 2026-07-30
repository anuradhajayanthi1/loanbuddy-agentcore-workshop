---
title: "LoanBuddy: Production Agents on Amazon Bedrock AgentCore"
weight: 0
---

A hands-on workshop that takes a complete multi-agent loan-origination
application and makes it production-real on Amazon Bedrock AgentCore.

**You are the platform engineer.** The application code is written; your job
is to deploy and wire every AgentCore primitive: **Runtime, Identity, Memory,
Gateway, Code Interpreter, Browser, and Observability.**

## The application

LoanBuddy is a loan-origination assistant for the fictional First Bank of
Workshopia:

- Applicants log in and chat with a **supervisor** agent (the loan officer)
- The supervisor delegates to two specialists behind an AgentCore **Gateway**:
  - **doc-coordinator** — collects and validates documents (ID, paystub,
    bank statement) with per-doc-type specialist agents, and verifies
    employers against a business registry using a live **Browser**
  - **credit-analyst** — pulls a (mocked) Experian credit report, applies
    lending policy, and runs underwriting math in a **Code Interpreter**
    sandbox
- Application state lives in DynamoDB, documents in S3, and conversational
  continuity in AgentCore **Memory** — an applicant can leave mid-application
  and return days later
- Auth boundaries at every hop, anchored on the login identity

```text
User ──> UI (S3 + CloudFront) ──JWT──> supervisor (Runtime)
                                          │  one MCP client connection
                                          ▼
                                       Gateway
                                          ├──> doc-coordinator (Runtime, MCP)
                                          │       └── Browser
                                          ├──> credit-analyst (Runtime, MCP)
                                          │       └── Code Interpreter
                                          └──> experian-mock (API)
```

## What you will learn

1. Deploying agents to **Runtime** with JWT inbound auth, and how identity
   propagates from a login token through every downstream store
2. **Memory** namespace design: what a memory survives is a design decision
3. **Gateway** as the tool plane: Lambdas, APIs, and whole agents behind one
   authenticated MCP catalog
4. Outbound **Identity**: the token vault, and agents whose credentials
   appear nowhere in their code
5. **Code Interpreter** and **Browser**: when the model should write code,
   and when it should drive a website
6. **Observability**: reading one trace that spans three runtimes and every
   primitive above

## Practical details

| | |
|---|---|
| Level | 300 (intermediate) |
| Duration | ~3 hours |
| Region | us-east-1 |
| Audience | Builders comfortable with a terminal and basic AWS |
| Cost (own account) | A few dollars: Bedrock model invocations dominate |

Start with **Getting started**.
