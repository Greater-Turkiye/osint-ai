# Architecture

> **EN/TR:** Bu belge İngilizcedir; özeti ve kararları [README](README.md) ve [ADR 0017 (önerildi)](https://github.com/Greater-Turkiye/handbook/pull/13) Türkçe özetler.
>
> **Status: proposal.** Nothing below stage 0 is implemented. Every number is arithmetic from
> geometry and published throughput figures, not a measurement of our own system. Where a
> stage needs money, a GPU we do not have, or a manual step by a maintainer, the sentence that
> proposes it says so.

## The shape of the answer

The ask was "an AI that scans millions of map and satellite images". Taken literally that is
unaffordable on any free tier, so the design turns it into a different, achievable statement:

> We embed a bounded number of **tiles** per pass, compare each tile to its own past,
> rank the few that changed, and spend an expensive model only on those.

The cost of the expensive stage is then set by how many tiles survive, not by how many exist.
This is the single architectural idea in this document; everything else is plumbing.

```
        ┌──────────────────────── runs on a free GPU session, once per pass ─────────────────┐
0. AOI  │ 1. catalogue   2. tile     3. mask      4. embed      5. change     6. rank        │  7. VLM     8. human
  gate  │    (STAC)         (grid)     (cloud,      (Clay /       (vs. the       (top-k)     │   triage      queue
        │                               water)      Prithvi)      baseline)                  │
        └────────────────────────────────────────────────────────────────────────────────────┘
  ↓                                                                                              ↓          ↓
refuse                                                                                       ≤20/pass   gt-ops.reviews
Türkiye                                                                                                 (platform)
```

Stages 0–2 exist in code today (`gt-osint-ai scenes` does 0, 1 and the arithmetic of 2).
Stages 3–8 are described here and implemented nowhere.

---

## Stage 0 — The area gate (implemented)

Before any network call, the area of interest is tested against the Türkiye geofence and
refused if it touches it. See [`src/gt_osint_ai/redlines.py`](src/gt_osint_ai/redlines.py).

- The fence is `land + internal waters + 15 nm`, built from the same `gt-geofence/1` file and
  the same code as the collectors' fence in `platform`. The extra 3 nm over the territorial
  sea covers a tile's own 2.56 km extent.
- A refusal is exit code `2`, distinct from "no results", and no catalogue is queried.
- The cost is real: at 15 nm the gate also refuses Idlib, Latakia and the Greek islands near
  the Turkish coast. We accept losing them rather than have a rule that argues case by case.
- **Runs where:** anywhere, in milliseconds, no GPU, no network.

## Stage 1 — Catalogue (implemented)

Ask a free STAC API which open scenes exist for the box and date range. Default is Earth
Search v1 (Element 84), which indexes the AWS Registry of Open Data and needs **no account,
no key and no payment method** — the reason it is usable at all under
[ADR 0008](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0008-zero-budget-infrastructure.md).

- Only collections whose licence has been checked are allowed; the list is in
  [`stac.py`](src/gt_osint_ai/stac.py) and each entry carries its licence string.
- Metadata only. A scene id is a pointer, not a picture.
- **Free-tier note:** Earth Search is offered "as a best effort" with no SLA. Planetary
  Computer and the Copernicus Data Space are the fallbacks; Planetary Computer's *search* is
  open but its asset URLs need a free SAS token, and the Copernicus Data Space needs a free
  account for downloads — **both are manual steps a maintainer would have to do**, which is
  why Earth Search is the default.
- **Runs where:** GitHub Actions, or a laptop. No GPU.

## Stage 2 — Tiling

Cut each AOI into a fixed grid of 256 × 256 pixel tiles with 32 px overlap, aligned to MGRS so
that **the same patch of ground has the same tile id on every date**. That stable id is what
makes change detection, deduplication and the review queue all work without storing imagery.

At Sentinel-2's 10 m resolution a tile is 2.56 km square (6.55 km²); with the overlap the
effective stride is 2.24 km, so a tile "costs" 5.02 km² of coverage.

- Reads are windowed from Cloud-Optimized GeoTIFFs: we fetch only the bands and the pixel
  window a tile needs, never a whole scene.
- **Runs where:** GitHub Actions (public repos: free, unlimited minutes, but a **6-hour job
  limit** and no GPU). Bandwidth, not CPU, is the constraint here.

## Stage 3 — Masking

Drop tiles that cannot inform anything, using the L2A scene-classification band (SCL):

- more than ~40 % cloud, cloud shadow, cirrus or no-data → drop;
- more than ~90 % water, unless the AOI is maritime → drop;
- a scene whose STAC item id and processing baseline are unchanged since the last pass → skip
  the whole scene, it is the same pixels.

This is the cheapest filter in the pipeline and it typically removes a third to a half of the
tiles over the eastern Mediterranean across a year. It runs on CPU.

## Stage 4 — Embedding

Run a remote-sensing foundation model over every surviving tile and keep the 1024-dimensional
vector. Recommended model and the alternatives, with licences and VRAM, are in
[MODELS.md](MODELS.md); the short version is **Clay v1.5** (Apache 2.0, 632M ViT, Sentinel-2
at 10 m, 256 × 256 tiles, 1024-d embedding) with **Prithvi-EO-2.0-300M** (Apache 2.0, 30 m
HLS, multi-temporal) as the fallback.

- No text, no generation, no prompt. This stage is a function from pixels to a vector, which
  is why it is cheap enough to run on everything.
- Vectors are quantised to int8 before storage: 1024 dims × 1 byte = 1 kB per tile.
- **Runs where:** a free Kaggle GPU session (30 h/week, P100 or T4, 9 h per session). Colab
  free is unsuitable for a schedule — no guaranteed GPU, idle disconnects — and is for
  experiments only. On CPU in GitHub Actions the same work is roughly 10–20× slower and would
  need sharding across matrix jobs to stay under the 6-hour limit; possible, ugly, and the
  honest fallback if Kaggle access lapses.

## Stage 5 — Change detection

For each tile id, compare this pass's vector to a **rolling baseline** (the previous pass's
vector and a running median over the last few passes). The change score is cosine distance.

