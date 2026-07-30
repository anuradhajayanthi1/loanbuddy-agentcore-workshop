# Workshop review form - drafted answers

Internal working doc (do NOT push to the Studio content repo). Answers map
1:1 to the AWS Workshop Review form. Items marked **[YOU]** need an action
only the owner can take; everything else can be answered as drafted.

## Content review SIM ticket (1)
- **[YOU]** Create a SIM ticket to record review decisions; paste its link.

## Publishing model (1)
- Publicly published? **Answer per your intent.** Recommendation: start
  INTERNAL. Public raises the bar on the security/license sections below.

## Workshop introduction (5)
1. Introduction states coverage? **Yes** - home page lists the seven
   primitives and the application narrative.
2. States outcomes? **Yes** - "What you will learn", six numbered outcomes.
3. Describes target audience? **Yes** - practical-details table (builders/
   SAs designing agentic applications).
4. Background knowledge? **Yes** - Background row: terminal, basic AWS,
   Python reading level.
5. Cost warning + pricing links? **Yes** - Cost section links Bedrock and
   CloudFront pricing and points to Cleanup.

## Environment setup (5)
1. **[YOU]** Validated via a test event? Answer Yes ONLY after you run the
   planned test event (create it, run the attendee path in the vended
   account).
2. Own-account prerequisite deployment described? **Yes** - Getting started
   "In your own account" + scripts/bootstrap.sh deploys CloudFormation.
3. WS-accounts-only warning needed? **N/A** - workshop supports own
   accounts.
4. Customer-device prerequisites? **Yes** - Getting started section 1 (AWS
   CLI, Python, Node, AgentCore CLI pip install).
5. Regions listed explicitly? **Yes** - us-east-1, stated on home page,
   getting started (alert box), and pinned in contentspec.

## Environment clean-up (5)
1. Cleanup instructions? **Yes** - dedicated Cleanup page, ordered.
2. Specific to created resources? **Yes** - names each AgentCore resource,
   buckets, stack.
3. Retained resources explained? **Yes** - "Leftovers worth checking"
   (log groups, toolkit bucket/ECR, model access).
4. Cost comment for retained resources? **Yes** - cleanup + cost section.
5. Cleanup referenced from intro/setup? **Yes** - home-page Cost section
   points to Cleanup.

## Well-Architected infrastructure (5)
1. Adheres where practical? **Yes** - serverless/managed services
   throughout; least-privilege agent execution roles; JWT auth at every
   entry point.
2. Deliberate non-redundancy noted? **Yes** - home page notes single-region
   as a deliberate workshop simplification.
3. Deployable to >1 region? **No (deliberate)** - noted; models and
   primitives are region-scoped for the labs. (Build warning acknowledged.)
4/5. CFN rollback/undeploy cleanly? **Yes with documented caveat** - S3
   buckets must be emptied before stack delete; the Cleanup page does this
   explicitly before delete-stack.

## External links and privacy (7)
1. Files within workshop structure? **Yes** - CFN template in /static; all
   images: none used (text diagrams).
2. Larger bundles centrally stored? **Application code in GitLab
   (gitlab.aws.dev/anjayan/agentcore-loanbuddy-workshop).** For PUBLIC
   publication this must move to aws-samples GitHub - flagged.
3. Video directive? **N/A** - no videos.
4. Third-party data sets? **None** - all sample data is generated fiction
   (State of Workshopia).
5. Image licensing? **N/A** - no images currently.
6. No Customer/Business data? **Confirmed** - fictional personas (alice,
   bob), generated documents, mock bureau.
7. AppSec review for customer data infra? **N/A** - none processed.

## Security (12)
1. Scoped policies for created roles? **Yes** - three agent execution roles
   are purpose-scoped (see infra/template.yaml *-boundaries policies);
   this is a teaching point of the workshop (Lab 0 reads them).
2. Restrict-public-access enabled? **Yes** - both S3 buckets block public
   access; CloudFront uses OAC; DynamoDB/Cognito not public.
3. EC2 security groups? **N/A** - no EC2.
4. Non-WA configurations noted? **Yes** - e.g., wildcard CORS on docs
   bucket is commented in the template with the production alternative.
5. Sample code least privilege? **Yes** for agent roles. **Flag:** the
   PARTICIPANT role is AdministratorAccess (build warning). Justification:
   attendees create AgentCore control-plane resources across seven services;
   scoping is planned before public publication.
6. **[YOU]** IAM Access Analyzer run + findings resolved - not yet run.
7. Attendees not asked to enter information? **Confirmed** - all personas
   and data are fictional and provided.
8. Service security best practices? **Yes** - JWT authorizers on all
   runtimes and gateway, credentials in Identity token vault (never in
   code), scoped IAM, no public endpoints without auth except the static UI.
9. **[YOU]** Holmes content scan findings - build's code scan passed
   ("no findings"); confirm the Holmes report in the build details.
10. Additional scans? Answer as applicable (e.g., git-secrets run: no
    secrets in repo; workshop-card/env files are gitignored).
11. No confidential info/internal tools in content? **Confirmed** - content
    references only public AWS services and public pip/npm packages.
12. Architecture diagram? **Partial** - text diagrams on home page and in
    labs. **[YOU/optional]** reviewers may want a rendered image with
    security controls; can be added to /static.

## Source code / third party / open source (5)
1. License with AWS-created code? **Yes** - MIT-0 LICENSE at repo root.
2. Third-party code license compatible? **Yes** - dependencies are
   Apache-2.0/MIT (strands-agents, bedrock-agentcore, boto3, mcp, Pillow).
3. Attributions present? **Yes** - via standard package metadata; no
   vendored third-party code.
4. Third-party data rights? **N/A** - no third-party data.
5. Code under Amazon-owned org? **Internal GitLab today.** For public
   publication: migrate to aws-samples - flagged (same as privacy Q2).

## Content, spelling, grammar (5)
1. Factually correct? **Yes** - every command validated end-to-end in two
   fresh accounts (reference build + attendee dry run).
2. Steps complete without error? **Yes** - attendee dry run drove fixes;
   guides regenerated from validated runs.
3. Content helps resolve errors? **Yes** - expected-failure callouts (401/
   403 proofs, 60-day statement rejection), checkpoint.sh catch-up per lab.
4. No sections better as diagrams? **Mostly** - text diagrams used;
   see Security Q12 flag.
5. Avoids unclear rhetorical devices? **Yes** - reviewed; idioms minimal.

## Accessibility and inclusion (5)
1. Image alt text? **N/A today** (no images); add alt text if diagrams are
   added.
2. Red/green reliance? **Yes/compliant** - UI status chip uses text labels;
   content uses no color-coded imagery.
3. Video subtitles? **N/A** - no videos.
4. Inclusive Tech Guidelines? **Yes** - e.g., git branch "mainline" in
   Studio repo; no exclusionary terms in content or code.
5. Translations? **N/A** - en-US only; contentspec declares a single locale.

## Before clicking "Ready for review"
1. **[YOU]** SIM ticket created and linked
2. **[YOU]** Test event run (also flips Environment setup Q1 to Yes)
3. **[YOU]** Find a Content Champion (directory linked at top of the form)
   and coordinate
4. Optional but likely requested: rendered architecture diagram; IAM Access
   Analyzer pass; aws-samples migration if public
