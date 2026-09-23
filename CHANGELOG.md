# Changelog

All notable changes to **K2 Annotator** (formerly K2 Analyzer / K2 GC-MS Suspect Screening Pipeline) will be documented in this file.

## [3.1.0] - 2026-09-23

Release produced from an independent scientific and software review of v3.0.21
against the manuscripts the pipeline implements (Koelmel et al. 2022, Brunet et
al. NYCSS manuscript + SI, Kwiecien et al. 2015). Finding IDs (S-* scientific,
D-* design) refer to that review; every finding is pinned by a test in the new
`tests/` package (`python -m pytest`). **No Level-2 threshold or window was
changed.** Several fixes make the code compute the written criteria correctly
and therefore change scores; see "Migration".

### Fixed — scoring (changes results)
- **RHRMF now subtracts the electron mass (S-RHRMF-1).** `rhrmf.py` compared
  measured ion m/z against *neutral* sub-formula masses. Kwiecien 2015 (SI)
  subtracts one electron mass before matching. The omission shifted the
  ±10 ppm window by 6 ppm at m/z 91 and 11 ppm at m/z 51, rejecting perfectly
  measured light fragments and making the effective tolerance asymmetric
  (toluene at −5 ppm mass error scored 0, at +5 ppm scored 100). The window is
  now symmetric about the measured cation m/z. RHRMF values rise for spectra
  rich in fragments below ~m/z 150; the "unexplained biphenyl zeros" noted in
  the v3.0.20 entry are a symptom of this defect.
- **Isotopically labelled formulas work in RHRMF (S-RHRMF-2).** `D`/`2H`,
  `13C` and other isotope symbols emitted by molmass were silently dropped, so
  every labelled surrogate scored RHRMF 0 against a low-resolution entry.
  Atom masses now come from molmass' isotope table (also fixing a ~0.8 ppm
  bias from the old 5-decimal table, S-DOC-1); unknown atoms trigger a
  warning at library load instead of silence.
- **Exact-mass library detector decides by stored precision (S-HR-1).** An
  entry is HR when its metadata says so (`resolution`/`hires` = high) or when
  ≥2 peaks carry ≥3 decimal digits with ≥1 in the top-3 by intensity. The
  v3.0.21 mass-defect rule classified exact-mass benzene, chlorobenzene and
  dichlorobiphenyl entries as low-resolution and discarded real C27–C28 alkyl
  fragments as z=2 artefacts. The old rule remains as
  `is_library_high_res_v3021()` for audit.
- **Surrogate recoveries were IS-normalised twice (S-SUR-1).** With IS
  normalisation on, `SurrogateAnalyzer` multiplied already-normalised
  abundances by the factor again (factor² → a true 100 % recovery reported as
  200 %/400 %). The surrogate matcher also now evaluates the 1.5 % RI rule
  relative to the feature RI like the screening engine (S-SUR-2).
