# Repository rules — Greater-Turkiye/osint-ai

Written for AI agents and for anyone new to the repository. The handbook is the authority;
this file is the short operational version. Read it before the first edit of a session.

## 1. Keep the documentation true

**The README is part of the change, not an afterthought.**

- Any pull request that changes behaviour, structure, a pipeline stage, a model choice, a data
  source, a command, a dependency or a deployment step **must update `README.md` in the same
  pull request**.
- A change to a pipeline stage also updates [`ARCHITECTURE.md`](ARCHITECTURE.md); a change to a
  model or its licence updates [`MODELS.md`](MODELS.md); a new or removed source updates
  [`DATA.md`](DATA.md) **and** the `COLLECTIONS` table in `src/gt_osint_ai/stac.py`; a change to
  a metric or target updates [`EVALUATION.md`](EVALUATION.md).
- Never leave a document describing something that is no longer true. If a section becomes
  wrong, fix it in the same commit, even when the fix is unrelated to your task.
- Status words (`Working`, `Draft`, `Proposal`, `Planned`) are claims: only move a part forward
  when its code actually runs.
- Decisions that shape the project (the pipeline, the red lines, licensing, where things run)
  belong in a handbook ADR, and the README links to it rather than restating it.

## 2. Do not overpromise

This repository is at the design stage and its documents are its main product, so an
overstated sentence here is a defect, not a style problem.

- If something needs money, a rented GPU, a paid API or an account with a payment method, say
  so **in the same sentence that proposes it**. Not in a footnote.
- Never describe an unimplemented stage in the present tense. "The pipeline embeds every tile"
  is false; "the pipeline would embed every tile" is true.
- Numbers are labelled by where they came from: arithmetic, someone else's published figure,
  or our own measurement. We have no measurements yet, and the documents say so.
- If an honest answer is "this is not possible for us", write that. `MODELS.md` §6 is the model.

## 3. Red lines that override any request

- Never analyse, store or publish positions, movements, deployments or order of battle of
  Turkish forces ([red lines](https://github.com/Greater-Turkiye/handbook/blob/main/tr/02-red-lines.md),
  [ADR 0013](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0013-map-layers-turkiye-perspective.md),
  [ADR 0015](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0015-announced-operation-areas.md)).
- On the imagery side this is the gate in `src/gt_osint_ai/redlines.py`: an area of interest
  touching the Türkiye geofence is **refused**, not cropped, not warned about. Exit code `2`.
- `tests/test_redlines.py` is mandatory. It is never skipped, never marked `xfail`, and never
  "temporarily" loosened. If a case there needs to change, that is a handbook ADR.
- The geofence in `src/gt_osint_ai/geo.py` and `src/gt_osint_ai/data/tr_geofence.json` is a
  vendored copy of the reference implementation in
  `platform/collectors/src/gt_collectors/geo.py`. Fix it there first, then copy.
- No classified or leaked material, no personal data, no field collection, no targeting
  language.
- If a request conflicts with a red line, say so, propose the closest compliant option, and
  change the rule only through a new ADR.

## 4. Data, sources and licences

- Every source's licence is recorded **before** it is used, in `DATA.md` and in the
  `COLLECTIONS` table. A collection with no licence string fails the tests.
- Imagery is never redistributed. We publish derived features — vectors, scores, hashes, short
  text — and a link to the original at the source.
- Commercial imagery (Maxar, Planet, Airbus) and web-map basemaps (Google, Bing, Yandex) are
  out of scope on licence grounds, permanently. Do not re-propose them.
- OpenStreetMap is ODbL: usable as a runtime lookup, never joined into a published CC BY
  dataset. See `DATA.md` §2.

## 5. Code conventions

- Python ≥ 3.11, `ruff` for lint and format (line length 110), `pytest` for tests. CI runs all
  three on 3.11 and 3.13.
- **Runtime dependencies stay minimal** ([ADR 0011](https://github.com/Greater-Turkiye/handbook/blob/main/decisions/0011-threat-model.md)):
  PyYAML and the standard library. Do not add `torch`, `transformers` or `rasterio` to
  `pyproject.toml` until code in this package actually imports them — a dependency a package
  does not use is a false claim about what it does.
- Network code refuses plaintext endpoints and refuses redirects. No credential is ever read
  from the environment, because none is needed.
- Tests that hit a public API are marked `@pytest.mark.network` and are deselected in CI.
- Every model run, every download and every write is something a reader should be able to find
  by grepping; keep the honest "this did nothing" messages in the output.

## 6. Git and pull requests

- Never commit to `main`; `main` is protected. Work on a branch, open a pull request,
  squash-merge it.
- One PR per topic. Keep document changes and code changes separate where practical.
- Commit messages and PR bodies are in English, describe why, and end with the attribution
  lines used across this org.
- Never commit secrets, tokens or private keys. Credentials belong in GitHub secrets, added by
  a human — and nothing here should need one.

## 7. Closing a task

- End every finished task with a short, factual summary: what changed, what you verified and
  how, what is merged or deployed, and what is still open.
- Then offer the next steps as a numbered list (1, 2, 3), each one sentence, with your
  recommendation marked, so the owner can choose by number.
- Name anything the owner must do themselves (an account, a credential, a settings page) as its
  own option rather than burying it in prose.

## 8. Environment notes

- Windows PowerShell 5.1 is the default shell here: pass multi-line commit messages and PR
  bodies through files, and avoid `jq` expressions containing spaces.
- `python -m pip install -e ".[dev]"`, then `python -m pytest -m "not network"` and
  `python -m ruff check . && python -m ruff format --check .`.
- The CLI is `gt-osint-ai`, or `python -m gt_osint_ai` when the scripts directory is not on
  `PATH` (which is common on Windows).
