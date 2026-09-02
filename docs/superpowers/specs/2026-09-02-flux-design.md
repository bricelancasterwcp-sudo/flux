# flux — deterministic pre-repair for real Rust: pre-registered design

**Date:** 2026-09-02. **Status:** awaiting owner approval. Nothing below has
been run. Written before any instrument exists, per the house method
(`~/.claude/skills/rigorous-experiments`). Every black-oxide number carries
the path it was read from; the census figures in §2.2 were computed from
the committed files named there, by the command in §2.2.1, and nothing
else was computed.

## 1. The question, as an estimand with its lens

**Estimand.** For a fixed small model on a fixed task set, the change in
first-attempt pass rate, first-attempt compile rate, and tokens-to-green
when every rustc suggestion marked `MachineApplicable` is applied to a
fixed point *before* the program is judged or the model is asked to
repair it.

**Lens**, named in every verdict:

| field | value |
|---|---|
| definition | a program is *green* when it compiles under `rustc --edition 2021` and its stdout equals the task's `expected_stdout` byte for byte (black-oxide SPEC §45, unchanged) |
| presentation | unconstrained decoding; the arm's own initial prompt; repair prompt = black-oxide `eval/repair.py` with the **post-applier** program and **residual** diagnostics |
| sampler | temperature 0.2, top_p 0.95, num_ctx 8192, num_predict 2048, seeds 1–10, llama-server backend — pinned in black-oxide `eval/exp_campaign.py` and recorded in every committed `provenance.json` (read from `eval/results/v04-wave8-phaseb/results-small/base-rs-7/provenance.json`) |
| applier | rustc version recorded per run; `suggestion_applicability == "MachineApplicable"` only; fixed point with a round cap (§4) |

A pass rate quoted without the applier's rustc version is not a property
of the model: applicability marks change between rustc releases.

## 2. Phase 0 — the $0 census that decides whether anything is funded

### 2.1 What black-oxide stored, read from the code

`eval/rustc_adapter.py::_adapt_one` keeps `code`, the `rendered` text,
the primary span, and non-primary span locations as `notes`. It pins
`"suggestion": ""` and **drops rustc's `children`**, which is where the
`suggested_replacement` spans and their `suggestion_applicability` live.
**Applicability is not retained in any committed diagnostic.**

What *is* retained is the full program text of every attempt
(`triples.jsonl`, field `code`), the stored first diagnostic code, and
the task's `expected_stdout`. So the census re-runs rustc on committed
programs. That is $0, deterministic, and — because the oracle is stored
too — it can measure not only "does a suggestion exist" but "does
applying it produce a green program", with no model in the loop.

Verified on this box (rustc 1.96.0, 2026-05-25): a two-defect program
yields `E0382` with a `MachineApplicable` child span (`.clone()`) and
`E0384` with a `MachineApplicable` child span (`mut `). The field name is
`suggestion_applicability` on the child's span object.

### 2.2 What the stored codes already say (computed, not estimated)

First attempts only, `compiled == false`, first diagnostic's `code`, over
every Rust arm committed by wave 8. Ownership/mutability class =
{E0382, E0499, E0502, E0505, E0507, E0596, E0384, E0506, E0503, E0716,
E0597, E0373}.

| arm | tier | first attempts | not compiling | ownership-class first diag | stored first codes |
|---|---|---:|---:|---:|---|
| `base-rs-7` | small | 200 | **1** | 0 | E???? 1 |
| `tune-rs-7` | small | 200 | 10 | 0 | E0308 10 |
| `tune-rs-7` | **large** | 200 | **37** | **0** | E0308 16, E???? 5, E0434 4, E0614 4, E0277 2, E0425 2, E0606 1, E0106 1, E0433 1, E0600 1 |
| `base-rs-14` | small | 60 | 0 | 0 | — |
| `tune-rs-14` | **large** | 60 | 14 | **4** | E0308 9, E0382 4, E0615 1 |

Sources: `eval/results/v04-wave8-phaseb/results-{small,large}/<arm>/*-gen-s*/triples.jsonl`
and `eval/results/v04-wave8-14b-screen/results-{small,large}/<arm>/*-gen-s*/triples.jsonl`,
black-oxide at `521f602f4aaf4ef18c7f724a3df3afcc2e27a100`. Published
companions: `base-rs-7` small compiles 99.5% / pass@1 0.565; `tune-rs-7`
large compiles 81.5% / pass@1 0.200
(`eval/results/v04-wave8-phaseb/REPORT.md`); `tune-rs-14` large compiles
46/60 (`eval/results/v04-wave8-14b-screen/screen.json`).

