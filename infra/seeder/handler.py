"""Workshop Seeder - CloudFormation custom resource.

Runs at stack provisioning time (AWS-hosted events) and performs everything
scripts/bootstrap.sh does on a laptop:

  Create : seed Cognito users, generate freshly-dated sample documents,
           publish the UI + mock registry (patched config.js).
  Update : same (idempotent re-seed).
  Delete : empty the docs and UI buckets so stack deletion is clean.

Assets (the code zip containing ui/ files) arrive via the Workshop Studio
assets bucket, passed in as resource properties.
"""
import io
import json
import logging
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

ZIP_UI_PREFIX = "ui/"
ZIP_REGISTRY = "infra/seed/registry-site/index.html"


# ---------------------------------------------------------------- cfn plumbing

def send(event, context, status, reason=""):
    body = json.dumps({
        "Status": status,
        "Reason": reason or f"See {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId",
                                        "loanbuddy-seeder"),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
    }).encode()
    req = urllib.request.Request(
        event["ResponseURL"], data=body, method="PUT",
        headers={"Content-Type": "", "Content-Length": str(len(body))})
    urllib.request.urlopen(req)


def handler(event, context):
    try:
        props = event.get("ResourceProperties", {})
        if event["RequestType"] == "Delete":
            empty_buckets(props)
        else:
            seed_users(props)
            seed_documents(props)
            publish_ui(props)
        send(event, context, "SUCCESS")
    except Exception as exc:  # surface the reason in the stack event
        log.exception("seeding failed")
        send(event, context, "FAILED", reason=str(exc)[:900])


# ---------------------------------------------------------------- create path

def seed_users(props):
    cognito = boto3.client("cognito-idp")
    pool = props["UserPoolId"]
    for user, password in (("alice", props["AlicePassword"]),
                           ("bob", props["BobPassword"])):
        try:
            cognito.admin_create_user(UserPoolId=pool, Username=user,
                                      MessageAction="SUPPRESS")
        except cognito.exceptions.UsernameExistsException:
            pass
        cognito.admin_set_user_password(UserPoolId=pool, Username=user,
                                        Password=password, Permanent=True)
    log.info("users seeded")


def seed_documents(props):
    outdir = Path("/tmp/sample-docs")
    subprocess.run(
        [sys.executable, str(Path(__file__).parent / "generate_docs.py"),
         str(outdir)],
        check=True, capture_output=True, text=True)
    s3 = boto3.client("s3")
    for png in outdir.glob("*.png"):
        s3.upload_file(str(png), props["DocsBucket"],
                       f"sample-docs/{png.name}",
                       ExtraArgs={"ContentType": "image/png"})
    log.info("sample documents generated and staged")


def publish_ui(props):
    s3 = boto3.client("s3")

    # Preserve an existing agent wiring across re-seeds (stack updates must
    # not un-wire a UI that a lab already pointed at a deployed supervisor).
    agent_arn_encoded = ""
    try:
        current = s3.get_object(Bucket=props["UiBucket"],
                                Key="config.js")["Body"].read().decode()
        for line in current.splitlines():
            if "agentArnEncoded" in line and '""' not in line:
                agent_arn_encoded = line.split('"')[1]
        log.info("preserve check: existing agentArnEncoded=%r",
                 agent_arn_encoded)
    except Exception:
        log.info("preserve check: no existing config.js (first seed)")

    raw = io.BytesIO()
    s3.download_fileobj(props["AssetsBucket"],
                        f"{props['AssetsPrefix']}loanbuddy-code.zip", raw)
    zf = zipfile.ZipFile(raw)

    def put(key, data, ctype):
        s3.put_object(Bucket=props["UiBucket"], Key=key, Body=data,
                      ContentType=ctype)

    config = zf.read(ZIP_UI_PREFIX + "config.js").decode()
    config = (config
              .replace('region: "us-east-1"', f'region: "{props["Region"]}"')
              .replace("REPLACED_BY_BOOTSTRAP_BADGE",
                       f"account {props['AccountId']}")
              .replace('userPoolId: "REPLACED_BY_BOOTSTRAP"',
                       f'userPoolId: "{props["UserPoolId"]}"')
              .replace('spaClientId: "REPLACED_BY_BOOTSTRAP"',
                       f'spaClientId: "{props["SpaClientId"]}"'))
    if agent_arn_encoded:
        config = config.replace('agentArnEncoded: ""',
                                f'agentArnEncoded: "{agent_arn_encoded}"')
    put("config.js", config.encode(), "application/javascript")
    put("index.html", zf.read(ZIP_UI_PREFIX + "index.html"), "text/html")
    put("app.js", zf.read(ZIP_UI_PREFIX + "app.js"), "application/javascript")
    put("styles.css", zf.read(ZIP_UI_PREFIX + "styles.css"), "text/css")
    put("registry/index.html", zf.read(ZIP_REGISTRY), "text/html")
    log.info("ui and registry published")


# ---------------------------------------------------------------- delete path

def empty_buckets(props):
    s3 = boto3.resource("s3")
    for name in (props["DocsBucket"], props["UiBucket"]):
        try:
            s3.Bucket(name).objects.all().delete()
            log.info("emptied %s", name)
        except Exception:
            log.warning("could not empty %s (may not exist)", name)
