#!/usr/bin/env bash
# start-lab.sh — start the local AI lab on demand.
#
# Double-click the "Start AI Lab" desktop icon (or run this script) and it:
#   1. starts llama-server + open-webui,
#   2. waits for both services to answer and prints the local URL.
#
# Safe to run when things are already up — every step is a no-op then.
set -u

LOCAL_URL="http://127.0.0.1:3000"
FAIL=0

step() { echo "==> $*"; }

step "[1/2] starting model services"
systemctl --user start llama-server.service open-webui.service
sleep 2

systemctl --user is-active --quiet llama-server.service \
    && echo "    llama-server: active" \
    || { echo "    ERROR: llama-server did not start"; FAIL=1; }

systemctl --user is-active --quiet open-webui.service \
    && echo "    open-webui: active" \
    || { echo "    ERROR: open-webui did not start"; FAIL=1; }

if [ "$FAIL" -eq 0 ]; then
    step "[2/2] health check"
    for _ in $(seq 1 30); do
        if curl -s -m 3 -o /dev/null http://127.0.0.1:3000/health \
            && curl -s -m 3 -o /dev/null http://127.0.0.1:8080/health; then
            break
        fi
        sleep 2
    done

    if curl -s -m 5 -o /dev/null "$LOCAL_URL"/; then
        echo
        echo "    READY  $LOCAL_URL"
        command -v notify-send >/dev/null \
            && notify-send "AI Lab ready" "$LOCAL_URL" 2>/dev/null || true
    else
        echo "    ERROR: services up but the local URL does not answer yet — wait a minute and retry"
        FAIL=1
    fi
fi

echo
if [ "$FAIL" -ne 0 ]; then
    read -r -p "Something failed — press Enter to close…"
    exit 1
fi
sleep 4
