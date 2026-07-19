# Deploying the hosted demo

Two free services: **Render** runs the Python API, **Vercel** serves the React dashboard. Total
cost is zero, with one caveat about cold starts that matters more than it sounds (§4).

Do the backend first — the frontend needs its URL.

---

## 1. Push to GitHub

Everything below deploys from the repo, so the repo has to be current first.

```bash
git push origin resilience-scout-pivot
```

---

## 2. Backend on Render

1. Sign in at [render.com](https://render.com) with GitHub.
2. **New → Blueprint**, choose this repo. Render reads [`render.yaml`](../render.yaml) and fills
   in the build and start commands itself.
3. Click **Apply**. First build takes 3–5 minutes.
4. Copy the service URL — something like `https://resiliencescout-api.onrender.com`.

Check it works before moving on:

```
https://<your-api>.onrender.com/health
https://<your-api>.onrender.com/docs
```

`/health` should return JSON. `/docs` is the interactive API browser, and is worth putting in the
application on its own — it lets a reviewer drive the whole engine without installing anything.

**Optional:** set `GROQ_API_KEY` under *Environment* to enable the natural-language copilot.
Without it the copilot returns the retrieved guidelines and simulation numbers instead of prose,
which is a degraded answer rather than an error — a missing key never breaks the demo.

---

## 3. Frontend on Vercel

1. Sign in at [vercel.com](https://vercel.com) with GitHub, **Add New → Project**, pick this repo.
2. Set **Root Directory** to `dashboard`. This is the one setting that is easy to miss and
   guarantees a failed build if wrong.
3. Add an environment variable:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | `https://<your-api>.onrender.com` |

   No trailing slash. This is baked in at build time, so **changing it later needs a redeploy**,
   not just a save.
4. **Deploy**, then copy the resulting URL.

---

## 4. Keep the API awake — do not skip this

Render's free tier stops the service after ~15 minutes idle, and the next request takes **~50
seconds** to wake it. A reviewer who clicks your link and sees a blank dashboard for 50 seconds
does not wait; they conclude it is broken.

Two ways out:

- **Free:** create a job at [cron-job.org](https://cron-job.org) that GETs
  `https://<your-api>.onrender.com/health` every 10 minutes. That keeps the instance warm
  indefinitely.
- **~$7/month:** upgrade the Render instance so it never sleeps.

Either is fine. Doing neither is what loses the reviewer.

---

## 5. Lock CORS to the dashboard

The API defaults to `allow_origins=["*"]` so the stack runs locally with no configuration. A
public deployment should not stay world-callable.

In Render → *Environment*, add:

| Name | Value |
|---|---|
| `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` |

Comma-separate to allow several (a preview domain and the production one, say). Do this **after**
the frontend exists — setting it to a guessed URL produces a CORS failure that presents as a
broken backend, which is a genuinely confusing thing to debug under time pressure.

---

## 6. Check the deployed demo

Open the Vercel URL and confirm:

- The dashboard loads with a CERI score, not an error panel.
- It opens at **0.82 m** — the observed 2018 flood mark — and the depth control reads
  *"3 cm more water and the generator goes under."*
- Dragging the slider past **0.85 m** collapses CERI from **76 Resilient** to **16 Critical**,
  and backup from 14 h to 0 h.
- *What to repair first* then shows **repair the generator, 12 h**, deferring 66 h of other work.
- The provenance notice still names what is still provisional.

If the dashboard loads but every panel errors, it is nearly always one of two things:
`VITE_API_BASE` has a trailing slash or a typo, or `ALLOWED_ORIGINS` does not match the Vercel
domain exactly.

---

## What is deliberately different in the deployed build

`requirements-deploy.txt` is `requirements.txt` without **chromadb** and **pytest**. chromadb
pulls onnxruntime and tokenizers — hundreds of megabytes that dominate both image size and
cold-start time — and the copilot already degrades to the built-in TF-IDF retriever without it.
Across four short guideline documents the two retrievers return the same passages.

This is a hosting decision, not a model change. **No number the dashboard displays is affected:**
retrieval chooses which guideline text grounds a copilot answer, never what the physics, the
dependency graph, or CERI compute.
