"""Phase 0 census (spec §2.3-2.4): re-judge every committed Rust-arm
attempt under the pinned rustc, record whether its diagnostics carry a
MachineApplicable suggestion, run the applier to its fixed point, and
judge the result with black-oxide's own oracle. Then compute `k` and `g`
and apply the three pre-committed readings.

Reuse contract (§5): reads black-oxide's committed data and imports only
`eval.rustc_adapter` (build + run, so the judge is byte-identical) --
nothing that measures the Oxide language.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from flux.applier import (
    STATE_COMPILES, Applied, apply_fixpoint, compile_check, error_diagnostics,
    first_error_code, has_machine_applicable, rustc_version,
)

RUSTC = Path(shutil.which("rustc") or "rustc")

#: Spec §2.2's ownership/mutability class.
OWNERSHIP_CODES = frozenset({
    "E0382", "E0499", "E0502", "E0505", "E0507", "E0596",
    "E0384", "E0506", "E0503", "E0716", "E0597", "E0373",
})

#: Spec §2.4: 2 SE of a difference of two rates near 0.20 at n = 200 is
#: 0.080; times 200 attempts = 16. Derived, not chosen.
_SE = math.sqrt(2 * 0.2 * 0.8 / 200)
K_FLOOR = round(2 * _SE * 200)

READ_NOT_FUNDED = "not-funded"
READ_DETERMINISTIC = "deterministic-clears-noise"
READ_FUNDED = "funded"
READ_UNMEASURED = "unmeasured"

MISSING_CODE = "E????"


class PinError(RuntimeError):
    """A run whose environment differs from the plan's pins is refused,
    not silently accepted (spec §4 invariant 7, §5)."""


@dataclass(frozen=True)
class Arm:
    name: str
    tier: str
    results: str  # relative to the black-oxide root
    tasks: str    # relative to the black-oxide root


ARMS = (
    Arm("base-rs-7", "small", "eval/results/v04-wave8-phaseb/results-small/base-rs-7", "eval/tasks.jsonl"),
    Arm("tune-rs-7", "small", "eval/results/v04-wave8-phaseb/results-small/tune-rs-7", "eval/tasks.jsonl"),
    Arm("tune-rs-7", "large", "eval/results/v04-wave8-phaseb/results-large/tune-rs-7", "eval/tasks-large.jsonl"),
    Arm("base-rs-14", "small", "eval/results/v04-wave8-14b-screen/results-small/base-rs-14", "eval/tasks.jsonl"),
    Arm("tune-rs-14", "large", "eval/results/v04-wave8-14b-screen/results-large/tune-rs-14", "eval/tasks-large.jsonl"),
)

#: The arm whose k decides funding (§2.4). The 14B row is reported only.
DECIDING_ARM = ("tune-rs-7", "large")


@dataclass(frozen=True)
class Attempt:
    seed: str
    task: str
    attempt: int
    code: str
    compiled: bool
    passed: bool
    first_code: str | None


@dataclass(frozen=True)
class AttemptRecord:
    arm: str
    tier: str
    seed: str
    task: str
    attempt: int
    stored_compiled: bool
    stored_first_code: str | None
    rederived_compiles: bool | None       # None: rustc could not run
    rederived_first_code: str | None
    drift: bool | None
    first_diag_ma: bool | None            # None when the attempt compiles
    any_diag_ma: bool | None
    applier_state: str | None
    applier_rounds: int | None
    applications: int | None
    applier_final_code: str | None
    outcome: str | None                   # green | wrong-output | nonterminating | build-failed; None when not judged
    rustc_version: str

    def to_json(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "AttemptRecord":
        return cls(**d)


def load_attempts(root: Path) -> list[Attempt]:
    out = []
    for p in sorted(Path(root).glob("*-gen-s*/triples.jsonl")):
        seed = "gen-" + p.parent.name.split("-gen-")[-1]
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            t = json.loads(line)
            diags = t.get("diagnostics") or []
            first = (diags[0].get("code") if diags else None) or None
            out.append(Attempt(seed, t["task"], int(t["attempt"]), t["code"],
                               bool(t["compiled"]), bool(t["passed"]), first))
    return out


def label(code: str | None) -> str:
    return code or MISSING_CODE


def stored_table(atts: list[Attempt]) -> dict:
    """Spec §2.2: first attempts, stored `compiled == False`, stored first
    diagnostic code. Missing codes are counted as E????, never dropped."""
    firsts = [a for a in atts if a.attempt == 1]
    failing = [a for a in firsts if not a.compiled]
    codes: dict[str, int] = {}
    for a in failing:
        codes[label(a.first_code)] = codes.get(label(a.first_code), 0) + 1
    return {
        "first_attempts": len(firsts),
        "not_compiling": len(failing),
        "ownership_class": sum(1 for a in failing if a.first_code in OWNERSHIP_CODES),
        "first_codes": dict(sorted(codes.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def _judge(source: str, expected_stdout: str, oxide_root: Path) -> str:
    """Build and run with black-oxide's own adapter so the verdict is the
    one the campaigns used (10 s cap, exact stdout equality)."""
    if str(oxide_root) not in sys.path:
        sys.path.insert(0, str(oxide_root))
    from eval.rustc_adapter import run_binary, rustc_build  # noqa: WPS433
    with tempfile.TemporaryDirectory(prefix="flux-judge-") as work:
        rs = Path(work) / "program.rs"
        rs.write_text(source, encoding="utf-8")
        binary = Path(work) / "program"
        ok, _ = rustc_build(rs, binary)
        if not ok:
            return "build-failed"
        finished, stdout = run_binary(binary)
        if not finished:
            return "nonterminating"
        return "green" if stdout == expected_stdout else "wrong-output"


def census_attempt(att: Attempt, arm: Arm, expected_stdout: str, *, rustc: Path,
                   oxide_root: Path, version: str) -> AttemptRecord:
    base = dict(arm=arm.name, tier=arm.tier, seed=att.seed, task=att.task, attempt=att.attempt,
                stored_compiled=att.compiled, stored_first_code=att.first_code, rustc_version=version)
    with tempfile.TemporaryDirectory(prefix="flux-census-") as work:
        ok, diags, fname = compile_check(att.code, rustc=rustc, work_dir=Path(work))
    if ok is None:
        return AttemptRecord(**base, rederived_compiles=None, rederived_first_code=None, drift=None,
                             first_diag_ma=None, any_diag_ma=None, applier_state=None,
                             applier_rounds=None, applications=None, applier_final_code=None, outcome=None)
    rederived_first = None if ok else first_error_code(diags)
    stored_label = None if att.compiled else label(att.first_code)
    rederived_label = None if ok else label(rederived_first)
    drift = stored_label != rederived_label
    if ok:
        return AttemptRecord(**base, rederived_compiles=True, rederived_first_code=None, drift=drift,
                             first_diag_ma=None, any_diag_ma=None, applier_state=STATE_COMPILES,
                             applier_rounds=0, applications=0, applier_final_code=None, outcome=None)
    errs = error_diagnostics(diags)
    first_ma = has_machine_applicable(errs[0], fname) if errs else False
    any_ma = any(has_machine_applicable(d, fname) for d in errs)
    applied = apply_fixpoint(att.code, rustc=rustc)
    outcome = None
    if applied.state == STATE_COMPILES and applied.applications:
        outcome = _judge(applied.source, expected_stdout, oxide_root)
    return AttemptRecord(**base, rederived_compiles=False, rederived_first_code=rederived_first, drift=drift,
                         first_diag_ma=first_ma, any_diag_ma=any_ma, applier_state=applied.state,
                         applier_rounds=applied.rounds, applications=len(applied.applications),
                         applier_final_code=applied.final_code, outcome=outcome)


def k_and_g(records: list[AttemptRecord]) -> tuple[int, int]:
    """§2.4: k = first attempts that fail to compile under the pinned rustc
    and whose FIRST diagnostic carries a MachineApplicable suggestion;
    g = those the applier alone brings to green."""
    firsts = [r for r in records if r.attempt == 1 and r.rederived_compiles is False]
    k_recs = [r for r in firsts if r.first_diag_ma]
    return len(k_recs), sum(1 for r in k_recs if r.outcome == "green")


def reading(k: int | None, g: int | None) -> str:
    if k is None or g is None:
        return READ_UNMEASURED
    if k < K_FLOOR:
        return READ_NOT_FUNDED
    if g >= K_FLOOR:
        return READ_DETERMINISTIC
    return READ_FUNDED


def summarize(records: list[AttemptRecord]) -> dict:
    """Counts over measured values only; every None is counted in
    `dropped` by field name so an unmeasured cell can never read as 0."""
    fields = ("rederived_compiles", "drift", "first_diag_ma", "any_diag_ma",
              "applier_state", "outcome")
    dropped = {f: sum(1 for r in records if getattr(r, f) is None) for f in fields}
    firsts = [r for r in records if r.attempt == 1]
    states: dict[str, int] = {}
    for r in records:
        if r.applier_state is not None:
            states[r.applier_state] = states.get(r.applier_state, 0) + 1
    outcomes: dict[str, int] = {}
    for r in records:
        if r.outcome is not None:
            outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
    return {
        "attempts": len(records),
        "first_attempts": len(firsts),
        "first_not_compiling_rederived": sum(1 for r in firsts if r.rederived_compiles is False),
        "drift": sum(1 for r in records if r.drift),
        "first_diag_ma": sum(1 for r in records if r.first_diag_ma),
        "any_diag_ma": sum(1 for r in records if r.any_diag_ma),
        "applier_states": dict(sorted(states.items())),
        "applied_and_compiles": sum(1 for r in records if r.applier_state == STATE_COMPILES and r.applications),
        "greens": outcomes.get("green", 0),
        "outcomes": dict(sorted(outcomes.items())),
        "dropped": {f: n for f, n in dropped.items() if n},
    }


def oxide_commit(root: Path) -> str:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def rustc_version_of(rustc: Path) -> str:
    return rustc_version(rustc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_expected(oxide_root: Path, tasks_rel: str) -> dict[str, str]:
    out = {}
    for line in (oxide_root / tasks_rel).read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            out[t["id"]] = t["expected_stdout"]
    return out


def probe_b(oxide_root: Path, *, rustc: Path) -> list[dict]:
    """Phase 0b: the 20 Rust probe records -- one ownership defect each,
    with the reference stdout. Which classes does rustc fix by itself?"""
    out = []
    for line in (oxide_root / "eval/probes.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") != "rust":
            continue
        with tempfile.TemporaryDirectory(prefix="flux-probe-") as work:
            ok, diags, _ = compile_check(r["broken"], rustc=rustc, work_dir=Path(work))
        applied = apply_fixpoint(r["broken"], rustc=rustc)
        outcome = None
        if applied.state == STATE_COMPILES and applied.applications:
            outcome = _judge(applied.source, r["expected_stdout"], oxide_root)
        out.append({
            "id": r["id"], "defect": r["defect"], "expected_code": r.get("expected_code"),
            "rederived_first_code": None if ok else first_error_code(diags),
            "broken_compiles": ok,
            "applier_state": applied.state, "applications": len(applied.applications),
            "codes_applied": sorted({a.code for a in applied.applications}),
            "outcome": outcome,
        })
    return out


def run(oxide_root: Path, out_dir: Path, *, expected_oxide_commit: str,
        expected_rustc_version: str, rustc: Path = RUSTC, limit: int | None = None,
        workers: int = 8) -> dict:
    oxide_root = Path(oxide_root)
    commit = oxide_commit(oxide_root)
    if commit != expected_oxide_commit:
        raise PinError(f"black-oxide checkout is {commit[:8]}, plan pins {expected_oxide_commit[:8]}")
    version = rustc_version_of(rustc)
    if version != expected_rustc_version:
        raise PinError(f"rustc is {version!r}, plan pins {expected_rustc_version!r}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    arms_out = []
    all_records: list[AttemptRecord] = []
    provenance_files = {}
    for arm in ARMS:
        root = oxide_root / arm.results
        for p in sorted(root.glob("*-gen-s*/triples.jsonl")):
            provenance_files[str(p.relative_to(oxide_root))] = _sha256(p)
        atts = load_attempts(root)
        expected = load_expected(oxide_root, arm.tasks)
        if limit is not None:
            atts = atts[:limit]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(
                lambda a: census_attempt(a, arm, expected[a.task], rustc=rustc,
                                         oxide_root=oxide_root, version=version), atts))
        records.sort(key=lambda r: (r.seed, r.task, r.attempt))
        all_records.extend(records)
        arms_out.append({
            "arm": arm.name, "tier": arm.tier, "results": arm.results,
            "stored_table": stored_table(load_attempts(root)),
            "summary": summarize(records),
            "k_g": k_and_g(records),
        })
    deciding = next(a for a in arms_out if (a["arm"], a["tier"]) == DECIDING_ARM)
    k, g = deciding["k_g"]
    if limit is not None:
        k = g = None  # a truncated run measures nothing that decides
    probes = probe_b(oxide_root, rustc=rustc) if limit is None else []
    report = {
        "plan": "docs/superpowers/specs/2026-09-02-flux-design.md §2",
        "started_utc": started,
        "finished_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "provenance": {"rustc": version, "black_oxide_commit": commit,
                       "triples_sha256": provenance_files, "limit": limit},
        "k_floor": K_FLOOR,
        "deciding_arm": list(DECIDING_ARM),
        "k": k, "g": g, "reading": reading(k, g),
        "arms": arms_out,
        "probe_b": probes,
    }
    with open(out_dir / "attempts.jsonl", "w", encoding="utf-8") as fh:
        for r in all_records:
            fh.write(json.dumps(r.to_json(), sort_keys=True) + "\n")
    (out_dir / "census.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "CENSUS.md").write_text(render(report), encoding="utf-8")
    return report


def render(report: dict) -> str:
    L = ["# flux Phase 0 census", "",
         f"rustc `{report['provenance']['rustc']}`, black-oxide `{report['provenance']['black_oxide_commit'][:8]}`, "
         f"{report['started_utc']} → {report['finished_utc']}.", ""]
    L += ["## Stored codes (spec §2.2, reproduced from the cells)", "",
          "| arm | tier | first | not compiling | ownership-class | first codes |", "|---|---|---:|---:|---:|---|"]
    for a in report["arms"]:
        t = a["stored_table"]
        L.append(f"| {a['arm']} | {a['tier']} | {t['first_attempts']} | {t['not_compiling']} | {t['ownership_class']} | "
                 + ", ".join(f"{c} {n}" for c, n in t["first_codes"].items()) + " |")
    L += ["", "## Re-judged under the pinned rustc", "",
          "| arm | tier | attempts | first | first not compiling | drift | first-diag MA | any-diag MA | applied→compiles | green | states | dropped |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for a in report["arms"]:
        s = a["summary"]
        L.append(f"| {a['arm']} | {a['tier']} | {s['attempts']} | {s['first_attempts']} | {s['first_not_compiling_rederived']} | "
                 f"{s['drift']} | {s['first_diag_ma']} | {s['any_diag_ma']} | {s['applied_and_compiles']} | {s['greens']} | "
                 f"`{s['applier_states']}` | `{s['dropped']}` |")
    L += ["", f"## The kill criterion (§2.4): k = **{report['k']}**, g = **{report['g']}**, floor {report['k_floor']} → **{report['reading'].upper()}**", ""]
    for a in report["arms"]:
        L.append(f"- {a['arm']} @ {a['tier']}: k = {a['k_g'][0]}, g = {a['k_g'][1]}")
    if report["probe_b"]:
        L += ["", "## Phase 0b: the 20 Rust probe records", "",
              "| id | defect | expected | re-derived | applier | applications | codes | outcome |", "|---|---|---|---|---|---:|---|---|"]
        for p in report["probe_b"]:
            L.append(f"| {p['id']} | {p['defect']} | {p['expected_code']} | {p['rederived_first_code']} | {p['applier_state']} | "
                     f"{p['applications']} | {', '.join(p['codes_applied'])} | {p['outcome']} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m flux.census")
    ap.add_argument("--oxide", type=Path, default=Path.home() / "workspace" / "oxide")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-commit", required=True)
    ap.add_argument("--expect-rustc", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)
    try:
        report = run(args.oxide, args.out, expected_oxide_commit=args.expect_commit,
                     expected_rustc_version=args.expect_rustc, limit=args.limit, workers=args.workers)
    except PinError as exc:
        ap.error(str(exc))
    print(render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
