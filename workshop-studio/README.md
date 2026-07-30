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
static/
  loanbuddy-infra.yaml      Copy of infra/template.yaml, referenced by
                            contentspec for optional event pre-provisioning
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

## Event assets (the two zips)

Event assets do NOT travel through the content git repo. They are uploaded
directly to the workshop's S3 assets channel:

```
s3://ws-content-<workshop-id>/<repository-name>/assets/
```

using the temporary credentials from the workshop's **Credentials** button.
Procedure after changing agent code, UI, scripts, labs, or the seeder:

```bash
./scripts/build-assets.sh        # writes workshop-studio/assets/*.zip
# source the Credentials-dialog exports, then:
aws s3 cp workshop-studio/assets/seeder-lambda.zip  s3://ws-content-<id>/<repo>/assets/
aws s3 cp workshop-studio/assets/loanbuddy-code.zip s3://ws-content-<id>/<repo>/assets/
# trigger a new build (any push, or console) so it snapshots the assets
```

The build page's "Uploaded assets" count confirms the snapshot.

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
