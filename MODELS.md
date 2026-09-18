# Models

The owner's question was "which base model should we build on?". This is the answer, with the
evidence, and with the parts that are **not** possible said plainly.

> **How to read the tables.** "Weights" is the download at bf16/fp16. "VRAM (4-bit)" is a
> working estimate for inference with a modest batch and image context, not a benchmark we
> ran. "Free GPU" means a Kaggle P100 or T4 with **16 GB** of VRAM, which is the largest card
> we can reach without a payment method. Licences were checked in September 2026; **check
> again for the exact revision you download**, because several of these have changed.

---

## 1. The recommendation

**First choice — a two-model pipeline, both Apache 2.0:**

| Stage | Model | Why |
|---|---|---|
| Embed every tile (stage 4–6) | **Clay v1.5** | Apache 2.0 for code *and* weights; built for Sentinel-2 at 10 m and 256 × 256 tiles, which is exactly our grid; a 1024-d embedding per tile; handles S1, Landsat and MODIS with the same encoder, so adding radar later is a configuration change, not a new model |
| Read the survivors (stage 7) | **Qwen3-VL-4B-Instruct** | Apache 2.0 across the small sizes; fits a free 16 GB card in 4-bit with room for image tokens; strong general visual understanding, and we only need a narrow, well-posed question answered |

**Fallback — when the first choice does not fit the week we have:**

| Instead of | Use | When |
|---|---|---|
| Clay v1.5 | **Prithvi-EO-2.0-300M** (Apache 2.0) | If Sentinel-2's 10 m download volume breaks a free runner. Prithvi eats 30 m HLS, so the same area is ~9× less data — and shows ~9× less. It is also natively multi-temporal (up to 4 timesteps), which suits change detection well |
| Qwen3-VL-4B | **Qwen3-VL-2B** (Apache 2.0), or **Moondream 2** (Apache 2.0, ~1.9B) | If the session's GPU is smaller than expected, or if the stage has to run on CPU. Moondream 2 is the "runs anywhere" floor, including a laptop |

Nothing in this recommendation requires an account with a payment method, a paid API or a
rented GPU. Clay, Prithvi and the Qwen3-VL small sizes are all Apache 2.0 downloads from
Hugging Face, and all of them run in a free Kaggle session.

---

## 2. Vision-language models

The VLM only ever sees the ~100 tiles per pass that survived change detection
([ARCHITECTURE.md](ARCHITECTURE.md)), so its cost is bounded and we can afford a good one.

| Model | Params | Licence | Weights | VRAM (4-bit) | Fits a free 16 GB GPU? |
|---|---:|---|---:|---:|---|
| **Qwen3-VL-2B-Instruct** | 2B | **Apache 2.0** | ~4 GB | ~2 GB | Yes, comfortably; also viable on CPU |
| **Qwen3-VL-4B-Instruct** | 4B | **Apache 2.0** | ~8 GB | ~3 GB | **Yes — recommended** |
| Qwen3-VL-8B-Instruct | 8B | **Apache 2.0** | ~16 GB | ~5–6 GB | Yes, with less headroom for image context |
| Qwen3-VL-32B | 32B | **Apache 2.0** | ~64 GB | ~18–20 GB | **No.** Needs a 24 GB+ card; that is a rented GPU, which we cannot pay for |
| Qwen3-VL-235B-A22B | 235B (MoE) | **Apache 2.0** | ~470 GB | ~130 GB | **No, and not close.** Not on any free tier that exists |
| InternVL3-8B / -14B | 8B / 14B | Repository **MIT**, but the Qwen2.5 backbone carries Alibaba's Qwen licence, which adds a 100M-MAU commercial ceiling | ~16 / ~28 GB | ~6 / ~9 GB | Yes for 8B. **Licence is not uniform across sizes — read the exact checkpoint's LICENSE, not the repo's** |
| InternVL3-1B / -2B | 1B / 2B | as above, smaller Qwen2.5 backbones | ~2–4 GB | ~1–2 GB | Yes |
| **Moondream 2** | ~1.9B | **Apache 2.0** | ~4 GB | ~2 GB | Yes; the CPU-capable baseline |
| Moondream 3 (preview) | 9B MoE, 2B active | **Its own LICENSE.md — not Apache.** Read it before any use | ~18 GB | ~6 GB | Technically yes; **licence must be cleared first** |
| ~~Llama 3.2 11B / 90B Vision~~ | 11B / 90B | Llama 3.2 Community Licence | — | — | **Excluded — see below** |

