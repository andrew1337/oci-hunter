# Oracle Free Tier Instance Hunter

Watches Oracle Cloud's Always Free `VM.Standard.A1.Flex` ARM quota and launches
an instance the moment capacity opens up (normally you just get
"Out of host capacity" over and over). Once it succeeds it sends you the
instance's public IP and a ready-made `ssh` command via Telegram.

Runs in podman or docker, config lives in `.env`.

## What you get

- 2 OCPU / 12 GB ARM instance (A1.Flex), Ubuntu 24.04 (aarch64), 128 GB boot volume
- Public IP, port 22 open to the world
- Telegram updates: hunt started, silent heartbeat every ~10 attempts,
  warnings on repeated server errors, fatal errors, and the success message
- Telegram `/status` command (owner chat only): live hunt progress on demand

## Setup

### 1. Create a Telegram bot and get its token

In Telegram, open [@BotFather](https://t.me/BotFather) and send `/newbot`.
Follow the prompts, then copy the token it gives you (`123456:AA...`) — that
goes into `TG_BOT_ID` in `.env`; `TG_CHAT_ID` is your own chat id
([@userinfobot](https://t.me/userinfobot) shows it).

### 2. Get OCI API credentials

Generated in the Oracle console — no keys are issued anywhere else:

1. Log in to the [Oracle Cloud console](https://cloud.oracle.com).
2. Profile icon (top right) → **My profile** → **API keys** → **Add API key**.
3. Choose **Generate API key pair**, download the private key
   (`<something>.pem`), and click **Copy** next to the *fingerprint* shown
   in the dialog (also copy the **Configuration file preview** — it contains
   the values you need).
4. Put them into `.env` next to this README:

   ```ini
   OCI_CLI_USER=ocid1.user.oc1.....        # "user" from the config preview
   OCI_CLI_TENANCY=ocid1.tenancy.oc1.....  # "tenancy" from the config preview
   OCI_CLI_FINGERPRINT=xx:xx:xx:...        # fingerprint of the key you added
   OCI_CLI_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----
   OCI_CLI_REGION=eu-amsterdam-1
   TG_BOT_ID=123456:AA...                  # already filled in
   TG_CHAT_ID=123456789                    # your chat id (@userinfobot shows it)
   ```

   For the private key either inline it with `\n` between lines (as above)
   or point `OCI_CLI_KEY_FILE=/absolute/path/to/key.pem` instead.

   Optional overrides (defaults shown): `OCPU=2`, `MEM_GB=12`, `BOOT_GB=100`,
   `CHECK_EVERY_SEC=65`, `HEARTBEAT_EVERY=10`, `SHAPE=VM.Standard.A1.Flex`,
   `AVAILABILITY_DOMAIN=` (empty = try every AD in the region, rotating),
   `IMAGE_PREFIX=Canonical-Ubuntu-24.04-aarch64-` (exact prefix of the image
   display name — if nothing matches, the hunter aborts and lists what is
   available in the region),
   `SSH_KEY_FILE=ssh_key` (name of the private key mounted into the
   container; the `.pub` next to it is used for the instance).
   Network naming: `VCN_NAME=free-tier-hunter-vcn`,
   `SUBNET_NAME=free-tier-hunter-subnet`, `IG_NAME=free-tier-hunter-ig`,
   `VCN_CIDR=10.0.0.0/16`, `SUBNET_CIDR=10.0.0.0/24`.

### 3. SSH key

Oracle doesn't provide these — generate your own pair
(`ssh-keygen -t ed25519 -f ssh_key`) next to the code. `run.sh` picks up the
first `*.pub` in the directory (or whatever `SSH_KEY_FILE` names) and mounts
it into the container; you never paste the key contents anywhere. The
private key name is reused for the `ssh -i ...` hint in the success message.

### 4. Run

```bash
chmod +x run.sh
./run.sh            # builds the image and starts hunting
```

First run creates a VCN / internet gateway / subnet (`free-tier-hunter-*`)
if they don't exist, then starts one launch attempt roughly every minute.
"Out of host capacity" responses are logged quietly.

`./run.sh --once` makes a single attempt and exits — handy for a quick test.

### 5. Telegram `/status`

Send `/status` to the bot from the chat whose id is in `TG_CHAT_ID` and it
replies with the live hunt state:

```
🐾 Hunter status
uptime: 2h 14m
attempts: 118
current AD: eu-amsterdam-1-AD-1
backoff: 240s (429 x2, ladder)
last error: 429 TooManyRequests: Too many requests for the user
```

Messages from any other chat are ignored — the bot never replies to
strangers, even if they somehow find the bot's handle.

### 6. When it catches an instance

You get a Telegram message like:

```
🎉 Got it!
VM.Standard.A1.Flex 2 OCPU / 12 GB in eu-amsterdam-1-AD-1
public IP: 130.x.x.x
ssh -i ssh-key-2026-11-04.key ubuntu@130.x.x.x
```

The script exits after success; the instance keeps running. Delete it from
the console (or with the OCI CLI) when you're done — the free tier only
covers *running* A1 instances, not idle-created ones.

## Architecture

Everything lives in the `oci_hunter` package (run with `python -m oci_hunter`):

```
oci_hunter/
├── __main__.py      CLI entry point (argparse, Fatal handling, TG on crash)
├── hunter.py        the hunt loop: setup → attempt → classify → backoff → notify
├── config.py        .env loading, validated config dict, OCI SDK client config
├── logging.py       timestamped log() + uptime formatting
├── state.py         durable .hunter_state.json + thread-safe HuntStats
├── telegram.py      TelegramClient: notifications + owner-only /status poller
├── oci_network.py   idempotent VCN / internet gateway / subnet bootstrap
├── oci_image.py     Ubuntu aarch64 image selection for A1.Flex
└── oci_instance.py  launch, lookup, error classification, Retry-After parsing
```

The layers only talk to each other through small, explicit surfaces:

- **`config`** is the only module that reads the environment / `.env`. It
  produces a plain dict (`cfg`) and the OCI SDK `conf` (user/tenancy/
  fingerprint/region + PEM content or key file). Missing credentials raise
  `Fatal` before any API call is made.
- **`oci_network.ensure_network`** is *idempotent network bootstrapping*: it
  looks up the VCN, internet gateway and subnet by display name and reuses
  them, creating them only when missing. Route table (0.0.0.0/0 → IG) and
  security list (SSH in from the world, all traffic inside the VCN) are
  re-applied on every start, so a stateless container can always converge to
  the desired network. All created OCIDs are recorded in the state file.
- **`oci_image.pick_image`** picks the newest matching Ubuntu aarch64 image
  for the A1.Flex shape, with a preference list (24.04 → 24.04 minimal →
  22.04 → …) and a fallback to any aarch64 image.
- **`oci_instance`** wraps the launch call (`LaunchInstanceDetails` with the
  shape config, boot volume, vnic and SSH metadata), waits for the public IP
  via vnic attachments, finds pre-existing instances after restarts, and —
  most importantly — **classifies every `ServiceError`**:
  - `429` → *ratelimit*: back off (see below), keep hunting
  - "Out of host capacity" → *capacity*: the normal no-luck-yet answer, just
    wait for the next attempt
  - `QuotaExceeded` / `LimitExceeded` → *fatal*: stop, nothing will succeed
  - `5xx` → *server*: transient, keep hunting (warn on Telegram every 3rd)
- **`state.py`** has two halves: the durable JSON state file (network OCIDs
  and the caught instance, so restarts never duplicate anything) and the
  in-memory `HuntStats` — a lock-protected snapshot of the live hunt that
  the hunt loop writes and the /status thread reads.

### Backoff policy (avoiding 429s)

The hunt paces itself: one `LaunchInstance` attempt per `CHECK_EVERY_SEC`
(default 65 s) plus random jitter of −8…+15 s. When Oracle answers `429`
anyway:

1. The **`Retry-After` header** from the response is honored if present —
   the hunt sleeps at least that long.
2. Otherwise an exponential ladder kicks in: 120 s, 240 s, 480 s, capped at
   **900 s** (15 min), reset on the next non-429 answer.
3. A bogus tiny `Retry-After` can't slam the API: the wait is floored at a
   quarter of the current ladder step.

Rotating availability domains happens on the attempt count, so consecutive
tries hit different ADs even at a slow pace.

## Notes

- **Rate limits**: attempts are spaced ~65 s apart with jitter; on HTTP 429
  the script backs off exponentially (up to 15 min) and honors `Retry-After`.
  That pacing is roughly the fastest you can safely go.
- **State**: `.hunter_state.json` remembers created network resources and any
  caught instance, so restarting the container never duplicates them.
- **SSH user**: `ubuntu` for Ubuntu images.
- **Cost**: Always Free covers 4 OCPUs / 24 GB total across A1.Flex instances;
  this uses half of that. The 128 GB boot volume counts against the 200 GB
  block-storage free quota.
- Stop with Ctrl+C; run `./run.sh` again later to resume (same state file).
