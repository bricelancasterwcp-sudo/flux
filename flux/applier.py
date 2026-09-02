"""Deterministic pre-repair: apply rustc's MachineApplicable suggestions to
a fixed point, with no model in the loop.

Spec: docs/superpowers/specs/2026-09-02-flux-design.md §4. Seven
invariants, each pinned by tests/test_applier.py. Stdlib only.

Spans are applied on the byte offsets rustc reports, never on line/column
arithmetic. Only diagnostics at level "error" contribute; a warning's
suggestion (`_x` for an unused variable) is never applied, so a compiling
program is returned byte-identical.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

EDITION = "2021"
COMPILE_TIMEOUT_SECONDS = 120
MACHINE_APPLICABLE = "MachineApplicable"
DEFAULT_ROUND_CAP = 8

STATE_COMPILES = "compiles"
STATE_STILL_FAILS = "still-fails"
STATE_OVERLAP = "overlap-refused"
STATE_ROUND_CAP = "round-cap"
STATE_RUSTC_FAILED = "rustc-failed"


@dataclass(frozen=True)
class Application:
    round: int
    code: str
    byte_start: int
    byte_end: int
    replacement: str


@dataclass(frozen=True)
class Applied:
    original: str
    source: str
    applications: tuple[Application, ...]
    state: str
    final_code: str | None
    rounds: int
    rustc_version: str

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["applications"] = [dataclasses.asdict(a) for a in self.applications]
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Applied":
        apps = tuple(Application(**a) for a in d["applications"])
        return cls(**{**d, "applications": apps})


def rustc_version(rustc: Path) -> str:
    proc = subprocess.run([str(rustc), "--version"], capture_output=True, text=True, timeout=30)
    return proc.stdout.strip()


def compile_check(source: str, *, rustc: Path, work_dir: Path) -> tuple[bool | None, list[dict], str]:
    """Type-check `source` the way black-oxide's `rustc_check` does
    (`--emit=metadata`). Returns (ok, diagnostics, file_name); ok is
    None when rustc itself could not run -- infrastructure, never a
    verdict."""
    path = Path(work_dir) / "program.rs"
    path.write_bytes(source.encode("utf-8"))
    try:
        proc = subprocess.run(
            [str(rustc), "--edition", EDITION, "--error-format=json",
             "--emit=metadata", "--out-dir", str(work_dir), str(path)],
            capture_output=True, text=True, timeout=COMPILE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, [], str(path)
    diags = []
    for line in proc.stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            diags.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return proc.returncode == 0, diags, str(path)


def error_diagnostics(diags: list[dict]) -> list[dict]:
    """Errors that carry a code. rustc's trailing "aborting due to N
    previous errors" is level error with code null and is not a defect."""
    return [d for d in diags if d.get("level") == "error" and (d.get("code") or {}).get("code")]


def first_error_code(diags: list[dict]) -> str | None:
    errs = error_diagnostics(diags)
    return errs[0]["code"]["code"] if errs else None


def _all_spans(diag: dict):
    for sp in diag.get("spans") or []:
        yield sp
    for child in diag.get("children") or []:
        yield from _all_spans(child)


def machine_applicable_spans(diag: dict, file_name: str) -> list[tuple[int, int, str]]:
    out = []
    for sp in _all_spans(diag):
        if sp.get("suggested_replacement") is None:
            continue
        if sp.get("suggestion_applicability") != MACHINE_APPLICABLE:
            continue
        if sp.get("file_name") != file_name:
            continue
        out.append((int(sp["byte_start"]), int(sp["byte_end"]), sp["suggested_replacement"]))
    return out


def has_machine_applicable(diag: dict, file_name: str) -> bool:
    return bool(machine_applicable_spans(diag, file_name))


def candidates(diags: list[dict], file_name: str) -> list[tuple[int, int, str, str]]:
    """(byte_start, byte_end, replacement, code) for every MachineApplicable
    span on an error diagnostic, identical triples deduplicated (the same
    fix is often attached to several diagnostics)."""
    seen = set()
    out = []
    for d in error_diagnostics(diags):
        code = d["code"]["code"]
        for start, end, repl in machine_applicable_spans(d, file_name):
            key = (start, end, repl)
            if key in seen:
                continue
            seen.add(key)
            out.append((start, end, repl, code))
    return out


def conflicts(cands: list[tuple[int, int, str, str]]) -> bool:
    """Two applications conflict when their byte ranges intersect, or when
    they start at the same offset with different content (two insertions
    at one point). Touching ranges do not conflict."""
    ordered = sorted(cands, key=lambda c: (c[0], c[1]))
    for a, b in zip(ordered, ordered[1:]):
        if a[1] > b[0] or a[0] == b[0]:
            return True
    return False


def apply_round(source: str, cands: list[tuple[int, int, str, str]]) -> str:
    """Right to left, so every earlier byte offset stays valid."""
    data = source.encode("utf-8")
    for start, end, repl, _code in sorted(cands, key=lambda c: c[0], reverse=True):
        data = data[:start] + repl.encode("utf-8") + data[end:]
    return data.decode("utf-8")


def apply_fixpoint(source: str, *, rustc: Path, round_cap: int = DEFAULT_ROUND_CAP) -> Applied:
    version = rustc_version(rustc)
    apps: list[Application] = []
    src = source
    with tempfile.TemporaryDirectory(prefix="flux-") as work:
        work_dir = Path(work)
        for rnd in range(1, round_cap + 1):
            ok, diags, fname = compile_check(src, rustc=rustc, work_dir=work_dir)
            if ok is None:
                return Applied(source, src, tuple(apps), STATE_RUSTC_FAILED, None, rnd - 1, version)
            if ok:
                return Applied(source, src, tuple(apps), STATE_COMPILES, None, rnd - 1, version)
            code = first_error_code(diags)
            cands = candidates(diags, fname)
            if not cands:
                return Applied(source, src, tuple(apps), STATE_STILL_FAILS, code, rnd - 1, version)
            if conflicts(cands):
                return Applied(source, src, tuple(apps), STATE_OVERLAP, code, rnd - 1, version)
            src = apply_round(src, cands)
            apps.extend(Application(rnd, c[3], c[0], c[1], c[2]) for c in sorted(cands, key=lambda c: c[0]))
        ok, diags, fname = compile_check(src, rustc=rustc, work_dir=work_dir)
        if ok:
            return Applied(source, src, tuple(apps), STATE_COMPILES, None, round_cap, version)
        return Applied(source, src, tuple(apps), STATE_ROUND_CAP, first_error_code(diags), round_cap, version)
