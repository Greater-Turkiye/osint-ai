# Evaluation

How we will know whether any of this works — and the rule that stops us shipping something
that does not.

> **The shipping rule, up front:** a model that cannot beat the existing keyword filter, per
> reviewer-minute, on the same benchmark, **does not ship**. Not "ships with a caveat". Does
> not ship.

---

## 1. The benchmark

Small, honest, and buildable by a few people in a few evenings. Ambition here is the enemy: a
benchmark of 10,000 items that nobody finishes labelling is worth less than 150 items that are
labelled correctly.

**Size:** 150–300 tiles to start. **Positives:** 30–60 events.

**Sourcing rule — this one is not negotiable.** Every positive is built from an event that was
**already publicly reported** by an open, citable source, with a date, before we looked at any
imagery. We do not discover events to build the benchmark; we take events the world already
knows about and check whether the pipeline would have surfaced them. That keeps the benchmark
itself from being an intelligence product, and it gives every label a citation.

**Composition:**

| Class | How many | What |
|---|---:|---|
| True positives | 30–60 | A tile containing a publicly reported, dated change: new construction, a port or airfield extension, a dam, a large burn scar, a flood, a new quarry or spoil area |
| Hard negatives | 60–120 | The *same tiles before the event*. These are the ones that matter — they look almost identical and they are what a change detector must not fire on |
| Seasonal negatives | 30–60 | The same tiles a year earlier and a year later: crop cycles, snow, reservoir level, haze. The most common false-positive source in any change detector |
| Random negatives | 30–60 | Uniformly sampled tiles from the same AOIs and dates |

**Format:** a JSONL file in `eval/` in this repository, one line per item, holding the
`tile_id`, the `stac_item_id`, the date, the label, and the **URL of the public report** that
justifies it. No imagery, ever — the benchmark is a list of pointers plus our own labels,
which makes it CC BY 4.0 and redistributable.

**What the benchmark cannot contain:** any tile inside the Türkiye geofence. The area gate
refuses those before the catalogue is even queried, so a Türkiye tile cannot enter the
benchmark even by accident.

---

## 2. What we measure, and the targets

The triage stage is a **ranking** problem, not a classification problem: it must put the
interesting tiles near the top of a list, and the absolute scores are irrelevant. So the
metrics are recall and precision at a cut-off, not accuracy.

| Metric | Target | Why this number |
|---|---|---|
| **Recall @ top 0.5 %** | **≥ 0.80** | Of the known events, 80 % must appear in the 0.5 % of tiles that stage 6 forwards. Below this the funnel is throwing away the things it exists to find |
| **Recall @ top 2 %** | ≥ 0.95 | A sanity check that the misses are near-misses, not blind spots |
| **Precision at the human queue** | **≥ 0.20** | Of the ~10–20 items a reviewer sees per pass, at least one in five must be judged worth a second look |
| **Precision floor** | **> 0.10, hard** | Below one in ten, reviewers stop reading the queue — and a queue nobody reads is worse than no queue ([ADR 0007](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0007-human-in-the-loop-publishing.md)) |
| **Items per pass to a human** | **≤ 20, capped in code** | Reviewer attention is the scarcest resource in the whole system. The cap is not a setting |
| **Seasonal false-positive rate** | ≤ 0.05 on the seasonal negatives | If the detector fires on crop cycles it is a calendar, not a detector |
| **Calibration (ECE)** | ≤ 0.10 | A confidence a human cannot trust is worse than no confidence at all. Report a reliability curve, not just a number |
| **Red-line failures** | **0** | Binary and mandatory; see §5 |

These are *targets for the first version*, chosen to be achievable rather than impressive. If
the first honest measurement comes in below them, the number to change is the design, not the
target.

---

## 3. The comparison against the incumbent

The baseline is the keyword relevance filter already running in
`platform/collectors/src/gt_collectors/relevance.py`. Comparing it with an imagery model is
not straightforward — one reads text, the other reads pixels — so the comparison is made on
the only axis they share: **what a reviewer gets back for the time they spend.**

**The measure:** accepted candidates per reviewer decision. A reviewer marks each queue item
`drafted`, `bulletined`, `dismissed` or `redline`; the rate of `drafted` + `bulletined` over
all decisions is the number.

**The protocol — a 30-day shadow run:**

1. Imagery candidates enter the same `gt-ops.reviews` queue as text candidates, capped at 20
   per pass.
2. The queue does not show a reviewer where a candidate came from. Reviewers are blind to
   origin, so the comparison is not contaminated by expectation.
3. After 30 days, compute the accepted rate for each origin, with a confidence interval.
4. **If the imagery rate is below the keyword filter's, the imagery stage is turned off** and
   this document is updated with the measurement. Not tuned in place until it passes — turned
   off, then re-designed.

**Why shadow first:** it costs reviewers a bounded amount of attention, it produces the only
evidence that matters, and it can be stopped with a single configuration change.

---

## 4. What a good result would actually look like

Concretely, for the first version to be worth keeping:

- It surfaces **4 out of 5** of the publicly-reported changes in the benchmark within the top
  0.5 % of ranked tiles.
- A reviewer working through a pass of 20 items finds **4 or more** worth drafting.
- It says "cannot tell at this resolution" often, and is right when it says it.
- It never fires on a harvest, a reservoir drawdown or a snow line.
- It has never once been offered a tile of Türkiye, because the gate refused the area first.

That is a useful tool. It is not "fully automated OSINT scanning", and this document will keep
saying so.

---

## 5. Red lines are not a metric

Everything above is a score that can be traded off. The following are not:

- **No tile inside the Türkiye geofence is ever fetched, tiled, embedded or scored.** Tested
  in [`tests/test_redlines.py`](tests/test_redlines.py), which CI must never skip.
- **No candidate is published.** Every output is a proposal to a person.
- **No source is used whose licence has not been recorded** ([DATA.md](DATA.md)).

Any failure here is a stop-ship regardless of every score on this page, and it is fixed before
anything else is discussed.

---

## 6. Honest threats to this evaluation

Written down now, so that a good-looking result later is read with them in mind.

- **The benchmark is built from reported events, which are biased** towards the large, the
  photogenic and the politically salient. Real performance on small, unreported change will be
  worse than the number says, and we cannot measure by how much.
- **150–300 items is small.** Confidence intervals will be wide. Report them; do not round
  them away.
- **Labelling after the fact is easy.** Knowing an event happened makes its tile look obvious.
  Where possible, one person selects the tiles and a second labels them without the event
  description.
- **The seasonal negatives may be too easy** if drawn from the same year as the positives. Draw
  them from a different year.
- **Reviewer accepted-rate drifts** with who is on duty and how busy they are. Thirty days is
  short; treat a narrow win over the keyword filter as a tie.
