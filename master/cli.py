"""Quick test helper for the Master Agent (stdlib only, no extra install).

    python cli.py register [--once]     register sample agents (backend, frontend, devops)
    python cli.py status                list agents and system state
    python cli.py project [file]        submit a requirement and print the task table
    python cli.py demo [library|todo|shop]  register agents, submit a sample, show status

DAP_TOKEN, DAP_URL (default http://localhost:<DAP_PORT or 8000>) and OLLAMA_BASE_URL
are read from master/.env; real environment variables take precedence.
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REQUIREMENT = (
    "Bir kütüphane yönetim sistemi geliştir. Kullanıcılar kitap arayabilmeli, ödünç alabilmeli "
    "ve iade edebilmeli. Yöneticiler kitap ekleyip silebilmeli ve gecikmiş iadeleri "
    "görebilmeli. Veriler bir veritabanında tutulmalı, bir REST API ve web arayüzü olmalı."
)

SAMPLE_AGENTS = [
    {"agent_id": "backend", "model": "llama3.1:8b", "coding": 90, "reasoning": 85,
     "context": 95, "context_window": 128000, "specialties": ["backend", "database", "testing"]},
    {"agent_id": "frontend", "model": "deepseek-coder:6.7b", "coding": 95, "reasoning": 70,
     "context": 80, "context_window": 16000, "specialties": ["frontend", "documentation"]},
    {"agent_id": "devops", "model": "mistral:7b", "coding": 75, "reasoning": 90,
     "context": 85, "context_window": 32000,
     "specialties": ["integration", "review", "analysis"]},
]
DEMO_DIR = Path(__file__).resolve().parent / "demo"


def load_env() -> None:
    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env()
BASE_URL = os.getenv("DAP_URL", f"http://localhost:{os.getenv('DAP_PORT', '8000')}").rstrip("/")
TOKEN = os.getenv("DAP_TOKEN", "")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


class CliError(Exception):
    pass


def call(method: str, path: str, body: dict = None, timeout: float = 15) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers={
        "X-DAP-Token": TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 401:
            raise CliError("401: DAP_TOKEN sunucudakiyle uyuşmuyor (master/.env kontrol edin)")
        raise CliError(f"{exc.code} {path}: {detail}")
    except (urllib.error.URLError, OSError) as exc:
        raise CliError(f"Sunucuya ulaşılamadı ({BASE_URL}): {exc}. "
                       "Önce 'python main.py' ile başlatın.")


def table(headers: list, rows: list) -> None:
    cells = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def cmd_register(args: argparse.Namespace) -> None:
    for agent in SAMPLE_AGENTS:
        call("POST", "/agents/register", agent)
        print(f"[REGISTER] {agent['agent_id']:<9} {agent['model']:<20} "
              f"C={agent['coding']} R={agent['reasoning']} X={agent['context']} "
              f"uzmanlık={','.join(agent['specialties'])}")
    if args.once:
        print("Not: heartbeat gönderilmezse ajanlar 30 sn sonra offline olur.")
        return
    print("Heartbeat her 10 sn gönderiliyor (durdurmak için Ctrl+C)...")
    try:
        while True:
            time.sleep(10)
            for agent in SAMPLE_AGENTS:
                call("POST", f"/agents/{agent['agent_id']}/heartbeat")
            print(f"[HEARTBEAT] {time.strftime('%H:%M:%S')} "
                  f"{', '.join(a['agent_id'] for a in SAMPLE_AGENTS)} canlı")
    except KeyboardInterrupt:
        print("\nDurduruldu; ajanlar 30 sn içinde offline olacak.")


def ollama_state() -> str:
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as resp:
            models = [m["name"] for m in json.loads(resp.read().decode()).get("models", [])]
        return f"çalışıyor ({OLLAMA_URL}; modeller: {', '.join(models) or '-'})"
    except (urllib.error.URLError, OSError, ValueError):
        return f"ulaşılamıyor ({OLLAMA_URL}); proje için yedek şablon kullanılır"


def cmd_status(_: argparse.Namespace) -> None:
    agents = call("GET", "/agents")["agents"]
    online = sum(1 for a in agents if a["status"] == "online")
    print(f"Master Agent : çalışıyor ({BASE_URL})")
    print(f"Ollama       : {ollama_state()}")
    print(f"Ajanlar      : {len(agents)} kayıtlı, {online} online, {len(agents) - online} offline\n")
    if agents:
        table(["AGENT", "DURUM", "MODEL", "C", "R", "X", "KUYRUK", "UZMANLIK", "SON HEARTBEAT"],
              [[a["agent_id"], a["status"], a["model"], f"{a['coding']:g}", f"{a['reasoning']:g}",
                f"{a['context']:g}", a["queue_length"], ",".join(a["specialties"]) or "-",
                a["last_heartbeat"].replace("T", " ")[:19]] for a in agents])


def cmd_project(args: argparse.Namespace) -> None:
    if args.file:
        requirement = Path(args.file).read_text(encoding="utf-8")
    else:
        requirement = DEFAULT_REQUIREMENT
        print("Doküman verilmedi, yerleşik kütüphane gereksinimi kullanılıyor.")
    print("Proje gönderiliyor; Llama 3.1 görevi bölüyor (30-60 sn sürebilir)...\n")
    p = call("POST", "/projects", {"requirement": requirement,
                                   "allow_fallback": not args.no_fallback}, timeout=300)
    print(f"{p['project_id']}  {p['name']}  (kaynak: {p['source']}, "
          f"contract {p.get('contract_version', '-')})")
    if p.get("summary"):
        print(p["summary"])
    print()
    table(["GÖREV", "TİP", "BAŞLIK", "AJAN", "SKOR", "DURUM", "BAĞIMLILIK"],
          [[t["task_id"], t["task_type"], t["title"][:45], t["assigned_agent"] or "-",
            "-" if t["score"] is None else f"{t['score']:.1f}", t["status"],
            ",".join(t["depends_on"]) or "-"] for t in p["tasks"]])
    pending = sum(1 for t in p["tasks"] if t["status"] == "pending")
    print(f"\n{len(p['tasks'])} görev, {len(p['tasks']) - pending} atandı.")
    if pending:
        print("Uyarı: online ajan yok. Önce 'python cli.py register' çalıştırın.")


def cmd_demo(args: argparse.Namespace) -> None:
    samples = sorted(p.stem for p in DEMO_DIR.glob("*.md"))
    if args.name not in samples:
        raise CliError(f"Bilinmeyen örnek '{args.name}'. Seçenekler: {', '.join(samples)}")
    print("== 1/3 Örnek ajanlar kaydediliyor ==")
    cmd_register(argparse.Namespace(once=True))
    print(f"\n== 2/3 Örnek proje gönderiliyor: demo/{args.name}.md ==")
    stop = threading.Event()

    def keep_alive() -> None:  # the LLM call can outlast the 30 s heartbeat timeout
        while not stop.wait(5):
            for agent in SAMPLE_AGENTS:
                try:
                    call("POST", f"/agents/{agent['agent_id']}/heartbeat")
                except CliError:
                    pass

    threading.Thread(target=keep_alive, daemon=True).start()
    try:
        cmd_project(argparse.Namespace(file=str(DEMO_DIR / f"{args.name}.md"),
                                       no_fallback=args.no_fallback))
    finally:
        stop.set()
    print("\n== 3/3 Sistem durumu ==")
    cmd_status(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Master Agent test CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="örnek ajanları kaydet")
    reg.add_argument("--once", action="store_true", help="kaydet ve çık (heartbeat gönderme)")
    reg.set_defaults(func=cmd_register)
    sub.add_parser("status", help="ajanları ve sistem durumunu göster").set_defaults(
        func=cmd_status)
    proj = sub.add_parser("project", help="proje gönder, görev tablosunu bas")
    proj.add_argument("file", nargs="?", help="gereksinim dosyası (yoksa yerleşik örnek)")
    proj.add_argument("--no-fallback", action="store_true", help="Ollama yoksa hata ver")
    proj.set_defaults(func=cmd_project)
    demo = sub.add_parser("demo", help="ajanları kaydet, örnek proje gönder, durumu göster")
    demo.add_argument("name", nargs="?", default="library", help="library (varsayılan), todo, shop")
    demo.add_argument("--no-fallback", action="store_true", help="Ollama yoksa hata ver")
    demo.set_defaults(func=cmd_demo)
    args = parser.parse_args()
    try:
        args.func(args)
    except CliError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
