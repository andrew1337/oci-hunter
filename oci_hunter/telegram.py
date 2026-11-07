"""Telegram notifications and the owner-only /status command.

Sending is fire-and-forget: Telegram problems must never kill the hunt.
The status poller long-polls getUpdates in a background thread and only
ever replies to the chat configured via TG_CHAT_ID; messages from any
other chat are ignored (acked but not answered).
"""

import json
import threading
import urllib.parse
import urllib.request

from .logging import log, fmt_uptime


class TelegramClient:
    def __init__(self, cfg, stats):
        self.token = cfg["tg_token"]
        self.chat_id = cfg["tg_chat"]
        self.stats = stats  # HuntStats from state.py
        self.state_file_note = ""  # filled by hunter for caught-instance info
        self._poll_thread = None
        self._stop = threading.Event()

    # ------------------------------------------------------------- send ----

    def send(self, text, silent=False):
        if not self.token or not self.chat_id:
            return
        body = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_notification": silent,
            }
        ).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as exc:  # never let TG problems kill the hunt
            log(f"telegram send failed: {exc}")

    # ------------------------------------------------------- /status -------

    def start_status_poller(self):
        """Start the daemon thread that answers /status (owner chat only)."""
        if not self.token or not self.chat_id or self._poll_thread:
            return
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="tg-status", daemon=True
        )
        self._poll_thread.start()

    def stop_status_poller(self):
        self._stop.set()

    def _api(self, method, **params):
        data = json.dumps(params).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = json.loads(resp.read())
        if not payload.get("ok"):
            raise RuntimeError(f"telegram {method}: {payload}")
        return payload["result"]

    def _poll_loop(self):
        offset = 0
        while not self._stop.is_set():
            try:
                updates = self._api(
                    "getUpdates", offset=offset, timeout=25, allowed_updates=["message"]
                )
            except Exception as exc:
                if not self._stop.is_set():
                    log(f"telegram getUpdates failed: {exc}")
                    self._stop.wait(10)
                continue
            for upd in updates:
                offset = max(offset, upd["update_id"] + 1)  # ack everything
                msg = upd.get("message") or {}
                # owner-only: never reply to anyone else
                if str((msg.get("chat") or {}).get("id")) != str(self.chat_id):
                    continue
                text = (msg.get("text") or "").strip()
                if text.split("@")[0].lower() in ("/status", "/status@"):
                    try:
                        self.send(self._status_text())
                    except Exception as exc:
                        log(f"telegram /status reply failed: {exc}")

    def _status_text(self):
        snap = self.stats.snapshot()
        lines = ["🐾 Hunter status"]
        if snap["uptime"] is not None:
            lines.append(f"uptime: {fmt_uptime(snap['uptime'])}")
        lines.append(f"attempts: {snap['attempts']}")
        if snap["ad"]:
            lines.append(f"current AD: {snap['ad']}")
        if snap["backoff"]:
            lines.append(f"backoff: {snap['backoff']}")
        if snap["last_error"]:
            lines.append(f"last error: {snap['last_error']}")
        if not hasattr(self, "_instance_info"):
            self._instance_info = self._load_instance_info()
        if self._instance_info:
            lines.append(f"instance: {self._instance_info}")
        return "\n".join(lines)

    @staticmethod
    def _load_instance_info():
        from .state import load_state

        inst = load_state().get("instance")
        if not inst:
            return None
        return f"{inst.get('ad', '?')}  ip {inst.get('public_ip') or '?'}"
