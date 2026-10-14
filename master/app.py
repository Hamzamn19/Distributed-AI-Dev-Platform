"""Master Agent dashboard (Streamlit). Talks to the FastAPI backend.

Run from master/:   streamlit run app.py
DAP_TOKEN and DAP_URL (default http://localhost:8000) are read from master/.env.
"""
import html
import os
import threading
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader
from pypdf.errors import PyPdfError

load_dotenv(Path(__file__).resolve().parent / ".env")
API = os.getenv("DAP_URL", f"http://localhost:{os.getenv('DAP_PORT', '8000')}").rstrip("/")
HEADERS = {"X-DAP-Token": os.getenv("DAP_TOKEN", "")}
MODEL_OPTIONS = ["llama3.1", "qwen2.5", "gemma2"]
AGENT_REFRESH_SECONDS = 5
TASK_TYPES = ["analysis", "database", "backend", "frontend",
              "testing", "review", "integration", "documentation"]
TYPE_COLORS = {
    "analysis": "#7c3aed", "database": "#d97706", "backend": "#2563eb",
    "frontend": "#db2777", "testing": "#059669", "review": "#4f46e5",
    "integration": "#0d9488", "documentation": "#475569",
}
DEFAULT_REQUIREMENT = (
    "Library Management System with API and Database. Users can search, borrow and return "
    "books; librarians can add and remove books and see overdue loans. Data is kept in a "
    "relational database, exposed through a REST API and used by a web interface.")
MIN_REQUIREMENT_CHARS = 80
SAMPLE_AGENTS = [
    {"agent_id": "backend", "model": "llama3.1:8b", "coding": 90, "reasoning": 85,
     "context": 95, "context_window": 128000, "specialties": ["backend", "database", "testing"]},
    {"agent_id": "frontend", "model": "deepseek-coder:6.7b", "coding": 95, "reasoning": 70,
     "context": 80, "context_window": 16000, "specialties": ["frontend", "documentation"]},
    {"agent_id": "devops", "model": "mistral:7b", "coding": 75, "reasoning": 90,
     "context": 85, "context_window": 32000,
     "specialties": ["integration", "review", "analysis"]},
]
STATE_STYLE = {  # label, colour
    "idle": ("IDLE", "#16a34a"),
    "busy": ("BUSY", "#ea580c"),
    "offline": ("OFFLINE", "#dc2626"),
}

st.set_page_config(page_title="DAP Master Agent", page_icon="🧠", layout="wide")
# Only badge styling: text and background colours come from the active Streamlit theme,
# so the page reads correctly in both light and dark mode.
st.markdown("""
<style>
.dap-badge {display:inline-block; padding:3px 12px; border-radius:999px; color:#fff;
            font-weight:600; font-size:.8rem; letter-spacing:.04em;}
.dap-chip  {display:inline-block; padding:2px 10px; border-radius:999px; color:#fff;
            font-size:.8rem; font-weight:600; margin:2px 4px 2px 0;}
</style>""", unsafe_allow_html=True)


# --- Helpers -----------------------------------------------------------------

def api(method: str, path: str, **kwargs):
    try:
        resp = requests.request(method, API + path, headers=HEADERS,
                                timeout=kwargs.pop("timeout", 10), **kwargs)
    except requests.RequestException:
        st.error(f"Master Agent'a ulaşılamadı ({API}). Önce `python main.py` ile başlatın.")
        st.stop()
    if resp.status_code == 401:
        st.error("DAP_TOKEN sunucudakiyle uyuşmuyor, `master/.env` dosyasını kontrol edin.")
        st.stop()
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = resp.text
        raise RuntimeError(str(detail))
    return resp.json()


@st.cache_resource
def demo_heartbeats() -> dict:
    """Background thread that keeps the demo agents online while the dashboard runs."""
    state = {"on": False}

    def loop() -> None:
        while True:
            time.sleep(10)
            if state["on"]:
                for agent in SAMPLE_AGENTS:
                    try:
                        requests.post(f"{API}/agents/{agent['agent_id']}/heartbeat",
                                      headers=HEADERS, timeout=5)
                    except requests.RequestException:
                        pass

    threading.Thread(target=loop, daemon=True).start()
    return state


def register_demo_agents() -> None:
    for agent in SAMPLE_AGENTS:
        api("POST", "/agents/register", json=agent)
    demo_heartbeats()["on"] = True
    project = st.session_state.get("project")
    if project and any(t["status"] == "pending" for t in project["tasks"]):
        assign_pending(project["project_id"])


DEMO_DIR = Path(__file__).resolve().parent / "demo"
SAMPLE_NAMES = {"library": "Kütüphane Yönetim Sistemi", "todo": "Yapılacaklar Uygulaması",
                "shop": "Online Mağaza"}


