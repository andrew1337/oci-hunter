#!/usr/bin/env bash
# Build the hunter image and run it. Ctrl+C stops the hunt;
# state (state/.hunter_state.json) survives restarts, so the network
# and any caught instance are reused rather than recreated.
set -euo pipefail
cd "$(dirname "$0")"

podman build -t oci-hunter .

exec podman run --rm -d --name oci-hunter \
  -v .:/app \
  -e SSH_KEY_HINT="${SSH_KEY_FILE:-ssh_key}" \
  oci-hunter "$@"
