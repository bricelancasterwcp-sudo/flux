# flux Phase 0 — not funded: k = 15 against a derived floor of 16

2026-09-02. Spec: `docs/superpowers/specs/2026-09-02-flux-design.md` §2
(pre-registered; the floor was derived before the instrument existed and
is not re-derived here). Instrument: `flux/census.py` + `flux/applier.py`
at commit `24cd5b4`, 24 tests, 18 mutations killed, the spec's §2.2 table
reproduced to the digit from the committed cells. rustc 1.96.0, black-oxide
`8f5399c8`. Runtime **6 seconds**, GPU cost **$0**. Every attempt is in
`attempts.jsonl` (1,695 records); the summaries in `census.json`.

## The pre-registered criterion

| | value |
|---|---:|
| `k` — large-tier `tune-rs-7` first attempts that fail under the pinned rustc and whose first diagnostic carries a `MachineApplicable` suggestion | **15** of 200 |
| `g` — of those, brought to **green** by the applier alone | **2** |
| floor to fund Phase 1 (2 SE of a rate difference near 0.20 at n = 200, × 200) | **16** |
| reading | **NOT FUNDED** |

One attempt short. The point estimate decides; the floor stays where it
was derived. Ceilings, in the protocol's units: the lever's hard ceiling
on large-tier pass@1 is `k / 200 = 0.075`, below the 0.080 that any live
run would have to clear; its deterministic component is `g / 200 =
0.010`. The small tier reads `k = 0` on both arms, as §2.2 said it would.

## What the 37 failing first attempts are

`tune-rs-7` @ large, re-judged under rustc 1.96.0:

| first diagnostic | attempts | MachineApplicable |
|---|---:|---:|
| `E0308` mismatched types | 16 | **12** |
| `E0434` can't capture dynamic environment | 4 | 0 |
| `E0614` deref of non-reference | 4 | 0 |
| `E????` (rustc fallback) | 4 | 0 |
| `E0106` missing lifetime | 2 | 0 |
| `E0277` trait not implemented | 2 | **2** |
| `E0425` unresolved name | 2 | 0 |
| `E0433`, `E0600`, `E0606` | 1 each | `E0606` only |

Ten of the fifteen are **one task, `g07`**. What rustc offered on them was
reference plumbing: `&` (20 applications), `*` (15), and two
`map_or`/closure rewrites.

**The applier brought all 15 to a compiling program. Thirteen print the
wrong answer.** The suggestion makes the program type-check; the logic
under it was already wrong. Across every attempt in the five arms,
first and repair alike, the applier moved 25 to compiling and 2 to green.
`any_diag_ma` equals `first_diag_ma` on every arm: no later diagnostic
carries a suggestion the first one lacked, so there is no second lever
hiding behind the first.

This is §2.2's second point, measured rather than inferred: **the
small-model Rust deficit on this box is wrong programs, not ceremony.**
The pre-repair lever converts compile failures into wrong-output at
13 : 2.

## The 14B row (reported; funds nothing, per §2.4)

`tune-rs-14` @ large: `k = 4` (three `E0308`, one `E0382`), `g = 0` —
all four compile after the suggestion and all four print the wrong
answer.

## The drift check

1 of 1,695 attempts changed its first diagnostic between the pods'
rustc (1.98.0) and this box's (1.96.0): `tune-rs-7` large, seed 7, `g03`,
attempt 1 — stored `E????`, re-derived `E0106`; not compiling under
either. The other 1,694 first codes are identical, so the structural
comparison the census rests on holds.

## Phase 0b: rustc alone on the 20 Rust probe records

| result | classes |
|---|---|
| **green by itself: 16 of 20** | every `E0382` class whose fix is `.clone()` (p01–p03, p05–p09, p11–p14, p16, p18, p19) and `E0505` consume-while-iterating (p20) |
| still fails: 3 | p04 assign-to-iterated-vec (`E0502`, no suggestion), p10 move-via-struct-update, p15 move-via-question-mark |
| **compiles, wrong output: 1** | **p17 accumulate-without-reassign** — rustc's `MachineApplicable` `.clone()` silences the error and drops the accumulation |

p17 is worth a sentence. It is the same trap black-oxide's `OX0403`
suggestion set for a frontier model (README, "It found a real bug"):
the diagnostic's own machine-applicable fix produces a program that
compiles, is silent, and is wrong. rustc is not immune to it.

As pre-stated, this row is a description, not a lever: the three 7B
families already repair this arm at 89.0 / 84.5 / 73.0% strict, and a
deterministic 80% floor under that changes no decision.

## Reading

Per the pre-committed table, `k < 16` → **Phase 1 is not funded, and
flux closes as a $0 census.** The thesis — that a deterministic
ceremony-remover in front of a small model would recover a meaningful
share of the Rust deficit — is bounded below the protocol's noise floor
on the committed data, before a single model call. That is the finding.

## What is not claimed

- Nothing about a model acting on the residual: no model ran.
- Nothing about tokens-to-green: the thirteen wrong-output programs may
  be nearer to right than the originals, and that distance was not
  measured because no repair loop ran.
- Nothing about `MaybeIncorrect` suggestions: by pre-registration they
  were never applied. Some would land; that is a different lever with
  its own lens.
- Nothing about 14B at q8_0 on this box (it cannot be served here), and
  nothing about Oxide.

## Honest limits

- `k` is concentrated: one task holds ten of fifteen. The protocol's
  task set is fixed and the floor is on the whole set, so this changes
  nothing here, but a different large-tier corpus could read a different
  `k`.
- The pods compiled under rustc 1.98.0; this census under 1.96.0. One
  attempt drifted.
- `MachineApplicable` is rustc's own label for its own confidence.

## Provenance

- `census.json` carries the rustc version, the black-oxide commit, and
  the sha256 of every `triples.jsonl` read; both pins are refused by the
  driver before any work (tested).
- Reproduce: `PYTHONPATH=. python -m flux.census --out <dir>
  --expect-commit 8f5399c8… --expect-rustc "rustc 1.96.0 (ac68faa20 2026-05-25)"`.
