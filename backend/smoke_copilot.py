"""Smoke test the RAG copilot (works offline; richer if GROQ_API_KEY is set)."""
from resilienceos.building import Building
from resilienceos import weather as wx
from resilienceos.hazard import analyze_heatwave, analyze_outage
from resilienceos.engine import resilience_score
from resilienceos.copilot.context import build_context
from resilienceos.copilot.rag import answer, retrieve

b = Building(battery_kwh=20)
day = wx.hottest_day(wx.fetch_forecast(b.latitude, b.longitude, days=3))
hw = analyze_heatwave(b, day, hvac_active=False)
out = analyze_outage(b, day, 14, 6)
score = resilience_score(hw, out)
ctx = build_context(b, hw, out, score)

print("=== RETRIEVAL TEST ===")
for s in retrieve("why should I pre-cool before a heatwave?", k=2):
    print(f"- {s['source']}: {s['text'][:90]}...")

print("\n=== COPILOT ANSWER ===")
q = "What should this building do before tomorrow's heatwave, and why?"
res = answer(q, ctx)
print("Q:", q)
print("LLM:", res["llm"], "| sources:", res["sources"])
print("A:", res["answer"])