**Three things follow before any instrument is built.**

1. **The small tier is unfundable and is not part of Phase 1.** The
   untuned 7B fails to compile 1 first attempt in 200. The lever's hard
   ceiling on small-tier pass@1 is 0.005. No band survives that.
2. **The thesis's mechanism is not what the data shows at 7B.** The
   Rust deficit on the small tier is programs that compile and print the
   wrong thing (0.565 pass against 0.995 compile), which no compiler
   suggestion addresses. On the large tier the 37 compile failures are
   type errors (`E0308`), scoping (`E0434`), and derefs (`E0614`) — zero
   ownership codes. Ownership codes appear only at 14B (4 of 14), which
   this box cannot serve at q8_0 in 16 GB.
3. **`E0308` decides it.** Sixteen of the 37 large-tier failures are
   type mismatches. rustc attaches suggestions to many of those
   (`.to_string()`, `as i64`, `&`, `.try_into().unwrap()`), and some are
   `MachineApplicable`. Whether that share is large or small is the whole
   census; it cannot be read from the stored codes.

#### 2.2.1 The command

Counted by a 25-line Python script over the files named above, filtering
`attempt == 1 and not compiled`, taking `diagnostics[0]["code"]`. The
script is committed with the Phase 0 instrument (§2.3) as its first
acceptance test: it must reproduce this table to the digit from the
pinned black-oxide checkout, or the instrument does not count.

### 2.3 The Phase 0 instrument

One module, `flux/census.py`, stdlib only, with the applier of §4 as its
dependency. For each of the five Rust arms above, for **every** attempt
(not only first attempts — later ones bound the tokens-to-green effect):

1. Re-run `rustc --edition 2021 --error-format=json --emit=metadata` on
   the stored `code` under the pinned rustc. Record the first error's
   code. **Drift check:** report every attempt whose re-derived first
   code differs from the stored one — rustc moved between the pod's
   version and 1.96.0, and that is a structural comparison the rest of
   the census depends on.
2. Record whether the first diagnostic carries at least one
   `MachineApplicable` span, and whether *any* diagnostic on the attempt
   does.
3. Run the applier to its fixed point. Record: rounds, applications
   (code, span, replacement), and the terminal state — `compiles`,
   `still-fails(code)`, `round-cap`, or `overlap-refused`.
4. For every attempt the applier brings to a compiling program: build,
   run under the black-oxide 10 s cap, compare stdout. Record `green`
   or `wrong-output` or `nonterminating`.

Every field is `None` until measured and named in a `dropped` list when
it cannot be; measured-and-zero is `0`. No default may look like a
measurement.

**Probe corpus, as a second reading (Phase 0b).** black-oxide's
`eval/probes.jsonl` holds 20 ownership defect classes × 3 arms, each
record with `broken`, `fix`, `expected_code`, `expected_stdout`. The Rust
arm's records are complete, correct programs carrying exactly one
ownership defect, with rustc's own diagnostic. Run the applier alone on
each of the 20 Rust records and report **which classes rustc fixes to
green by itself**. This is exact, has no sampling noise, and is the only
committed data in which ownership diagnostics are guaranteed to exist. It
is reported per class; it feeds no band, because the 7B families already
repair this arm at 89.0 / 84.5 / 73.0% strict
(`eval/results/ownership-probe-10seed/REPORT.md`, addendum table) and a
deterministic floor under a near-ceiling rate is a description, not a
lever.

### 2.4 The kill criterion, derived

Let `k` be the number of large-tier `tune-rs-7` first attempts (of 200)
that fail to compile and whose first diagnostic carries a
`MachineApplicable` suggestion, and `g ≤ k` the number the applier alone
brings to **green**.

The lever's hard ceiling on pass@1 is `k / 200`; on compile rate it is
also `k / 200`. Its deterministic component is exactly `g / 200`.

**Noise floor.** A difference of two rates near 0.20 at n = 200 has
SE = √(2 · 0.2 · 0.8 / 200) = 0.040, so 2 SE = **0.080**. That is the
unpaired figure; pairing on (seed, task) can only tighten it, so it is
the conservative bar. Near 0.815 (the compile rate) the same arithmetic
gives 2 SE = 0.078; the pass@1 bar of 0.080 is used for both.

