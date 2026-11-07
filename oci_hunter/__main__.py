"""CLI entry point: python -m oci_hunter"""
import argparse
import sys

from .config import build_cfg, load_env
from .errors import Fatal
from .logging import log
from .state import HuntStats
from .telegram import TelegramClient


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Cloud free tier instance hunter")
    parser.add_argument("--once", action="store_true",
                        help="make one launch attempt and exit")
    args = parser.parse_args()
    from .hunter import run
    try:
        return run(args)
    except Fatal as exc:
        log(f"FATAL: {exc}")
        try:  # report even misconfigurations, if TG is usable
            cfg = build_cfg(load_env())
            TelegramClient(cfg, HuntStats()).send(f"⚠️ Hunter stopped: {exc}")
        except Exception:
            pass
        return 1
    except KeyboardInterrupt:
        log("stopped by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
