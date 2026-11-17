"""Point the worker env files in the repository root at a new master (test day).

    python scripts/set_master.py http://100.x.y.z:8000

Rewrites the MASTER_URL line of every .env.for-* and .env.worker* file that has
one (the files sent to the members). .env, the master's own file, has no
MASTER_URL and is never touched. Prints each file it changed.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^MASTER_URL=.*$", re.MULTILINE)


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not args[0].startswith(("http://", "https://")):
        print("Usage: python scripts/set_master.py http://<master Tailscale IP>:8000")
        return 1
    url = args[0].rstrip("/")
    changed = 0
    for path in sorted([*root.glob(".env.for-*"), *root.glob(".env.worker*")]):
        if path.name.endswith((".bak", ".example")):
            continue
        text = path.read_text(encoding="utf-8")
        if not LINE.search(text):
            continue
        path.write_text(LINE.sub(f"MASTER_URL={url}", text), encoding="utf-8")
        print(f"{path.name}: MASTER_URL={url}")
        changed += 1
    print(f"{changed} files now point at {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
