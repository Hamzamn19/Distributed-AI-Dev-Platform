# local-stack

The whole Gemma chat setup, in one folder: model, inference server, chat
interface, its settings, and the one folder the model is allowed to edit.

Design and rationale live in [`docs/local-stack/MODIFICATIONS.md`](../docs/local-stack/MODIFICATIONS.md).

## What is in here

```
local-stack/
├── models/                 # GGUF weights              (git-ignored, ~17 GB)
├── llama.cpp/              # llama-server + CUDA libs  (git-ignored, 1.4 GB)
├── open-webui/
│   ├── app/                # the Open WebUI install    (git-ignored, 7.6 GB)
│   └── data/               # webui.db: chats, model settings, tool, permissions
├── project-files/          # the ONLY folder the model may read or edit
├── systemd/                # committed copies of the two units
├── patches/                # source patches + apply.sh
├── start-lab.sh            # on-demand starter (desktop icon runs this)
├── env/open-webui.env      # annotated copy of the service environment
└── setup.sh                # idempotent: restores every setting and restarts
```

## Daily use

Nothing starts at boot. Two desktop icons run `start-lab.sh` / `stop-lab.sh`:

- **Start AI Lab**: starts Tailscale (password prompt if needed), the two model
  services, re-publishes the Tailscale URL, and prints when it is ready.
- **Stop AI Lab**: stops both services, removes the site mapping so the page
  goes dark for friends, then stops Tailscale itself.

```bash
systemctl --user status llama-server open-webui   # health
tailscale status                                  # who is on the tailnet
```

Open: **<https://hamzah.tail983031.ts.net/>**

## After changing something

```bash
cd local-stack
./setup.sh
```

Restores the systemd units, the web-search config, the `project_files` tool, and
the model settings, then restarts both services. Safe to run repeatedly.

## After upgrading Open WebUI

An upgrade re-downloads the package and discards the source patches.

```bash
uv tool install --python 3.12 --with playwright --with unstructured open-webui
python3 -m playwright install chromium

cd local-stack
./patches/apply.sh    # put all five source patches back
./setup.sh            # restore every setting and restart
```

## Giving the friend access

1. Invite them: <https://login.tailscale.com/admin/users> → **Users → Invite**.
2. They install Tailscale and sign in with the invitation.
3. They open the URL above. There is **no login page** — everyone on the tailnet
   shares the same admin identity.

Only tailnet members can reach the URL. Open WebUI binds `127.0.0.1` and
llama-server binds `127.0.0.1`, so nothing is exposed to the wider network.

## Where the model may work

`local-stack/project-files/` only. The model has no shell and no access to
anything outside that folder — path escapes are rejected by the tool itself, and
there are 6 escape tests recorded in the modifications doc.

## Machine specs

See [`docs/hardware.md`](../docs/hardware.md).