def load_sample() -> None:
    name = st.session_state.get("sample_pick")
    path = DEMO_DIR / f"{name}.md"
    if path.exists():
        st.session_state["req_text"] = path.read_text(encoding="utf-8").strip()
        st.session_state.pop("req_warning", None)


def reset_requirement() -> None:
    st.session_state["req_text"] = DEFAULT_REQUIREMENT
    st.session_state.pop("req_warning", None)


def assign_pending(project_id: str) -> None:
    try:
        updated = api("POST", f"/projects/{project_id}/assign-pending")
    except RuntimeError as exc:
        st.session_state["demo_notice"] = f"Bekleyen görevler atanamadı: {exc}"
        return
    if (st.session_state.get("project") or {}).get("project_id") == project_id:
        st.session_state["project"] = updated


def badge(label: str, color: str) -> str:
    return f'<span class="dap-badge" style="background:{color}">{html.escape(label)}</span>'


def chip(label: str, color: str) -> str:
    return f'<span class="dap-chip" style="background:{color}">{html.escape(label)}</span>'


def agent_state(agent: dict) -> str:
    if agent["status"] != "online":
        return "offline"
    return "busy" if agent.get("queue_length", 0) > 0 else "idle"


def model_installed(name: str, installed: list) -> bool:
    return any(n == name or n.startswith(f"{name}:") for n in installed)


def read_document(file) -> str:
    """Text of an uploaded file, or "" when nothing usable could be read."""
    if file.name.lower().endswith(".pdf"):
        try:
            return "\n".join(p.extract_text() or "" for p in PdfReader(file).pages).strip()
        except PyPdfError as exc:
            st.session_state["req_warning"] = f"PDF okunamadı ({exc})."
            return ""
    return file.read().decode("utf-8", errors="replace").strip()


