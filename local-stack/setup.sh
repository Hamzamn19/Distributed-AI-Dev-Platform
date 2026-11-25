#!/usr/bin/env bash
# setup.sh — put the Gemma stack into its configured state.
#
# Safe to run repeatedly: every step is idempotent. Run it after a fresh clone,
# after an Open WebUI upgrade, or whenever something looks unset.
#
# What it does:
#   1. installs the systemd units from local-stack/systemd/
#   2. writes the web-search / web-loader settings into the database
#   3. creates (or refreshes) the project_files tool
#   4. attaches the tool and web-search defaults to the model
#   5. repairs model ids if the model file has moved
#   6. restarts both services
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
LS="$HERE"
DATA="$LS/open-webui/data"
DB="$DATA/webui.db"
UNITS_SRC="$LS/systemd"
UNITS_DST="$HOME/.config/systemd/user"
PROJECT_FILES="$LS/project-files"
BIN="$LS/open-webui/app/bin"

MODEL_PATH="$LS/models/gemma4-26b-a4b/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf"

echo "repo        : $REPO"
echo "data dir    : $DATA"
echo "model       : $MODEL_PATH"

# ---------------------------------------------------------------- 1. units
echo
echo "[1/6] systemd units"
mkdir -p "$UNITS_DST"
for unit in llama-server.service open-webui.service; do
    if [ -f "$UNITS_SRC/$unit" ]; then
        if cmp -s "$UNITS_SRC/$unit" "$UNITS_DST/$unit" 2>/dev/null; then
            echo "  = $unit already current"
        else
            cp "$UNITS_SRC/$unit" "$UNITS_DST/$unit"
            echo "  + $unit installed"
        fi
    fi
done
systemctl --user daemon-reload

# --------------------------------------------------------------- 2. settings
echo
echo "[2/6] web search / web loader settings"
python3 - "$DB" <<'PY'
import json, sqlite3, sys, time
db = sys.argv[1]
want = {
    # ship real browser traffic so protected sites answer instead of 403
    "web.loader.engine": "playwright",
    "web.loader.playwright_timeout": 30000,
    # wider net, and each fetched page is capped so a single result cannot flood
    # the context window
    "web.search.result_count": 12,
    "web.fetch.max_content_length": 20000,
    # the query generator emits several queries per question — run them together
    "web.search.concurrent_requests": 6,
}
con = sqlite3.connect(db, timeout=20)
con.execute("PRAGMA busy_timeout=20000")
now = int(time.time())
for k, v in want.items():
    con.execute(
        "INSERT INTO config(key,value,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (k, json.dumps(v), now),
    )
con.commit()
for k in want:
    raw = con.execute("SELECT value FROM config WHERE key=?", (k,)).fetchone()[0]
    # SQLite gives numeric config values back as int/float rather than text
    got = json.loads(raw) if isinstance(raw, str) else raw
    flag = "OK " if got == want[k] else "!! "
    print(f"  {flag}{k} = {got!r}")
con.close()
PY

# ------------------------------------------------------------------ 3. tool
echo
echo "[3/6] tools (project_files + deep_search)"
if [ ! -d "$PROJECT_FILES" ]; then
    mkdir -p "$PROJECT_FILES"
    echo "# AI Project Folder" > "$PROJECT_FILES/README.md"
    echo "  created $PROJECT_FILES/README.md"
fi
python3 - "$DB" "$PROJECT_FILES" "$LS" <<'PY'
import pathlib, sqlite3, sys, time
db, project_root, local_stack = sys.argv[1], sys.argv[2], sys.argv[3]

con = sqlite3.connect(db, timeout=20)
con.execute("PRAGMA busy_timeout=20000")

# --- project_files: keep PROJECT_ROOT pointing at this machine's folder -----
row = con.execute("SELECT content FROM tool WHERE id='project_files'").fetchone()
if row:
    content = row[0]
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("PROJECT_ROOT"):
            lines[i] = f'PROJECT_ROOT = "{project_root}"'
    new = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
    if new != content:
        con.execute(
            "UPDATE tool SET content=?, updated_at=? WHERE id='project_files'",
            (new, int(time.time())),
        )
        con.commit()
        print(f"  = PROJECT_ROOT -> {project_root}")
    else:
        print("  = project_files already correct")
