# System One Decision Models: an evaluation of Jev, Kev and CLM-8B

A working evaluation of the three most-discussed "System One" decision models —
models that read a piece of state plus typed questions and return calibrated
probabilities instead of generated text:

- **Jev** (TypeSafe AI) — the hosted, closed-weight original.
- **Kev** (Jared Palmer) — an open Apache-2.0 family (0.8B–27B) that reimplements
  Jev's API contract on Qwen3.5/3.8 bases.
- **CLM-8B** (Stanford + NVIDIA) — an open contrastive model that turns the
  decision into a vector-matching step with cached actions.

The repo combines published third-party benchmarks with fresh latency
measurements from running Kev-0.8B locally on a mainstream consumer laptop
(GTX 1650 4 GB). Raw logs are in [`data/`](data/), reproduction scripts in
[`scripts/`](scripts/).

**Headline findings**

1. On straightforward classification, open Kev-4B lands within 1–2 accuracy
   points of hosted Jev, but its stated probabilities are noticeably less
   calibrated (Opper fresh-data A/B, 362 items).
2. On decisions that require reasoning over a state (rule chaining, "proof
   depth"), Jev leads by large margins: +25 points over Kev-9B on 1,800 items.
   Kev is competitive only on depth-0 decisions.
3. CLM-8B is genuinely faster (up to 9× in its own zero-shot tests, mostly
   from local execution plus action caching) but trades 4–5 accuracy points on
   tool-calling, is not calibrated, and rarely abstains (<2% "uncertain" vs
   75% for Jev in tri-state tests).
4. On a 4 GB laptop GPU only Kev-0.8B fits. It answers short states in ~190 ms
   (median) — comparable to hosted Jev including network — but throughput is
   ~5 req/s with 8 concurrent clients, and there is no cross-request state
   caching on the CUDA backend.

---

## 1. Background

TypeSafe launched Jev on 15 September 2026 as its first *System One model*: a
model that takes a state (any text) and a set of typed questions — yes/no
(`noul`), multiple choice (`choice`), or rubric score (`score`) — and returns a
probability for every option, plus a confidence. No paragraph generation. The
intended use is the small bounded decisions inside agent loops: route a ticket,
pick a tool, verify a claim, decide whether to escalate.

Jev is hosted and closed-weight; its size and architecture are unpublished.
Within a week of release, roughly 30 open reproductions appeared, rebuilt from
the API contract alone. The two most visible are Kev and CLM-8B.

## 2. The contenders

| | Jev | Kev | CLM-8B |
|---|---|---|---|
| Maker | TypeSafe AI | Jared Palmer (open source) | Stanford Scaling Intelligence Lab / Hazy Research + NVIDIA Research |
| Released | 2026-09-15 | Kev 1.0, 2026-10-01 | 2026-09-23 |
| Weights | closed, versioned | open, Apache-2.0 | open, Apache-2.0 |
| Sizes | undisclosed | 0.8B / 4B / 9B / 27B | 8B (35B-A3B announced) |
| Architecture | undisclosed ("System One", RLCD-trained) | Qwen3.5/3.8 base + rank-16 LoRA + pointer head (27B: full fine-tune); DeltaNet hybrid attention | contrastive dual-encoder (InfoNCE), frozen Qwen3-8B backbone + trained projection heads; per-action embedding cache |
| Hosting | hosted API (`/v1/systemone`) | self-hosted, same wire format; TypeSafe SDK drop-in | self-hosted, TypeSafe-compatible API |
| Calibration | calibrated (RLCD) | fitted temperature shipped per checkpoint; calibrated on seen workloads | not calibrated for general use |

All three answer the same request shape, which makes head-to-head testing and
switching cheap.

## 3. Methodology and provenance

Three kinds of evidence, kept separate:

- **Third-party independent benchmarks** — run by parties not affiliated with
  the models' makers.
- **Maker-reported numbers** — the two open projects' own harnesses and the
  Stanford/NVIDIA team's paper numbers; flagged as such because selection
  bias and base-model exposure are unknown.
- **Our own measurements** — fresh, single-machine latency runs of Kev-0.8B
  (see §4.5). Raw logs in `data/`.

Caveats that apply throughout:

- Harder fresh tasks would separate the models more than the easy
  classification tasks in the fresh-data A/B.
- Kev trained on several public classification datasets; "fresh" means fresh
  items, not necessarily fresh task types.
- Hosted-model latency includes network round-trip; local numbers do not.
  These are not like-for-like and are reported as such.

## 4. Results

### 4.1 Reasoning-heavy decisions: Jev vs Kev (independent, hard-decisions.anth.us)

1,800 items scored by "proof depth" (number of inference steps needed), open
world (true / false / unknown), 95% intervals:

| Model | Overall | depth 0 | depth 1 | depth 2 | depth 3 | depth 4 | depth 5 |
|---|---|---|---|---|---|---|---|
| Jev | **83.8%** | 97.7% | 87.7% | 84.8% | 79.9% | 71.9% | 81.0% |
| Kev-9B | 58.6% | 89.3% | 73.8% | 58.4% | 49.5% | 38.6% | 41.2% |
| Kev-4B | 53.6% | 87.7% | 62.9% | 52.1% | 44.6% | 37.3% | 36.3% |
| Kev-0.8B | 53.6% | 70.3% | 54.0% | 46.9% | 48.8% | 50.5% | 50.9% |

- Jev minus Kev-9B: **+25.3 points** overall (95% CI +23.0 to +27.8).
- The gap grows with depth: +8.3 at depth 0 → **+39.8** at depth 5.
- Closed-world (true/false) results show the same pattern (Jev 99.3% → 76.3%
  across depths; Kev-9B 89.7% → 43.0%).

On depth-0 decisions Kev-9B is close to Jev; anything requiring chained
reasoning separates them sharply.

### 4.2 Fresh-data classification and calibration (independent, Opper A/B)

362 items published *after* both models were released (new arXiv papers,
Stack Exchange questions, GitHub issues), Kev-4B vs Jev through the same
endpoint, one question per request:

| Task | Jev acc | Kev-4B acc | Jev calib. error | Kev-4B calib. error |
|---|---|---|---|---|
| arXiv category (8 options, n=160) | 96.9% | 95.0% | 0.032 | 0.044 |
| Stack Exchange site (6 options, n=120) | 97.5% | 98.3% | 0.027 | **0.125** |
| GitHub bug vs feature (yes/no, n=82) | 95.1% | 93.9% | 0.049 | **0.137** |

Accuracy is inside the noise for both; the systematic difference is
**calibration**: Kev's top-1 accuracy is fine, but its probability values
drift from actual hit rates, which matters whenever a threshold
("escalate if p > 0.8") is applied to the output.

On five older public datasets Kev did not train on (emotion, offensive tweets,
QNLI, PAWS, SciQ), Jev led clearly on paraphrase detection (PAWS 87.0% vs
74.5%) and slightly on QNLI and SciQ; Kev led on emotion and offensive tweets.

Also from the same A/B: Jev counts a fixed ~257 extra input tokens on every
request (most likely its internal prompt). Same one-line request: 280 tokens on
Jev vs 23 on Kev — up to a 12× cost gap on short requests at identical list
prices, shrinking to ~1.3× on long multi-question requests.

### 4.3 Kev family, maker-reported (jaredpalmer.com blog + model cards)

Accuracy on *new sources* (datasets and policy rules Kev never trained on),
development / test splits:

| Model | New sources | Brier (new) | Generalization index |
|---|---|---|---|
| Kev-0.8B | 0.648 / 0.697 | 0.481 / 0.416 | 23.3 |
| Kev-4B | 0.817 / 0.838 | 0.269 / 0.242 | 38.0 |
| Kev-9B | 0.820 / 0.852 | 0.289 / 0.217 | 41.0 |
| Kev-27B | **0.851 / 0.889** | **0.225 / 0.156** | **52.3** |
| Jev | 0.857 (dev only) | 0.211 (dev only) | 54.0 |

- Kev-27B is within a point of Jev on new sources; 4B and 9B within four.
- Brier (full distribution, lower is better): Kev-27B 0.225 vs Jev 0.211.
- Same data, author caveat: Jev has only been run on the development split,
  so this is not a controlled comparison.

### 4.4 CLM-8B vs Jev (Stanford/NVIDIA team numbers)

Zero-shot evaluation across computer use, gaming and tool calling:

| Benchmark | CLM-8B | Jev |
|---|---|---|
| BFCL v4 tool calling | 95.2% | **99.2%** |
| WikiRacing (tasks completed) | 26/30 | **30/30** |
| T-Rex game | comparable | comparable |
| Latency (cached actions) | **up to 9× faster** | baseline |

As a best-of-N verifier after lightweight fine-tuning (a role Jev does not
serve in these tests):

| Benchmark | CLM-8B | Jev |
|---|---|---|
| DeepSWE (38 held-out tasks) | **81.6%** | 71.1% |
| Terminal-Bench 2.1 (30 tasks) | **87.6%** | 83.1% |
| Latency as verifier (H100) | **4.1–5.7× faster** | baseline |

Independent caveats (null_teck, Zenn): the 9× figure partly compares local GPU
execution against a cloud API round-trip; with dynamically changing action
spaces the cache hit rate drops to zero and CLM must run full 8B forward passes
per candidate, which can be *slower* than specialized decision models.
CLM also abstains almost never: in tri-state routing tests it assigned <2%
probability to "uncertain" vs 75% for Jev — relevant for any workflow that
expects the model to escalate ambiguous cases.

### 4.5 Latency: measured locally (this repo)

Our own runs: Kev-0.8B (v1.0) on a GTX 1650 4 GB / i7-9750H (6c/12t) / 16 GB
RAM / Windows 10.0.26200, CUDA via torch 2.6.0+cu126, single server process,
median over N requests:

| Scenario | Median | Min–Max | N |
|---|---|---|---|
| Short state (~100 tok), 3 questions | **187 ms** | 186–188 ms | 6 |
| Document, 2,417 tokens, 3 questions | **798 ms** | 765–859 ms | 4 |
| Document, 7,310 tokens, 1 question | **1,036 ms** | – | 1 |
| Same state, new question (KV reuse) | 407 → 296 ms | 1.4× | 1 |
| 8 concurrent clients × 8 requests | 4.9 req/s | median 1,620 ms, p90 1,688 ms | 64 |

Reference points for context:

- Jev (hosted): ~190 ms internal (hard-decisions.anth.us timing); ~265–275 ms
  end-to-end via Opper from a EU location; ~150–500 ms in press coverage —
  all including network.
- Kev-0.8B on an Apple M1 Max: 123 ms median; Kev-4B on M1 Max: 897 ms
  (18 GB peak memory).
- Kev-4B on an Apple M5 (maker-reported): 721 ms for 5 questions over a short
  text, **136 ms** when the state is cached — the CUDA backend we tested did
  not show equivalent cross-request caching (1.4× vs 5×).
- Maker-reported GPU serving (Modal): Kev-0.8B 63 req/s, 23 ms model time on
  an L4; Kev-4B 51 req/s, 42 ms.

Variance note: this class of laptop is sensitive to background load. During an
earlier run under load the same long-document scenarios took up to 34 s
(2.4k tokens) and 219 s (7.3k tokens). Figures above are from an idle machine;
treat them as indicative, not certified.

## 5. What actually runs on a 4 GB laptop GPU

- **Kev-0.8B fits**: ~1.8 GB of weights (bf16) — the only member of the family
  validated for a 4 GB GPU.
- **Kev-4B / 9B do not**: ~9.3 GB / ~19.3 GB of weights; they target 32 GB-class
  hardware. On this CPU-only the per-decision time becomes minutes.
- **CLM-8B does not**: a Q4 quant is ~5 GB, above 4 GB VRAM.
- Long documents are usable but slow: a 7.3k-token state takes ~1 s on this
  GPU, and the CUDA backend does not cache the state between requests (the MLX
  backend does).
- Setup notes for Windows (encountered during this study):
  - `uv sync` installs a CPU-only torch build; reinstall it from the PyTorch
    CUDA index (`uv pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.6.0`).
  - `huggingface_hub` fails with `WinError 1314` on Windows unless
    `HF_HUB_DISABLE_SYMLINKS=1` is set — the cache then uses file copies.

## 6. Recommendations

- **High-volume, low-ambiguity, short-state decisions** (routing, triage,
  label checks): Kev-0.8B locally is free, ~190 ms per decision and keeps data
  on-premise. Validate your own error budget first.
- **Decisions with confidence thresholds or chained reasoning**: hosted Jev.
  The accuracy gap on anything beyond depth-0 reasoning is 20+ points and its
  probabilities are calibrated; at ~$0.001 per decision the cost is negligible
  at low volume.
- **Stable, large action spaces or best-of-N verification, with ≥8 GB VRAM**:
  CLM-8B. Cache the action set once and score states in a single dot-product
  step — the one scenario where the 9× claim holds. It is not calibrated and
  almost never abstains: keep an explicit fallback for ambiguity.

## 7. Reproduction

```bash
# 1. Serve Kev locally (repo: https://github.com/jaredpalmer/kev)
git clone https://github.com/jaredpalmer/kev.git && cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.8b --port 8009

# 2. Run the benchmarks from this repo (server on localhost:8009)
python scripts/bench_latency.py     # short + long + cache scenarios
python scripts/bench_throughput.py  # context ceiling + concurrency
```

Scripts only need the Python standard library. Raw outputs are in `data/`.

## 8. References

- Jev announcement — TypeSafe AI: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- Kev repo, model cards, blog: https://github.com/jaredpalmer/kev ·
  https://jaredpalmer.com/blog/introducing-kev
- Kev vs Jev by proof depth (independent): https://hard-decisions.anth.us/compare/jev-vs-kev/
- Jev vs Kev fresh-data A/B (independent): https://opper.ai/blog/jev-vs-kev-open-decision-model
- CLM-8B (Stanford/NVIDIA), benchmarks and independent caveats:
  https://www.eneralabs.com/blog/stanford-nvidia-clm-8b-system-one-agent-routing-enterprise-2026/ ·
  https://zenn.dev/null_teck/articles/clm-vs-decision-models
- CLM-8B vs Jev comparison: https://jevtypesafeai.com/compare/clm-8b-vs-jev

## 9. License and attribution

The content of this repo is licensed CC-BY-4.0. External figures are quoted
from their sources above and remain the property of their authors; this repo
does not redistribute any model weights or datasets. The local latency data
was produced by the scripts in `scripts/` against a stock Kev-0.8B server.