# Workshop Studio packaging

This directory is a content package for AWS Workshop Studio
(https://studio.us-east-1.prod.workshops.aws/).

## Layout

```
contentspec.yaml            Workshop Studio manifest (locales, infra, account config)
content/
  index.en.md               Home page
  10-getting-started/       Environment, clone, bootstrap, env sourcing
  20-explore-the-environment/   Lab 0 (inspection only)
  30-runtime-inbound-identity/  Lab 1
  40-memory/                    Lab 2
  50-gateway-outbound-identity/ Lab 3
  60-subagents/                 Lab 4
  70-builtin-tools/             Lab 5
  80-observability/             Lab 6
  90-cleanup/
  95-conclusion/
```

## Publishing

1. In Workshop Studio, create a new workshop and connect it to a Git
   repository containing THIS DIRECTORY's contents at the repo root
   (contentspec.yaml must be top-level). Easiest: publish this subtree to
   its own repo, or use Studio's content upload.
2. Replace `<YOUR-REPO-URL>` in `content/10-getting-started/index.en.md`
   with the public URL of the application-code repository (the parent of
   this directory).
3. Preview the build in Studio; the numbered directories become the left
   nav, ordered by `weight`.
4. Lab pages are GENERATED from ../labs/*.md. If you edit the labs, re-run
   the sync (see below) rather than editing both copies.

## Format: self-paced, own account

This workshop is delivered self-paced. Attendees clone the application repo
and run `scripts/bootstrap.sh` in their own AWS account (see the
Getting started page). Workshop Studio hosts only the CONTENT; it does not
pre-provision infrastructure or ship code bundles as event assets.

Auto-provisioning into Workshop Studio-vended event accounts (a Seeder
custom resource that seeds users, generates sample docs, and publishes the
UI at provisioning time) is built and validated (`infra/seeder/`,
`scripts/build-assets.sh`) but NOT wired into this package: it needs the
Workshop Studio asset tooling (the `workshopstudio://` git helper or the
magic-variables / assets-URL directive) to deliver the two zips into vended
accounts. That is a v2 item for whoever has the Studio CLI in hand.

## Keeping labs in sync

The lab pages were produced by wrapping ../labs/*.md with front matter and
stripping the H1. If labs change, regenerate rather than hand-editing:
each page is front matter + the lab file body, title moved to front matter.

## Event vs self-paced

- The contentspec pre-deploys the base CloudFormation stack into vended
  event accounts. Attendees still run scripts/bootstrap.sh (idempotent) to
  seed users, generate dated sample documents, publish the UI, and write
  workshop-env.sh.
- Self-paced attendees in their own accounts follow Getting Started as-is;
  bootstrap deploys the stack too.
- Keep instructor/reference deployments off attendee networks: identical
  UIs with valid shared logins invite wrong-deployment confusion (the UI's
  account badge exists because of this).
