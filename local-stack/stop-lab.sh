#!/usr/bin/env bash
# stop-lab.sh — shut the shared AI lab down (the counterpart of start-lab.sh).
#
# Double-click the "Stop AI Lab" desktop icon (or run this script) and it:
#   1. stops open-webui + llama-server,
#   2. removes the Tailscale site mapping (friends stop seeing the page),
#   3. stops the Tailscale daemon itself (graphical password prompt via pkexec).
#
# Safe to run when things are already down — every step is a no-op then.
set -u

FAIL=0

step() { echo "==> $*"; }

step "[1/3] model services"
systemctl --user stop open-webui.service llama-server.service 2>/dev/null
sleep 1
if systemctl --user is-active --quiet open-webui.service \
    || systemctl --user is-active --quiet llama-server.service; then
    echo "    ERROR: a service is still running"
    FAIL=1
else
    echo "    stopped"
fi

if [ "$FAIL" -eq 0 ]; then
    step "[2/3] unpublish from Tailscale"
    if tailscale serve reset >/dev/null 2>&1; then
        echo "    site mapping removed"
    else
        echo "    note: nothing to unpublish (daemon down?)"
    fi
fi

step "[3/3] Tailscale daemon"
if systemctl is-active --quiet tailscaled; then
    echo "    stopping tailscaled (password prompt may appear)…"
    if pkexec systemctl stop tailscaled; then
        echo "    tailscaled stopped"
    else
        echo "    Could not stop tailscaled from here."
        echo "    Run once in a terminal:  sudo systemctl stop tailscaled"
        FAIL=1
    fi
else
    echo "    tailscaled already down"
fi

echo
if [ "$FAIL" -eq 0 ]; then
    echo "    OFF — lab is fully shut down"
    command -v notify-send >/dev/null \
        && notify-send "AI Lab stopped" "Tailscale and the model are off" 2>/dev/null || true
    sleep 4
else
    read -r -p "Something needs attention — press Enter to close…"
    exit 1
fi
