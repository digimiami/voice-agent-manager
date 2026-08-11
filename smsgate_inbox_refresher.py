#!/usr/bin/env python3
"""sms-gate inbox refresher — forces the device to sync inbound SMS promptly.

The C25_Ultra device only pushes inbound SMS to the cloud (firing our webhook)
on its ~15-min heartbeat. This poller calls POST /3rdparty/v1/inbox/refresh
every 2 minutes so customer replies reach the AI engine within ~2 min instead
of up to 15+ min. Cron: */2 * * * *
"""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/voice-agent-manager")
from smsgate_sms import get_access_token, BASE_URL

def refresh():
    try:
        token = get_access_token(force=True)
        now = datetime.now(timezone.utc)
        payload = {
            "Since": (now - timedelta(hours=6)).isoformat(),
            "Until": now.isoformat(),
        }
        req = urllib.request.Request(
            BASE_URL + "/3rdparty/v1/inbox/refresh", method="POST",
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json",
                     "User-Agent": "curl/8.0"})
        resp = urllib.request.urlopen(req, timeout=60)
        print(f"[{datetime.now().isoformat()}] inbox refresh: {resp.status}")
        return resp.status == 202
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] inbox refresh ERROR: {e}")
        return False

if __name__ == "__main__":
    refresh()
