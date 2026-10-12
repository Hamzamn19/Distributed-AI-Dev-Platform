"""Worker Agent: the same program runs on six PCs; only the .env file differs.

Owner: Eray - card S1-07.

Run from the repository root:
    python -m dap.worker.main

Sprint 1 behaviour (no LLM call yet):
1. Read the settings (dap.worker.config.get_settings()).
2. Register with the master. While the master is unreachable, wait a few
   seconds and try again instead of exiting.
3. Send a heartbeat every HEARTBEAT_INTERVAL_SEC with status "idle".
   If the master answers 404, register again.
4. Stop cleanly on Ctrl+C.

Sprint 3 adds the task loop (ask for a task every POLL_INTERVAL_SEC, run it
with the local LLM, send the result).
"""


def main() -> None:
    raise NotImplementedError("S1-07: implement the worker loop")


if __name__ == "__main__":
    main()
