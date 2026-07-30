#!/usr/bin/env bash
# Build the two deployables that ship in workshop-studio/static/:
#   seeder-lambda.zip   - CFN custom resource (handler + doc generator +
#                         vendored Pillow for the Lambda's linux/x86_64 py312)
#   loanbuddy-code.zip  - the attendee code bundle (fetched from the event
#                         assets bucket; also what the Seeder reads ui/ from)
# Re-run after changing agent code, UI, scripts, labs, or the seeder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Event assets live in assets/ (staged by Workshop Studio into the per-event
# assets bucket); static/ is only for files served on the content website.
STATIC="$ROOT/workshop-studio/assets"
mkdir -p "$STATIC"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

echo "==> seeder-lambda.zip"
mkdir -p "$BUILD/seeder"
cp "$ROOT/infra/seeder/handler.py" "$ROOT/infra/seed/generate_docs.py" "$BUILD/seeder/"
python3 -m pip install --quiet --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 312 \
  --implementation cp --target "$BUILD/seeder" "Pillow>=12.1.1,<13"
(cd "$BUILD/seeder" && zip -qr "$STATIC/seeder-lambda.zip" . -x '*.dist-info/*' -x '*__pycache__*')

echo "==> loanbuddy-code.zip"
(cd "$ROOT" && zip -qr "$STATIC/loanbuddy-code.zip" \
  README.md LICENSE agents infra labs scripts ui \
  -x '*.bedrock_agentcore*' -x '*__pycache__*' -x '*.DS_Store' \
  -x 'infra/seed/sample-docs/*')

ls -la "$STATIC"/*.zip