### Why Llama 3.2 Vision is excluded

Two independent reasons, either of which is enough:

1. **The EU multimodal carve-out.** The Llama 3.2 Community Licence does not grant the
   §1(a) rights for the *multimodal* models to an individual domiciled in, or a company with
   its principal place of business in, the European Union. Our contributors are pseudonymous
   and distributed; we cannot audit where they are, and a licence whose validity depends on
   each contributor's address is not one we can rely on.
2. **The Acceptable Use Policy.** It prohibits use for "military, warfare, nuclear industries
   or applications, espionage". We are a civilian, open-source records project and we believe
   we are outside that, but a defence-and-security OSINT project arguing that line with Meta
   is a risk we do not need to take when Apache 2.0 alternatives are at least as good.

We therefore do not use Llama vision weights, and this is recorded here so nobody re-opens it
without reading both reasons.

---

## 3. Embedding models for retrieval

These turn a tile into a vector so that "find tiles like this one" and "has this tile changed"
become nearest-neighbour problems instead of model problems.

| Model | Params | Licence | Embedding dim | Notes |
|---|---:|---|---:|---|
| **SigLIP 2, base/patch16-224** | ~0.4 GB class | **Apache 2.0** | 768 | Strong image–text retrieval; lets a reviewer search tiles with a phrase. CPU-capable |
| OpenCLIP ViT-B/32 (LAION) | ~150M | MIT | 512 | The cheap, well-understood baseline. Weaker than SigLIP 2 on fine detail |
| DINOv2 ViT-B/14 | ~86M | Apache 2.0 — **but it was relicensed from CC BY-NC 4.0 in 2023; confirm the licence on the revision you actually download** | 768 | Self-supervised, excellent dense features, no text side |

These are *natural-image* models. They are useful for search and for a human-facing "show me
similar tiles" feature, and they are a reasonable sanity baseline, but for overhead imagery
with more than three bands an Earth-observation model beats them — which is the next section.

---

## 4. Remote-sensing foundation models

This is the stage that must be cheap, because it runs on everything.

| Model | Params | Licence | Input | Embedding dim | VRAM | Free GPU? |
|---|---:|---|---|---:|---:|---|
| **Clay v1.5** | 632M ViT | **Apache 2.0** (code *and* weights) | Multi-sensor: 10 bands S2, 6 Landsat, 2 S1, 4 NAIP, 7 MODIS; 256 × 256 tiles, 8 × 8 patches | 1024 (class token) | ~3–5 GB fp16 | **Yes — recommended** |
| **Prithvi-EO-2.0-300M / -300M-TL** | 300M (ViT-L) | **Apache 2.0** | HLS at 30 m, 6 bands (B02, B03, B04, B05, B06, B07), 224 × 224, up to 4 timesteps; `-TL` adds temporal and location embeddings | 1024 (`embed_dim`) | ~2–4 GB | **Yes — the fallback** |
| Prithvi-EO-2.0-600M / -600M-TL | 600M (ViT-H) | **Apache 2.0** | as above, patch 14 | 1280 | ~4–6 GB | Yes |
| Prithvi-EO-2.0-tiny / -100M | 5M / 100M | **Apache 2.0** | as above | smaller | <2 GB | Yes; the CPU-capable floor for EO |
| TerraMind 1.0 base / large | — | **Apache 2.0** (IBM + ESA) | Any-to-any generative EO, multi-modal | — | moderate | Yes. Interesting for cross-modal work (e.g. generating an optical view from radar); more than we need for stage 4 |
| DOFA | — | **Check per repository.** DOFA-**CLIP** is MIT; the base model's licence is not uniformly stated | Dynamic across wavelengths, 5 sensors | — | moderate | Probably, but **do not adopt until the licence is confirmed in writing** |
| SatMAE | — | **Check per repository** | Temporal / multi-spectral MAE | — | small | Yes. Older than the above; kept here because it is the ancestor of the approach, not because it is the best choice today |

