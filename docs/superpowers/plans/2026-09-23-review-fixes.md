# K2 Annotator v3.1.0 — Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement every finding in `D:\K2AnnotatorReview\review_artifacts\REPORT.md` (sections 3, 4 and 6) as version 3.1.0, without changing any Level-2 criterion as written in Koelmel 2022 / NYCSS SI / Kwiecien 2015.

**Architecture:** The scoring core (`scripts/src/rhrmf.py`, `spectral_math.py`, `matching_engine.py`, `surrogate_analyzer.py`) is corrected in place. Input handling is consolidated into one tolerant `scripts/src/msp_reader.py` used by every MSP consumer, and every "zero of something" condition becomes an error instead of a print. Reporting gains provenance (run manifest, RI-extrapolation flag, HR-aware scores). GUI/pipeline plumbing and the external-API layer are fixed in their own files. A `tests/` package (pytest) ships with the repo and is the acceptance gate; it is derived from `review_artifacts/tests`, with every strict `xfail` turned into a plain assertion.

**Tech Stack:** Python 3.8+, numpy/scipy/pandas, molmass, reportlab, pytest. Git repository initialised at the package root with the v3.0.21 baseline as the first commit.

**Versioning:** Version string `3.1.0` in `CHANGELOG.md`, `README.md`, `K2.spec`, `scripts/k2_gui.py` (window title / About), and a new `scripts/src/version.py` (`__version__ = "3.1.0"`) that `cli.py` prints and writes to the run manifest. One commit per task.

**Shared interfaces (fixed up front so parallel tasks agree):**
- New CLI flags in `scripts/cli.py`: `--ri-extrapolation {spline,linear}` (default `spline`), `--allow-no-blanks` (flag), `--name` (now used for output file names). `--grouping` becomes live. Exit codes: 0 success, 2 completed with zero Level-2 matches (summaries still written), 1 error.
- `gcms_pipeline.py` forwards `--ri-extrapolation`, `--allow-no-blanks`, `--max-lib-peaks`, `--name`, treats cli exit 2 as success-with-warning, and never overwrites an existing results directory.
- `MatchCandidate` gains `hr_dot`, `hr_rev_dot` (ints, `None` for LR) and `rhrmf_score` is `None` for HR candidates (no sentinel).
- `Feature` gains `ri_extrapolated: bool`, `raw_abundances: dict` (pre-normalisation copy).
- `RICalibrator` gains `rt_range` (tuple), `is_in_range(rt)`, `extrapolation` (`'spline'|'linear'`).
- `StructureHelper.get_hazard_matrix(inchikey, name, cas)` keeps its signature but is cached per CAS, uses a shared `requests.Session` with timeouts/backoff, and never raises.
- `msp_reader.iter_msp(path)` yields `(fields: dict[str,str] (keys upper-cased, `_`/space-normalised), peaks: list[(mz, intensity)])`.

---

### Task 0: Repository baseline and test package

**Files:**
- Create: `tests/conftest.py`, `tests/synth/make_dataset.py` (copy of `review_artifacts/synth/make_dataset.py`), `tests/test_science.py`, `tests/test_e2e.py`, `tests/test_parsers.py` (copies of the review tests with `sys.path` pointing at `../scripts`), `pytest.ini`
- Modify: `.gitignore` (add `tests/synth/data/`, `results/`, `temp_assets/`)

- [x] Step 1: `git init`, commit v3.0.21 baseline (done 2026-09-23).
- [ ] Step 2: Copy the review tests into `tests/`; keep every `xfail(strict=True)` marker for now. Run `python -m pytest tests -q` → expect `55 passed, 24 xfailed`.
- [ ] Step 3: Commit `test: add review test suite (findings pinned as strict xfails)`.

Each later task removes the xfail markers it fixes; the suite must never show an XPASS.

### Task 1: S-RHRMF-1 electron mass, S-DOC-1 exact masses, S-DOT-2 rounding