**Floor to fund Phase 1: `k ≥ 16`.** Below that even the hard ceiling
cannot clear noise at the protocol's n, and no live run can distinguish
the lever from sampling. This is a derived number (0.080 × 200 = 16),
not a chosen one; the one chosen input is the 2-SE convention the
sibling repos already use.

Three pre-committed readings:

| Phase 0 result | reading | consequence |
|---|---|---|
| `k < 16` | the lever is below the noise floor of the protocol | **Phase 1 not funded.** flux closes as a $0 census with this table, the drift check, and the probe-class list. That is a finding, and it is published as one. |
| `k ≥ 16` and `g ≥ 16` | the deterministic component alone clears noise | publish `g / 200` as the no-model result; Phase 1 asks only whether the model adds to it on the residual |
| `k ≥ 16` and `g < 16` | suggestions apply but do not land green | Phase 1 is funded, because the residual is where the model would act; report `g` beside `k` so a reader sees how much rustc did by itself |

The 7B `k` decides. The 14B row is reported but funds nothing: this box
serves 14B only at q4_K_M in 16 GB, which is a different lens from the
q8_0 the committed data used, and robigo already measured what 14B
costs in KV geometry at this VRAM.

## 3. Phase 1 — the live experiment, funded only by §2.4

### 3.1 Arms

| # | arm | task set | role |
|---|---|---|---|
| 1 | `base-rs-7` | small (`eval/tasks.jsonl`, 20 tasks) | **drift guard.** Anchor pass@1 **0.565**, reproduced in eight environments to the digit, including this box (`eval/results/v04-wave8-phaseb/REPORT.md`; `eval/results/runpod-exp/REPORT.md` "byte-exact to the committed local v03c rust rate"). A miss voids the run. |
| 2 | `base-rs-7` | large (`eval/tasks-large.jsonl`, 20 tasks) | **baseline.** No anchor exists — wave 8 ran only tuned arms on the large tier — so this is a new row and is reported as one. |
| 3 | `base-rs-7 + flux` | large | **treatment.** Same model, same prompt, same seeds; the applier runs on every submission before the oracle and before any repair prompt. |
| 4 | applier alone on arm 2's submissions | large | **no-model floor.** Derived from arm 2's stored attempts, not a live arm; it is Phase 0's instrument run on Phase 1's data. |

Subject: `qwen2.5-coder:7b-instruct-q8_0`, the Ollama blob on this box
served by llama-server with `--expect-model-path` guarding identity. The
other two black-oxide families (`codegemma:7b-instruct-q8_0`,
`granite-code:8b-instruct-q8_0`, both present locally) run only if arm 3
vs arm 2 clears its band — a subject that cannot discriminate is dropped
before it is measured, not after.

The untuned model is the subject, not the tuned one: the v5 Rust
adapters are preserved locally but their merged 7B GGUF is not, and
rebuilding it is a pipeline change the guard would then be testing as
well as the environment.

### 3.2 Where the applier sits

Black-oxide's session (`eval/driver.py::run_session`) submits up to
`harness.MAX_ATTEMPTS = 4` programs (`eval/harness.py:65`); each failed
submission's diagnostics feed `eval/repair.py` for the next. flux inserts
one step between *submission* and *judgement*:

    model output → applier (fixed point) → rustc oracle → [fail] → repair prompt built from the APPLIED program and its RESIDUAL diagnostics

The model therefore never sees a diagnostic the compiler could have
resolved by itself, and it repairs from the cleaned text. Arm 2 is the
same loop with the applier replaced by identity.

### 3.3 Endpoints, pre-registered

All computed by black-oxide's `eval/experiment_report.py` where it has
the function, and by flux code only where it does not.

| endpoint | definition | primary? |
|---|---|---|
| **pass@1** | share of sessions whose first submission is green *after the arm's own pre-judgement step* — identity for arm 2, applier for arm 3. Both arms also report the raw model-only `first_passed`, so the applier's contribution to attempt 1 is visible, not folded. | **yes** |
| first-compile rate | same, for compiles | secondary |
| tokens-to-green | composition-controlled: pair on (seed, task), keep cells green in **both** arms, ratio of means (`paired_tokens_to_green`, `green_pair_keys`). Black-oxide SPEC §59.7 records why the per-arm mean is a defective estimand: a pass-rate change admits harder tasks into one arm's green set and moves the ratio for a non-efficiency reason. | secondary |
| applier landing | arm 4: share of arm-2 first attempts the applier alone brings to green | secondary |
| residual mix | first diagnostic codes *after* the applier, per arm | mechanism check |

