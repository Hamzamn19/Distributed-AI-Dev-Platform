"""Start the master: python -m dap.master

Host and port come from MASTER_HOST and MASTER_PORT in .env (default 0.0.0.0:8000).
The console shows what the master does: each task sent to which agent and worker,
its remote A2A task id, completions, failures and reassignments.
"""

import logging

import uvicorn

from dap.master.config import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # no line per status poll
    settings = get_settings()
    uvicorn.run("dap.master.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
