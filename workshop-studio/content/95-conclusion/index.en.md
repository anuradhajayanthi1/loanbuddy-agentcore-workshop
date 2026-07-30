---
title: "Conclusion and next steps"
weight: 95
---

You started with an empty account and finished with a production-shaped,
multi-agent loan origination system:

- **3 deployed agents** (supervisor, doc-coordinator, credit-analyst), each
  with exactly the credentials its job requires and provably nothing more
- **8 agent personas** — one conversationalist at the edge, seven strict
  functionaries behind it
- Every AgentCore primitive doing a load-bearing job: Runtime, Identity
  (inbound and outbound), Memory, Gateway, Code Interpreter, Browser,
  Observability

## The five ideas to take home

1. **Identity is established once and flows as data.** The login token's
   `sub` claim became the key for the ledger, the documents, the memory
   namespaces, and every tool argument. Past the first hop, machines
   authenticate as themselves and carry the user as an argument.
2. **What a memory survives is a namespace design decision.** Facts scoped
   to the applicant survive forever; summaries scoped to the session capture
   one sitting. Ground truth still belongs in a database.
3. **Everything behind the Gateway is a tool.** A Lambda, a REST API, and an
   entire reasoning agent are indistinguishable from the caller's seat —
   which is what makes implementations swappable.
4. **Repo code for rules, sandbox code for computation.** Lending policy is
   reviewable Python in the repo; per-applicant math is model-written code
   in an isolated sandbox. Never let the model freestyle either one.
5. **Boundaries that hold regardless of what the model decides.** IAM
   prefixes, JWT authorizers, and vaulted credentials protected the system
   even when the model was talked into trying — and the traces can prove it.

## Make it yours

- Swap the mock Experian for a real API: change the OpenAPI target's server
  URL and credential — nothing else moves
- Add a W-2 document type: one entry in `DOC_SPECS`, one line of policy — no
  new infrastructure
- Promote a specialist to its own runtime when (and only when) its
  permissions, change cadence, or scaling diverge
- Production-harden the front: streaming responses or async tasks for long
  turns, WAF and a custom domain in front of the UI

Thanks for building with us. Now go originate something.
