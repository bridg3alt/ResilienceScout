"""End-to-end smoke test of the analytics pipeline (no LLM, no server)."""
import json
from resilienceos.building import Building
from resilienceos import weather as wx
from resilienceos.hazard import analyze_heatwave, analyze_outage
from resilienceos.engine import resilience_score, operational_plan, outage_sequence
from resilienceos.scenarios import compare, budget_optimizer

b = Building(battery_kwh=20)
fc = wx.fetch_forecast(b.latitude, b.longitude, days=3)
day = wx.hottest_day(fc)

hw = analyze_heatwave(b, day, hvac_active=False)
hw_ac = analyze_heatwave(b, day, hvac_active=True)
out = analyze_outage(b, day, start_hour=14, duration_h=6)
score = resilience_score(hw, out)
print(f"(AC-on cooling peak for energy planning: {hw_ac.peak_indoor}C indoor, "
      f"{max(r['cooling_kw'] for r in hw_ac.profile):.1f} kW)")

print("RESILIENCE SCORE:", score["score"], score["band"], score["components"])
print(f"Heatwave: peak indoor {hw.peak_indoor}C, peak HI {hw.peak_heat_index}C, "
      f"safe {hw.safe_occupancy_hours}/{hw.occupied_hours} occ hours")
print(f"Outage(14:00,6h): peak {out.peak_indoor_during}C, "
      f"hours_until_unsafe {out.hours_until_unsafe}, backup {out.backup_hours}h")

print("\nOPERATIONAL PLAN:")
for a in operational_plan(b, day, hw):
    print(f"  {a['time']}  [{a['category']}] {a['action']}")

print("\nOUTAGE SEQUENCE:")
for s in outage_sequence(b, out):
    print(f"  {s['step']}: {s['action']}")

print("\nSCENARIO — cool roof:")
print(json.dumps(compare(b, day, "cool_roof")["deltas"], indent=2))

print("\nBUDGET OPTIMIZER (Rs 5 lakh):")
opt = budget_optimizer(b, day, 500000)
for r in opt["ranked"]:
    print(f"  {r['label']:28s} +{r['score_gain']:>4} pts  "
          f"{r['gain_per_lakh']:>5}/lakh  cost Rs{r['cost_inr']}")
print("  recommended:", opt["recommended"])