**Files:** `scripts/src/rhrmf.py`, `scripts/src/spectral_math.py`, `tests/test_science.py`

- [ ] Remove xfail from `test_rhrmf_all_peaks_of_perfect_benzene_are_explained`, `test_rhrmf_true_low_mz_cation_is_explained`, `test_rhrmf_tolerates_minus_5ppm_error`, `test_half_integer_binding_is_direction_consistent`; run → 4 FAIL.
- [ ] `spectral_math.py`: add `ELECTRON_MASS = 0.000548579909` and `def nominal_mass(mz): return int(math.floor(float(mz) + 0.5))`; use it in `bin_spectrum`.
- [ ] `rhrmf.py`: replace `ATOM_MASSES` with molmass-derived monoisotopic masses (`Formula('C').monoisotopic_mass` etc. computed at import) including `'2H'`, `'13C'`, `'D'`, `'[2H]'`, `'[13C]'`, and `'F','P','I','B','Na','K','Se','Sn'`; in `explain_peak` compare `abs(target - (current_mass - ELECTRON_MASS)) <= tolerance` and bound `theoretical_max` with the same offset; use `nominal_mass` for `lib_bins`.
- [ ] Run tests → PASS. Commit `fix(rhrmf): subtract electron mass, exact isotope masses, consistent nominal rounding (S-RHRMF-1, S-DOC-1, S-DOT-2)`.

### Task 2: S-RHRMF-2 labelled atoms

**Files:** `scripts/src/rhrmf.py`, `scripts/src/library_parser.py`, `tests/test_science.py`, `tests/test_e2e.py`

- [ ] Remove xfail from `test_rhrmf_deuterated_surrogate_passes`, `test_rhrmf_13C_surrogate_passes`; move the two labelled pairs out of `KNOWN_MISSES`; run → FAIL.
- [ ] `parse_formula`: keep every symbol; `explain_peak`: if any parent element is missing from `ATOM_MASSES`, log once per formula (`warnings.warn`) and skip that element. `library_parser`: after load, count formulas with unknown atoms and print the count + first 5 names.
- [ ] Run → PASS. Commit `fix(rhrmf): support D/13C-labelled formulas (S-RHRMF-2)`.

### Task 3: S-HR-1 detector, S-HR-2 reporting, HR-aware scores in output

**Files:** `scripts/src/rhrmf.py`, `scripts/src/matching_engine.py`, `scripts/src/surrogate_analyzer.py`, `scripts/src/reporter.py`, `scripts/src/summary_tables.py`, tests

- [ ] Remove xfail from `test_hr_detector_accepts_small_defect_exact_mass_entries`, `test_hr_match_rhrmf_not_reported_as_100`, `test_exact_mass_entries_take_the_hr_path`; run → FAIL.
- [ ] `is_library_high_res(spectrum, metadata=None)`: (1) metadata override — keys `resolution`/`hires`/`high_res` with values high/hr/true/1 → True, low/lr/false/0 → False; (2) otherwise a peak is "exact-mass" if it carries ≥3 decimal digits (`abs(mz*100 - round(mz*100)) > 1e-6`); entry is HR if ≥2 such peaks and ≥1 in the top-3 by intensity. Document in docstring; keep the old rule as `is_library_high_res_v3021` for audit.
- [ ] `MatchCandidate`: `rhrmf_score=None`, `hr_dot=None`, `hr_rev_dot=None`; engine sets them; surrogate analyser mirrors (`SurrogateMatch.hr_dot/hr_rev_dot`).
- [ ] Reporter/summary/surrogate reporter: RHRMF column prints `N/A` when `None`; add `HR_RevDot`, `HR_FwdDot` columns.
- [ ] Run → PASS. Commit `fix(hr): stored-precision HR detector with metadata override; report HR-aware scores instead of sentinel (S-HR-1, S-HR-2)`.

