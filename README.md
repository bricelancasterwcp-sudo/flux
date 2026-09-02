# flux

**Does rustc's own machinery remove enough ceremony that a small model's
repair lands?**

Soldering flux cleans the oxide off a surface so the joint takes. This
tool applies rustc's `MachineApplicable` suggestions — the machinery
behind `cargo fix` — automatically, to a fixed point, *before* a model
ever sees a diagnostic. The question is how much of the small-model Rust
deficit that removes on its own, and whether the model repairs the
residual better than it repairs the raw program.

## Status

**Closed on 2026-09-02 as a $0 census; Phase 1 was not funded.** The
pre-registered design is
[`docs/superpowers/specs/2026-09-02-flux-design.md`](docs/superpowers/specs/2026-09-02-flux-design.md);
it opens with a $0 census over black-oxide's committed Rust-arm attempts
that decides whether the live experiment is funded at all. That census
ran and read **k = 15 against a derived floor of 16**: the lever's
ceiling on large-tier pass@1 is 0.075, below the protocol's 0.080 noise
floor, and its deterministic component is 0.010 — thirteen of the
fifteen suggestion-fixed programs compile and print the wrong answer.
The report is
[`results/phase0-2026-09-02/REPORT.md`](results/phase0-2026-09-02/REPORT.md);
the applier and census ship tested (24 tests, 18 mutations killed).

**Kill criterion, in one line:** if fewer than 16 of the 200 committed
large-tier first attempts can gain a compiling program from machine-
applicable suggestions alone, the lever is below the noise floor of a
200-cell comparison and no live run is funded.

**Read the bound before reading the thesis.** The committed data already
caps this lever hard. On the small tier the untuned 7B compiles 199 of
200 first attempts, so there is nothing for a compiler suggestion to
fix; on the large tier the tuned 7B fails to compile 37 of 200, and not
one of those failures carries an ownership code. The census exists to
measure the cap exactly, and a clean null is a publishable outcome.

## Where the thesis comes from

Three sibling projects, all public under the same account:

- **[robigo](https://github.com/bricelancasterwcp-sudo/robigo)** ran a
  naive agent loop on a 7B model against a 33.3% pre-registered floor
  and read **1.06%** (10 of 940). Naive small-model agent loops are not
  the path; narrow, verifier-backed loops are.
- **[black-oxide](https://github.com/bricelancasterwcp-sudo/black-oxide)**
  found that small models repair a single ownership defect far better
  when ownership is implicit than when it is written out:
  **+59.0 / +35.0 / +9.5pp** on qwen2.5-coder-7b / codegemma-7b /
  granite-code-8b, of which about **+10pp** is ownership and the rest is
  surface ergonomics, and **0.0pp** at frontier. Its design loop then
  found that every durable win was *subtractive* — ceremony removed —
  while every additive construct paid for its novelty.
- **[assay](https://github.com/bricelancasterwcp-sudo/assay)** measures
  what a locally served model can actually do, and named the rule that
  a measurement quoted without its instrument is not a property of the
  subject.

Real Rust already has a deterministic ceremony-remover. rustc attaches
suggestions to its diagnostics, and marks the ones it is confident about
`MachineApplicable`: insert `mut`, append `.clone()`, borrow here. flux
applies those, recompiles, and repeats. The model is asked to repair only
what is left.

## What it reuses

black-oxide's harness, task corpora, rustc adapter, repair prompt, and
composition-controlled estimands, pinned at one commit and imported via
`PYTHONPATH` the way bloomery pins assay. Nothing of the Oxide language
itself. The spec lists exactly which modules cross the line and which
must not.

## What it is not

Not a Rust tool for people; `cargo fix` already exists. Not a claim
about frontier models, which repair Rust ownership defects at ceiling
already. Not a claim about Oxide. It is one measurement: how much of
what a 7B model gets wrong in Rust is ceremony a compiler can remove by
itself, on consumer hardware, with numbers a reader can reproduce from
this repository.

## Layout

| Path | |
|---|---|
| `docs/superpowers/specs/` | the pre-registered design |
| `docs/superpowers/plans/` | written only after the spec is approved |
| `docs/CARRIED-DEBT.md` | every deferred decision, with rulings |

## License

MIT — see [LICENSE](LICENSE).
