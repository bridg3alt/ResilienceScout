# ResilienceScout dashboard

React/Vite frontend for the ResilienceScout backend. Originally a Figma Make energy-submetering
export ([original design](https://www.figma.com/design/8IOpvgL35c6EzyLq0Hmm5t/Energy-Management-System-Dashboard));
the UI shell (Tailwind v4 + the vendored shadcn/Radix primitives in `src/app/components/ui/`) was
kept, and all domain content was replaced.

## Run

The dashboard is useless without the backend — there is **no mock data and no offline fallback**.
Start the API first:

```bash
cd ../../backend
uvicorn resilienceos.api:app --reload      # http://127.0.0.1:8000
```

Then:

```bash
npm install
npm run dev        # http://localhost:5173
```

> Vite binds IPv6-only here, so use `http://localhost:5173` — `http://127.0.0.1:5173` will refuse
> the connection.

Point at a different backend with `VITE_API_BASE=http://host:port npm run dev`.

## Scripts

| Script | Does |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | typecheck, then production build |

## DEMO DATA

While the backend reports `placeholder: true`, an amber **"DEMO DATA — NOT SURVEYED"** banner is
displayed. Flood depths, equipment elevations and population-served figures are invented
(`backend/resilienceos/presets.py`). The banner clears itself once those are replaced with
surveyed values and `DATA_IS_PLACEHOLDER` is set to `False`. Do not remove it by hand.

## Structure

```
src/app/
  lib/api.ts          typed fetch client (no fallbacks — failures surface as errors)
  hooks/useApi.ts     {data, loading, error, reload}, discards stale responses
  components/
    Layout.tsx        shell + switch routing + phase state
    PhaseSelector     Preparedness | Active Flood | Recovery
    Overview          CERI headline, sub-score cards, charts
    DependencyMap     hand-rolled layered SVG; click a node for its cascade
    ShelterStatusBoard / RecoveryPrioritization
    CopilotPanel      grounded Q&A
    DemoDataBanner / States
    ui/               vendored shadcn primitives (unmodified except import normalisation)
```

## Notes on the original export

- Source files imported version-pinned specifiers (`from "recharts@2.15.2"`), which required
  self-aliasing `package.json` keys that **npm rejects as invalid package names** — the project
  could not be installed at all. Imports were normalised to plain ESM.
- `react`/`react-dom` were declared only as *optional peer* dependencies, so they would never
  have installed. They are now real dependencies.
- `@mui/*` and `@emotion/*` were declared but imported by zero files; removed. Radix is the only
  UI system here.
- No `tsconfig.json`, `typescript`, or `@types/react` existed, so TypeScript was unenforced.
  Added, and the codebase typechecks clean under `strict`.