### Task 4: S-SUR-1, S-SUR-2 surrogate analyser

**Files:** `scripts/src/surrogate_analyzer.py`, tests

- [ ] Remove xfail from `test_surrogate_recovery_is_100_when_surrogate_tracks_is`, `test_surrogate_and_engine_use_same_ri_percent_reference`; run → FAIL.
- [ ] `_get_normalized_abundance` returns `feature.abundances[sample]` (already normalised); percent error uses `feat.ri`.
- [ ] Run → PASS. Commit `fix(surrogate): no double IS normalisation; RI % relative to feature (S-SUR-1, S-SUR-2)`.

### Task 5: RI calibration (S-RI-1, S-RI-2, D-4)

**Files:** `scripts/src/ri_calibration.py`, `scripts/src/universal_parser.py`, `scripts/src/matching_engine.py`, `scripts/src/reporter.py`, `scripts/src/summary_tables.py`, `scripts/cli.py`, tests

- [ ] Remove xfail from `test_ri_calibrator_flags_extrapolation`, `test_ri_cal_without_header`, `test_ri_cal_missing_file_raises`, `test_engine_refuses_features_without_ri`; add `test_ri_linear_extrapolation_matches_van_den_dool`; run → FAIL.
- [ ] `RICalibrator(calibration_file, extrapolation='spline')`: missing path raises `FileNotFoundError`; loader sniffs delimiter (`sep=None, engine='python'`, `header=None`, drop row 0 only if non-numeric); validates ≥3 rows, unique carbon numbers, strictly increasing RT with explicit messages; `rt_range`, `is_in_range`; `rt_to_ri` uses spline inside range and, when `extrapolation == 'linear'`, van den Dool linear extrapolation from the terminal alkane pair outside it. Print an explicit warning at load: "features outside RT x–y min will be extrapolated (mode)".
- [ ] `Feature.ri_extrapolated`; `UniversalParser.set_ri_calibrator(path, extrapolation)`; parser sets the flag; engine: `ValueError` if MZmine format and no calibrator; warns with count of features whose RI is 0 or extrapolated.
- [ ] Reporter + summaries: `RI_Extrapolated` column. `cli.py --ri-extrapolation`.
- [ ] Run → PASS. Commit `feat(ri): validate calibration input, flag/limit extrapolation, refuse RI-less MZmine runs (S-RI-1, S-RI-2, D-4)`.

### Task 6: Blank/sample guards and grouping (S-BFF-1, D-1, D-2)

**Files:** `scripts/src/universal_parser.py`, `scripts/cli.py`, tests

- [ ] Remove xfail from `test_zero_blank_columns_is_an_error`, `test_grouping_json_changes_blank_set`; run → FAIL.
- [ ] `UniversalParser(blank_identifier, allow_no_blanks=False)`: empty identifier → `ValueError`; after column classification: 0 quant columns → `ValueError`; 0 samples → `ValueError`; 0 blanks → `ValueError` unless `allow_no_blanks`; print the final classification table. With `sample_types`, unlisted columns fall back to auto-detection in both branches. Any name in `sample_types`/`reference_samples` absent from the columns → `ValueError` listing the names.
- [ ] `cli.py`: load `--grouping` JSON (`{name: {"type": "Blank"|"Sample"|"Reference", ...}}` or `{name: "blank"|"sample"}`), build `sample_types`, derive `reference_samples` (union with `--reference-samples`), pass both to `MatchingEngine`; `--allow-no-blanks`.
- [ ] Run → PASS. Commit `fix(cli): honour sample grouping; refuse silent zero-blank runs (D-1, D-2, S-BFF-1)`.

### Task 7: Shared MSP reader and parser robustness (D-3)

**Files:** Create `scripts/src/msp_reader.py`; modify `scripts/src/library_parser.py`, `scripts/src/universal_parser.py`, `scripts/src/is_normalizer.py`; delete `scripts/src/msdial_parser.py`; tests

