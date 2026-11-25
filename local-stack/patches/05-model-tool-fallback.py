#!/usr/bin/env python3
"""Fall back to the model's own toolIds when the client sends none.

Stock `chat_completion` takes `tool_ids` only from the request. The web UI
keeps tool selection as per-chat composer state, so a fresh chat can arrive
with no `tool_ids` key at all — and the model then truthfully reports it has
no web/file tools, even though the admin attached them to the model.

On this shared single-purpose box the model's toolIds ARE the policy ("web
search on, file tool attached"), so when the key is absent we substitute the
model's list. An explicit empty list still means "no tools" and is respected.

It is idempotent: running it against an already-patched file changes nothing.

    python3 05-model-tool-fallback.py /path/to/site-packages
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MARKER = "MODEL_TOOL_FALLBACK"

OLD_BLOCK = """                'tool_approval_mode': tool_approval_mode,
            },
        }
"""

NEW_BLOCK = """                'tool_approval_mode': tool_approval_mode,
            },
        }

        # MODEL_TOOL_FALLBACK: honour the model's own toolIds when the client
        # did not name any. A missing key means "client didn't say"; an
        # explicit [] still disables tools.
        if metadata.get('tool_ids') is None:
            _model_tool_ids = ((model.get('info') or {}).get('meta') or {}).get('toolIds') or []
            if _model_tool_ids:
                metadata['tool_ids'] = list(_model_tool_ids)
                form_data['tool_ids'] = list(_model_tool_ids)
"""


def main(site_packages: str) -> int:
    target = Path(site_packages) / "open_webui" / "main.py"
    if not target.is_file():
        print(f"  FAIL: not found: {target}")
        return 1

    src = target.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already up to date — nothing to do")
        return 0

    if OLD_BLOCK not in src:
        print("  FAIL: metadata block not recognised — Open WebUI changed this file")
        return 1

    src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

    ast.parse(src)
    target.write_text(src, encoding="utf-8")
    print("  - chat_completion falls back to model.toolIds when tool_ids absent")
    print(f"  wrote {target}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
