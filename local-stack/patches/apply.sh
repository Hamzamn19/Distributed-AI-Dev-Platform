#!/usr/bin/env bash
# apply.sh — re-apply the Open WebUI source patches after an upgrade.
#
# `uv tool install --with playwright --with unstructured open-webui` downloads a
# fresh copy of the package, which silently wipes every edit made in
# site-packages. Run this afterwards and the web loader + search-depth fixes are
# back.
#
# Usage:
#   ./apply.sh                       # auto-detect site-packages
#   ./apply.sh /path/to/site-packages
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_STACK="$(dirname "$HERE")"
STAMP="$(date +%Y%m%d%H%M%S)"

if [ $# -ge 1 ]; then
    SITE_PACKAGES="$1"
else
    SITE_PACKAGES="$LOCAL_STACK/open-webui/app/lib/python3.12/site-packages"
fi

PKG="$SITE_PACKAGES/open_webui"
UTILS="$PKG/retrieval/web/utils.py"
BUILTIN="$PKG/tools/builtin.py"
TASKS="$PKG/tasks.py"
CHATS="$PKG/models/chats.py"
MAIN="$PKG/main.py"

if [ ! -f "$UTILS" ] || [ ! -f "$BUILTIN" ] || [ ! -f "$TASKS" ] || [ ! -f "$CHATS" ] || [ ! -f "$MAIN" ]; then
    echo "❌ open_webui not found under: $SITE_PACKAGES"
    echo "   Pass the site-packages directory as the first argument."
    exit 1
fi

echo "site-packages: $SITE_PACKAGES"

# ---------------------------------------------------------------------------
# 1. Web loader: real browser fingerprint, redirect following, HTML fallback
# ---------------------------------------------------------------------------
echo
echo "[1/5] web loader patch (retrieval/web/utils.py)"

if grep -q "_new_playwright_context" "$UTILS"; then
    echo "      already applied — skipping"
else
    cp "$UTILS" "$UTILS.bak.$STAMP"
    if patch --dry-run -p1 -d "$SITE_PACKAGES" < "$HERE/01-web-loader.patch" >/dev/null 2>&1; then
        patch -p1 -d "$SITE_PACKAGES" < "$HERE/01-web-loader.patch"
        echo "      applied (backup: $UTILS.bak.$STAMP)"
    else
        echo "      ❌ patch does not apply cleanly — Open WebUI changed this file."
        echo "         See docs/local-stack/MODIFICATIONS.md for the manual steps."
        rm -f "$UTILS.bak.$STAMP"
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 2. Search depth: ship full page text alongside each snippet
# ---------------------------------------------------------------------------
echo
echo "[2/5] search-depth patch (tools/builtin.py)"

if ! grep -q "_attach_page_content" "$BUILTIN"; then
    cp "$BUILTIN" "$BUILTIN.bak.$STAMP"
    echo "      backup: $BUILTIN.bak.$STAMP"
fi
python3 "$HERE/02-search-depth.py" "$SITE_PACKAGES"

# ---------------------------------------------------------------------------
# 3. Background tasks: log failures instead of vanishing silently
# ---------------------------------------------------------------------------
echo
echo "[3/5] task failure log (tasks.py)"
python3 "$HERE/03-task-failure-log.py" "$SITE_PACKAGES"

# ---------------------------------------------------------------------------
# 4. Chat writes: log upsert failures instead of returning silent None
# ---------------------------------------------------------------------------
echo
echo "[4/5] upsert error log (models/chats.py)"
python3 "$HERE/04-upsert-error-log.py" "$SITE_PACKAGES"

# ---------------------------------------------------------------------------
# 5. Model tools: fall back to model.toolIds when the client sends none
# ---------------------------------------------------------------------------
echo
echo "[5/5] model tool fallback (main.py)"
python3 "$HERE/05-model-tool-fallback.py" "$SITE_PACKAGES"

# ---------------------------------------------------------------------------
# verify all files still parse
# ---------------------------------------------------------------------------
echo
echo "verifying…"
python3 - "$UTILS" "$BUILTIN" "$TASKS" "$CHATS" <<'PY'
import ast, sys
for path in sys.argv[1:]:
    ast.parse(open(path, encoding="utf-8").read())
    print(f"  OK  {path}")
PY

echo
echo "✅ patches applied. Restart the service to pick them up:"
echo "   systemctl --user restart open-webui.service"