**Bands, derived.** At n = 200 per arm, 2 SE of the pass@1 difference
near 0.20 is 0.080 (§2.4).

| arm 3 − arm 2, pass@1 | reading |
|---|---|
| ≥ +0.080 | the lever is real at this tier; report `g / 200` beside it so the deterministic share is separated from the model's |
| within ±0.080 | indistinguishable from sampling at n = 200; **not extended** to more seeds after seeing the number — the protocol's n was fixed here |
| ≤ −0.080 | the applier harms repair (a cleaned program misleads the model); report it |

The tokens-to-green band is set from arm 2's own dispersion once arm 2
exists and **before arm 3 runs**: 2 SE of the paired ratio from arm 2's
cells against themselves under a seed split. Written into the run plan at
that point and not moved.

### 3.4 Stops

1. Arm 1 ≠ 0.565 → environment not comparable; no number is published
   against prior waves; diagnose before any large-tier hour is spent.
2. Any applier application that produces a program the oracle marks
   green while the *pre*-applier program was already green → the applier
   is not idempotent; stop, it is a defect (§4 invariant 1).
3. An `overlap-refused` or `round-cap` terminal state on more than 5% of
   arm-3 submissions → the applier's fixed point is not well-defined on
   this data; stop and report the cases.
4. Infrastructure (`ModelError`, server identity mismatch, context
   overflow before any submission) is never a model result: the
   black-oxide driver's separation is kept verbatim.

### 3.5 Cost, in box hours

From black-oxide's local amplification timings (~11 s per small-tier
session on this box, `~/workspace/oxide-amp2-run.log`) and wave 8's pod
timing for large-tier arms (≈45 min per 200-session large arm on a
3090, `eval/results/v04-wave8-phaseb/REPORT.md`, 3h40m for five arms
including setup) scaled ×1.5 for Vulkan on the RTX 5080:

| step | hours |
|---|---:|
| Phase 0 (rustc on ~1,700 stored attempts, applier, oracle) | < 0.5, CPU only |
| arm 1 guard | ~0.7 |
| arm 2 baseline | ~1.2 |
| arm 3 treatment | ~1.2 |
| second and third family, if funded | ~2.5 each |

No RunPod. Runs over ~2 h are OS-detached with a `.DONE`/`.FAILED`
marker and a watcher, per the house rule.

## 4. The applier — invariants and their falsification tests

Interface: `apply_fixpoint(source: str, *, rustc: Path, round_cap: int = 8) -> Applied`
where `Applied` carries the final source, the ordered list of
applications `(round, code, span, replacement)`, the terminal state
(§2.3 step 3), and the rustc version string. Stdlib only.

Invariants, each with the test that must FAIL when the invariant is
broken (mutation-tested before it counts; `__pycache__` purged and
`PYTHONDONTWRITEBYTECODE=1`, per the pyc rule):

1. **Identity on a compiling program.** `apply_fixpoint(p) == p` with
   zero applications when `p` compiles. Test: a green task reference from
   `eval/tasks-large.jsonl`'s Rust references passes through unchanged;
   mutation: make the applier apply warnings' suggestions too — the test
   must fail.
2. **Only `MachineApplicable`.** A diagnostic whose only suggestion is
   `MaybeIncorrect` or `HasPlaceholders` is never applied. Test: a
   program whose sole suggestion is `HasPlaceholders` is returned
   unchanged with terminal state `still-fails(code)`; mutation: accept
   `MaybeIncorrect` — must fail.
3. **No overlapping spans in one round.** If two applications in the
   same round overlap byte ranges, apply neither and terminate
   `overlap-refused`. Test: a crafted pair of overlapping suggestions;
   mutation: apply the first and skip the second — must fail.
4. **Right-to-left application within a round**, so earlier byte offsets
   stay valid. Test: two non-overlapping suggestions on one line, both
   land at the positions rustc named; mutation: left-to-right — must
   fail on the second span's position.
