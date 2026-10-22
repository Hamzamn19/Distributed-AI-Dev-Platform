"""Start the master: python -m dap.master

Host and port come from MASTER_HOST and MASTER_PORT in .env (default 0.0.0.0:8000).
"""

import uvicorn

from dap.master.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("dap.master.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
