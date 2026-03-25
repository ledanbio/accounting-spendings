"""Ждём, пока DB_HOST:DB_PORT начнёт принимать TCP (резолв имени Docker + готовность Postgres)."""
import os
import socket
import sys
import time


def main() -> None:
    host = os.environ.get("DB_HOST", "db")
    port = int(os.environ.get("DB_PORT", "5432"))
    timeout_sec = int(os.environ.get("DB_WAIT_TIMEOUT", "120"))
    deadline = time.monotonic() + timeout_sec
    last_err: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                print(f"PostgreSQL reachable at {host}:{port}", flush=True)
                return
        except OSError as e:
            last_err = e
            time.sleep(1)
    print(f"Timeout waiting for PostgreSQL at {host}:{port}: {last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
