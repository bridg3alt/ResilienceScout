"""
RAG copilot — the LLM never answers from memory.

It grounds every answer in two things:
  1. RETRIEVED external knowledge (ChromaDB over the curated /knowledge docs), and
  2. The building's LIVE simulation numbers (twin + hazard outputs) passed as context.

ChromaDB's default local embedding model (all-MiniLM, ONNX, no key) is used; swap
for BGE for higher recall. Index is built in-memory at startup from the markdown docs.
"""
from __future__ import annotations

import glob
import math
import os
import re
from collections import Counter

from .llm import ask_llm, has_llm

_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")
_COLLECTION = "resilienceos_kb"

_collection = None          # chromadb collection (primary)
_chunks: list[dict] = []    # [{text, source}] — always loaded
_tf_index = None            # lightweight fallback index
_use_fallback = False


def _chunk(text: str, size: int = 600):
    """Split a doc into paragraph-ish chunks."""
    parts, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(buf) + len(para) < size:
            buf += ("\n\n" + para) if buf else para
        else:
            if buf:
                parts.append(buf)
            buf = para
    if buf:
        parts.append(buf)
    return parts


def _load_chunks():
    global _chunks
    if _chunks:
        return _chunks
    for path in sorted(glob.glob(os.path.join(_KNOWLEDGE_DIR, "*.md"))):
        source = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            for ch in _chunk(f.read()):
                _chunks.append({"text": ch, "source": source})
    return _chunks


# ---- primary: ChromaDB (semantic, local ONNX embeddings) ----------------------
def _ensure_chroma():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    client = chromadb.Client()
    try:
        client.delete_collection(_COLLECTION)
    except Exception:
        pass
    col = client.create_collection(_COLLECTION)
    chunks = _load_chunks()
    col.add(
        ids=[f"c{i}" for i in range(len(chunks))],
        documents=[c["text"] for c in chunks],
        metadatas=[{"source": c["source"]} for c in chunks],
    )
    _collection = col
    return col


# ---- fallback: pure-python TF-IDF cosine (no heavy deps, no download) ----------
_TOKEN = re.compile(r"[a-z]+")


def _tok(s: str):
    return _TOKEN.findall(s.lower())


def _ensure_tfidf():
    global _tf_index
    if _tf_index is not None:
        return _tf_index
    chunks = _load_chunks()
    docs = [Counter(_tok(c["text"])) for c in chunks]
    df = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(docs)
    idf = {t: math.log((n + 1) / (v + 1)) + 1 for t, v in df.items()}
    vecs = []
    for d in docs:
        v = {t: (1 + math.log(c)) * idf[t] for t, c in d.items()}
        norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
        vecs.append((v, norm))
    _tf_index = (vecs, idf)
    return _tf_index


def _tfidf_query(query: str, k: int):
    (vecs, idf) = _ensure_tfidf()
    q = Counter(_tok(query))
    qv = {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in q.items()}
    qnorm = math.sqrt(sum(w * w for w in qv.values())) or 1.0
    scored = []
    for i, (v, norm) in enumerate(vecs):
        dot = sum(qv.get(t, 0.0) * w for t, w in v.items())
        scored.append((dot / (qnorm * norm), i))
    scored.sort(reverse=True)
    return [_chunks[i] for _, i in scored[:k]]


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Semantic retrieval via ChromaDB; falls back to TF-IDF if it's unavailable."""
    global _use_fallback
    if not _use_fallback:
        try:
            col = _ensure_chroma()
            res = col.query(query_texts=[query], n_results=k)
            return [{"text": d, "source": m["source"]}
                    for d, m in zip(res["documents"][0], res["metadatas"][0])]
        except Exception:
            _use_fallback = True  # OOM / no model download / etc. -> degrade
    return _tfidf_query(query, k)


SYSTEM = (
    "You are ResilienceOS Copilot, an energy-resilience advisor for public buildings "
    "(schools, clinics, community centres) facing heatwaves and power outages. "
    "Answer ONLY from the CONTEXT provided: the building's simulation results and the "
    "retrieved guideline snippets. Cite specific numbers from the simulation. If the "
    "context does not support an answer, say so. Be concise, practical and calm — your "
    "reader is a facility manager, not an engineer. Never invent numbers."
)


def answer(question: str, sim_context: str, k: int = 3) -> dict:
    """
    question: the user's natural-language question.
    sim_context: pre-formatted string of the building's current simulation numbers.
    """
    snippets = retrieve(question, k=k)
    evidence = "\n\n".join(f"[{s['source']}]\n{s['text']}" for s in snippets)

    user = (
        f"QUESTION: {question}\n\n"
        f"CONTEXT:\n"
        f"--- Building simulation (live) ---\n{sim_context}\n\n"
        f"--- Retrieved guidelines ---\n{evidence}"
    )
    text = ask_llm(SYSTEM, user)
    return {
        "answer": text,
        "sources": sorted(set(s["source"] for s in snippets)),
        "grounded": True,
        "llm": "groq" if has_llm() else "offline-fallback",
        "retrieval": "tfidf" if _use_fallback else "chromadb",
    }
