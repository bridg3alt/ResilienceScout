"""
Multi-agent copilot — the vision's "Future AI" supervisor + specialist architecture.

Instead of a single LLM call, the question is worked by four role-specialised agents whose
notes are then synthesised by a supervisor:

    Weather Analyst  -> reads the forecast / hazard numbers
    Building Physicist -> interprets the twin's thermal behaviour
    Energy Optimizer  -> reasons over solar / battery / backup duration
    Facility Manager  -> turns the above into concrete, prioritised actions
    Supervisor        -> synthesises one grounded, cited answer

Every agent shares the SAME grounding: the retrieved knowledge-base snippets (reusing
rag.retrieve — no duplicate index) and the live simulation context. The whole pipeline runs
on the existing Groq path (copilot.llm.ask_llm) and degrades gracefully to the single-shot
grounded answer when no key is configured, so it still works fully offline.
"""
from __future__ import annotations

from .llm import ask_llm, has_llm
from .rag import retrieve, answer as single_answer

_GROUND_RULES = (
    "Ground every statement in the CONTEXT (live simulation numbers + retrieved guidelines). "
    "Cite specific numbers. Never invent figures. Be concise. If the context doesn't support "
    "a point, say so."
)

SPECIALISTS = {
    "weather_analyst": (
        "Weather Analyst",
        "Focus ONLY on the climate hazard: the forecast outdoor peak, heat-index bands, the "
        "timing and duration of the outage window, and how severe/urgent this event is.",
    ),
    "building_physicist": (
        "Building Physicist",
        "Focus ONLY on the building's thermal behaviour from the twin: passive peak indoor "
        "temperature, thermal lag/mass, how fast it heats up when cooling is lost, and which "
        "envelope properties drive that.",
    ),
    "energy_optimizer": (
        "Energy Optimizer",
        "Focus ONLY on energy: rooftop solar, battery state and backup duration, critical-load "
        "ride-through, and when to charge/discharge and cool to stay safe for longest.",
    ),
    "facility_manager": (
        "Facility Manager",
        "Do NOT re-analyse. Convert the specialists' notes into a short, prioritised, concrete "
        "action list a non-technical operator can execute today, each tied to a reason.",
    ),
}


def _run_specialist(role_key: str, question: str, context: str, prior: str) -> str:
    label, focus = SPECIALISTS[role_key]
    system = (
        f"You are the {label} agent of ResilienceOS, advising a public-building operator. "
        f"{focus} {_GROUND_RULES} Answer in 2-4 tight sentences."
    )
    user = (
        f"QUESTION: {question}\n\n"
        f"CONTEXT:\n{context}\n"
        + (f"\nNOTES FROM PRIOR AGENTS:\n{prior}\n" if prior else "")
    )
    return ask_llm(system, user).strip()


def _run_supervisor(question: str, context: str, notes: dict) -> str:
    joined = "\n".join(f"[{SPECIALISTS[k][0]}] {v}" for k, v in notes.items())
    system = (
        "You are the Supervisor agent of ResilienceOS. Synthesise the specialist agents' notes "
        "into ONE coherent answer for a facility manager: lead with the recommendation, then the "
        "why, citing the simulation numbers the specialists used. Resolve any disagreement and "
        f"drop unsupported claims. {_GROUND_RULES}"
    )
    user = f"QUESTION: {question}\n\nSPECIALIST NOTES:\n{joined}\n\nCONTEXT:\n{context}"
    return ask_llm(system, user).strip()


def answer_multiagent(question: str, sim_context: str, k: int = 3,
                      extra_context: str = "") -> dict:
    """
    Orchestrate the specialist -> supervisor pipeline over shared grounding.

    extra_context: optional extra grounding appended to the simulation context, for callers
    that have domain numbers the shared context doesn't already carry.
    """
    snippets = retrieve(question, k=k)
    evidence = "\n\n".join(f"[{s['source']}]\n{s['text']}" for s in snippets)
    context = (
        f"--- Building simulation (live) ---\n{sim_context}\n"
        + (f"\n--- Optimised dispatch ---\n{extra_context}\n" if extra_context else "")
        + f"\n--- Retrieved guidelines ---\n{evidence}"
    )

    if not has_llm():
        base = single_answer(question, sim_context, k=k)
        base["agent_notes"] = {
            "note": "Multi-agent narration needs GROQ_API_KEY; showing grounded evidence instead."
        }
        base["mode"] = "offline-fallback"
        return base

    notes: dict[str, str] = {}
    prior = ""
    for role_key in SPECIALISTS:
        note = _run_specialist(role_key, question, context, prior)
        notes[role_key] = note
        prior += f"[{SPECIALISTS[role_key][0]}] {note}\n"

    final = _run_supervisor(question, context, notes)
    return {
        "answer": final,
        "agent_notes": {SPECIALISTS[key][0]: txt for key, txt in notes.items()},
        "sources": sorted(set(s["source"] for s in snippets)),
        "grounded": True,
        "llm": "groq",
        "retrieval": "chromadb",
        "mode": "multi-agent",
    }