### Why Clay first and Prithvi second

- **Resolution.** Clay works at Sentinel-2's 10 m; Prithvi at HLS's 30 m. A 30 m pixel cannot
  show a berm, a revetment or a small hardstand — it can show a new runway, a new building of
  a few tens of metres, a burn scar, a flood. Starting at 10 m keeps more of the questions we
  actually want to ask answerable.
- **Tile shape.** Clay's 256 × 256 native tile is the grid in [`tiling.py`](src/gt_osint_ai/tiling.py);
  Prithvi's is 224 × 224. Matching the model's native tiling avoids a resampling step that
  costs quality for nothing.
- **Sensors.** Clay covers Sentinel-1 with the same encoder, so the radar path — the one that
  works at night and through cloud — is a configuration change rather than a second model.
- **Multi-temporal.** This is Prithvi's advantage: it takes up to 4 timesteps natively, which
  is a better fit for change detection than comparing two independent embeddings. If change
  detection turns out to be the hard part rather than the easy part, Prithvi moves to first
  place, and this document should be rewritten rather than quietly ignored.
- **Precomputed embeddings.** Clay publishes Sentinel-2 embeddings on Source Cooperative under
  a CC BY licence, which would save us the whole of stage 4 — but the published coverage is
  Suriname, Brazil, Andhra Pradesh and the USA. **None of our areas are covered, so this is
  not usable today.** It is worth re-checking, because if global coverage lands, our most
  expensive stage becomes a download.

---

## 5. What fine-tuning could realistically add

In order of cost, cheapest first. Do them in this order.

**a) A linear probe on frozen embeddings — hours of work, no GPU.**
Train a logistic regression on the 1024-d Clay vectors against the labelled benchmark in
[EVALUATION.md](EVALUATION.md). It trains in seconds on a CPU, needs a few hundred labels, and
is often within a few points of a fine-tuned model on a narrow task. **This is the first thing
to try and the thing most likely to be enough.**

**b) QLoRA on the VLM — a few GPU-hours, genuinely free.**
A 4-bit QLoRA adapter on Qwen3-VL-2B or -4B, with 1,000–5,000 labelled tiles, fits in a single
9-hour Kaggle session on a 16 GB card. The adapter is tens of megabytes and is ours to publish
under MIT. What it realistically buys:

- **Vocabulary.** Teaching the model what a berm, a revetment, a hardstand, a pontoon, a
  laydown yard or a spoil pile looks like *at 10 m*, which a general VLM has barely seen.
- **Calibrated refusal.** Getting "too cloudy to say" and "cannot tell at this resolution" as
  frequent, correct answers instead of a confident guess. For a human-in-the-loop system this
  is worth more than raw accuracy.
- **Format.** A stable label + one sentence + confidence, so the queue row is machine-built.

What it cannot buy: **resolution**. A LoRA does not put information into a 10 m pixel that the
sensor never recorded. If the question needs to see a vehicle, the answer is no, and no amount
of training changes that.

**c) Fine-tuning the EO encoder — possible, probably not worth it.**
Unfreezing Clay's or Prithvi's later blocks on our own labels is within a free GPU budget for
the 300M model and marginal for the 632M one. It should only be attempted after (a) and (b)
have been measured, because it risks overfitting a few hundred labels and it makes every
stored embedding in the history incompatible with the new encoder.

