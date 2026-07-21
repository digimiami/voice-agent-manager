#!/usr/bin/env python3
"""Follow-up sequence processor - call every 15 min via cron."""
import sys
sys.path.insert(0, '/root/voice-agent-manager')
from premium_features2 import process_followups
processed = process_followups()
print(f"Processed {processed} follow-up sequences")