def render_project(project: dict, where: str = "main") -> None:
    tasks = project["tasks"]
    assigned = sum(t["status"] == "assigned" for t in tasks)
    source = (project.get("model") or "Llama") if project["source"] == "ollama" \
        else "Yedek şablon"

    st.subheader(f"{project['project_id']} · {project['name']}")
    if project.get("summary"):
        st.write(project["summary"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Görev", len(tasks))
    c2.metric("Atanan", assigned)
    c3.metric("Ajan", len({t["assigned_agent"] for t in tasks if t["assigned_agent"]}))
    c4.metric("Görevleri bölen", source)

    if assigned < len(tasks):
        st.warning(f"{len(tasks) - assigned} görev beklemede (online ajan yok).")
        if st.button("Bekleyen görevleri ata", key=f"assign_{where}_{project['project_id']}"):
            assign_pending(project["project_id"])
            st.rerun()

    st.markdown("**Görevler**")
    cols = st.columns(3)
    for i, t in enumerate(tasks):
        done = t["status"] != "pending"
        with cols[i % 3].container(border=True):
            st.markdown(chip(t["task_type"], TYPE_COLORS.get(t["task_type"], "#475569")) +
                        f" <small>{t['task_id']}</small>", unsafe_allow_html=True)
            st.markdown(f"**{t['title']}**")
            who = f"**{html.escape(t['assigned_agent'])}**" if t["assigned_agent"] else "—"
            score = "" if t["score"] is None else f" · S = **{t['score']:.1f}**"
            st.markdown(f"{who}{score}", unsafe_allow_html=True)
            st.markdown(badge("ATANDI" if done else "BEKLİYOR",
                              "#16a34a" if done else "#ea580c"), unsafe_allow_html=True)

    st.markdown("**Tablo**")
    df = pd.DataFrame([{
        "Görev": t["task_id"], "Tür": t["task_type"], "Başlık": t["title"],
        "Atanan ajan": t["assigned_agent"] or "—", "S skoru": t["score"],
        "Durum": "atandı" if t["status"] != "pending" else "bekliyor",
        "Bağımlı olduğu": ", ".join(t["depends_on"]) or "—",
    } for t in tasks])
    st.dataframe(df.style.format({"S skoru": "{:.1f}"}, na_rep="—"),
                 use_container_width=True, hide_index=True)

    st.markdown("**Bağımlılık haritası**")
    lines = ['digraph G {', 'rankdir=TB; bgcolor="transparent"; nodesep=0.4; ranksep=0.35;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontcolor="white", '
             'fontsize=11, penwidth=0, margin="0.2,0.1"];',
             'edge [color="#94a3b8", penwidth=1.4];']
    for t in tasks:
        score = "" if t["score"] is None else f' · S={t["score"]:.1f}'
        label = f'{t["task_id"]} · {t["task_type"]}\\n{t["assigned_agent"] or "pending"}{score}'
        lines.append(f'"{t["task_id"]}" [label="{label}", '
                     f'fillcolor="{TYPE_COLORS.get(t["task_type"], "#475569")}"];')
    lines += [f'"{e["from"]}" -> "{e["to"]}";' for e in project["task_graph"]["edges"]]
    lines.append("}")
    st.graphviz_chart("\n".join(lines), use_container_width=False)

    with st.expander("S skoru hesap detayı"):
        st.dataframe(pd.DataFrame([{
            "Görev": t["task_id"], "Ajan": t["assigned_agent"] or "—",
            "w_c·C": b.get("coding"), "w_r·R": b.get("reasoning"), "w_x·X": b.get("context"),
            "+10·u": b.get("specialty_bonus"), "−15·q": b.get("queue_penalty"),
            "S": t["score"],
        } for t in tasks for b in [t["score_breakdown"] or {}]]),
            use_container_width=True, hide_index=True)


# --- Header & model selection ------------------------------------------------

models_info = api("GET", "/models")
installed = models_info["installed"]
head, pick = st.columns([3, 1])
head.title("🧠 DAP Master Agent")
default_model = models_info["default"] if models_info["default"] in MODEL_OPTIONS \
    else MODEL_OPTIONS[0]


def model_label(name: str) -> str:
    if not models_info["ollama_online"]:
        return name
    return f"{name}  ✓" if model_installed(name, installed) else f"{name}  (yüklü değil)"


model = pick.selectbox("LLM modeli", MODEL_OPTIONS, index=MODEL_OPTIONS.index(default_model),
                       format_func=model_label)
if not models_info["ollama_online"]:
    st.warning("Ollama'ya ulaşılamıyor. Projeler yedek şablonla bölünecek.")
elif not model_installed(model, installed):
    st.warning(f"**{model}** Ollama'da yüklü değil. Kurmak için terminalde: "
               f"`ollama pull {model}`")

with st.sidebar:
    st.header("Demo modu")
    st.caption("Simülasyon ajanlarını kaydeder ve canlı tutar; görevler hemen dağıtılır.")
    demo_on = demo_heartbeats()["on"]
    if st.button("Örnek Ajanları Kaydet (Backend/Frontend/DevOps)", key="demo_side",
                 use_container_width=True, type="secondary" if demo_on else "primary"):
        register_demo_agents()
        st.rerun()
    if demo_on:
        st.success("Örnek ajanlar çalışıyor")
    if st.session_state.get("demo_notice"):
        st.warning(st.session_state.pop("demo_notice"))

tab_project, tab_agents, tab_history = st.tabs(
    ["🚀 Proje Gönder & Görevler", "🤖 Ajan Listesi & Canlı Skorlar", "📁 Geçmiş Projeler"])


# --- Tab 1: submit a project ---------------------------------------------------

with tab_project:
    st.session_state.setdefault("req_text", DEFAULT_REQUIREMENT)
    if not any(a["status"] == "online" for a in api("GET", "/agents")["agents"]):
        st.info("Online ajan yok; görevler beklemede kalır. Yan menüden örnek ajanları kaydedin.")
    uploaded = st.file_uploader("Gereksinim dokümanı (isteğe bağlı: PDF, TXT veya MD)",
                                type=["pdf", "txt", "md"])
    if uploaded is not None and st.session_state.get("req_file") != uploaded.file_id:
        st.session_state["req_file"] = uploaded.file_id
        st.session_state.pop("req_warning", None)
        text = read_document(uploaded)
        if len(text) >= MIN_REQUIREMENT_CHARS:
            st.session_state["req_text"] = text
        else:
            reason = st.session_state.pop("req_warning", None) or \
                f"Dokümandan yalnızca {len(text)} karakter okunabildi."
            st.session_state["req_text"] = DEFAULT_REQUIREMENT
            st.session_state["req_warning"] = (
                f"{reason} En az {MIN_REQUIREMENT_CHARS} karakter gerekli; varsayılan proje "
                "gereksinimi kullanıldı, isterseniz aşağıda düzenleyin.")
    if st.session_state.get("req_warning"):
        st.warning(st.session_state["req_warning"])
    st.selectbox("Örnek gereksinim", list(SAMPLE_NAMES), index=None,
                 placeholder="Hazır bir örnek seçin...", key="sample_pick",
                 format_func=SAMPLE_NAMES.get, on_change=load_sample)
    requirement = st.text_area("Proje tanımı", key="req_text", height=150,
                               help="Ne geliştirmek istediğinizi birkaç cümleyle yazın.")
    st.button("Örnek proje tanımına dön", type="secondary", on_click=reset_requirement)
    allow_fallback = st.toggle("Ollama çalışmıyorsa yedek şablonu kullan", value=True)

    if st.button("Projeyi Analiz Et", type="primary", use_container_width=True):
        if len(requirement.strip()) < MIN_REQUIREMENT_CHARS:
            st.warning(f"Tanım çok kısa (en az {MIN_REQUIREMENT_CHARS} karakter). Biraz "
                       "detay ekleyin ya da örnek tanıma dönün.")
        else:
            with st.spinner(f"{model} görevleri çıkarıyor, ajanlara S skoruyla dağıtılıyor..."):
                try:
                    st.session_state["project"] = api(
                        "POST", "/projects", timeout=300,
                        json={"requirement": requirement, "allow_fallback": allow_fallback,
                              "model": model})
                except RuntimeError as exc:
                    st.error(f"Proje oluşturulamadı: {exc}")

    if st.session_state.get("project"):
        st.divider()
        render_project(st.session_state["project"], where="new")


# --- Tab 2: agents (auto-refreshing) --------------------------------------------

with tab_agents:
    live = st.toggle(f"Canlı yenile ({AGENT_REFRESH_SECONDS} sn)", value=True)

    @st.fragment(run_every=AGENT_REFRESH_SECONDS if live else None)
    def agent_panel() -> None:
        agents = api("GET", "/agents")["agents"]
        counts = {s: sum(agent_state(a) == s for a in agents) for s in STATE_STYLE}
        m1, m2, m3 = st.columns(3)
        m1.metric("🟢 Boşta (IDLE)", counts["idle"])
        m2.metric("🟠 Meşgul (BUSY)", counts["busy"])
        m3.metric("🔴 Offline", counts["offline"])

        if not agents:
            st.info("Kayıtlı ajan yok. Aşağıdaki formdan ya da `python cli.py register` ile ekleyin.")
        cols = st.columns(3)
        for i, a in enumerate(agents):
            label, color = STATE_STYLE[agent_state(a)]
            with cols[i % 3].container(border=True):
                st.markdown(f"### {html.escape(a['agent_id'])} &nbsp;{badge(label, color)}",
                            unsafe_allow_html=True)
                st.caption(f"{a['model']} · kuyruk q = {a['queue_length']}")
                st.progress(int(a["coding"]), text=f"C · Kodlama: {a['coding']:g}")
                st.progress(int(a["reasoning"]), text=f"R · Akıl yürütme: {a['reasoning']:g}")
                st.progress(int(a["context"]), text=f"X · Bağlam: {a['context']:g}")
                st.markdown("".join(chip(s, TYPE_COLORS.get(s, "#475569"))
                                    for s in a["specialties"]) or "uzmanlık yok",
                            unsafe_allow_html=True)
        st.caption(f"Son güncelleme {time.strftime('%H:%M:%S')}")

    agent_panel()

    st.divider()
    st.subheader("Yeni ajan kaydet")
    with st.form("register_agent", clear_on_submit=True):
        c1, c2 = st.columns(2)
        agent_id = c1.text_input("Ajan ID", placeholder="örn. tester")
        agent_model = c2.text_input("Model", value="llama3.1:8b")
        c1, c2, c3 = st.columns(3)
        coding = c1.slider("C · Kodlama", 0, 100, 80)
        reasoning = c2.slider("R · Akıl yürütme", 0, 100, 80)
        context = c3.slider("X · Bağlam", 0, 100, 80)
        specialties = st.multiselect("Uzmanlık alanları", TASK_TYPES)
        if st.form_submit_button("Kaydet", type="primary"):
            if not agent_id.strip():
                st.warning("Ajan ID gerekli.")
            else:
                try:
                    api("POST", "/agents/register", json={
                        "agent_id": agent_id.strip(), "model": agent_model, "coding": coding,
                        "reasoning": reasoning, "context": context,
                        "specialties": specialties})
                    st.success(f"{agent_id} kaydedildi. Heartbeat göndermezse 30 sn sonra "
                               "offline olur.")
                except RuntimeError as exc:
                    st.error(str(exc))


# --- Tab 3: past projects --------------------------------------------------------

with tab_history:
    projects = api("GET", "/projects")["projects"]
    if not projects:
        st.info("Henüz proje yok. İlk sekmeden bir proje gönderin.")
    else:
        st.dataframe(pd.DataFrame([{
            "Proje": p["project_id"], "Ad": p["name"],
            "Model": p["model"] or ("yedek şablon" if p["source"] == "fallback" else "—"),
            "Görev": p["task_count"], "Atanan": p["assigned_count"] or 0,
            "Oluşturma (UTC)": p["created_at"].replace("T", " ")[:16],
        } for p in projects]), use_container_width=True, hide_index=True)
        chosen = st.selectbox("İncelenecek proje", [p["project_id"] for p in projects],
                              format_func=lambda pid: next(
                                  f"{p['project_id']} · {p['name']}" for p in projects
                                  if p["project_id"] == pid))
        st.divider()
        render_project(api("GET", f"/projects/{chosen}"), where="history")