else:
    print("  ! project_files row missing — create it in Workspace > Tools, then re-run")

# --- deep_search: local-stack/tools/deep_search.py is the source of truth ----
src = pathlib.Path(local_stack) / "tools" / "deep_search.py"
if not src.is_file():
    print("  ! tools/deep_search.py not found")
else:
    wanted = src.read_text()
    row = con.execute("SELECT content FROM tool WHERE id='deep_search'").fetchone()
    if row is None:
        print("  ! deep_search row missing — POST /api/v1/tools/create with tools/deep_search.py")
    elif row[0] != wanted:
        con.execute(
            "UPDATE tool SET content=?, updated_at=? WHERE id='deep_search'",
            (wanted, int(time.time())),
        )
        con.commit()
        print("  = deep_search content synced from tools/deep_search.py")
    else:
        print("  = deep_search already current")
con.close()
PY

# ---------------------------------------------------------------- 4. model
echo
echo "[4/6] model defaults (web search on, project_files attached)"
python3 - "$DB" "$MODEL_PATH" <<'PY'
import sqlite3, sys, json, time
db, model_path = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db, timeout=20)
con.execute("PRAGMA busy_timeout=20000")

row = con.execute("SELECT id, params, meta FROM model ORDER BY created_at DESC").fetchone()
if not row:
    print("  ! no model row — start llama-server once so Open WebUI registers it")
    raise SystemExit(0)

mid, params, meta = row
meta = json.loads(meta) if meta else {}

changed = []
if mid != model_path:
    changed.append(f"id {mid} -> {model_path}")
    con.execute("UPDATE model SET id=? WHERE id=?", (model_path, mid))
    con.execute("UPDATE access_grant SET resource_id=? WHERE resource_id=?", (model_path, mid))
    con.execute("UPDATE chat_message SET model_id=? WHERE model_id=?", (model_path, mid))
    con.execute("UPDATE chat SET chat=replace(chat, ?, ?) WHERE chat LIKE ?",
                (mid, model_path, f"%{mid}%"))

# Attach every tool that exists, so creating one never leaves it orphaned.
tool_ids = [r[0] for r in con.execute("SELECT id FROM tool ORDER BY id")]
if meta.get("toolIds") != tool_ids:
    meta["toolIds"] = tool_ids
    changed.append(f"toolIds = {tool_ids}")
if meta.get("defaultFeatureIds") != ["web_search"]:
    meta["defaultFeatureIds"] = ["web_search"]; changed.append("defaultFeatureIds = ['web_search']")
if (meta.get("capabilities") or {}).get("web_search") is not True:
    meta["capabilities"] = {**(meta.get("capabilities") or {}), "web_search": True}
    changed.append("capabilities.web_search = True")

con.execute("UPDATE model SET meta=? WHERE id=?", (json.dumps(meta), model_path))
con.commit()

if changed:
    for c in changed: print(f"  + {c}")
else:
    print("  = model already configured")
print(f"  params: {params}")
con.close()
PY

# ------------------------------------------------------ 5. runtime listeners
echo
echo "[5/6] start services"
systemctl --user enable --now llama-server.service >/dev/null 2>&1 || true
systemctl --user enable --now open-webui.service   >/dev/null 2>&1 || true
systemctl --user restart llama-server.service
systemctl --user restart open-webui.service

for i in $(seq 1 40); do
    ok1=$(curl -s -o /dev/null -w "%{http_code}" -m 3 http://127.0.0.1:8080/health 2>/dev/null || echo 000)
    ok2=$(curl -s -o /dev/null -w "%{http_code}" -m 3 http://127.0.0.1:3000/api/version 2>/dev/null || echo 000)
    [ "$ok1" = "200" ] && [ "$ok2" = "200" ] && break
    sleep 3
done
echo "  llama-server  :8080 = $ok1"
echo "  open-webui    :3000 = $ok2"

# --------------------------------------------------------------- 6. report
echo
echo "[6/6] summary"
systemctl --user is-active llama-server.service open-webui.service | paste -d' ' - - | sed 's/^/  services: /'
echo "  public URL   : https://hamzah.tail983031.ts.net/"
echo "  project files: $PROJECT_FILES"
echo
echo "✅ done. Web search and the file tools are enabled by default."
