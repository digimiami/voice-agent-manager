"""
sms-gate device watchdog — prints an alert ONLY when the gateway device
has been offline too long. Used by a no_agent cron job: non-empty stdout
is delivered verbatim, empty stdout = silent (the watchdog pattern).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, "/root/voice-agent-manager")
from smsgate_sms import get_access_token, _headers, BASE_URL

OFFLINE_MINUTES = 30  # device heartbeats every ~15 min — 10 min false-alarms constantly
STATE_FILE = "/root/.hermes/scripts/.smsgate_state"


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(state)
    except Exception:
        pass


def main():
    try:
        import requests
        h = _headers()
        resp = requests.get(f"{BASE_URL}/3rdparty/v1/devices", headers=h, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        devices = data if isinstance(data, list) else (data.get("data") or [])
        now = datetime.datetime.now(datetime.timezone.utc)
        alerts = []
        was_offline = _load_state() == "offline"
        any_online = False
        for dev in devices:
            dev_id = dev.get("id", "?")
            name = dev.get("name", "")
            last_seen_raw = dev.get("lastSeen", "")
            if not last_seen_raw:
                alerts.append(f"⚠️ sms-gate device {dev_id} ({name}): no lastSeen — status unknown!")
                continue
            try:
                ts = datetime.datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
                age_min = (now - ts).total_seconds() / 60
                if age_min <= OFFLINE_MINUTES:
                    any_online = True
                if age_min > OFFLINE_MINUTES:
                    alerts.append(
                        f"🔴 sms-gate device {dev_id} ({name}) OFFLINE for "
                        f"{int(age_min)} min (last seen {last_seen_raw}). "
                        f"Incoming SMS are NOT being delivered — AI SMS replies are down. "
                        f"Check the device power/SIM at sms-gate.app."
                    )
            except Exception as e:
                alerts.append(f"⚠️ sms-gate device {dev_id}: bad lastSeen {last_seen_raw!r} ({e})")
        if any_online and was_offline:
            alerts.insert(0, "🟢 sms-gate device is BACK ONLINE — queued SMS should flush now. AI SMS replies resumed.")
        if alerts:
            _save_state("offline" if not any_online else "online")
            print("\n".join(alerts))
        else:
            _save_state("online")
    except Exception as e:
        print(f"⚠️ sms-gate watchdog error: {e}")


if __name__ == "__main__":
    main()
