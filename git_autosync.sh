#!/bin/bash
# Auto-commit + push every change in /root/voice-agent-manager to GitHub.
# Runs from cron; logs to /var/log/diazites-git-autosync.log. Retries push on next run if it fails.
LOG=/var/log/diazites-git-autosync.log
REPO=/root/voice-agent-manager
export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new -i /root/.ssh/id_ed25519"

cd "$REPO" || exit 1
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "autosync: $(date '+%Y-%m-%d %H:%M:%S UTC')"
  echo "$(date '+%F %T') committed pending changes" >> "$LOG"
fi
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if [ "${AHEAD:-0}" -gt 0 ]; then
  if git push -q origin main; then
    echo "$(date '+%F %T') pushed $AHEAD commit(s) to GitHub" >> "$LOG"
  else
    echo "$(date '+%F %T') PUSH FAILED ($AHEAD commit(s) pending, retry next run)" >> "$LOG"
  fi
fi
