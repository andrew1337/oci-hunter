"""The hunt loop: setup, launch attempts, backoff, notifications."""

import random
import time
from datetime import datetime

from oci.exceptions import ServiceError
from oci.core import ComputeClient, VirtualNetworkClient
from oci.identity import IdentityClient

from .config import build_cfg, load_env, oci_config
from .errors import Fatal
from .logging import log, fmt_uptime
from .oci_image import pick_image
from .oci_instance import (
    classify_error,
    find_existing_instance,
    launch_instance,
    load_pubkey,
    retry_after_seconds,
    wait_public_ip,
)
from .oci_network import ensure_network
from .state import load_state, save_state, HuntStats
from .telegram import TelegramClient

# 429 backoff ladder: 120s, 240s, 480s, then capped at 900s.
RL_BASE = 120
RL_CAP = 900


def run(args):
    cfg = build_cfg(load_env())  # may raise Fatal

    conf = oci_config(cfg)
    try:
        identity = IdentityClient(conf)
        ads_all = identity.list_availability_domains(cfg["tenancy"]).data
        compute = ComputeClient(conf)
        vnet = VirtualNetworkClient(conf)
    except Exception as exc:
        raise Fatal(f"could not initialise OCI clients / authenticate: {exc}")

    log(f"region {cfg['region']}, ADs: {[a.name for a in ads_all]}")

    if cfg["ad_name"]:
        ads = [a.name for a in ads_all if cfg["ad_name"].lower() in a.name.lower()]
        if not ads:
            raise Fatal(
                f"availability domain matching '{cfg['ad_name']}' not found; "
                f"available: {[a.name for a in ads_all]}"
            )
    else:
        ads = [a.name for a in ads_all]

    stats = HuntStats()
    tg = TelegramClient(cfg, stats)
    stop = tg.hunt_stop  # /stop sets this; the hunt loop obeys it

    tg.send(
        f"🐾 Hunt started: {cfg['region']}, {cfg['shape']} "
        f"{cfg['ocpus']} OCPU / {cfg['mem_gb']:.0f} GB, "
        f"boot {cfg['boot_gb']} GB, ~{cfg['check_every']}s per attempt"
    )
    tg.start_status_poller()

    try:
        subnet_id = ensure_network(vnet, cfg)
        image = pick_image(compute, cfg["tenancy"], cfg["image_prefix"])
        log(f"image: {image.display_name}")
    except ServiceError as exc:
        raise Fatal(f"setup failed: {exc.status} {exc.code}: {exc.message}")
    pubkey = load_pubkey(cfg)

    existing = find_existing_instance(compute, cfg["tenancy"])
    if existing:
        ip = wait_public_ip(compute, vnet, cfg["tenancy"], existing.id, timeout=120)
        log(
            f"instance already exists ({existing.lifecycle_state}), "
            f"ocid {existing.id}"
        )
        tg.send(
            f"🎉 Instance '{'free-tier-hunter'}' already exists "
            f"({existing.lifecycle_state}).\n"
            f"ssh -i {cfg['ssh_key_hint'] or '<key>'} ubuntu@{ip or '<no public ip yet>'}"
        )
        return 0

    log(
        f"hunting: {cfg['shape']} {cfg['ocpus']} OCPU / {cfg['mem_gb']:.0f} GB "
        f"in {len(ads)} AD(s), image {image.display_name}"
    )
    stats.start()
    started = time.monotonic()
    attempt = 0
    server_streak = 0
    rl_streak = 0
    while True:
        if stop.is_set():
            log("hunt stopped via /stop")
            return 0
        attempt += 1
        ad = ads[(attempt - 1) % len(ads)]
        ad_short = ad.split(":")[-1]
        stats.record_attempt(ad_short)
        try:
            inst = launch_instance(compute, cfg, ad, subnet_id, image.id, pubkey)
        except ServiceError as exc:
            kind = classify_error(exc)
            err = f"{exc.status} {exc.code}: {(exc.message or '')[:140]}"
            log(f"attempt #{attempt} @ {ad_short} → {err}")
            if kind == "fatal":
                raise Fatal(f"{exc.status} {exc.code}: {exc.message}")
            if kind == "ratelimit":
                rl_streak += 1
                ladder = min(RL_BASE * 2 ** (rl_streak - 1), RL_CAP)
                wait_s = max(retry_after_seconds(exc, default=ladder), ladder // 4)
                header = "Retry-After" if wait_s != ladder else "ladder"
                log(f"rate limited — sleeping {wait_s}s ({header})")
                stats.record_result(
                    error="429 " + err,
                    backoff=f"{wait_s}s (429 x{rl_streak}, {header})",
                )
                if stop.wait(wait_s):
                    log("hunt stopped via /stop")
                    return 0
                if args.once:
                    return 1
                continue
            rl_streak = 0
            stats.record_result(error=err)
            if kind == "server":
                server_streak += 1
                if server_streak % 3 == 0:
                    tg.send(
                        f"⚠️ {server_streak} server errors in a row, "
                        f"still retrying (last: {exc.status} "
                        f"{exc.code}: {(exc.message or '')[:120]})"
                    )
            if args.once:
                return 1
        except Exception as exc:  # transient (DNS, TLS, proxy, ...)
            rl_streak = 0
            log(
                f"attempt #{attempt} @ {ad_short} → unexpected error, "
                f"retrying: {exc}"
            )
            stats.record_result(error=f"unexpected: {exc}")
            if args.once:
                return 1
        else:
            server_streak = 0
            rl_streak = 0
            log(f"🎉 attempt #{attempt} @ {ad_short} → launched! " f"ocid {inst.id}")
            try:
                ip = wait_public_ip(
                    compute, vnet, cfg["tenancy"], inst.id, stop_event=stop
                )
            except Exception as exc:
                log(f"public ip lookup failed: {exc}")
                ip = None
            state = load_state()
            state["instance"] = {
                "ocid": inst.id,
                "ad": ad,
                "public_ip": ip,
                "launched_at": datetime.now().isoformat(),
            }
            save_state(state)
            tg.send(
                f"🎉 Got it!\n"
                f"{cfg['shape']} {cfg['ocpus']} OCPU / "
                f"{cfg['mem_gb']:.0f} GB in {ad_short}\n"
                f"public IP: {ip or 'not assigned yet (check console)'}\n"
                f"ssh -i {cfg['ssh_key_hint'] or '<key>'} ubuntu@{ip or '<ip>'}"
            )
            return 0
        if attempt % cfg["heartbeat_every"] == 0:
            uptime = fmt_uptime(time.monotonic() - started)
            tg.send(f"Still hunting: {attempt} attempts, uptime {uptime}", silent=True)
            log(f"heartbeat: {attempt} attempts, uptime {uptime}")
        stats.record_result()  # capacity error: clear backoff display
        if stop.wait(cfg["check_every"] + random.uniform(-8, 15)):
            log("hunt stopped via /stop")
            return 0