---

## 6. What is not feasible, stated plainly

- **Training a foundation model from scratch.** Prithvi-EO-2.0 was trained on 4.2 million
  samples; Clay v1.5 is a 632M-parameter ViT trained across six sensors globally. Runs like
  these are hundreds to thousands of GPU-days on A100-class hardware. Against 30 free
  Kaggle GPU-hours a week on a P100, a 1,000 GPU-day run is on the order of **eight hundred
  years**. This is not a "someday when we have more time" item; it is arithmetic.
- **Running a 70B model, or Qwen3-VL-32B or -235B.** 32B needs ~20 GB in 4-bit, above the
  16 GB we can reach for free; 235B needs ~130 GB. Renting a GPU would cost money, and
  [ADR 0008](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0008-zero-budget-infrastructure.md)
  forbids a payment method on any account.
- **Running the VLM on every tile.** ~900,000 tiles a year at even 3 seconds each is ~750 GPU-
  hours a year — inside the Kaggle quota on paper, but it would consume the entire budget to
  answer a question that change detection answers for free on 99.5 % of tiles. The funnel is
  not a compromise; it is the design.
- **Sub-metre analysis of any kind.** Vehicle counting, aircraft identification, personnel:
  these need ~0.5 m commercial imagery from Maxar, Planet or Airbus, which costs money *and*
  forbids redistributing derived products in the way we would need. Out of scope on two
  independent grounds ([DATA.md](DATA.md)).
- **Anything about Turkish forces.** Not a capability question. The area gate refuses the
  imagery before a model ever sees it.

---

## 7. Sources

- Prithvi-EO-2.0 — [arXiv:2412.02732](https://arxiv.org/abs/2412.02732); model card and
  `config.json` at [ibm-nasa-geospatial/Prithvi-EO-2.0-300M](https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M)
  (Apache 2.0; `embed_dim` 1024, 6 bands, 224 px, 4 frames)
- Clay v1.5 — [clay-foundation.github.io/model](https://clay-foundation.github.io/model/);
  [release specification](https://clay-foundation.github.io/model/release-notes/specification.html);
  precomputed embeddings at [source.coop/clay/clay-v1-5-sentinel2](https://source.coop/clay/clay-v1-5-sentinel2)
- Qwen3-VL — [github.com/QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)
- InternVL 3 — [github.com/OpenGVLab/InternVL](https://github.com/OpenGVLab/InternVL);
  licence discussion on [OpenGVLab/InternVL3-38B](https://huggingface.co/OpenGVLab/InternVL3-38B/discussions/1)
- Llama 3.2 — [Acceptable Use Policy](https://www.llama.com/llama3_2/use-policy/);
  EU multimodal carve-out in the [Llama-3.2-11B-Vision model card](https://huggingface.co/meta-llama/Llama-3.2-11B-Vision)
- Moondream — [vikhyatk/moondream2](https://huggingface.co/vikhyatk/moondream2) (Apache 2.0);
  [moondream3-preview LICENSE.md](https://huggingface.co/moondream/moondream3-preview/blob/main/LICENSE.md)
- SigLIP 2 — [google/siglip2-base-patch16-224](https://huggingface.co/google/siglip2-base-patch16-224) (Apache 2.0)
- TerraMind — [github.com/IBM/terramind](https://github.com/IBM/terramind) (Apache 2.0),
  [ESA announcement](https://www.esa.int/Applications/Observing_the_Earth/ESA_and_IBM_collaborate_on_TerraMind)
- DOFA — [arXiv:2403.15356](https://arxiv.org/abs/2403.15356); DOFA-CLIP (MIT) at
  [xiong-zhitong/DOFA-CLIP](https://github.com/xiong-zhitong/DOFA-CLIP)
- Free-tier figures — [Kaggle: efficient GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage);
  Cloudflare Workers AI free allocation (10,000 neurons/day)
