# Scoring methods as implemented in K2 Annotator (v3.1.x)

This document describes what K2 Annotator computes when it assigns a Level 2 annotation, in enough detail to support a methods section or supporting information. The criteria are those of Koelmel et al. (2022, *Exposome* 2(1), osac007) as adapted in Brunet et al. (Table 1 and Section S3 of the supporting information), and the exact-mass filter follows Kwiecien et al. (2015, *Anal. Chem.* 87, 8328). Where the papers leave a choice open, the choice made here is stated. No threshold or window differs from the published criteria. Every quantity described below is exercised by the test suite in `tests/`.

## 1. Inputs

The pipeline accepts an MZmine (or MS-DIAL) aligned feature table with one abundance column per sample, the corresponding deconvoluted spectra in MSP format, a spectral library in CSV or MSP format, and a table of retention times for an n-alkane series run under the same chromatographic method. Feature spectra are used as exported and are not trimmed. A library entry is usable only if it has a retention index and a peak list, and a molecular formula is required for the RHRMF path. Each library spectrum is trimmed at load to its 20 most intense peaks (`--max-lib-peaks`, 0 disables trimming). It should be noted that this trim affects both the dot products and the set of peaks the RHRMF evaluates for any entry with more than 20 peaks, and the value used is therefore recorded in `run_manifest.json`.

## 2. Retention index

Retention indices are calculated as RI = 100 × n, where n is the carbon number obtained by cubic-spline interpolation (SciPy `CubicSpline`, not-a-knot end conditions) of carbon number against retention time through the alkane series. Outside the retention-time range of the alkanes the RI is extrapolated, and the feature is flagged `RI_Extrapolated = Yes` in every output table. The extrapolation mode is selected with `--ri-extrapolation`: `spline` (the default) extends the terminal cubic polynomial of the spline, which reproduces versions 3.0.21 and earlier, while `linear` applies the van den Dool and Kratz convention of linear extrapolation from the two terminal alkanes on that side. Neither mode is reliable far from the alkane range, and the appropriate remedy is an alkane series that spans every feature of interest. Given that the retention index is a mandatory Level 2 criterion, a run on MZmine data without a calibration file is refused.

## 3. Blank feature filter

For each feature the threshold is

    threshold = c × (mean of blank abundances + 3 × SD of blank abundances)

with c = 5 by default (`--bff-c-factor`) and SD the sample standard deviation (n − 1). A feature is retained when its maximum abundance in any sample column strictly exceeds the threshold. Reference (spiked) samples are excluded from the maximum. Blank and sample columns are taken from the explicit sample classification (the GUI table or `--grouping`) or, for columns not listed there, from the blank-identifier substring (`--blank-id`). A run in which no blank column is identified is refused unless `--allow-no-blanks` is given. The optional `--bff-mode adjusted` rule, which substitutes a median and MAD estimate when the blanks fail a Shapiro-Wilk test, is not part of the Koelmel framework. It is off by default and is reported in the `BFF_Mode` column when used.

## 4. Retention-index window

A library entry is a candidate for a feature when both

    |RI_feature − RI_library| ≤ 50   and   |RI_feature − RI_library| / RI_feature ≤ 1.5%

where the percentage is relative to the feature RI. The same window is applied to every entry, whether its library RI is experimental or predicted.

## 5. Spectral similarity

Both spectra are binned to unit mass (half-integer values round up, so 76.5 becomes 77) and each bin is weighted as w = √I × m/z. The scores are squared cosines scaled to 0 to 1000:

    forward dot = 1000 × (Σ w_f w_l)² / (Σ w_f² × Σ w_l²)     summed over all bins
    reverse dot = 1000 × (Σ w_f w_l)² / (Σ' w_f² × Σ w_l²)    Σ' over bins present in the library entry

The reverse dot product therefore ignores feature peaks that are absent from the library entry (co-eluting interferences), while the forward dot product penalizes them. A candidate passes when the reverse dot product exceeds 600 and the forward dot product exceeds 500. The weighting exponents (m/z¹ and I^0.5) are those K2 has always used. They are not the m/z³ × I^0.6 optimum reported by Stein and Scott (1994), and scores computed with different exponents are not comparable.

## 6. Exact-mass evidence

Exactly one of the two following paths applies, depending on the library entry.

### 6.1 Exact-mass library entries

An entry is treated as exact-mass when its metadata says so (a `resolution`, `hires`, or `high_res` field set to high, hr, exact, true, or yes) or, in the absence of such a field, when at least two of its peaks carry three or more decimal digits in m/z and at least one of those peaks is among the three most intense. Half-integer artifacts in NIST entries (76.5) and entries stored to one decimal place (93.1) are consequently low-resolution.

For exact-mass entries the dot products are recomputed with peak-pair matching at ±10 ppm rather than unit-mass binning (greedy nearest-neighbor pairing in m/z order, with the same weighting and formulae as in Section 5), and the candidate must again exceed 600 (reverse) and 500 (forward) at this resolution. These scores are reported as `HR_RevDot` and `HR_FwdDot`, and `RHRMF` is reported as `N/A`.

### 6.2 Low-resolution library entries: RHRMF

The reverse high-resolution mass filter follows Kwiecien et al. (2015), applied in the reverse direction as described by Koelmel et al. (2022):

1. Only feature peaks whose nominal mass occurs in the (trimmed) library spectrum are considered.
2. For each such peak, all sub-formulas of the candidate's molecular formula are enumerated (exhaustively and without a valence constraint) and searched for a singly charged cation mass within ±10 ppm of the measured m/z. Theoretical masses are the monoisotopic atom masses from molmass minus one electron mass (0.000549 Da), as specified by Kwiecien et al. Isotopically labeled formulas (D, 13C, and so on) are supported.
3. If no monoisotopic sub-formula fits, heavy-isotope variants are tried by subtracting k × Δ(13C, 37Cl, 81Br, 34S, or 30Si), with k up to the parent's count of that element, and repeating the search. This is an approximation in that the sub-formula found for the residual mass is not required to contain the heavy atom.
4. The score is 100 × Σ(m/z × I) over the explained peaks divided by Σ(m/z × I) over the considered peaks, that is, the total-ion-current weighting of Kwiecien et al.

A candidate passes when the RHRMF exceeds 75. Entries without a formula cannot pass this path.

## 7. Reporting

Candidates that pass every criterion are listed per feature in descending order of reverse dot product, and the first entry is the "best match" in the sense used in the manuscript. Every run writes `run_manifest.json`, which records the software and package versions, the SHA-256 hash of every input file, all resolved options including `max_lib_peaks` and the extrapolation mode, the sample classification, library statistics, the calibration range, and the feature and match counts.

## 8. Changes from versions 3.0.21 and earlier that affect scores

| Change | Effect |
|---|---|
| Electron mass subtracted in the RHRMF (Section 6.2) | RHRMF values rise for spectra rich in fragments below roughly m/z 150, and the ±10 ppm window is symmetric. Candidates rejected by v3.0.x because of a small negative mass error now pass. |
| Labeled atoms supported in the RHRMF | Deuterated and 13C-labeled compounds can pass the low-resolution path. |
| Exact isotope masses from molmass | A shift of less than 1 ppm that removes a bias dependent on the hydrogen count. |
| Exact-mass detector based on stored precision (Section 6.1) | Exact-mass entries with small mass defects (benzene, chlorinated aromatics) take the exact-mass path instead of the RHRMF. |
| Half-integer binning rounds up | Only half-integer m/z values are affected. |
| Surrogate recoveries normalized once | With IS normalization enabled, recoveries are divided by the IS factor once rather than twice. |
