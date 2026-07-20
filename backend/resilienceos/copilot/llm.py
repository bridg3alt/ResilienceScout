"""
LLM provider abstraction — one swappable entry point: ask_llm().

Default provider is Groq (free tier, fast Llama models). The key lives ONLY here,
server-side, read from the GROQ_API_KEY environment variable. To switch providers
(Gemini / OpenAI / Ollama) change only this file.

If no key is configured, ask_llm() falls back to a deterministic template answer so
the whole app (and the demo) still runs offline with zero keys.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def has_llm() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def ask_llm(system: str, user: str, temperature: float = 0.2) -> str:
    """Return the model's text answer, or a template fallback if no key is set."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return _fallback(user)
    try:
        from groq import Groq

        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return _fallback(user) + f"\n\n_(LLM unavailable: {type(e).__name__})_"


def _fallback(user: str) -> str:
    """
    Deterministic answer assembled from the CONTEXT block we pass in, so the demo
    works with no key. It simply surfaces the retrieved evidence and simulation
    numbers rather than inventing anything.
    """
    return (
        "AI narration is running in offline mode (no GROQ_API_KEY set), so here is the "
        "grounded evidence the recommendation is based on:\n\n"
        + _extract_context(user)
        + "\n\nSet GROQ_API_KEY to have the copilot turn this into a natural-language explanation."
    )


def _extract_context(user: str) -> str:
    if "CONTEXT:" in user:
        return user.split("CONTEXT:", 1)[1].strip()
    return user.strip()
