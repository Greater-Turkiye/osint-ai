# Data

Every source below has its licence recorded **before** it is proposed for use, as
[ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md)
requires. A source with no clear, redistributable licence does not enter the pipeline, however
useful it looks.

> **The one rule that shapes everything here:** we never redistribute imagery. We publish
> **derived features** — vectors, scores, hashes, short text — and a link so anyone can fetch
> the original from the source themselves.

---

## 1. Imagery sources

| Source | Licence | Access | Resolution | Revisit | Quota / cost | Use |
|---|---|---|---|---|---|---|
| **Sentinel-2 MSI L2A** | Copernicus open licence: free, full and open; attribution required | Earth Search STAC + COGs on AWS Open Data — **no account, no key** | 10 m (VIS/NIR), 20 m, 60 m | 5 days | None that we can reach; Earth Search is best-effort with no SLA | **Primary optical.** Stages 2–6 |
| **Sentinel-1 SAR GRD** | Copernicus open licence | Earth Search STAC + AWS | 10 m | 12 days per satellite, shorter where passes overlap | as above | **Cloud- and night-independent.** The answer to a month of overcast |
| **Landsat 8/9 Collection 2 L2** | USGS/NASA, public domain (attribution requested) | Earth Search STAC + AWS | 30 m (15 m pan) | ~8 days combined | None | **The cheap wide sweep** — 9× fewer tiles than Sentinel-2 |
| **HLS (Harmonized Landsat–Sentinel-2)** | NASA, free and open | NASA Earthdata / LP DAAC — **needs a free account**, which is a manual step for a maintainer | 30 m | ~2–3 days combined | Generous, but account-gated | Only if we adopt Prithvi, which is trained on HLS |
| **Copernicus DEM (GLO-30)** | ESA, free with attribution | AWS Open Data | 30 m elevation | static | None | Context: slope, terrain masking |
| ~~Maxar, Planet, Airbus~~ | **Commercial.** Costs money *and* restricts redistribution of derived products | — | 0.3–3 m | — | — | **Excluded on two independent grounds.** Not "later when we have budget" — the licence is the harder problem |
| ~~Planet NICFI basemaps~~ | Free for approved users, but redistribution-restricted, and **tropics only** | — | ~4.7 m | monthly | — | **Excluded.** Even if the licence were fine, it does not cover our region |
| ~~Google / Bing / Yandex satellite tiles~~ | **Terms of service forbid bulk tile access and derived analysis** | — | ~0.3 m in places | — | — | **Excluded.** This is the one most likely to be suggested — "just scrape the map images" — and it is the clearest no in this document |

### On "map images"

The original ask mentioned scanning map and satellite imagery. Web-map basemaps (Google,
Bing, Yandex, Apple) are the images most people picture, and they are exactly the ones we
cannot use: their terms prohibit bulk downloading and derived analysis, and imagery in them is
licensed from commercial providers. Using them would put the project's licensing, and anyone
who republished our output, in a bad position. The open missions above are what we have, and
they are genuinely good — just coarser.

---

## 2. Metadata and context sources

| Source | Licence | Access | Quota | Use |
|---|---|---|---|---|
| **NASA FIRMS** (thermal anomalies) | NASA, free and open, attribution | REST API — **needs a free API key**, a manual step | Documented per-key transaction limits; well within our volume | Near-real-time (~3 h) fire and thermal signal at 375 m (VIIRS) / 1 km (MODIS). A cheap independent cue for "look here" |
| **Natural Earth** | **Public domain** | Vendored | — | The Türkiye geofence in [`data/tr_geofence.json`](src/gt_osint_ai/data/tr_geofence.json), built in `platform` |
| **OpenStreetMap** | **ODbL 1.0** — attribution **and share-alike on derived databases** | Overpass / planet extracts | Be polite to Overpass; it is volunteer-run | Reference only — see the warning below |
| **GEBCO / EMODnet bathymetry** | Free with attribution; check the specific product | Download | — | Maritime context |

### The OpenStreetMap trap

ODbL's share-alike applies to a *derived database*. Our data is CC BY 4.0
([ADR 0009](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0009-licensing.md)),
and the two are not compatible in the direction we would need. So:

- **Allowed:** using OSM at runtime as a lookup — "is there already a known port, airfield or
  quarry in this tile?" — to suppress false positives, without the answer becoming part of a
  published database.
- **Not allowed:** publishing a dataset of our tiles enriched with OSM attributes under CC BY.
  That is a derived database and it would have to be ODbL.
- **If we ever need an OSM-derived layer**, it is published separately, under ODbL, with its
  own attribution, and it is not mixed into the CC BY record set.

This is written down because it is the kind of thing that is easy to get wrong six months from
now, in a single convenient join.

---

## 3. "Millions of images" — the realistic answer

