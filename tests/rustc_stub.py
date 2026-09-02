#!/usr/bin/env python3
"""A stub rustc for applier tests that need diagnostics real rustc will not
produce on demand: overlapping suggestions, two suggestions on one line,
a suggestion that never converges. The scenario is the program's first
line, `// scenario: <name>`. Emits rustc's JSON shape on stderr."""
import json
import sys


def diag(code, spans):
    return {
        "message": f"stub {code}", "code": {"code": code}, "level": "error",
        "spans": [], "children": [{
            "message": "stub help", "code": None, "level": "help",
            "spans": spans, "children": [], "rendered": None}],
        "rendered": f"error[{code}]: stub\n",
    }


def span(path, start, end, repl, appl="MachineApplicable"):
    return {"file_name": path, "byte_start": start, "byte_end": end,
            "line_start": 1, "line_end": 1, "column_start": 1, "column_end": 1,
            "is_primary": True, "text": [], "label": None,
            "suggested_replacement": repl, "suggestion_applicability": appl,
            "expansion": None}


def main(argv):
    if "--version" in argv:
        print("rustc 0.0.0-stub (stub 2026-01-01)")
        return 0
    path = next(a for a in argv if a.endswith(".rs"))
    data = open(path, "rb").read()
    first = data.split(b"\n", 1)[0].decode()
    scenario = first.replace("// scenario:", "").strip()
    body_off = len(data.split(b"\n", 1)[0]) + 1
    out = []
    if scenario == "overlap":
        i = data.find(b"abcdef")
        out = [diag("E9001", [span(path, i, i + 4, "XXXX")]),
               diag("E9002", [span(path, i + 2, i + 6, "YYYY")])]
    elif scenario == "sameinsert":
        i = data.find(b"abcdef")
        out = [diag("E9003", [span(path, i, i, "P")]),
               diag("E9004", [span(path, i, i, "Q")])]
    elif scenario == "rtl":
        a = data.find(b"aa"); b = data.find(b"bb")
        if a >= 0 and b >= 0:
            out = [diag("E9005", [span(path, a, a + 2, "AAAA")]),
                   diag("E9006", [span(path, b, b + 2, "BB")])]
    elif scenario == "loop":
        out = [diag("E9007", [span(path, body_off, body_off, "x")])]
    elif scenario == "maybe":
        out = [diag("E9008", [span(path, body_off, body_off, "z", "MaybeIncorrect")])]
    elif scenario == "otherfile":
        out = [diag("E9009", [span("/nowhere/else.rs", 0, 0, "x")])]
    for d in out:
        sys.stderr.write(json.dumps(d) + "\n")
    if out:
        sys.stderr.write(json.dumps({"message": "aborting due to previous error", "code": None,
                                     "level": "error", "spans": [], "children": [], "rendered": ""}) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
