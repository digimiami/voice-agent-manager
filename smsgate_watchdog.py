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

OFFLINE_MINUTES = 10


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
                if age_min > OFFLINE_MINUTES:
                    alerts.append(
                        f"🔴 sms-gate device {dev_id} ({name}) OFFLINE for "
                        f"{int(age_min)} min (last seen {last_seen_raw}). "
                        f"Incoming SMS are NOT being delivered — AI SMS replies are down. "
                        f"Check the device power/SIM at sms-gate.app."
                    )
            except Exception as e:
                alerts.append(f"⚠️ sms-gate device {dev_id}: bad lastSeen {last_seen_raw!r} ({e})")
        if alerts:
            print("\n".join(alerts))
    except Exception as e:
        print(f"⚠️ sms-gate watchdog error: {e}")


if __name__ == "__main__":
    main()