We never hold millions of images. We hold a bounded number of **tiles**, and most of them are
discarded before anything expensive happens. Four mechanisms do the work.

### a) Tiling with a stable identity

The AOI is cut on a fixed MGRS-aligned grid, so the same patch of ground gets the same tile id
on every date. At 10 m a 256 × 256 tile is 2.56 km square; with 32 px overlap it costs
5.02 km² of coverage. A watch list of 100,000 km² is therefore **~20,000 tiles per pass**,
and that number does not grow with time — only with area.

### b) Masking before anything expensive

Using the L2A scene-classification band: drop tiles over ~40 % cloud, cloud shadow, cirrus or
no-data; drop tiles over ~90 % water unless the AOI is maritime. Over a year in the eastern
Mediterranean this removes roughly a third to a half of all tiles, on CPU, for free.

### c) Deduplication at three levels

| Level | Test | Effect |
|---|---|---|
| Scene | STAC item id + processing baseline unchanged since the last pass | Skip the whole scene — it is the same pixels. Reprocessed scenes get new ids, so this is safe |
| Tile | Content hash of the exact byte window read | Catches identical reads across overlapping scenes |
| Semantic | Cosine distance of the tile embedding to its own rolling baseline below threshold | **This is the big one.** It is the change detector and the deduplicator at once, and it removes 99 %+ of tiles |

### d) Change detection instead of recognition

We do not ask "what is in this tile?" of 20,000 tiles. We ask "is this tile different from
itself last month?", which is a cosine distance — pure linear algebra on CPU. Only the top
0.5 % (hard cap 200) go to a model that thinks, and only ~10–20 reach a human.

**Annual totals:** ~900,000 tile-embeddings a year, ~20 MB of vectors per pass, and roughly
500 human-facing candidates a year. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full
arithmetic and where each free tier runs out.

---

## 4. What we store, and what we never store

**Never stored, never committed, never published:**

- imagery, tiles, crops, thumbnails or quicklooks — not even "just for the queue";
- anything inside the Türkiye geofence, at any stage, in any form;
- raw model prompts or outputs containing third-party text.

**Stored — all of it derived, all of it ours to license as CC BY 4.0:**

| Field | What it is | Size |
|---|---|---|
| `tile_id` | Deterministic from the MGRS grid cell and pixel offset | ~24 bytes |
| `stac_item_id` | A pointer to the source scene, so anyone can fetch the original | ~32 bytes |
| `observed_at` | The scene's datetime | 20 bytes |
| `source_hash` | `sha256:` of the exact byte window read, for reproducibility | 71 bytes |
| `embedding` | The int8-quantised 1024-d vector | 1,024 bytes |
| `change_score` | Cosine distance to the rolling baseline | 4 bytes |
| `label`, `reason_tr`, `reason_en`, `confidence` | Only for candidates that reached the VLM | a few hundred bytes |

Roughly **1.2 kB per tile**, so ~20 MB per pass and under a gigabyte a year if we kept
everything — and we do not: only the rolling baseline and the candidates survive a pass.

**Where it lives.** Vectors do not go into Cloudflare D1: the free plan is 500 MB per database
and 100,000 row writes a day, and it is the operational store for the review queue, not a
vector store. The proposal is a **public Hugging Face dataset repository** for embeddings
(free, no payment method, and they are CC BY 4.0 derived features), with only the ~10–20
candidate rows per pass written into `gt-ops.reviews`. Cloudflare R2 is not used because it
requires a payment method on the account, which
[ADR 0008](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0008-zero-budget-infrastructure.md)
forbids.

---

## 5. Attribution we owe

Any published output derived from these sources carries, at minimum:

- **Copernicus Sentinel data [year]** for Sentinel-1 and Sentinel-2;
- **Landsat courtesy of the U.S. Geological Survey** for Landsat;
- **NASA FIRMS** for thermal anomalies;
- **© OpenStreetMap contributors, ODbL** wherever an OSM-derived layer is published, and only
  then, and only under ODbL;
- **Greater Türkiye contributors, CC BY 4.0** for our own derived features.

A source-by-source credit file lands alongside the first real pipeline run, following the
pattern of `platform/apps/web/assets/LICENSES.md`.

---

## 6. Adding a source

1. Find the licence text. Not a blog post about the licence — the licence.
2. Confirm it permits redistribution of **derived features** with attribution. If it does not,
   the source can at most be a private cue and can never be the sole basis of a record
   ([ADR 0010](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0010-content-safety-gates.md)).
3. Record resolution, revisit, access method and quota in the table above.
4. If access needs an account or a key, say so explicitly — it is a manual step for a
   maintainer and it must never become a secret in this repository.
5. Add the collection to `COLLECTIONS` in [`stac.py`](src/gt_osint_ai/stac.py) with its licence
   string. The test suite fails if a collection has no licence recorded.
