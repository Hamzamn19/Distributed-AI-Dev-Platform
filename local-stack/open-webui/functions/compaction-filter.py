"""
OpenWebUI Inlet Filter: Auto-Compaction (opencode-style)
=========================================================
Mirrors sst/opencode `session/compaction.ts` in miniature:

1. Trigger (overflow.ts): compact when estimated tokens >= CONTEXT_LIMIT - RESERVE.
2. Prune (cheap, no model call): truncate very long older assistant messages.
3. Summarize: ask the model to summarize the head, keep system + summary +
   recent tail (TAIL_BUDGET), drop the rest, continue the conversation.

Install: OpenWebUI Admin -> Functions -> + -> paste this file -> save -> enable
for the local model. Requires the filter to reach llama-server at SUMMARIZE_URL.

Test: COMPACT_TEST_LIMIT=3000 python3 compaction-filter.py  (uses live :8080)
"""

import json
import os
import urllib.request

# ---------------------------------------------------------------- pure logic

def estimate_tokens(messages) -> int:
    total_chars = 0
    for m in messages or []:
        c = m.get("content", "")
        if isinstance(c, list):  # multimodal parts
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    total_chars += len(p.get("text", ""))
        else:
            total_chars += len(c or "")
    return total_chars // 4


def split_head_tail(messages, tail_budget_tokens: int):
    """Keep system messages + most recent turns fitting the budget.

    Returns (head, tail). Tail always keeps at least the last user message.
    """
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    if not rest:
        return [], system
    tail = []
    used = 0
    for m in reversed(rest):
        t = estimate_tokens([m])
        if tail and used + t > tail_budget_tokens:
            break
        tail.insert(0, m)
        used += t
    head = rest[: len(rest) - len(tail)] if tail else rest
    return head, system + tail


def prune_long_messages(messages, max_chars: int = 4000, keep_last_turns: int = 2):
    """Cheap stage: truncate huge older assistant outputs (opencode prunes
    old *tool results*; in plain chat the analogue is long code dumps)."""
    out = [dict(m) for m in messages]
    assistant_idx = [i for i, m in enumerate(out) if m.get("role") == "assistant"]
    protected = set(assistant_idx[-keep_last_turns:])
    for i in assistant_idx:
        if i in protected:
            continue
        c = out[i].get("content", "")
        if isinstance(c, str) and len(c) > max_chars:
            out[i]["content"] = c[:max_chars] + "\n[...truncated by auto-compaction prune]"
    return out


COMPACTION_PROMPT = """لخص المحادثة التالية تلخيصا دقيقا ومكثفا في العربية مع إبقاء المصطلحات التقنية والأسماء بالإنجليزية كما هي.
يجب أن يتضمن الملخص:
1. الهدف الحالي للمستخدم وما تم إنجازه منه.
2. القرارات المهمة المتخذة (إعدادات، أوامر، أرقام، مسارات ملفات).
3. الحقائق التقنية الأساسية (موديلات، سياقات، نتائج قياسات).
4. الخطوة التالية المنتظرة.
لا تضف تعليقات من عندك خارج التلخيص."""


def summarize_head(head, base_url: str, model: str, timeout: int = 600) -> str:
    convo = []
    for m in head:
        role = "المستخدم" if m.get("role") == "user" else "المساعد"
        c = m.get("content", "")
        if isinstance(c, list):
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
        convo.append(f"[{role}]: {c}")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": COMPACTION_PROMPT},
            {"role": "user", "content": "\n\n".join(convo)},
        ],
        "temperature": 0,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"].strip()


def maybe_compact(messages, base_url: str, model: str,
                  context_limit: int, reserve: int, tail_budget: int):
    """Returns (messages, compacted_bool, info). Pure except summarize call."""
    total = estimate_tokens(messages)
    usable = context_limit - reserve
    if total < usable:
        return messages, False, {"tokens": total, "usable": usable}
    pruned = prune_long_messages(messages)
    if estimate_tokens(pruned) < usable:
        return pruned, True, {"tokens": total, "stage": "prune"}
    head, tail_framed = split_head_tail(pruned, tail_budget)
    if not head:
        return pruned, False, {"tokens": total, "note": "nothing to compact"}
    summary = summarize_head(head, base_url, model)
    system = [m for m in tail_framed if m.get("role") == "system"]
    tail = [m for m in tail_framed if m.get("role") != "system"]
    new_messages = system + [
        {"role": "user",
         "content": "[ملخص تلقائي للمحادثة السابقة — تابع من هنا]\n" + summary}
    ] + tail
    return new_messages, True, {"tokens": total, "stage": "summarize",
                                "summary_chars": len(summary)}


# ------------------------------------------------------- OpenWebUI wrapper

try:
    from pydantic import BaseModel, Field

    class Filter:
        class Valves(BaseModel):
            CONTEXT_LIMIT: int = Field(default=131072)
            RESERVE: int = Field(default=8192)
            TAIL_BUDGET: int = Field(default=15000)
            SUMMARIZE_URL: str = Field(default="http://127.0.0.1:8080")
            MODEL: str = Field(
                default="/home/hamzah/Documents/Distributed-AI-Dev-Platform/local-stack/models/gemma4-26b-a4b/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf")

        def __init__(self):
            self.valves = self.Valves()

        async def inlet(self, body: dict, __event_emitter__=None):
            async def emit(msg: str):
                if __event_emitter__:
                    await __event_emitter__({"type": "status",
                                            "data": {"description": msg, "done": False}})

            v = self.valves
            messages = body.get("messages", [])
            model = body.get("model", v.MODEL)
            try:
                new_messages, compacted, info = maybe_compact(
                    messages, v.SUMMARIZE_URL, model,
                    v.CONTEXT_LIMIT, v.RESERVE, v.TAIL_BUDGET)
            except Exception as e:  # never break the chat on compaction failure
                await emit(f"تعذر الدمج التلقائي: {e}")
                return body
            if compacted:
                await emit(f"تم دمج المحادثة تلقائيا ({info})")
                body["messages"] = new_messages
            return body

except ImportError:
    pass  # plain-python import for local testing (no pydantic needed)


# ------------------------------------------------------------------ self-test
if __name__ == "__main__":
    import asyncio

    LIM = int(os.environ.get("COMPACT_TEST_LIMIT", "3000"))
    transcript = []
    for i in range(12):
        transcript.append({"role": "user", "content": f"سؤال رقم {i}: اشرح موضوع الشبكات العصبية بالتفصيل " * 20})
        transcript.append({"role": "assistant",
                           "content": f"إجابة رقم {i}: الشبكات العصبية تتكون من طبقات " * 30})
    print("before:", len(transcript), "msgs,", estimate_tokens(transcript), "tok est, limit", LIM)
    new_msgs, compacted, info = maybe_compact(
        transcript, "http://127.0.0.1:8080",
        "/home/hamzah/Documents/Distributed-AI-Dev-Platform/local-stack/models/gemma4-26b-a4b/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf",
        LIM, 200, 800)
    print("compacted:", compacted, info)
    print("after:", len(new_msgs), "msgs,", estimate_tokens(new_msgs), "tok est")
    assert compacted and len(new_msgs) < len(transcript), "compaction did not shrink history"
    assert any("ملخص تلقائي" in (m.get("content") or "") for m in new_msgs), "no summary injected"
    assert new_msgs[-1]["content"].startswith("إجابة رقم 11"), "recent tail not preserved"
    print("SELF-TEST PASS")