- We keep the baseline, not the history. Two vectors per tile, not fifty.
- A tile whose distance is below the noise threshold is dropped. Seasonal change, sun angle
  and haze all move the vector, so the threshold is set per AOI from its own distribution
  rather than as a global constant, and the seasonal drift is subtracted by comparing against
  the same season's median where a year of history exists.
- This stage is what removes 99 %+ of tiles, and it is pure linear algebra on CPU.

## Stage 6 — Ranking

Take the top *k* by change score, capped hard: **k = 0.5 % of the pass's tiles, and never more
than 200**. The cap is in code, not in a configuration file and not in a prompt, because the
whole system's affordability depends on it.

Optional, and cheap enough to be worth trying before any fine-tuning: a logistic regression on
the frozen 1024-d vectors, trained on the labelled benchmark from [EVALUATION.md](EVALUATION.md).
It trains in seconds on a CPU and often beats a much more expensive approach.

## Stage 7 — Vision-language triage

Only the survivors reach a vision-language model, which is asked a narrow question — "does
this tile show new construction, a new berm or revetment, a new hardstand, a vessel at a berth
that was empty, a burn scar?" — and must answer with a label, a one-sentence reason, and a
confidence, or with "cannot tell at this resolution".

- Recommended: **Qwen3-VL-4B-Instruct** (Apache 2.0). It fits a free 16 GB T4 or P100 in
  4-bit, in the same Kaggle session as stage 4.
- The model never sees a prompt built from untrusted text, and its output is never parsed as a
  command. It produces a label and a sentence, nothing else
  ([ADR 0011](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0011-threat-model.md)).
- **Free-tier note:** Cloudflare Workers AI could host this stage instead — 10,000 neurons/day
  free, no card needed — but a vision model burns that pool fast and the catalogue's vision
  models are limited. GitHub Models is prototyping-only at roughly 50–150 requests/day. Both
  are usable at our volume (≈100 calls per pass) and neither is something to depend on.

## Stage 8 — The human queue (reuse, do not rebuild)

Surviving candidates go into the **existing** review queue in `platform`. This repository does
not create a second queue, a second bot or a second database.

| What | Where it already exists | What we add |
|---|---|---|
| Queue rows | `gt-ops.reviews` in Cloudflare D1 (`platform/db/migrations/ops`) | rows with `content_hash`, `summary_tr`, `summary_en`, `status='queued'` |
| Phone review | The Telegram review bot (`platform/apps/review-bot`) | nothing — an imagery candidate is just another row |
| Public queue | The `inceleme-kuyrugu` GitHub issue from `collect.yml` | an extra section for imagery candidates |
| Decision | A human, recorded with `decided_by` and `decided_at` | nothing |

A candidate row carries: the tile id, the STAC item id and date, the change score, the VLM
label and sentence, a confidence, and a **link to the original scene at the source** so the
reviewer opens the imagery from Copernicus or USGS themselves. **We do not attach the image**,
because we do not redistribute imagery ([DATA.md](DATA.md)).