- **Unit-mass binning rounds half up** (76.5 → 77 and 77.5 → 78; previously
  banker's rounding gave 76 and 78) (S-DOT-2).

### Fixed — correctness
- **`--grouping` is live (D-1).** The GUI's per-sample Blank/Sample/Reference
  table was written to JSON and forwarded, but `cli.py` never used it; BFF
  fell back to the blank-identifier substring. Reference samples are derived
  from the grouping as well.
- **Zero-of-anything is an error (D-2, D-5, S-BFF-1, S-RI-2).** No
  quantification columns, no features, no sample columns, no blank columns
  (unless `--allow-no-blanks`), unknown names in the grouping, a missing
  calibration file, or MZmine data without a calibration file now stop the
  run with a clear message instead of an empty "successful" result. The
  final blank/sample classification is printed.
- **One tolerant MSP reader (`src/msp_reader.py`) for every consumer (D-3).**
  Handles UTF-8 BOM, CRLF, any key case, `Retention_index:`/`NUM_PEAKS:`
  spellings, NIST `41 59; 43 999;` and `(41 59)` peak lines, records without
  blank-line separators, and `Num Peaks` mismatches (warned, never
  truncated). Previously a NIST export could load zero compounds silently.
  MZmine quant files with `Peak height` or `datafile:X.mzML:area` columns are
  accepted; sample names are normalised (extension / suffix stripped) so GUI
  file stems, `--reference-samples` and column headers agree.
- **RI calibration loader validates its input (D-4):** header-less tables
  no longer lose their first alkane; comma/semicolon/space delimiters
  accepted; duplicate carbon numbers and non-monotonic RTs are rejected with
  explicit messages.
- **IS normalisation is idempotent and validated (D-10):** factors are
  applied to the parsed (`raw_abundances`) values, string IS values fail
  with a message, the IS MSP goes through the shared reader, auto-detected IS
  areas are reported in `IS_Area_*` columns.
- **Reports (D-9):** `Instrument`/`Comments` columns read the template keys
  `instrument`/`comments`; reference samples are excluded from feature-summary
  statistics (they were excluded from the BFF but not from the summaries);
  `Mean_Detected_Abundance` added; hazard lookups happen once per CAS; mirror
  plots are rendered only for the PDF; one bad page no longer loses the whole
  PDF (`c.save()` in `finally`); `temp_assets/` is removed unless
  `--keep-assets`; surrogate recovery of exactly 0 renders as 0.
- **External APIs (D-8):** one `requests.Session` with timeouts, retries and
  a PubChem rate limit; per-CAS on-disk cache (`~/.k2/cache/`); the guessed
  `EpaClient` endpoint (which returned an all-zero matrix and suppressed the
  PubChem fallback whenever an API key was present) is removed; DTXSIDs come
  from `ctxpy`; `pubchempy` dependency dropped.
- **GUI / pipeline (D-7):** the Thread Count setting is honoured (import
  serialisation is now an explicit checkbox); the PyInstaller build runs the
  pipeline in-process instead of re-launching the GUI; `max_lib_peaks`,
  `ri_extrapolation` and `allow_no_blanks` are exposed in the Analysis
  screen; project/preset state no longer leaks between projects; the EPA API
  key travels via `K2_EPA_API_KEY` and is stored only in
  `~/.k2/credentials.json`, never in `.K2` files or command echoes; Tk widgets
  are updated on the main thread; Cancel kills the whole process tree;
  `results/<name>` is never overwritten (`_2`, `_3`, …); `--name` is sanitised
  and used; dead code (`main.py`, `InternalStandardScreen`, `msdial_parser.py`)
  removed.

### Added
- **`RI_Extrapolated` column** in every table and a load-time warning: RIs
  for features outside the alkane range are flagged (S-RI-1).
  `--ri-extrapolation {spline,linear}` selects how they are derived
  (default `spline` = v3.0.x behaviour; `linear` = van den Dool from the
  terminal alkane pair). `RICalibrator.rt_range` / `is_in_range()`.
- **`run_manifest.json`** in every results folder (D-6): K2 and package
  versions, SHA-256 of every input, resolved options (including
  `max_lib_peaks`), sample classification, library statistics, calibration
  range and feature/match counts. `pipeline_log.txt` and the untruncated
  `mzmine_log.txt` are saved alongside.
- **`HR_RevDot` / `HR_FwdDot` columns**; `RHRMF` reads `N/A` for exact-mass
  entries instead of the sentinel `100.0` (S-HR-2).
- **CLI exit codes:** 0 matches found, 2 completed with no matches (summaries
  and manifest still written), 1 error. `--csv-only`/`--pdf-only` are mutually
  exclusive; `--version`.
- **`tests/`**: 99 pytest tests with a formula-derived synthetic dataset
  (`tests/synth/make_dataset.py`) covering every criterion, edge cases and the
  end-to-end CLI. `templates/ri_calibration_template.txt` ships so the
  template data runs out of the box.
- **`docs/SCORING_METHODS.md`**: the exact computations (weights, trimming,
  detector rule, RHRMF details, extrapolation) in SI-ready form.

### Documentation
- Dot-product weighting (m/z¹ · I^0.5, squared cosine × 1000), the top-20
  library trim and the HR-aware re-scoring step are now stated explicitly;
  they were undocumented (S-DOT-1, S-TRIM-1). The `adjusted` BFF mode is
  labelled as outside the Koelmel framework. The IS factor is documented as
  max(IS)/IS (the guide said median).

### Migration
- Re-run analyses whose RHRMF values, HR classification or surrogate
  recoveries matter: RHRMF scores rise for light-fragment spectra, some
  candidates rejected by v3.0.x now pass, exact-mass aromatic/halogenated
  entries take the HR path, and IS-normalised recoveries are lower by the IS
  factor.
- MZmine runs now require `--ri-cal`; runs with no blank column require
  `--allow-no-blanks`.
- `epa_client.py`, `msdial_parser.py` and `main.py` are gone; `pubchempy` is
  no longer required.

---

## [3.0.21] - 2026-05-12

### Changed
- **`is_library_high_res()` tightened to require real exact-mass evidence in the top-3 peaks.** The previous rule ("any peak in the trimmed top-20 has fractional m/z > 0.05") was tripped by half-integer doubly-charged ion artifacts (76.5, 160.5, etc.) and by entries stored at 1-decimal precision (93.1, 91.1, ...). The new rule requires (a) at least two "real-HR" peaks — fractional m/z > 0.05, NOT half-integer (0.40 ≤ frac ≤ 0.60 excluded), NOT 1-decimal-rounded — AND (b) at least one such peak among the top 3 by intensity. A May 2026 library audit on the 97k-entry unified library found the old rule had ~29% false-positive rate (282 of 989 K2-flagged-HR entries were artifacts); the new rule eliminates this misclassification source.
- **`calculate_scores_hr_aware()` is now production scoring for HR library matches.** Previously HR library entries were "auto-passed" through RHRMF (sentinel score 100.0) based on unit-resolution dot product alone — meaning the library being HR was load-bearing for skipping RHRMF, but the HR mass precision was never actually used. v3.0.21 runs an HR-aware dot product using **10 ppm peak-pair matching** for HR library entries and gates on the same >600/>500 thresholds. RHRMF is intentionally not run on HR candidates: the HR-aware dot product itself uses exact-mass precision, so RHRMF would be redundant. The unit-resolution `calculate_scores()` is still used as a pre-filter (a candidate must first pass unit-res >600/>500 to reach HR-aware scoring); since HR-aware is strictly stricter than unit-res for true matches, the pre-filter is safe and cheap.
- **`MatchingEngine.run_matching()` and `SurrogateAnalyzer._match_single_compound()` both wired to the new HR path.** LR library matches still use unit-resolution dot + the v3.0.20 Kwiecien-style RHRMF (10 ppm + isotopologues + TIC-weighted), unchanged.

### Why this change
- **Variant comparison (diag_run5, May 2026):** Variant A (v3.0.20 production, HR auto-pass) admitted 38 HR matches; Variant B (RHRMF for everyone) admitted 1; Variant C (HR-aware dot, this release) admitted 0 under the old loose HR detector. Drilling down: all 37 of the disagreement-bucket candidates (A passes, B/C fail) had RHRMF_opt3 < 75 AND HR-aware dot = 0. They were passing purely on coincidental unit-resolution alignment with library entries that K2 mis-classified as HR via half-integer artifacts. Variant A was admitting matches with no actual exact-mass evidence behind them.
- **Tolerance choice (10 ppm):** Kwiecien 2015 (SI Fig 6) empirically determined 10 ppm as the optimum tradeoff between low-S/N fragment acceptance and formula discrimination on Q Exactive GC data. Same value as v3.0.20's RHRMF, so a peak that's "in" for RHRMF is also "in" for HR-aware dot. Typical Orbitrap GC mass accuracy is 1–5 ppm; 10 ppm provides ~2× headroom for real-world calibration drift without bleeding into noise.
- **Algorithm choice (ppm peak-pairing, not fixed-Da binning):** Fixed Da binning at 0.01 Da gives wildly different effective ppm tolerances across the GC-MS mass range (~100 ppm at m/z 100, ~10 ppm at m/z 1000), defeating the point of an HR-aware approach. The new implementation uses greedy peak-pair matching with a ppm window that scales naturally with m/z.

### Expected impact on match counts
- Under the new HR detector + HR-aware dot, candidates against genuinely-HR library entries get a rigorous accurate-mass check; candidates against misclassified-LR library entries (half-integer artifacts) flow through the LR path with RHRMF instead. From the May 2026 diag_run5 data, the 37 HR auto-pass candidates that v3.0.20 admitted on the misclassified entries would be re-routed through RHRMF; based on their rhrmf_opt3 distribution (mostly 0–55), most would fail there too. Sabinene at feat_id 123 — the one solid auto-pass in v3.0.20 — has rhrmf_opt3=95.8, so it should still pass via the LR path under the new rules.
- Final pass count expected: similar to Variant B in the diagnostic (~283) — substantially fewer than v3.0.20's 320 but with all matches now backed by actual exact-mass evidence rather than misclassification artifacts.

### Backward compatibility
- The legacy `calculate_rhrmf()` function and the diagnostic K2_DIAG/K2_DIAG_VARIANT instrumentation remain available for audit purposes (set `K2_DIAG_MATCHING_CSV`). The `K2_DIAG_DOTVAR` columns are not in this release because the v3.0.21 production behavior already incorporates HR-aware dot; the side-by-side comparison can still be retrieved by checking out `claude/dot-product-variants`.
- Re-run prior analyses if matching score continuity matters; v3.0.21 changes which compounds pass and which don't for HR library entries.

---

## [3.0.20] - 2026-05-12

### Changed
- **RHRMF production scoring now follows Kwiecien 2015 (Anal. Chem. 87, 8328) closely.** Switches from the K2-original implementation (0.015 Da fixed tolerance, no isotopologue handling, count-based scoring) to: **10 ppm mass tolerance**, **on-the-fly heavy-isotope substitution for 13C / 37Cl / 81Br / 34S / 30Si**, and **TIC-weighted scoring** (`∑(mz × intensity)_annotated / ∑(mz × intensity)_observed`). The reverse direction (filter to peaks present in library) is preserved, since the framework calls for RHRMF rather than forward HRMF (Koelmel 2022, Exposome 2(1) osac007). Threshold remains `> 75`. Applied identically in `MatchingEngine.run_matching()` and `SurrogateAnalyzer._match_single_compound()`.
- **HR auto-pass logic unchanged.** Library entries the HR detector flags as high-resolution still bypass RHRMF and receive the `100.0` sentinel + automatic `final_pass=True`, exactly as in v3.0.19.

### Why this change
- A May 2026 review of K2's `rhrmf.py` against the Kwiecien 2015 HRF paper and the Koelmel 2022 framework paper found three material deviations: tolerance ~3–30× wider than spec, no isotopologue handling (significant for halogenated/sulfur-containing compounds), and count-based instead of TIC-weighted scoring. Each deviation made RHRMF more permissive than the literature method; the cumulative effect was a low-bar filter that admitted many marginal matches.
- A side-by-side diagnostic run on a 97k-compound unified library (1,721 dot-passing candidates from the user's environmental air-sample dataset) compared four scoring options:
  - Option 0 (legacy K2): 357 candidates > 75 — wide-tolerance baseline.
  - Option 1 (just tighten tolerance to 10 ppm): 1 candidate > 75 — too strict alone.
  - Option 2 (10 ppm + isotopologues, count-based): 98 candidates > 75.
  - Option 3 (10 ppm + isotopologues + TIC-weighted): 283 candidates > 75 — **adopted as production**.
- Comparing the per-match CSV outputs from the same input under Option 0 (basecase) and Option 3:
  - 142 matches are kept; 248 dropped; 178 new.
  - Median LR RHRMF rises from 83.8 → 94.7. The 95–100 high-confidence bin nearly doubles (73 → 134); the marginal 76–80 bin shrinks (83 → 32).
  - Dropped matches are dominated by compounds whose Option 3 score is 0–25 (likely Option 0 false positives admitted by its loose tolerance — small ketones like 2-heptanone variants, phenylethyl alcohol, etc.).
  - Added matches include major environmental PAH targets (Pyrene ×16, Fluoranthene ×4, Fluorene at rev_dot 953) that Option 0 missed.

### Known limitations
- A handful of borderline matches (phenanthrene, anthracene, o-xylene at feat_id 68/756 in the validation set) score 70–74 under the new RHRMF and fall just below the >75 threshold. These are PAH compounds for which higher-confidence supporting evidence (e.g., RI match within stricter bounds, molecular ion confirmation) may be appropriate when reviewing borderline annotations.
- A subset of Biphenyl features (24 library entries across feat_ids 538/542/543 in the validation set) scored 0 under the new RHRMF despite excellent dot-product matches. The synthetic test predicts these should score ~100 at full HR feature m/z precision; the empirical 0s remain unexplained and may indicate a precision-mismatch on those specific deconvolved features. Not addressed in this release.

### Backward compatibility
- The legacy `calculate_rhrmf()` function in `scripts/src/rhrmf.py` is preserved (unchanged signature and behavior) so the diagnostic `rhrmf_opt0` column in `K2_DIAG_MATCHING_CSV` traces continues to expose the v3.0.19 baseline for auditing.
- The four "Option" diagnostic configurations on `calculate_rhrmf_variant(...)` remain available for any future re-runs of the comparison (set `K2_DIAG_MATCHING_CSV` and read the resulting CSV's `rhrmf_opt0`/`opt1`/`opt2`/`opt3` columns).
- Re-run prior analyses if RHRMF score continuity matters for publication or reporting.

---

## [3.0.19] - 2026-05-11

### Changed
- **Library spectra are trimmed to the top-N peaks by intensity at load (default N=20).** A May 2026 diagnostic on a ~97k-entry unified library showed HR Orbitrap-derived entries scoring ~4x lower on reverse-dot than the LR version of the same compound — e.g. 9-fluorenone matched a feature at rev_dot=735 against its 27-peak NIST entry but rev_dot=167 against the 79-peak HR entry, *with similar forward-dot scores*. The cause is asymmetric peak counts: MZmine-deconvoluted feature spectra carry ~16 peaks median, but HR library entries carry ~125+ low-intensity peaks that inflate the reverse-dot denominator (`lib_norm_sq`) without contributing to the numerator. Trimming to top-N intensities at load equalises both sides and removes that bias. NIST MS Search applies a similar preprocessing step internally. Configurable via `--max-lib-peaks N` on `cli.py` and `gcms_pipeline.py`; pass `0` to disable.
- **`is_library_high_res()` now scans the full (post-trim) spectrum** instead of only the first 5 peaks. The May 2026 library audit found ~1,100 compounds where decimal m/z values exist later in the spectrum but the leading peaks happen to sit near-integer (molecular ion, common immonium ions, hydrocarbon fragments at <0.05 Da fractional). The old first-5-only rule classified those as LR, sending them through `calculate_rhrmf()` (which uses integer-binned matching anyway) instead of the HR auto-pass path. The 0.05 Da fractional threshold is unchanged; only the scan range expanded. With libraries now trimmed to ≤20 peaks at load, the full-spectrum scan is cheap.

### Why this combination
- The two changes are complementary: (a) trimming brings HR libraries' peak counts into parity with LR libraries and with experimental spectra, restoring fair dot-product comparison; (b) the expanded HR detector correctly routes the resulting trimmed spectra to the HR vs LR matching path. Doing only (a) would leave most HR entries classified LR (where the trim moves the integer-m/z M+ to the front and the few decimal peaks get clipped from the first-5 view); doing only (b) would route more entries to HR auto-pass but leave them failing the dot-product gate.

### Backward compatibility
- Default `max_lib_peaks=20` changes scoring numerically for any compound with more than 20 library peaks. LR libraries with sparse spectra (≤20 peaks, most of NIST/Wiley low-mass) are unaffected. Larger libraries see a deterministic rescore; the direction is usually higher dot-products (smaller `lib_norm_sq`) but not always. Re-run prior analyses if scoring continuity matters.
- Pass `--max-lib-peaks 0` to fully restore pre-v3.0.19 behavior (no trimming).
- GUI doesn't currently expose this flag, so all GUI-launched runs use the default 20. To override from the GUI flow, edit the saved `.K2config` preset or set the flag in `k2_screens.py`'s command builder.

---

## [3.0.18] - 2026-05-11

### Fixed
- **`-memory mass` was never a valid MZmine 4.x value.** v3.0.17 made `mass` the default `--mzmine-memory` based on a misread of MZmine's source — but in MZmine 4.x `KeepInMemory.parse("mass")` throws `IllegalStateException` (the valid values are `none`, `all`, `features`, `centroids`, `raw`, and `masses_features`). MZmine catches the exception, logs a non-fatal `WARNING io.github.mzmine.main.ArgsToConfigUtils checkAndOverrideArgsMemoryOption Issue while reading keep in memory option from CLI argument`, falls back internally to `NONE`, then exits 1 a few steps later with no `SEVERE`/`ERROR` line in the 200-line tail buffer. Users on v3.0.17 against any current MZmine 4 install saw this as a silent failure right after MZmine startup.
  - Default `--mzmine-memory` is now `none`, which matches MZmine 4's own fallback when no `-memory` flag is passed.
  - `--mzmine-memory` choices updated to the actual MZmine 4 enum: `none`, `all`, `features`, `centroids`, `raw`, `masses_features`.
  - The previous v3.0.17 CHANGELOG entry's claim that `mass` was "MZmine's own default" is incorrect; the actual default is `NONE`. The page-file commit-memory failure that prompted the v3.0.17 revert was an OS-side disk/page-file sizing issue (see below), not a function of the memory mode.
- **Disk-space exhaustion was masquerading as `InternalError: a fault occurred in an unsafe memory access operation`.** When MZmine's `-temp` scratch volume runs out of space mid-import, the rotating `mzmine.tmp` write truncates, the memory-mapped region becomes invalid, and the next `MemoryMapStorage.storeData` access faults via Unsafe.copyMemory. MZmine's own preceding `Cannot memory map array of length N, not enough space left` log message reads as a memory issue, but the "space" refers to disk. Users with low free space on `%TEMP%`'s drive hit this on any multi-GB dataset and were sent chasing antivirus / parallel-import / cloud-sync hypotheses that didn't apply.
  - `run_mzmine()` now pre-flights free disk space on the resolved scratch volume against the total `*.mzML` input size. Refuses with a clear error below 1.5x input size; warns below 3x.
  - When MZmine *does* fault with `InternalError: unsafe memory access`, the diagnosis handler now lists disk-space exhaustion as cause #1 (with the post-failure free-space figure re-read live), ahead of the existing cloud-sync / parallel-import / antivirus / memory-mode hypotheses.

---

## [3.0.17] - 2026-05-10

### Fixed
- **Default `--mzmine-memory` reverted to `mass`.** v3.0.16 defaulted to `all` while chasing the `MemoryMapStorage` race, but on the user's next run that change exposed a different failure: the JVM tried to commit a ~2.2 GB G1 heap region mid-import and Windows rejected it with `ERROR_COMMITMENT_LIMIT` ("paging file is too small", errno 1455). Reading the MZmine source more carefully: `-memory all` actually memory-maps *features* and keeps mass spectra in heap, which is exactly the wrong trade-off for typical mzML files where spectrum data is the bulk. `-memory mass` (MZmine's own default) memory-maps the bulk spectrum data and keeps features in heap — lowest heap pressure, most resilient on machines with small page files.
- **New diagnosis hint** for the Windows commit-memory failure pattern: when the log contains `paging file is too small`, `errno=1455`, `commit_memory`, or the JVM's "insufficient memory for the Java Runtime Environment" banner, the failure handler now prints a Windows-page-file-sizing fix and a `mzmine.vmoptions` heap-tuning fallback.

---

## [3.0.16] - 2026-05-10

### Fixed
- **Second pass at `java.lang.InternalError: a fault occurred in an unsafe memory access operation` during MZmine import.** v3.0.15 routed scratch off OneDrive but the same crash kept happening on the user's machine, this time inside `Unsafe.unpark` during a `ReentrantReadWriteLock.WriteLock.unlock()` — i.e., a JVM-level fault from a mapped page that disappeared while another thread held a lock on it. Root causes diagnosed: MZmine's parallel mzML import threads share a rotating `mzmine.tmp` scratch file, and when one thread rotates the file mid-write, the other thread's mmap is invalidated.
  - `run_mzmine()` now serialises the mzML import phase by capping the `-threads` value to `import_threads` (default 1). Overall `--threads` is still passed through to the post-import stages, but the import phase no longer fights itself for the rotating scratch file.
  - `-memory none` was being passed; the name is misleading and still uses memory-mapped scratch for the import path. Default is now `-memory all` (memory-map everything; deterministic behaviour). Override with `--mzmine-memory {none,mass,all}`.
  - A `--mzmine-import-threads N` flag exposes the import-thread cap for users who want to raise it on a dataset where the rotating scratch doesn't trip.
- **Better failure diagnosis.** When MZmine emits the `InternalError: a fault occurred in an unsafe memory access operation` message, the failure handler now prints the three most common Windows-specific causes (cloud-synced scratch / parallel import races / antivirus real-time scanning) along with the exact `--mzmine-*` flag to try for each, plus a reminder that the printed `MZmine command:` line can be copy-pasted into a terminal to reproduce outside the pipeline.

---

## [3.0.15] - 2026-05-10

### Fixed
- **MZmine import no longer crashes with `java.lang.InternalError: a fault occurred in an unsafe memory access operation` when the pipeline lives on OneDrive.** Root cause: `TEMP_DIR` was hardcoded to `PIPELINE_ROOT / "temp"`, and `gcms_pipeline.py` passed that to MZmine via `-temp`. On installs where the pipeline root is in OneDrive, MZmine's memory-mapped scratch files (`mzmine.tmp`) ended up under OneDrive's filter driver, which interferes with Java NIO page-level access and causes `Unsafe` to throw `InternalError` mid-import. `run_mzmine()` now creates MZmine's scratch as a fresh per-run subdirectory of the system temp folder (`%TEMP%\k2_mzmine_*`) and cleans it up on exit. The pipeline root location no longer affects MZmine's scratch location.
- New `--mzmine-temp PATH` override for users who want scratch on a specific local SSD. The pipeline warns loudly if the override path contains "onedrive" or "dropbox".
- When MZmine fails with the memory-mapped-file fault AND the scratch dir looks cloud-synced (only possible via explicit `--mzmine-temp`), the failure handler now emits a hint pointing at the root cause.
- Documented in `K2_USER_GUIDE.md` under "Troubleshooting".

---

## [3.0.14] - 2026-05-10

### Fixed
- **MZmine failures no longer surface as a blank log followed by "ERROR: MZmine processing failed".** The previous output reader filter dropped any line that didn't contain `SEVERE`, `ERROR`, `INFO`, or `WARNING` — so JVM startup faults, Java `Exception` / `Caused by:` chains, `usage:` banners (emitted when a CLI arg is wrong), and bare stack frames were silently discarded, leaving the user with no diagnostic. The reader now:
  - Also matches `Exception`, `Caused by`, and `Traceback` for live-print.
  - Keeps every line in a 200-line rolling buffer.
  - On non-zero exit, dumps that buffer verbatim under `--- Last N line(s) of MZmine output ---` so the actual failure is visible.
- The exact MZmine command is now printed before the run, so the user can copy it into a terminal and reproduce the failure manually if needed.

---

## [3.0.13] - 2026-05-10

### Fixed
- **MSConvert conversion no longer drags for hours when the output folder is on a network share.** Root cause: MSConvert writes the `.mzML` incrementally with frequent fsyncs, and over a network share (Z:, SMB, VPN) each fsync round-trips over the network, turning a sub-minute conversion into a multi-hour ordeal. `run_conversion()` now stages every conversion through a local scratch directory (`%TEMP%\k2_msconvert_*`) and copies the finished file to the requested output folder in one shot. The slow part is reduced to one bulk-copy at the end of each file instead of thousands of tiny synchronous writes.
- A new `--no-stage-locally` CLI flag opts out for users whose output is already on a fast local disk.
- Documented in `K2_USER_GUIDE.md` under "Troubleshooting".

---

## [3.0.12] - 2026-05-10

### Fixed
- **GUI console no longer goes silent for minutes during raw-data conversion.** Two compounding issues:
  1. The GUI launched `python gcms_pipeline.py` without `-u`, so the child Python's stdout was block-buffered. Validation messages and per-stage progress lines accumulated in a ~4 KB buffer and didn't reach the GUI console until the buffer filled or the process exited. The GUI now passes `-u` and sets `PYTHONUNBUFFERED=1` in the child environment.
  2. `run_conversion()` used `subprocess.run(..., capture_output=True)` for MSConvert, which means MSConvert's output was bottled up until each file finished converting. Converting a `.D` folder from a network share routinely takes several minutes, so the GUI looked hung that whole time. Conversion now streams MSConvert's output line-by-line, each prefixed with `[msconvert]`.

Net effect: every `print()` in the pipeline reaches the GUI console as soon as it is emitted, and MSConvert's per-file progress is visible while it runs.

---

## [3.0.11] - 2026-05-10

### Fixed
- **GUI-configured tool paths are now actually forwarded to the pipeline.** Previously, `gcms_pipeline.py` hardcoded the locations of `msconvert.exe`, `mzmine_console.exe`, the MZmine `.mzuser` profile, and the `.mzbatch` workflow as module-level constants relative to its own parent directory, and exposed no way to override them. So no matter what paths a user picked in the K2 Annotator settings screens, the pipeline always tried to run the binaries baked into `software/` next to `gcms_pipeline.py` — confusing on its own, and visibly broken on installs where that folder was a OneDrive placeholder while the user's "real" tools lived elsewhere.
- `gcms_pipeline.py` now accepts `--msconvert`, `--mzmine`, `--user-file`, and `--batch-file` flags and applies them before validation. The bundled-relative paths remain as defaults for direct CLI users who haven't moved anything.
- The K2 Annotator GUI command builder now forwards the saved tool paths (`msconvert_path`, `mzmine_path`, `mzmine_user_file`, `mzmine_batch_file`) on every run.

---

## [3.0.10] - 2026-05-09

### Fixed
- **Surface a clear error when MSConvert / MZmine binaries are cloud-only placeholders.** When the `software/` folder is kept in OneDrive and OneDrive isn't running, the binaries inside are placeholders that pass `os.path.exists()` but fail with a confusing `WinError 362: The cloud file provider is not running` when the pipeline tries to launch them. `validate_setup()` now detects this case via the `RECALL_ON_DATA_ACCESS` / `RECALL_ON_OPEN` / `OFFLINE` file attributes and refuses to start the pipeline, with a message telling the user how to fix it ("Always keep on this device" or start the cloud client). The MSConvert and MZmine subprocess calls also catch a leaked WinError 362 and report the same diagnosis instead of dumping the raw OSError trace.
- Documented this scenario explicitly in `K2_USER_GUIDE.md` under "Troubleshooting".

---

## [3.0.9] - 2026-05-09

### Changed
- **Vendor-neutral raw-data entry point.** The "Instrument Files (.D)" option on the welcome screen is now labelled **"Raw Instrument Data"**, and the input-folder hint reads "Select folder containing raw instrument data". The MSConvert configuration screen, GUI help text, and CLI argument help all use the generic phrasing.
- **Multi-vendor file discovery.** `find_d_files()` is now `find_raw_data()` (the old name remains as a back-compat alias) and scans for `.D` / `.d` (Agilent, Bruker), `.raw` (Thermo, Waters), `.wiff` (Sciex), and `.lcd` (Shimadzu). MSConvert auto-detects the vendor from the input path, so all of these are passed through unchanged.
- **Documentation explicitly notes the tested vendor.** README, `K2_USER_GUIDE.md`, and `INSTALLATION.txt` now state that K2 Annotator has been tested with Agilent `.D` folders and that other vendor formats are accepted on a best-effort basis via MSConvert's native readers.

### Backward Compatibility
- Existing `--from-raw` invocations still work — the flag now accepts any vendor format, not just `.D`.
- The Python function `find_d_files` is preserved as an alias for `find_raw_data`, so any external scripts importing it continue to work.

---

## [3.0.8] - 2026-05-09

### Changed
- **Renamed software to K2 Annotator** ahead of public release. Internal command-line and Python-package layouts are unchanged; only the user-facing brand name, the splash logo, and documentation references are updated.
- **New splash logo** (`K2Logo.png`) replaces the previous wordmark on the welcome screen and in the README. The window icon (`K2Icon.png`) is unchanged.
- GUI window title, About dialog, and User Guide popup now read "K2 Annotator". README, CHANGELOG, launcher batch file, and architecture / module diagrams updated to match.
- Older `K2Logo2.png` is retained as a fallback in `WelcomeScreen` so the splash screen still renders on machines that have an older asset bundle.

### Backward Compatibility
- File extensions (`.K2`, `.K2config`) are unchanged — existing project files and presets continue to load.
- The `~/.k2/k2_defaults.json` user-config location is unchanged — existing user settings carry over.
- Git repository URL is unchanged.

---

## [3.0.7] - 2026-05-05

### Fixed
- **Internal Standard normalization direction was inverted.** The per-sample factor was computed as `IS(sample) / max(IS)` and applied multiplicatively, which scaled samples with lower IS response *down* — the opposite of the intended correction. The factor is now `max(IS) / IS(sample)`, so samples with reduced injection efficiency (or matrix suppression) are scaled *up* to the reference injection level. The sample carrying the maximum IS still keeps factor = 1; samples with no detectable IS are still flagged and left unnormalized.

### Action Required
- Any prior reanalysis that used IS normalization was directionally incorrect. Re-run those analyses with v3.0.7+ before publishing or interpreting them.

---

## [3.0.6] - 2026-04-29

### Added
- **Feature Detection Summary** (CSV + PDF): every observed feature with detection frequency (% of true samples with abundance > 0), per-sample abundances, and BFF pass/fail. Blanks are excluded from the frequency statistic but their abundances are still echoed for QA in the CSV.
- **Match Summary** (CSV + PDF): every library match keyed back to its feature, with RevDot/FwdDot/RHRMF and RI deltas. One row per (feature, candidate) pair.
- **Landscape PDF front pages**: both summary tables are rendered as the first pages of the report, in landscape orientation, before the per-match detail pages.
- **`blank_columns` parameter** added to `ReportGenerator` so the summary tables can compute detection frequency over true samples only (`engine.parser.blank_columns` is now passed in from the CLI).

### Fixed
- **GUI Results screen showing all "Unknown"**: The Results-screen CSV picker globbed `*.csv` and took `[0]`, which after v3.0.6 could pick `*_feature_summary.csv` (1866 rows, no `Compound_Name` column) instead of `*_matches_*.csv`. Now the picker explicitly prefers the matches file and ignores summary files.
- **PDF feature summary unreadable on real-sized studies**: With ~1800 features × ~150 samples, the per-sample abundance grid compressed into hairline columns or fanned out into hundreds of horizontally-chunked pages. The PDF now shows the stat overview only (Feat #, RT, RI, Det %, Det N, Tot N, Mean Abd, Max Abd, BFF) — the full per-sample grid lives in the companion CSV, where spreadsheet column widening makes it usable.
- **`generate_pdf` return value**: the method now returns the saved file path (it previously returned `None`, causing the CLI to print `[OK] PDF saved: None`).
- **PDF orientation restoration**: `render_summary_pdf_pages` now restores portrait orientation via a `finally` block, so a partial failure mid-render can no longer leave the canvas stuck in landscape and corrupt the per-match pages.
- **Summary table header overlap**: PDF column headers were drawn over each other when verbose names exceeded the column width. Replaced with abbreviated display headers and proportional column widths sized for content. CSV headers remain fully descriptive.

### Files
- New: `scripts/src/summary_tables.py` (table-building, CSV writing, PDF rendering)

---

## [3.0.5] - 2026-04-29

### Added
- **`--bff-c-factor` flag** (CLI, pipeline wrapper, GUI): the multiplier in front of the BFF threshold rule is now user-configurable. Applies to both `standard` and `adjusted` modes, so the two stay on the same scale. Validated as a positive number at every boundary; default remains `5.0` to preserve existing outputs.
- **GUI control**: numeric entry for the c-factor on the Analysis Parameters screen, alongside the existing BFF mode radio buttons. Invalid (non-numeric, ≤ 0) values are rejected with a dialog before the user can advance.
- **`BFF_CFactor` audit column** in the per-match CSV: records the multiplier used for each row alongside the existing BFF_Mode/BFF_Rule audit fields.

### Why This Change
- The legacy 5× multiplier on `(mean + 3·SD)` is conservative for some sample sets. Allowing the user to choose 1×, 2×, etc. relaxes the filter when blanks are clean enough that 5× masks real low-magnitude signals — without removing the legacy default.

### Backward Compatibility
- Default `bff_c_factor` is `5.0`; existing analyses produce byte-identical thresholds. Audit column is appended without disturbing existing column order.

---

## [3.0.4] - 2026-04-28

### Added
- **Adjusted BFF Mode**: New `bff_mode={standard,adjusted}` option for Blank Feature Filtering. Standard mode preserves existing `c_factor * (mean + 3*SD)` behavior unchanged. Adjusted mode runs a per-feature Shapiro-Wilk normality test (alpha=0.05) on the field blanks and selects between `mean + 3*SD` (normal blanks) and `median + 3 * 1.4826 * MAD` (non-normal). The 1.4826 scaling makes MAD a consistent estimator of sigma under normality, so adjusted mode reduces to the standard rule when blanks truly are normal — but is robust to sparse high-magnitude blank detections that would otherwise inflate the SD enough to mask real sample signal.
- **BFF Fallback Rules** (adjusted mode): When MAD = 0 but at least one blank is nonzero, threshold falls back to `max(blanks)`. When all blanks are zero, threshold is 0. Features whose blanks are all identical (zero variance, Shapiro can't run) are routed through these fallbacks as non-normal.
- **CLI / Pipeline Flag**: `--bff-mode {standard,adjusted}` added to both `cli.py` and `gcms_pipeline.py` (default: `standard`).
- **GUI Control**: Radio-button selector for BFF mode on the Analysis Parameters screen.
- **CSV Audit Columns**: Matches CSV now records `BFF_Mode`, `BFF_Rule`, `BFF_Shapiro_P`, and `BFF_Normal` per feature for downstream auditing. Existing `BFF_Threshold` column is unchanged.
- **`reset_to_defaults()` helper** in `K2Config` for scrubbing stale paths and secrets from a previous install.

### Changed
- **Saved-Config Path Validation**: On every load of `~/.k2/k2_defaults.json` (and on `load_preset`), path-type keys (`msconvert_path`, `mzmine_path`, `mzmine_user_file`, `mzmine_batch_file`, `library_path`, `ri_cal_path`) are checked against the filesystem and cleared if the target no longer exists. Prevents stale absolute paths from a previous install location from re-populating the GUI.
- **Preset Export Hygiene**: `export_preset()` now strips sensitive and per-machine keys (`epa_api_key`, `last_input_folder`, `last_output_folder`, `window_geometry`) before writing, so a `.K2config` preset can be shared with collaborators without leaking API keys or environment-specific state.

### Why This Change
- The old universal `mean + 3*SD` rule assumes normally distributed blanks. In practice, sparse high-magnitude detections in otherwise-clean field blanks inflate the SD enough that the threshold exceeds legitimate sample signal, filtering out real detections. Adjusted mode preserves the strict rule where blanks really are normal but switches to a MAD-based robust estimator otherwise.
- Saved configs frequently outlive their install location (repo moved, OneDrive synced to a new machine, software dir reinstalled). Path validation at load time keeps the GUI in a clean, browseable state instead of silently retaining dead absolute paths.

### Backward Compatibility
- Default `bff_mode` is `standard`; existing analyses produce byte-identical thresholds. Audit columns are appended to the CSV without disturbing existing column order.

---

## [3.0.3] - 2026-01-31

### Fixed
- **Default Configuration Paths**: Removed developer-specific paths from distribution. New users now see blank fields for library and RI calibration paths on first launch
- **Distribution Structure**: Documentation files (README, USER_GUIDE, QUICK_START) and templates folder now appear at top level alongside K2.exe instead of buried in _internal subfolder
- **User-Specific Files**: Removed user-specific .K2 project files and .K2config presets from templates folder

### Changed
- **GitHub Distribution**: Repository now configured for downloadable ZIP releases instead of requiring git clone
- **.gitignore**: Updated to exclude user config directory (.k2/) and .K2config preset files with personal paths
- **Build Script**: Enhanced create_distribution.bat to automatically restructure distribution after PyInstaller build

### Improved
- **First-Run Experience**: Clean slate for new users with no pre-populated file paths
- **Documentation Accessibility**: Key documentation files immediately visible when opening distribution folder
- **Release Workflow**: Simplified process for downloading and using K2 from GitHub releases

---

## [3.0.2] - 2026-01-25

### Changed
- **Structure Lookup Safety Improvement**: Removed compound name fallback in `get_structure_image()`
  - Structures are now fetched exclusively using InChIKey identifiers
  - If InChIKey is missing or invalid, "Structure Not Available" is displayed instead of potentially incorrect structure
  - Prevents ambiguous name searches from returning wrong chemical structures

### Why This Change
- Name-based PubChem searches can match similar compounds or derivatives
- Some library entries may have missing InChIKey values - better to show no structure than wrong structure
- Ensures displayed structures match the specific compound identified by the library entry

---

## [3.0.1] - 2026-01-25

### Fixed
- **Multiple Library Entries for Same Compound**: When the same compound (e.g., phenanthrene) appears multiple times in the library from different sources, each entry now generates its own unique spectral mirror plot in both PDF and GUI displays

### Added
- `library_index` attribute to `LibraryCompound` - unique identifier assigned to each library entry during loading
- `Library_Entry_ID` column in CSV output for tracking specific library entries
- Plot filenames now use `plot_{feat_id}_lib{library_index}.png` format for guaranteed uniqueness

### Changed
- **library_parser.py**: `LibraryCompound` class now includes `library_index` parameter; indices assigned after RI-sorting
- **reporter.py**: CSV headers include `Library_Entry_ID`; plot filenames use library index
- **k2_screens.py**: `update_visuals()` prioritizes library index format for finding plots, with fallback to legacy formats for backward compatibility

### Backward Compatibility
- Existing CSV files without `Library_Entry_ID` column continue to work (GUI falls back to older filename patterns)
- Library files require no changes (index is assigned dynamically during loading)

---

## [3.0.0] - 2026-01-28

### Major Feature: Surrogate Standard Recovery Analysis

This release introduces comprehensive surrogate standard recovery calculation, enabling users to track and quantify labeled (13C/deuterated) surrogate standards spiked into samples.

### New Files
- `scripts/src/surrogate_analyzer.py` - Core surrogate matching and recovery calculation
- `scripts/src/surrogate_reporter.py` - CSV, PDF, and GUI output generation

### New GUI Screens
- **SurrogateConfigScreen**: Configure surrogate standard recovery analysis
  - Enable/disable surrogate recovery calculation
  - Upload custom surrogate standard library (CSV/MSP)
  - Select/deselect specific compounds from the library

### Extended Sample Classification Screen
- New sample type: "Reference" (auto-detected by "ref" in filename)
- "Spiked" checkbox column for marking samples with surrogate spikes
- "Spike Ratio" column for relative spike amounts
- "Group" column for organizing samples by experimental groups
- Reference samples are automatically excluded from suspect screening

### New Results Tab
- "Surrogate Recovery" tab in ResultsScreen
- Recovery summary table with average, standard deviation, and per-sample values
- Match details for each surrogate compound
- Export functionality for surrogate data

### CLI Extensions
- `--surrogate-library` / `-sl`: Path to surrogate standard library
- `--surrogate-config`: JSON file with surrogate configuration
- `--reference-samples`: Comma-separated list of reference sample names

### Matching Engine Updates
- `reference_samples` parameter to exclude samples from BFF calculation
- Reference samples are excluded from suspect screening workflow
- Surrogate matching uses same criteria (RI, spectral scores, RHRMF) but skips BFF filter

### Recovery Calculation
- Formula: `% Recovery = (sample_abundance / sample_ratio) / avg(reference_abundances / reference_ratios) * 100`
- Group-based calculations allow different reference sets per experimental group
- IS normalization applied before recovery calculation if enabled

### Output Formats
- Separate CSV file: `SurrogateRecoveries_{ProjectName}_{date}.csv`
  - Normalized abundances table
  - % Recovery table with statistics
  - Match information table
- New page in PDF report
- Dedicated GUI tab with color-coded recovery values

---

## [2.9.1] - 2026-01-26

### Reverted
- Removed enhanced ToxValDB columns from CSV (data not available for most compounds)
- Removed severity index, NOAEL, genetox display from GUI

### Retained
- `ctx-python` package remains installed for future use
- `scripts/src/ctx_client.py` kept for potential future integration
- `Hazard_Summary` and `EPA_Link` columns continue to work as in v2.8.0

### Note
The ToxValDB data via ctx-python was not sufficiently populated for the compounds of interest.
CSV now shows only the GHS hazard category and EPA CompTox link.

---

## [2.9.0] - 2026-01-26

### Added
- **Enhanced Hazard Data Integration**: New integration with EPA CompTox via official `ctx-python` package
  - Quantitative toxicity values from ToxValDB (NOAEL, LOAEL, POD, RfD)
  - Ecological toxicity data (LC50, LD50)
  - Genetic toxicity summary (Ames test, positive/negative report counts)
  - Computed Severity Index (1-5 scale based on toxicity thresholds)

### New CSV Columns (removed in 2.9.1)
- `Tox_NOAEL` - Most protective No Observable Adverse Effect Level (mg/kg-day)
- `Tox_LOAEL` - Lowest Observable Adverse Effect Level (mg/kg-day)
- `Tox_POD` - Point of Departure (mg/kg-day)
- `Tox_RfD` - EPA Reference Dose (mg/kg-day)
- `Tox_Source` - Source of toxicity data (e.g., EPA IRIS, ATSDR)
- `Eco_LC50` - Fish LC50 (mg/L)
- `Eco_LD50` - Oral LD50 (mg/kg)
- `Genetox_Positive` - Count of positive genotoxicity reports
- `Genetox_Negative` - Count of negative genotoxicity reports
- `Genetox_Ames` - Ames test result (positive/negative)
- `Severity_Index` - Computed severity score (1-5)

### New Files
- `scripts/src/ctx_client.py` - EPA CompTox API client using ctx-python package

### Updated
- `scripts/src/structure_helper.py` - Added `get_enhanced_hazard()` method
- `scripts/src/reporter.py` - Added 11 new CSV columns for enhanced hazard data
- `scripts/k2_screens.py` - GUI now displays severity index and key toxicity values
- `requirements.txt` - Added ctx-python dependency

### Dependencies
- Added: `ctx-python>=0.1.0` for EPA CompTox API access

---

## [2.8.0] - 2026-01

### Added
- Internal Standard (IS) normalization integration in Sample Classification screen
- IS area and normalization factor columns in CSV reports
- IS area and normalization factor display in GUI sample table

### Fixed
- Spectral plot display in GUI (now generated during CSV export)
- IS Area showing as "0" in GUI
- Hazard summary and EPA link data consistency between CSV and PDF
- Multiple matches for same feature ID now show correct individual structures/plots

### Removed
- Log2FoldChange and P-value from GUI (deprecated statistics package)
- IS normalization info from PDF reports (CSV only)

---

## [2.7.0] - 2026

### Added
- Structure image helper module separated from statistics visualization
- High-resolution structure images from PubChem
- Hazard matrix visualization in PDF reports with color-coded badges

### Changed
- Replaced Visualizer with StructureHelper for cleaner architecture
- Statistics module deprecated (external analysis recommended)

---

## [2.6.0] - 2026

### Added
- MZmine integration for feature detection
- Universal parser supporting both MS-DIAL and MZmine formats
- Improved BFF (Blank Feature Filtering) calculations

---

## Previous Versions

See archived code in `scripts/archive/` for historical changes.
