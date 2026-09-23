# K2 Annotator — scoring methods as implemented (v3.1.0)

This document states exactly what K2 Annotator computes when it assigns a
Level-2 annotation, in enough detail to be pasted into a methods section or
supporting information. The criteria are those of Koelmel et al. (2022,
*Exposome* 2(1), osac007) as adapted in Brunet et al. (NYCSS manuscript,
Table 1 and SI S3); the exact-mass filter follows Kwiecien et al. (2015,
*Anal. Chem.* 87, 8328). Where the implementation makes a choice the papers
leave open, the choice is stated here. Nothing below changes a threshold.

Every number in this document is produced by code that is exercised by the
test suite in `tests/` (`python -m pytest`).

## 1. Inputs

* **Features**: MZmine (or MS-DIAL) aligned feature table with one column
  per sample, plus the deconvoluted spectra (MSP). Feature spectra are used
  as exported; they are **not** trimmed.
* **Library**: CSV (`name, formula, ri, peaks_json, ...`) or MSP. An entry is
  usable only if it has a retention index and a peak list; a formula is
  required for the RHRMF path. Every library spectrum is trimmed to its
  **N = 20 most intense peaks at load** (`--max-lib-peaks`, 0 disables). The
  value used is written to `run_manifest.json`.
* **Alkane calibration**: a table of (carbon number, retention time) for the
  n-alkane series run under the same chromatographic method.

## 2. Retention index

RI = 100 × n, where n is the carbon number obtained from a cubic-spline
interpolation (SciPy `CubicSpline`, not-a-knot) of carbon number against
retention time through the alkane series.

Outside the calibrated retention-time range the RI is **extrapolated** and the
feature is flagged `RI_Extrapolated = Yes` in every output table. Two
extrapolation modes exist (`--ri-extrapolation`):

* `spline` (default): the terminal cubic polynomial of the spline is
  extended (identical to versions ≤ 3.0.21);
* `linear`: van den Dool & Kratz linear extrapolation from the two terminal
  alkanes on that side.

Neither mode is reliable far from the alkane range; the recommended practice
is to run an alkane series that spans every feature of interest. A run on
MZmine data without a calibration file is refused, because RI is a mandatory
Level-2 criterion.

## 3. Blank feature filter (BFF)

For each feature, with c = 5 by default (`--bff-c-factor`):

    threshold = c × ( mean(blank abundances) + 3 × SD(blank abundances) )

SD is the sample standard deviation (n − 1). A feature is retained when its
**maximum abundance in any sample column strictly exceeds** the threshold.
Reference (spiked) samples are excluded from the maximum. Blank and sample
columns come from the explicit sample classification (GUI table /
`--grouping`) or, for unlisted columns, from the blank identifier substring
(`--blank-id`). A run with zero blank columns is refused unless
`--allow-no-blanks` is given.

`--bff-mode adjusted` (Shapiro-Wilk-gated MAD rule) is an **optional mode that
is not part of the Koelmel framework**; it is off by default and reported in
the `BFF_Mode` column when used.

## 4. Retention-index window

A library entry is a candidate for a feature when both

    |RI_feature − RI_library| ≤ 50   and   |RI_feature − RI_library| / RI_feature ≤ 1.5 %

(the percentage is relative to the feature RI). The same window is used for
every entry regardless of whether the library RI is experimental or
predicted.

## 5. Spectral similarity

Both spectra are binned to unit mass (round-half-up: 76.5 → 77) and weighted
with

    w(m/z, I) = sqrt(I) × m/z

Scores are squared cosines scaled to 0–1000:

    forward dot  = 1000 × (Σ w_f w_l)² / (Σ w_f² × Σ w_l²)          over all bins
    reverse dot  = 1000 × (Σ w_f w_l)² / (Σ' w_f² × Σ w_l²)         Σ' over bins present in the library

i.e. the reverse dot ignores feature peaks that are absent from the library
entry (co-eluting interferences), while the forward dot penalises them.

A candidate passes when **reverse dot > 600 and forward dot > 500**.

Note: the weighting exponents (m/z¹, I^0.5) are the ones K2 has always used.
They are *not* the m/z³ · I^0.6 optimum reported by Stein & Scott (1994);
scores computed with different exponents are not comparable.

## 6. Exact-mass evidence

Exactly one of the two paths applies, depending on the library entry.

### 6.1 Exact-mass ("high-resolution") library entries

An entry is treated as exact-mass when (a) its metadata says so
(`resolution`/`hires`/`high_res` = high|hr|exact|true), or (b) at least two
of its peaks carry three or more decimal digits in m/z and at least one of
those is among the three most intense peaks. NIST half-integer artefacts
(76.5) and one-decimal entries (93.1) are therefore low-resolution.

For such entries the dot products are recomputed with **peak-pair matching at
±10 ppm** instead of unit-mass binning (greedy nearest-neighbour pairing in
m/z order, same weighting and formulae as §5), and the candidate must clear
**reverse > 600 and forward > 500 again** at this resolution. These scores are
reported as `HR_RevDot` / `HR_FwdDot`; `RHRMF` is reported as `N/A`.

### 6.2 Low-resolution library entries: RHRMF

Reverse high-resolution mass filter after Kwiecien et al. (2015), reverse
direction as in Koelmel et al. (2022):

1. Only feature peaks whose nominal mass occurs in the (trimmed) library
   spectrum are considered.
2. For each such peak, all sub-formulas of the candidate's molecular formula
   are searched (exhaustively, no valence constraint) for a **singly charged
   cation mass** within **±10 ppm** of the measured m/z. Theoretical masses
   are monoisotopic atom masses (molmass) **minus one electron mass
   (0.000549 Da)**, as in Kwiecien et al. Isotopically labelled formulas
   (D, ¹³C, …) are supported.
3. If no monoisotopic sub-formula fits, heavy-isotope variants are tried by
   subtracting k × Δ(¹³C, ³⁷Cl, ⁸¹Br, ³⁴S, ³⁰Si) for k up to the parent's atom
   count of that element, and re-searching. (Approximation: the sub-formula
   found for the residual mass is not required to contain the heavy atom.)
4. Score = 100 × Σ(m/z × I) over explained peaks / Σ(m/z × I) over considered
   peaks (total-ion-current weighted, Kwiecien's formula).

A candidate passes when **RHRMF > 75**. Entries without a formula cannot pass
this path.

## 7. Reporting

Candidates that pass every criterion are listed per feature in descending
order of reverse dot product; the first entry is the "best match" in the
sense of the NYCSS manuscript. Every run writes `run_manifest.json`
(software and package versions, SHA-256 of every input file, resolved
options including `max_lib_peaks` and the extrapolation mode, sample
classification, library statistics, calibration range, feature counts).

## 8. Changes from versions ≤ 3.0.21 that affect scores

| Change | Effect |
|---|---|
| Electron mass subtracted in RHRMF (§6.2) | RHRMF rises for spectra rich in fragments below ~m/z 150; the ±10 ppm window is now symmetric. Candidates rejected by v3.0.x because of a small negative mass error now pass. |
| Labelled atoms supported in RHRMF | Deuterated / ¹³C-labelled compounds can pass the low-resolution path. |
| Exact isotope masses (molmass) | < 1 ppm shift; removes a hydrogen-count-dependent bias. |
| Exact-mass detector by stored precision (§6.1) | Small-mass-defect exact-mass entries (benzene, chlorinated aromatics) now take the exact-mass path instead of RHRMF. |
| Round-half-up binning | Only affects half-integer m/z values. |
| Surrogate recovery no longer double-normalised | Recoveries with IS normalisation on are divided by the IS factor once, not twice. |