Nothing is published. Approval at this gate means "worth drafting", exactly as it does for a
text signal ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).

---

## The arithmetic

Assume a watch list of **10 areas averaging 100 × 100 km**, so 100,000 km² of coverage, on
Sentinel-2 at 10 m, at the mission's 5-day revisit.

| Quantity | Value | Where it comes from |
|---|---:|---|
| Tiles per pass | ~20,000 | 100,000 km² ÷ 5.02 km² of effective stride per tile |
| Passes per year | ~73 | 365 ÷ 5-day revisit |
| Usable passes after cloud | ~45 | roughly 40 % of acquisitions lost to cloud over a year |
| **Tile embeddings per year** | **~900,000** | 20,000 × 45 |
| Bytes read per pass | ~10.5 GB | 20,000 × 65,536 px × 4 bands × 2 bytes |
| Bytes stored per pass | **0 of imagery**, ~20 MB of vectors | 20,000 tiles × 1 kB int8 |
| Embedding time per pass | ~17–35 min of GPU | 20,000 ÷ 10–20 tiles/s |
| Tiles reaching the VLM | ~100 | 0.5 % cap |
| VLM time per pass | ~5–15 min of GPU | 100 × 3–8 s |
| **Candidates reaching a human** | **~10, hard cap 20** | the reviewer budget, set deliberately |

So "millions of images" is honestly **about 0.9 million tile-embeddings a year and roughly 500
human-facing candidates a year** — not millions of images a day, and not a model that looks at
everything with its full attention.

### Where each free tier runs out

| Service | Free limit | What we need | Headroom | Where it breaks |
|---|---|---|---|---|
| Kaggle GPU | ~30 h/week, P100/T4 (16 GB), 9 h/session | ~1 h/week | ~30× | Model size, not hours: a 32B VLM needs ~20 GB in 4-bit and will not load on 16 GB. Scheduling is also fragile — **in practice a maintainer presses go**, so the real cadence may be weekly, not 5-daily |
| Colab free | No guaranteed GPU, idle disconnects, ~12 h cap | experiments only | n/a | Unsuitable for anything scheduled. Do not build on it |
| GitHub Actions | Free and unlimited on public repos, 6 h/job, no GPU | tiling, masking, orchestration | large | The 6-hour job limit if CPU embedding is ever the fallback; shard across a matrix |
| Cloudflare Workers | 100k req/day, 10 ms CPU/request | orchestration only | large | Cannot run a model at all. Ever |
| Cloudflare Workers AI | 10,000 neurons/day, no card required | ~100 VLM calls/pass | thin | A vision model burns neurons fast; a few hundred image calls a day is the realistic ceiling |
| Cloudflare D1 | 100k row writes/day, 500 MB per database | ~10–20 rows/pass | vast | Never put vectors here. 900k × 1 kB would fill the database twice over in a year |
| GitHub Models | ~50–150 requests/day, prototyping | optional experiments | thin | Not something to schedule against |
| Hugging Face | Free public dataset hosting | ~20 MB of vectors/pass | good | The free Inference API is rate-limited and is not a batch backend |
| Bandwidth | — | ~10.5 GB/pass | — | **The real bottleneck.** 10 GB on a 6-hour runner is fine; 10 areas becoming 40 is not |

The binding constraints, in order: **reviewer attention**, then **bandwidth**, then **VRAM**,
and only then GPU hours. GPU hours are the one thing we have plenty of, which is exactly
backwards from how this kind of project is usually described.

### What we would do if a limit were hit

- **More areas than bandwidth allows** → drop to Landsat at 30 m for the wide sweep (9× fewer
  tiles, 9× less data) and reserve Sentinel-2 for areas the sweep flags. Says less; costs less.
- **Kaggle access lapses** → CPU embedding in sharded GitHub Actions jobs, at a weekly cadence.
- **Reviewers saturated** → lower the cap from 20 to 10 and raise the change threshold. Never
  the other way: a queue nobody reads is worse than no queue
  ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)).

---

## What this architecture deliberately cannot do

- **See a vehicle, a person or a tail number.** At 10 m a car is a tenth of a pixel. This is a
  property of open imagery, not of the model, and no amount of fine-tuning changes it.
- **Be live.** Sentinel-2 revisits every 5 days, Sentinel-1 every 12, Landsat 8/9 about every
  8. A finding can never be fresher than the last usable pass, and cloud makes that worse.
- **Watch Türkiye.** By construction, not by policy setting.
- **Publish anything.** Every output is a proposal to a person.
