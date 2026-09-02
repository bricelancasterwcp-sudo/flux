# flux Phase 0 census

rustc `rustc 1.96.0 (ac68faa20 2026-05-25)`, black-oxide `8f5399c8`, 2026-09-02T13:54:17+00:00 → 2026-09-02T13:54:23+00:00.

## Stored codes (spec §2.2, reproduced from the cells)

| arm | tier | first | not compiling | ownership-class | first codes |
|---|---|---:|---:|---:|---|
| base-rs-7 | small | 200 | 1 | 0 | E???? 1 |
| tune-rs-7 | small | 200 | 10 | 0 | E0308 10 |
| tune-rs-7 | large | 200 | 37 | 0 | E0308 16, E???? 5, E0434 4, E0614 4, E0277 2, E0425 2, E0106 1, E0433 1, E0600 1, E0606 1 |
| base-rs-14 | small | 60 | 0 | 0 |  |
| tune-rs-14 | large | 60 | 14 | 4 | E0308 9, E0382 4, E0615 1 |

## Re-judged under the pinned rustc

| arm | tier | attempts | first | first not compiling | drift | first-diag MA | any-diag MA | applied→compiles | green | states | dropped |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| base-rs-7 | small | 461 | 200 | 1 | 0 | 0 | 0 | 0 | 0 | `{'compiles': 457, 'still-fails': 4}` | `{'first_diag_ma': 457, 'any_diag_ma': 457, 'outcome': 461}` |
| tune-rs-7 | small | 278 | 200 | 10 | 0 | 0 | 0 | 0 | 0 | `{'compiles': 238, 'still-fails': 40}` | `{'first_diag_ma': 238, 'any_diag_ma': 238, 'outcome': 278}` |
| tune-rs-7 | large | 668 | 200 | 37 | 1 | 21 | 21 | 21 | 2 | `{'compiles': 581, 'still-fails': 87}` | `{'first_diag_ma': 560, 'any_diag_ma': 560, 'outcome': 647}` |
| base-rs-14 | small | 141 | 60 | 0 | 0 | 0 | 0 | 0 | 0 | `{'compiles': 141}` | `{'first_diag_ma': 141, 'any_diag_ma': 141, 'outcome': 141}` |
| tune-rs-14 | large | 147 | 60 | 14 | 0 | 4 | 4 | 4 | 0 | `{'compiles': 123, 'still-fails': 24}` | `{'first_diag_ma': 119, 'any_diag_ma': 119, 'outcome': 143}` |

## The kill criterion (§2.4): k = **15**, g = **2**, floor 16 → **NOT-FUNDED**

- base-rs-7 @ small: k = 0, g = 0
- tune-rs-7 @ small: k = 0, g = 0
- tune-rs-7 @ large: k = 15, g = 2
- base-rs-14 @ small: k = 0, g = 0
- tune-rs-14 @ large: k = 4, g = 0

## Phase 0b: the 20 Rust probe records

| id | defect | expected | re-derived | applier | applications | codes | outcome |
|---|---|---|---|---|---:|---|---|
| p01 | use-after-move | E0382 | E0382 | compiles | 1 | E0382 | green |
| p02 | double-consume | E0382 | E0382 | compiles | 1 | E0382 | green |
| p03 | loop-carried-move | E0382 | E0382 | compiles | 1 | E0382 | green |
| p04 | assign-to-iterated-vec | E0502 | E0502 | still-fails | 0 |  | None |
| p05 | move-then-read-field | E0382 | E0382 | compiles | 1 | E0382 | green |
| p06 | move-inside-branch | E0382 | E0382 | compiles | 1 | E0382 | green |
| p07 | move-into-struct-literal | E0382 | E0382 | compiles | 1 | E0382 | green |
| p08 | move-into-enum-variant | E0382 | E0382 | compiles | 1 | E0382 | green |
| p09 | move-into-vec-push | E0382 | E0382 | compiles | 1 | E0382 | green |
| p10 | move-via-struct-update | E0382 | E0382 | still-fails | 0 |  | None |
| p11 | destructure-then-use | E0382 | E0382 | compiles | 1 | E0382 | green |
| p12 | move-in-match-scrutinee | E0382 | E0382 | compiles | 1 | E0382 | green |
| p13 | move-in-while-body | E0382 | E0382 | compiles | 1 | E0382 | green |
| p14 | move-then-early-return | E0382 | E0382 | compiles | 1 | E0382 | green |
| p15 | move-via-question-mark | E0382 | E0382 | still-fails | 0 |  | None |
| p16 | move-in-nested-block | E0382 | E0382 | compiles | 1 | E0382 | green |
| p17 | accumulate-without-reassign | E0382 | E0382 | compiles | 1 | E0382 | wrong-output |
| p18 | double-move-in-one-expression | E0382 | E0382 | compiles | 1 | E0382 | green |
| p19 | move-then-conditional-use | E0382 | E0382 | compiles | 1 | E0382 | green |
| p20 | consume-while-iterating | E0505 | E0505 | compiles | 1 | E0505 | green |
