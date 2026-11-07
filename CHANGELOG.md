# Changelog

## 2026-11-07 (2)

- `docker-compose.yml` / `run.sh` mount the whole project dir (`- .:/app`)
  instead of individual files. Per-file mounts silently created junk
  directories on the host whenever a file was missing (e.g. no
  `ssh_key.pub`), so the container started but crashed in a loop with
  "no SSH public key found" — exactly what broke `compose up -d` on a
  fresh machine.
- Key picking moved into the hunter: `SSH_PUBKEY` env, then `SSH_KEY_FILE`
  (the `.pub` sibling of the private key), then the first `*.pub` in the
  project dir. `run.sh` lost its own key detection and pre-touching of the
  state file — both are handled inside the container now.
- State file moved to `state/.hunter_state.json` (matching the compose
  host path), created on demand; the legacy root-level
  `.hunter_state.json` is still read as a fallback. `save_state` also
  recovers from the empty leftover directories those per-file mounts
  created on the host in place of the state file (`Errno 21 Is a
  directory`).

## 2026-11-07

- Default instance size raised to 2 OCPU / 12 GB (half of the A1 free-tier
  pool instead of a quarter).
- Image selection reworked: a single `IMAGE_PREFIX` (default
  `Canonical-Ubuntu-24.04-aarch64-`) instead of a hardcoded preference list;
  a mismatch now aborts with a `Fatal` listing the aarch64 images actually
  available in the region.
- SSH key handling: `run.sh` auto-detects the key pair (first `*.pub` in the
  project dir, or `SSH_KEY_FILE`) and mounts the public key into the
  container — no more manual `SSH_PUBKEY` pasting; the hard-coded
  `ssh-key-2026-11-04.key.pub` fallback is gone. Key name also drives the
  `ssh -i ...` hint via `SSH_KEY_HINT`.
- Network naming/CIDRs moved to config: `VCN_NAME`, `SUBNET_NAME`,
  `IG_NAME`, `VCN_CIDR`, `SUBNET_CIDR` are read from `.env` (previous
  hard-coded values kept as defaults); `ensure_network` now takes `cfg`.
- README: new Setup steps for creating the Telegram bot (BotFather `/newbot`)
  and generating the SSH key; env-var reference updated with the new knobs.

## 2026-11-06

- Refactored the single-file `hunter.py` into the `oci_hunter` package with
  focused modules (config, state, telegram, OCI network/image/instance
  abstractions, hunt loop, `python -m oci_hunter` entry point).
- Smarter 429 backoff: the `Retry-After` response header is honored, and the
  exponential ladder cap was raised from 10 to 15 minutes.
- New Telegram `/status` command: the bot answers live hunt stats (uptime,
  attempts, current AD, backoff, last error) — and only ever in the owner's
  chat (`TG_CHAT_ID`); all other chats are ignored.
- README rewritten with an Architecture section documenting the package
  structure, layer boundaries and the backoff policy.
- Project is now a git repository (no remote), with personal files
  (`.env`, SSH keys, API PEMs, state) gitignored.
- Deployment target: docker compose on the pi5 (`~/composes/oci-hunter`) with
  `restart: unless-stopped`, replacing the stale `run.sh`-launched container.

# FOR THOSE WHO WANTS IT FREE AND HAVE SOME TIME TO WAIT
