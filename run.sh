#!/usr/bin/env bash
# Build the hunter image and run it. Ctrl+C stops the hunt;
# state (.hunter_state.json) survives restarts, so the network
# and any caught instance are reused rather than recreated.
set -euo pipefail
cd "$(dirname "$0")"

touch .hunter_state.json

# Pick the SSH key pair: SSH_KEY_FILE env or the first *.pub here.
PUB="${SSH_KEY_FILE:-}"
[ -z "$PUB" ] && PUB="$(ls -1 ./*.pub 2>/dev/null | head -n1 || true)"
if [ -z "$PUB" ]; then
  echo "no .pub key found in $(pwd); set SSH_KEY_FILE=... or generate one:" >&2
  echo "  ssh-keygen -t ed25519 -f ssh_key" >&2
  exit 1
fi
KEY="${PUB%.pub}"
echo "using ssh key: $KEY(.pub)"

podman build -t oci-hunter .

exec podman run --rm -d --name oci-hunter \
  -v ./.env:/app/.env:ro \
  -v "./$KEY.pub":/app/ssh_key.pub:ro \
  -e SSH_KEY_HINT="$KEY" \
  -v ./.hunter_state.json:/app/.hunter_state.json \
  oci-hunter "$@"