- [ ] Remove xfail from the five `test_parsers.py` MSP cases; add tests for CRLF, tab-separated peaks, `Num Peaks` mismatch warning, `Peak height` quant columns, `datafile:X.mzML:area` columns, non-integer `row ID` error, duplicate `row ID` warning; run → FAIL.
- [ ] `msp_reader.py`: `open(path, encoding='utf-8-sig', errors='replace')`; keys upper-cased with `_`→space and collapsed whitespace; a `NAME:` while a record is open closes it; peak lines tokenised on `;`, whitespace, commas, parentheses, several pairs per line; count mismatch → collected warning; `RI` parsed from `RI`, `RETENTIONINDEX`, `RETENTION INDEX`, `KOVATS`, first numeric token of `Retention_index: SemiStdNP=1000/8/25`.
- [ ] `library_parser._load_msp` and `universal_parser.parse_*_msp_file` and `is_normalizer._parse_msp_file` call `iter_msp`; CSV opened with `newline=''`, `utf-8-sig`, empty file → clear error. MZmine quant: accept ` Peak area`, ` Peak height`, `datafile:<name>:area|height` (strip extension); validate required columns before the loop; raise on 0 features; warn on duplicate IDs and on features lacking spectra.
- [ ] Run → PASS. Commit `refactor(io): one tolerant MSP reader; validated quant parsing (D-3)`.

### Task 8: Reporter, summaries, zero-match runs (D-5, D-9)

**Files:** `scripts/src/reporter.py`, `scripts/src/summary_tables.py`, `scripts/src/surrogate_reporter.py`, `scripts/cli.py`, tests

- [ ] Add tests: metadata fallback (`instrument`/`comments`), reference samples excluded from feature summary stats, zero-match run writes feature summary and exits 2, `IS_Area` filled for auto methods.
- [ ] Reporter: `meta.get('instrument_type') or meta.get('instrument')`, same for comments; `reference_samples` parameter excluded from `true_sample_columns`; hazard lookup once per CAS via `StructureHelper` cache; no plot rendering in CSV path; PDF per-candidate `try/except` and `c.save()` in `finally`; `temp_assets` removed at the end unless `--keep-assets`; `Mean_Sample_Abundance` documented (mean over all samples, non-detects as 0) plus `Mean_Detected_Abundance`. Surrogate reporter: `0.0` rendered, not blank. `cli.py`: zero matches → still write summaries, exit 2; `--csv-only`/`--pdf-only` mutually exclusive (argparse group); `--name` used in file names.
- [ ] Commit `fix(report): metadata keys, reference-sample stats, robust PDF, zero-match summaries (D-5, D-9)`.

### Task 9: IS normaliser (D-10)

**Files:** `scripts/src/is_normalizer.py`, `scripts/src/universal_parser.py`, `scripts/src/matching_engine.py`, tests

- [ ] Tests: idempotent (second call gives same result), string IS values coerced or clear error, MSP via shared reader, `is_values` exported back into `is_config`.
- [ ] `Feature.raw_abundances` set once at parse; `_apply_normalization` always computes from `raw_abundances`; `float()` coercion with error listing bad samples; engine copies `normalizer.is_values` into `is_config['is_values']` so the CSV reports auto-detected areas.
- [ ] Commit `fix(is): idempotent normalisation from raw abundances; validated inputs (D-10)`.

### Task 10: Run manifest and provenance (D-6)

**Files:** Create `scripts/src/version.py`, `scripts/src/run_manifest.py`; modify `scripts/cli.py`; tests

- [ ] Test: after a CLI run, `run_manifest.json` exists with keys `k2_version`, `python`, `packages`, `args`, `inputs` (path, size, sha256), `sample_classification`, `library_stats`, `ri_calibration`, `timestamp`.
- [ ] Implement; `cli.py` prints the version banner and writes the manifest into the output directory.
- [ ] Commit `feat(cli): run manifest with versions, input hashes and resolved configuration (D-6)`.

