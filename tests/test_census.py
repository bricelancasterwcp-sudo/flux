"""Phase 0 census (spec §2.3-2.4): the stored-codes table reproduced to the
digit, the derived floor, the three pre-committed readings, None-vs-zero,
and the driver's two refusals."""
import dataclasses
import json
import math
from pathlib import Path

import pytest

from flux import census
from flux.census import (
    ARMS, K_FLOOR, OWNERSHIP_CODES, AttemptRecord, load_attempts, reading,
    stored_table, k_and_g, PinError,
)

OXIDE = Path.home() / "workspace" / "oxide"

SPEC_2_2 = {  # (arm, tier): (first attempts, not compiling, ownership-class, first codes)
    ("base-rs-7", "small"): (200, 1, 0, {"E????": 1}),
    ("tune-rs-7", "small"): (200, 10, 0, {"E0308": 10}),
    ("tune-rs-7", "large"): (200, 37, 0, {"E0308": 16, "E????": 5, "E0434": 4, "E0614": 4,
                                          "E0277": 2, "E0425": 2, "E0606": 1, "E0106": 1,
                                          "E0433": 1, "E0600": 1}),
    ("base-rs-14", "small"): (60, 0, 0, {}),
    ("tune-rs-14", "large"): (60, 14, 4, {"E0308": 9, "E0382": 4, "E0615": 1}),
}


def test_stored_codes_table_reproduces_spec_2_2_to_the_digit():
    """§2.2.1: the instrument must reproduce the table from the pinned
    checkout or it does not count."""
    for arm in ARMS:
        atts = load_attempts(OXIDE / arm.results)
        t = stored_table(atts)
        assert (t["first_attempts"], t["not_compiling"], t["ownership_class"], t["first_codes"]) == \
            SPEC_2_2[(arm.name, arm.tier)], (arm.name, arm.tier, t)


def test_the_floor_is_derived_not_chosen():
    se = math.sqrt(2 * 0.2 * 0.8 / 200)
    assert round(2 * se, 3) == 0.080
    assert K_FLOOR == round(2 * se * 200) == 16


def test_the_three_pre_committed_readings():
    assert reading(15, 0) == "not-funded"
    assert reading(0, 0) == "not-funded"
    assert reading(16, 16) == "deterministic-clears-noise"
    assert reading(20, 17) == "deterministic-clears-noise"
    assert reading(16, 15) == "funded"
    assert reading(16, 0) == "funded"
    assert reading(None, None) == "unmeasured"


def test_ownership_class_is_the_spec_set():
    assert OWNERSHIP_CODES == {"E0382", "E0499", "E0502", "E0505", "E0507", "E0596",
                               "E0384", "E0506", "E0503", "E0716", "E0597", "E0373"}


def _rec(**kw):
    base = dict(arm="tune-rs-7", tier="large", seed="gen-s1", task="g01", attempt=1,
                stored_compiled=False, stored_first_code="E0308", rederived_compiles=False,
                rederived_first_code="E0308", drift=False, first_diag_ma=True, any_diag_ma=True,
                applier_state="compiles", applier_rounds=1, applications=1,
                applier_final_code=None, outcome="green", rustc_version="rustc x")
    base.update(kw)
    return AttemptRecord(**base)


def test_k_and_g_count_first_attempts_that_fail_under_the_pinned_rustc():
    recs = [
        _rec(task="g01"),                                       # k, g
        _rec(task="g02", outcome="wrong-output"),               # k only
        _rec(task="g03", first_diag_ma=False, any_diag_ma=True, applier_state="still-fails",
             applications=0, outcome=None),                     # neither: first diag not MA
        _rec(task="g04", attempt=2),                            # repair attempt: excluded
        _rec(task="g05", rederived_compiles=True, rederived_first_code=None,
             first_diag_ma=None, any_diag_ma=None, applier_state="compiles",
             applications=0, outcome=None),                     # compiles: excluded
    ]
    assert k_and_g(recs) == (2, 1)


def test_unmeasured_is_none_and_named_not_zero():
    """A compiling attempt has no first diagnostic and was never run by
    the applier's judge: those fields are None, not False or 0."""
    r = _rec(rederived_compiles=True, rederived_first_code=None, first_diag_ma=None,
             any_diag_ma=None, applications=0, outcome=None)
    payload = r.to_json()
    assert payload["first_diag_ma"] is None and payload["outcome"] is None
    s = census.summarize([r, _rec()])
    assert s["greens"] == 1
    assert s["first_diag_ma"] == 1
    assert "outcome" in s["dropped"] and s["dropped"]["outcome"] == 1


def test_attempt_record_round_trips_completely():
    r = _rec()
    payload = r.to_json()
    assert set(payload) == {f.name for f in dataclasses.fields(AttemptRecord)}
    assert AttemptRecord.from_json(json.loads(json.dumps(payload))) == r


def test_driver_refuses_a_wrong_black_oxide_pin(tmp_path):
    with pytest.raises(PinError, match="black-oxide"):
        census.run(OXIDE, tmp_path, expected_oxide_commit="0" * 40,
                   expected_rustc_version=census.rustc_version_of(census.RUSTC), limit=1)


def test_driver_refuses_a_wrong_rustc_version(tmp_path):
    with pytest.raises(PinError, match="rustc"):
        census.run(OXIDE, tmp_path, expected_oxide_commit=census.oxide_commit(OXIDE),
                   expected_rustc_version="rustc 0.0.0-not-this", limit=1)


def test_a_missing_first_code_is_labelled_not_folded():
    """black-oxide's fallback diagnostic already carries the literal
    `E????`, so on committed cells the None path is dead; pin it anyway so
    a triple with no diagnostics at all can never be counted under a real
    code."""
    from flux.census import Attempt, label
    assert label(None) == "E????" and label("") == "E????" and label("E0308") == "E0308"
    atts = [Attempt("gen-s1", "g01", 1, "fn main(){}", False, False, None),
            Attempt("gen-s1", "g02", 1, "fn main(){}", False, False, "E0308")]
    assert stored_table(atts)["first_codes"] == {"E0308": 1, "E????": 1}
