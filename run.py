"""One-step launcher: starts the Master Agent backend and the Streamlit dashboard together.

    python run.py              # backend :8000 + dashboard :8501, opens the browser
    python run.py --no-browser

Uses the project's .venv when present. Ctrl+C stops both.
"""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "master"
DASH_PORT = int(os.getenv("DASH_PORT", "8501"))


def read_env() -> dict:
    env = {}
    path = MASTER / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    return env


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def backend_up(url: str) -> bool:
    try:
        urllib.request.urlopen(url + "/openapi.json", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True  # 401 etc. still means the server answers
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Master Agent + dashboard")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    env = {**os.environ, **{k: v for k, v in read_env().items() if k not in os.environ}}
    port = int(env.get("DAP_PORT", "8000"))
    url = f"http://localhost:{port}"
    venv_python = ROOT / ".venv" / "bin" / "python"
    python = str(venv_python if venv_python.exists() else sys.executable)

    for name, p in (("Backend", port), ("Dashboard", DASH_PORT)):
        if port_in_use(p):
            print(f"Hata: {name} portu {p} zaten kullanımda. Eski süreci kapatın "
                  f"(örn. lsof -ti :{p} | xargs kill) ve tekrar deneyin.")
            return 1
    if not env.get("DAP_TOKEN"):
        print("Hata: master/.env içinde DAP_TOKEN yok (.env.example dosyasını kopyalayın).")
        return 1

    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    procs = []
    try:
        print(f"[1/2] Backend başlıyor ({url}) ...")
        procs.append(subprocess.Popen([python, "main.py"], cwd=MASTER, env=env))
        for _ in range(60):
            if procs[0].poll() is not None:
                print("Hata: backend başlamadan kapandı, yukarıdaki çıktıya bakın.")
                return 1
            if backend_up(url):
                break
            time.sleep(0.5)
        else:
            print("Hata: backend 30 sn içinde cevap vermedi.")
            return 1

        print(f"[2/2] Dashboard başlıyor (http://localhost:{DASH_PORT}) ...")
        procs.append(subprocess.Popen(
            [python, "-m", "streamlit", "run", "app.py", "--server.port", str(DASH_PORT),
             "--server.headless", "true"], cwd=MASTER, env=env))
        for _ in range(60):
            if procs[1].poll() is not None:
                print("Hata: dashboard başlamadan kapandı.")
                return 1
            if port_in_use(DASH_PORT):
                break
            time.sleep(0.5)
        if not args.no_browser:
            webbrowser.open_new_tab(f"http://localhost:{DASH_PORT}")
        print("\nHazır. Durdurmak için Ctrl+C.\n")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print("Bir süreç kapandı, diğeri de durduruluyor.")
        return 1
    except KeyboardInterrupt:
        print("\nDurduruluyor...")
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