### Task 11: GUI and pipeline plumbing (D-7) — parallel subagent A

**Files:** `scripts/gcms_pipeline.py`, `scripts/k2_gui.py`, `scripts/k2_screens.py`, `scripts/k2_config.py`, `K2.spec`, `K2.bat`, `INSTALLATION.txt`; delete `scripts/main.py`

- [ ] Forward the new CLI flags; treat exit 2 as success-with-warning; never overwrite `results/<name>` (append `_2`, `_3`…); tee the pipeline log into the results directory; thread clamp fixed (`--mzmine-import-threads` default `None` → use `--threads`, GUI exposes the serialise switch); frozen build launches the pipeline in-process; `max_lib_peaks` in `K2Config.defaults`, Analysis screen and command builder; `new_project`/`open_project` rebuild `pipeline_config` from defaults; `save_preset` whitelist; API key via env var `K2_EPA_API_KEY`, redacted in echoes, stripped from `.K2` files; `on_completion` via `self.after`; Cancel kills the process tree; `--name` sanitised; `K2.spec` version 3.1.0, icon optional; `K2.bat` re-installs when `requirements.txt` changes; dead `InternalStandardScreen` and `main.py` removed; `subprocess.list2cmdline` for echoes; unsorted glob fallback removed.
- [ ] Commit `fix(gui,pipeline): plumbing, threading, frozen build, config hygiene (D-7)`.

### Task 12: External API layer (D-8) — parallel subagent B

**Files:** `scripts/src/structure_helper.py`, `scripts/src/ctx_client.py`; delete `scripts/src/epa_client.py`

- [ ] Shared `requests.Session` with `timeout=(5, 20)` and `urllib3.Retry` backoff; in-memory + on-disk (`~/.k2/cache/hazard.json`) cache per CAS; ≤4 requests/s to PubChem; `EpaClient` removed and DTXSID resolved through `CTXClient`; a hazard matrix is only trusted when at least one record parsed; no bare `except`; `get_structure_image` returns `None` quickly on failure.
- [ ] Commit `fix(api): timeouts, retries, caching; remove guessed EPA endpoint (D-8)`.

### Task 13: Documentation and version bump

**Files:** `CHANGELOG.md`, `README.md`, `K2_USER_GUIDE.md`, `QUICK_START.md`, create `docs/SCORING_METHODS.md`, `templates/TEST_DATA_README.md`, create `templates/ri_calibration_template.txt`, `requirements.txt`

- [ ] `CHANGELOG.md` `[3.1.0]` entry: every finding ID, what changed, what it does to scores, migration notes (re-run analyses; RHRMF values rise for light-fragment spectra; HR classification changes).
- [ ] `docs/SCORING_METHODS.md`: SI-ready description of exactly what is computed (BFF; RI calibration incl. extrapolation mode and flag; dot-product weighting m/z¹·I^0.5, squared cosine ×1000, unit-mass bins with round-half-up; top-N library trim; HR detector rule; HR-aware 10 ppm re-scoring; RHRMF with electron mass, isotopologue approximation, TIC weighting; the "adjusted" BFF mode being outside the Koelmel framework).
- [ ] User guide: criteria section rewritten from `SCORING_METHODS.md`; IS factor = max/IS; new flags; troubleshooting entries for the new errors.
- [ ] Templates: ship an alkane table that covers the template features; correct README expectations.
- [ ] Commit `docs: v3.1.0 changelog, scoring methods, user guide, templates`.

### Task 14: Acceptance

- [ ] `python -m pytest tests -q` → all pass, zero xfail/xpass. Run `review_artifacts/tests` against the fixed tree with markers removed → all pass. Run `python scripts/cli.py` on `templates/` and on `tests/synth/data` → exit 0, manifest present. Tag `v3.1.0`.
