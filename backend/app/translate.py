"""Free offline Russian → English translation (no API key, no cost).

Uses the open-source Argos Translate ru→en model (OPUS-MT based) directly through
CTranslate2 + SentencePiece, which avoids installing PyTorch. In GitHub Actions the model
is downloaded once and cached.

    python -m app.translate --download models/   # fetch and unpack the model
    TRANSLATE_MODEL_DIR=models/translate-ru_en-1_9 python -m app.translate "текст"
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

MODEL_URL = "https://argos-net.com/v1/translate-ru_en-1_9.argosmodel"
MODEL_NAME = "translate-ru_en-1_9"

# Fix recurring machine-translation slips in nuclear terminology
GLOSSARY = [
    (r"\breactor hull\b", "reactor vessel"), (r"\breactor body\b", "reactor vessel"),
    (r"\bASMM\b", "land-based SMR (ASMM)"), (r"\bNPP\b", "NPP"), (r"\bZio-Podolsk\b", "ZiO-Podolsk"),
    (r"\bAtommash\b", "Atommash"), (r"\bRosatom\b", "Rosatom"), (r"\bpower unit No\. ?(\d)", r"Unit \1"),
    (r"\bfuel assemblies\b", "fuel assemblies"), (r"\bTVEL\b", "TVEL"), (r"\bRostechnadzor\b", "Rostekhnadzor"),
    (r"\bRostekhnadzor\b", "Rostekhnadzor"), (r"\bfloating nuclear thermal power plant\b", "floating NPP"),
    (r"\bin Forest\b", "in Lesnoy"), (r"\btars\b", "containers"), (r"\btara\b", "container"), (r"\bNRS experts\b", "SEC NRS experts"),
]
_GLOSS = [(re.compile(a, re.I), b) for a, b in GLOSSARY]
_SENT = re.compile(r"(?<=[.!?…»])\s+(?=[А-ЯЁA-Z«\"„0-9])")


def model_dir() -> Path | None:
    d = os.getenv("TRANSLATE_MODEL_DIR")
    if d and (Path(d) / "model" / "model.bin").exists():
        return Path(d)
    return None


def enabled() -> bool:
    return model_dir() is not None


@lru_cache(maxsize=1)
def _load():
    import ctranslate2
    import sentencepiece as spm
    d = model_dir()
    sp = spm.SentencePieceProcessor(model_file=str(d / "sentencepiece.model"))
    tr = ctranslate2.Translator(str(d / "model"), device="cpu", compute_type="int8")
    return sp, tr


def _fix(s: str) -> str:
    for rx, rep in _GLOSS:
        s = rx.sub(rep, s)
    return s.strip()


def translate(texts: list[str]) -> list[str]:
    """Translate a batch of Russian texts to English. Empty strings stay empty."""
    if not texts:
        return []
    sp, tr = _load()
    pieces, owners = [], []
    for i, t in enumerate(texts):
        for sent in _SENT.split((t or "").strip()):
            if sent.strip():
                pieces.append(sp.encode(sent[:1000], out_type=str))
                owners.append(i)
    out = [""] * len(texts)
    if pieces:
        results = tr.translate_batch(pieces, beam_size=2, max_decoding_length=300, max_batch_size=32)
        for i, r in zip(owners, results):
            out[i] = (out[i] + " " + sp.decode(r.hypotheses[0])).strip()
    return [_fix(s) for s in out]


def download(dest: Path) -> Path:
    import httpx
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / MODEL_NAME
    if (target / "model" / "model.bin").exists():
        return target
    r = httpx.get(MODEL_URL, follow_redirects=True, timeout=600)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(dest)
    return target


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--download", type=Path)
    p.add_argument("text", nargs="*")
    a = p.parse_args()
    if a.download:
        print(download(a.download))
    elif a.text:
        if not enabled():
            sys.exit("Set TRANSLATE_MODEL_DIR to the unpacked model folder")
        print("\n".join(translate(a.text)))
