#!/usr/bin/env python3
"""Stop swallowing chat-write failures in upsert_message_to_history's caller.

Stock `upsert_message_to_chat_by_id_and_message_id` ends with a bare
`except Exception: return None`. The streaming pipeline treats None as
"nothing to save", so a failed write erases the user's answer without a trace:
no UI update, no error event, and the background task still reports OK.

This logs the exception (with chat and message ids) before returning None.

It is idempotent: running it against an already-patched file changes nothing.

    python3 04-upsert-error-log.py /path/to/site-packages
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MARKER = "Failed to upsert message"

OLD_BLOCK = """            return updated_chat
        except Exception:
            return None

    async def delete_message_from_chat_by_id_and_message_id(self, id: str, message_id: str) -> ChatModel | None:
"""

NEW_BLOCK = """            return updated_chat
        except Exception as e:
            # Never swallow chat-write failures silently: the caller treats
            # None as "nothing to save" and the user's answer vanishes
            # without a trace (no UI update, no error, task reports OK).
            log.exception('Failed to upsert message %s to chat %s: %s', message_id, id, e)
            return None

    async def delete_message_from_chat_by_id_and_message_id(self, id: str, message_id: str) -> ChatModel | None:
"""


def main(site_packages: str) -> int:
    target = Path(site_packages) / "open_webui" / "models" / "chats.py"
    if not target.is_file():
        print(f"  FAIL: not found: {target}")
        return 1

    src = target.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already up to date — nothing to do")
        return 0

    if OLD_BLOCK not in src:
        print("  FAIL: upsert tail block not recognised — Open WebUI changed this file")
        return 1

    src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

    ast.parse(src)
    target.write_text(src, encoding="utf-8")
    print("  - upsert_message_to_chat_by_id_and_message_id now logs failures")
    print(f"  wrote {target}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
