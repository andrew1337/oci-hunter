"""Configuration loading (.env + environment) and OCI client config."""

import os
from pathlib import Path

from .errors import Fatal
from .logging import log

APP_DIR = Path(__file__).resolve().parent.parent

HOWTO_OCI_KEY = (
    "Missing OCI API credentials. Generate them in the Oracle console: "
    "Profile -> My profile -> API keys -> Add API Key (generate, download the "
    "private key). Then set OCI_CLI_USER, OCI_CLI_TENANCY, OCI_CLI_FINGERPRINT "
    "and either OCI_CLI_PRIVATE_KEY (PEM with newlines as \\n) or "
    "OCI_CLI_KEY_FILE in .env. See README.md."
)


def load_env():
    """Process environment overlaid with APP_DIR/.env (env wins)."""
    env = dict(os.environ)
    env_file = APP_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            env.setdefault(key.strip(), value)
    return env


def build_cfg(env):
    cfg = {
        "user": env.get("OCI_CLI_USER", "").strip(),
        "tenancy": env.get("OCI_CLI_TENANCY", "").strip(),
        "fingerprint": env.get("OCI_CLI_FINGERPRINT", "").strip(),
        "region": env.get("OCI_CLI_REGION", "eu-amsterdam-1").strip(),
        "pem": env.get("OCI_CLI_PRIVATE_KEY", "").strip(),
        "key_file": env.get("OCI_CLI_KEY_FILE", "").strip(),
        "tg_token": env.get("TG_BOT_ID") or env.get("TG_BOT_TOKEN") or "",
        "tg_chat": env.get("TG_CHAT_ID", "").strip(),
        "shape": env.get("SHAPE", "VM.Standard.A1.Flex").strip(),
        "image_prefix": env.get(
            "IMAGE_PREFIX", "Canonical-Ubuntu-24.04-aarch64-"
        ).strip(),
        "vcn_name": env.get("VCN_NAME", "free-tier-hunter-vcn").strip(),
        "subnet_name": env.get("SUBNET_NAME", "free-tier-hunter-subnet").strip(),
        "ig_name": env.get("IG_NAME", "free-tier-hunter-ig").strip(),
        "vcn_cidr": env.get("VCN_CIDR", "10.0.0.0/16").strip(),
        "subnet_cidr": env.get("SUBNET_CIDR", "10.0.0.0/24").strip(),
        "ocpus": int(env.get("OCPU", "2")),
        "mem_gb": float(env.get("MEM_GB", "12")),
        "boot_gb": int(env.get("BOOT_GB", "100")),
        "check_every": max(40, int(env.get("CHECK_EVERY_SEC", "65"))),
        "heartbeat_every": max(1, int(env.get("HEARTBEAT_EVERY", "10"))),
        "ad_name": env.get("AVAILABILITY_DOMAIN", "").strip(),
        "ssh_pubkey": env.get("SSH_PUBKEY", "").strip(),
        "ssh_key_file": env.get("SSH_KEY_FILE", "").strip(),
        "ssh_key_hint": env.get("SSH_KEY_HINT", "").strip()
        or env.get("SSH_KEY_FILE", "").strip(),
    }
    missing = [k for k in ("user", "tenancy", "fingerprint") if not cfg[k]]
    if not cfg["pem"] and not cfg["key_file"]:
        missing.append("OCI_CLI_PRIVATE_KEY / OCI_CLI_KEY_FILE")
    if missing:
        raise Fatal(f"{HOWTO_OCI_KEY} (missing: {', '.join(missing)})")
    if cfg["key_file"]:
        kf = Path(cfg["key_file"])
        if not kf.is_absolute():
            kf = APP_DIR / kf
        if not kf.is_file():
            raise Fatal(f"OCI_CLI_KEY_FILE not found: {kf}")
        cfg["key_file"] = str(kf)
    else:
        cfg["pem"] = cfg["pem"].replace("\\n", "\n")
    if not cfg["tg_token"] or not cfg["tg_chat"]:
        log(
            "telegram not fully configured (TG_BOT_ID / TG_CHAT_ID) "
            "-- notifications disabled"
        )
    return cfg


def oci_config(cfg):
    """OCI SDK client configuration dict."""
    conf = {
        "user": cfg["user"],
        "tenancy": cfg["tenancy"],
        "fingerprint": cfg["fingerprint"],
        "region": cfg["region"],
    }
    if cfg["key_file"]:
        conf["key_file"] = cfg["key_file"]
    else:
        conf["key_content"] = cfg["pem"]
    return conf