5. **Bounded.** Terminates within `round_cap` rounds with state
   `round-cap` if no fixed point is reached. Test: a program whose
   suggestion re-introduces the same error (constructed, or a stub rustc
   that always returns the same suggestion); mutation: remove the cap —
   must hang, so the test runs under a timeout and fails on it.
6. **Every application is logged with the code that produced it**, and
   the log round-trips through JSON with dataclass equality and a
   completeness check (every field of `Applied` present in the payload).
7. **rustc version is recorded in every `Applied`** and in run
   provenance; a run whose recorded version differs from the plan's pin
   is refused by the driver, not silently accepted.

Spans are applied on the byte offsets rustc reports (`byte_start`,
`byte_end`), never on line/column arithmetic; the acceptance test for
this is a suggestion inside a line containing a multi-byte character.

What the applier does **not** do: reorder, reformat, or apply
`cargo clippy` lints. Those are levers with their own lens and are out
of scope here.

## 5. Reuse contract with black-oxide

Pinned at commit **`521f602f4aaf4ef18c7f724a3df3afcc2e27a100`**, imported
via `PYTHONPATH=~/workspace/oxide` the way bloomery pins assay. The
driver asserts the checkout's `git rev-parse HEAD` equals the pin before
any session runs. The pin is bumped only by a commit that says why.

**Imported:**

| module | used for |
|---|---|
| `eval.harness` | `load_tasks`, `build_prompt`, `new_session`, `check_file`, `run_file`, `MAX_ATTEMPTS`, `OUTPUT_CONTRACT` |
| `eval.rustc_adapter` | `rustc_check`, `rustc_build`, `run_binary`, `adapt_diagnostics` (the stored diagnostic shape) |
| `eval.repair` | `initial_context`, `render_diagnostics`, `FIX_INSTRUCTION` — the repair prompt is byte-identical in both arms |
| `eval.driver` | `run_session`, with the applier injected at the seam in §3.2 (a small upstream hook or a flux-side subclass; the plan decides, the spec requires that arm 2 be the unmodified loop) |
| `eval.llamacpp`, `eval.models` | the client, `ModelError`, `estimate_tokens` |
| `eval.experiment_report` | `load_cells`, `load_cells_keyed`, `green_pair_keys`, `paired_tokens_to_green`, `paired_pass1` |
| data | `eval/tasks.jsonl`, `eval/tasks-large.jsonl`, `eval/probes.jsonl`, and the committed `eval/results/**/triples.jsonl` named in §2.2 |

**Must not be imported:** anything under `src/` (the Oxide compiler and
its explicit dialect); `eval.probe` and `eval.probe_campaign` beyond
reading the Rust records of `probes.jsonl` as data; `eval.demand_census`,
`eval.cost_census`, `eval.learnability`, `eval.token_match`,
`eval.train_corpus`, `eval.deformation`, `eval.wave8_*` — all of them
measure the Oxide language, and importing one would make a Rust-only
result depend on it.

## 6. What is not claimed

- Nothing about Black Oxide. flux runs one arm, Rust, and its result
  says nothing about the language beside it.
- Nothing about frontier models. Black-oxide measured 0.0pp at frontier
  on the ownership probe; this lever exists for models that cannot
  already do what rustc suggests.
- Nothing about tuned models at this stage (§3.1).
- Nothing beyond 40–600 token programs on 40 tasks. Every number is
  quoted with its tier, as black-oxide's wave 8 required.
- Nothing about `cargo fix` as a product. The applier is an instrument.

## 7. Open rulings for the owner

1. **Name.** `flux` is a working name.
2. **Phase 0 as the whole project.** If `k < 16`, flux publishes a
   census and closes. Confirm that a clean null is an acceptable end
   state before Phase 0 runs, so the result is not re-narrated.
3. **The E0308 question is the census.** If the owner would rather not
   spend the ~half hour, the stored codes alone already bound the lever
   at ≤ 0.185 on the large tier and ≤ 0.005 on the small.
4. **Public repository.** The siblings are public from day one; this
   one has not been pushed. Say when.
5. **Injection seam.** A two-line hook in black-oxide's `run_session`
   (a `pre_judge` callable defaulting to identity) versus a flux-side
   copy of the loop. The hook keeps arm 2 provably unmodified; the copy
   keeps black-oxide untouched. The spec prefers the hook, landed as its
   own reviewed black-oxide commit that bumps the pin.
6. **14B row.** Reported from committed data only, never run here, unless
   the owner wants the q4_K_M lens added as a separately named row.
