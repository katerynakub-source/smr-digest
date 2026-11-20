"""AI module: English translation + 3-5 bullet digest, and Q&A over long documents.

Uses the OpenAI API when OPENAI_API_KEY is set (model via OPENAI_MODEL). Without a key it
falls back to an extractive digest (sentences richest in facts and figures) so the app
still works end to end; such digests are marked ai_model="extractive".
"""
from __future__ import annotations

import json
import os
import re

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_client = None


def enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI()
    return _client


DIGEST_PROMPT = """You are the editor of an industry digest on nuclear energy (focus: small modular reactors).
You receive the headline and text of a publication in any language. Return JSON:
{"title_en": "<accurate English translation of the headline (or the headline itself if already English)>",
 "bullets": ["3-5 bullets in English: key facts and figures (MW, dates, amounts, licensing stages), who did what"]}
Rules: facts from the text only, no opinions or filler; each bullet <= 25 words; keep reactor and company
names in their original spelling (BWRX-300, NuScale, Rolls-Royce SMR, RITM-200); units as MWe / MWt."""

QA_PROMPT = """Answer the user's question strictly from the document excerpts provided, in English.
If the excerpts do not contain the answer, say so. End with the numbers of the excerpts you relied on, e.g. [1], [3]."""


async def digest(title: str, text: str, lang: str) -> dict:
    """Return {"title_en", "bullets", "ai_model"}."""
    body = (text or "").strip()
    if enabled() and (body or title):
        resp = await client().chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {"role": "system", "content": DIGEST_PROMPT},
                {"role": "user", "content": f"Headline: {title}\n\nText:\n{body[:12000]}"},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        bullets = [b.strip() for b in data.get("bullets", []) if b.strip()][:5]
        return {"title_en": data.get("title_en") or title, "bullets": bullets, "ai_model": MODEL}
    return {"title_en": title if lang == "en" else None,
            "bullets": extractive_bullets(body), "ai_model": "extractive"}


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ«\"“])")
_FACT = re.compile(r"\d|МВт|MW|млрд|млн|billion|million|%|€|\$|£|₽")


def extractive_bullets(text: str, n: int = 4) -> list[str]:
    sents = [s.strip(" •") for p in text.split("\n\n") for s in _SENT.split(p) if 40 <= len(s) <= 320]
    if not sents:
        return []
    scored = []
    for i, s in enumerate(sents[:40]):
        score = min(len(_FACT.findall(s)), 4) * 1.5 + max(0.0, 6 - i * 0.6)  # facts, but news is front-loaded
        scored.append((score, i, s))
    top = sorted(sorted(scored, reverse=True)[:n], key=lambda x: x[1])
    return [s for _, _, s in top]


# ---------- document Q&A ----------

def chunk(text: str, size: int = 1200) -> list[str]:
    paras, chunks, cur = text.split("\n\n"), [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            chunks.append(cur.strip())
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def _terms(s: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[\w\-]{3,}", s.lower())}


def retrieve(text: str, question: str, k: int = 5) -> list[tuple[int, str]]:
    q = _terms(question)
    chunks = chunk(text)
    scored = sorted(((len(q & _terms(c)), i, c) for i, c in enumerate(chunks)), reverse=True)[:k]
    return sorted((i, c) for s, i, c in scored if s > 0) or [(i, c) for i, c in enumerate(chunks[:2])]


async def ask(title: str, text: str, question: str) -> dict:
    passages = retrieve(text, question)
    if not enabled():
        return {"answer": "No AI key configured — below are the document passages closest to your question.",
                "passages": [{"n": i + 1, "text": c[:700]} for i, c in passages], "ai_model": "extractive"}
    ctx = "\n\n".join(f"[{i + 1}] {c}" for i, c in passages)
    resp = await client().chat.completions.create(
        model=MODEL, temperature=0.1,
        messages=[{"role": "system", "content": QA_PROMPT},
                  {"role": "user", "content": f"Document: {title}\n\nExcerpts:\n{ctx}\n\nQuestion: {question}"}],
    )
    return {"answer": resp.choices[0].message.content.strip(),
            "passages": [{"n": i + 1, "text": c[:700]} for i, c in passages], "ai_model": MODEL}
