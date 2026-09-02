# Carried debt

The durable record of every deferred decision, appended at each merge:
*what the slice settled* → *deferred, with rulings* → *process lessons*.
Resolved items are struck through, never deleted.

## Spec stage (2026-09-02) — nothing merged yet

Open rulings live at the end of
`docs/superpowers/specs/2026-09-02-flux-design.md` until the owner rules
on them; they move here, with the ruling, when the first slice lands.

## Phase 0 census — 2026-09-02 (closes the project)

**Settled.** `k = 15`, `g = 2`, floor 16 → not funded; flux is a $0
census (`results/phase0-2026-09-02/REPORT.md`). The applier ships with
its seven invariants tested and eighteen mutations killed; the §2.2 table
reproduces to the digit. rustc's own `MachineApplicable` `.clone()` on
the accumulate-without-reassign probe (p17) yields a compiling, silent,
wrong program — the `OX0403` trap exists in rustc too.

**Deferred, with rulings.**
- `MaybeIncorrect` suggestions as a lever: never applied, by
  pre-registration. Own lens if ever pursued.
- Tokens-to-green of the 13 wrong-output programs: unmeasured (no model
  ran). Would need Phase 1, which is not funded.
- A different large-tier corpus: `k` is concentrated on one task (`g07`,
  10 of 15). The protocol's corpus is fixed; re-running on another is a
  new pre-registration, not an extension of this one.

**Process lessons.**
- Two mutations survived first time and both were test gaps: a compiling
  program returns before any suggestion is read (the errors-only filter
  needed an error-plus-warning program), and black-oxide already stores
  the literal `E????`, so the `None`-labelling path was dead on real
  data. Mutation-test against the data's actual shape, not the shape you
  assumed.
- The spec's black-oxide pin was one merge stale by the time the census
  ran; bumping it with the empty `git diff --stat` on every file read is
  the cheap, sufficient record.
