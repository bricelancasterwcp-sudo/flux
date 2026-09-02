"""The applier's seven invariants (spec §4), each pinned by a test that
fails when the invariant is broken. Real rustc where it can produce the
case; the stub in rustc_stub.py where it cannot."""
import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from flux.applier import Application, Applied, apply_fixpoint, rustc_version

REAL = Path(shutil.which("rustc"))
STUB = Path(__file__).with_name("rustc_stub.py")


def test_identity_on_a_compiling_program_even_with_a_warning_suggestion():
    """Invariant 1. `x` is unused: rustc emits a WARNING with a
    MachineApplicable `_x`. A compiling program must come back untouched."""
    src = 'fn main() { let x = 5; println!("hi"); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.source == src
    assert a.applications == ()
    assert a.state == "compiles"
    assert a.final_code is None


def test_only_machine_applicable_is_applied():
    """Invariant 2. E0282's `: Vec<T>` is HasPlaceholders; E0308's
    `.to_string()` is MaybeIncorrect. Neither may be applied."""
    src = 'fn main() { let v = Vec::new(); println!("{}", v.len()); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.state == "still-fails" and a.final_code == "E0282"
    assert a.applications == () and a.source == src
    src2 = 'fn main() { let s: String = "abc"; println!("{}", s); }\n'
    b = apply_fixpoint(src2, rustc=REAL)
    assert b.state == "still-fails" and b.final_code == "E0308"
    assert b.applications == ()


def test_machine_applicable_fix_lands_and_the_program_compiles():
    src = 'fn main() { let x = 5; x = 6; println!("{}", x); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.state == "compiles"
    assert [(p.code, p.byte_start, p.byte_end, p.replacement) for p in a.applications] == [
        ("E0384", 16, 16, "mut ")]
    assert a.source == 'fn main() { let mut x = 5; x = 6; println!("{}", x); }\n'


def test_clone_suggestion_repairs_a_use_after_move():
    src = 'fn main() { let s = String::from("a"); let t = s; println!("{} {}", s, t); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.state == "compiles"
    assert [p.code for p in a.applications] == ["E0382"]
    assert "s.clone()" in a.source


def test_spans_are_byte_offsets_not_columns():
    """Acceptance for the byte-offset rule: a multi-byte character before
    the fix. Column arithmetic would land `mut ` one byte early."""
    src = 'fn main() { let s = "héllo"; let n = 5; n = 6; println!("{} {}", s, n); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.state == "compiles"
    assert a.applications[0].byte_start == 34
    assert "let mut n = 5" in a.source


def test_overlapping_spans_in_one_round_apply_neither(tmp_path):
    """Invariant 3."""
    src = "// scenario: overlap\nabcdef\n"
    a = apply_fixpoint(src, rustc=STUB)
    assert a.state == "overlap-refused"
    assert a.applications == () and a.source == src


def test_two_insertions_at_one_point_are_a_conflict():
    src = "// scenario: sameinsert\nabcdef\n"
    a = apply_fixpoint(src, rustc=STUB)
    assert a.state == "overlap-refused" and a.applications == ()


def test_right_to_left_application_keeps_later_offsets_valid():
    """Invariant 4. Applying `aa`->`AAAA` first would shift `bb`."""
    src = "// scenario: rtl\naa bb\n"
    a = apply_fixpoint(src, rustc=STUB)
    assert a.state == "compiles"
    assert a.source == "// scenario: rtl\nAAAA BB\n"
    assert sorted(p.code for p in a.applications) == ["E9005", "E9006"]
    assert all(p.round == 1 for p in a.applications)


def test_bounded_by_the_round_cap():
    """Invariant 5. The stub re-emits the same suggestion forever; without
    the cap this would never return, so the test runs under an alarm."""
    import signal

    def _boom(*_):
        raise TimeoutError("applier did not terminate: the round cap is not bounding it")
    signal.signal(signal.SIGALRM, _boom); signal.alarm(30)
    try:
        src = "// scenario: loop\nbody\n"
        a = apply_fixpoint(src, rustc=STUB, round_cap=5)
    finally:
        signal.alarm(0)
    assert a.state == "round-cap"
    assert a.rounds == 5
    assert len(a.applications) == 5
    assert a.source == "// scenario: loop\nxxxxxbody\n"


def test_suggestions_in_other_files_are_never_applied():
    src = "// scenario: otherfile\nbody\n"
    a = apply_fixpoint(src, rustc=STUB)
    assert a.state == "still-fails" and a.final_code == "E9009"
    assert a.applications == ()


def test_maybe_incorrect_alone_is_still_fails_with_no_application():
    src = "// scenario: maybe\nbody\n"
    a = apply_fixpoint(src, rustc=STUB)
    assert a.state == "still-fails" and a.final_code == "E9008"
    assert a.applications == ()


def test_every_application_is_logged_with_its_code_and_round_trips():
    """Invariant 6: JSON round trip with dataclass equality, plus
    completeness -- every field of Applied is in the payload."""
    src = 'fn main() { let x = 5; x = 6; println!("{}", x); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    payload = a.to_json()
    assert set(payload) == {f.name for f in dataclasses.fields(Applied)}
    assert set(payload["applications"][0]) == {f.name for f in dataclasses.fields(Application)}
    assert Applied.from_json(json.loads(json.dumps(payload))) == a


def test_rustc_version_is_recorded_in_every_applied():
    """Invariant 7 (the applier half; the driver's refusal is in the census tests)."""
    a = apply_fixpoint("// scenario: rtl\naa bb\n", rustc=STUB)
    assert a.rustc_version == "rustc 0.0.0-stub (stub 2026-01-01)"
    assert rustc_version(REAL).startswith("rustc 1.")
    b = apply_fixpoint('fn main() {}\n', rustc=REAL)
    assert b.rustc_version == rustc_version(REAL)


def test_a_warning_suggestion_is_not_applied_even_while_fixing_an_error():
    """Invariant 1's load-bearing half. A compiling program returns before
    any suggestion is read, so the errors-only filter only matters when
    an error and a warning coexist: `unused` has a MachineApplicable
    `_unused`; only the E0384 fix may land."""
    src = 'fn main() { let x = 5; x = 6; let unused = 1; println!("{}", x); }\n'
    a = apply_fixpoint(src, rustc=REAL)
    assert a.state == "compiles"
    assert [p.code for p in a.applications] == ["E0384"]
    assert "let unused = 1" in a.source
