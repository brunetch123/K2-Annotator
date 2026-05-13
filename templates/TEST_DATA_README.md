# Test Data for Library Format Validation

## Files

1. **library_template.csv** - CSV version of the MSP library template
2. **library_template.msp** - Original MSP library template
3. **test_quant.csv** - MZmine quantification file with 5 test features
4. **test_spectra.msp** - MZmine spectral file with spectra for the 5 features

## Test Features

### Feature #1: n-Decane (RI 1000)
- **RT**: 15.791 min (matches C10 calibration point)
- **m/z**: 142.0
- **Expected**: Should match library compound "n-Decane"
- **BFF**: Blanks [150, 250], Samples [5200, 6800, 7500] → Should PASS
- **RI**: Should convert to ~1000 via calibration

### Feature #2: 2,4-Dimethylpentane (RI 672)
- **RT**: 9.2 min (extrapolated from calibration)
- **m/z**: 100.0
- **Expected**: Should match library compound "2,4-Dimethylpentane"
- **BFF**: Blanks [100, 180], Samples [4800, 6200, 5800] → Should PASS
- **RI**: Should convert to ~672 via calibration (extrapolated)

### Feature #3: Benzene (RI 652)
- **RT**: 8.5 min (extrapolated from calibration)
- **m/z**: 78.0
- **Expected**: Should match library compound "Benzene"
- **BFF**: Blanks [120, 200], Samples [5500, 7200, 6800] → Should PASS
- **RI**: Should convert to ~652 via calibration (extrapolated)

### Feature #4: Unknown Compound (RI 800)
- **RT**: 11.5 min (extrapolated from calibration)
- **m/z**: 120.0
- **Expected**: Should NOT match any library compound
- **BFF**: Blanks [180, 220], Samples [5800, 6400, 6000] → Should PASS
- **RI**: Should convert to ~800 via calibration (extrapolated)

### Feature #5: Contaminant (RI 750)
- **RT**: 10.5 min (extrapolated from calibration)
- **m/z**: 110.0
- **Expected**: Should be filtered by BFF (high in blanks, low in samples)
- **BFF**: Blanks [8200, 7800], Samples [900, 1100, 950] → Should FAIL
- **RI**: Should convert to ~750 via calibration (extrapolated)

## BFF Calculations

BFF threshold = 5.0 × (mean_blank + 3 × std_blank)
- Feature 1: threshold = 5 × (200 + 3×70.71) = 2060.65, max_sample=7500 → PASS ✓
- Feature 2: threshold = 5 × (140 + 3×56.57) = 1548.55, max_sample=6200 → PASS ✓
- Feature 3: threshold = 5 × (160 + 3×56.57) = 1648.55, max_sample=7200 → PASS ✓
- Feature 4: threshold = 5 × (200 + 3×28.28) = 1424.24, max_sample=6400 → PASS ✓
- Feature 5: threshold = 5 × (8000 + 3×282.84) = 44242.6, max_sample=1100 → FAIL ✓

## Matching Criteria

For a match to be found (current K2 production behavior):

1. Feature must pass BFF filter
2. RI must be within ±50 units of library compound **AND** RI % error < 1.5%
3. Forward dot product > 500 **AND** reverse dot product > 600 (NIST-style
   weighted cosine, computed on the library spectrum trimmed to its top-20
   most intense peaks at load)
4. **For library entries classified as truly high-resolution** (≥2 sub-Da
   m/z peaks with ≥1 in the top 3 by intensity, excluding z=2 half-integer
   artifacts and 1-decimal-rounded m/z values): re-score with an HR-aware
   dot product using 10 ppm peak-pair matching, and require its
   forward/reverse scores to also clear >500 / >600. RHRMF is skipped on
   this path (the HR-aware dot product IS the exact-mass discrimination).
5. **For all other library entries**: RHRMF score > 75. K2's RHRMF
   follows Kwiecien 2015: 10 ppm tolerance, on-the-fly isotopologue
   substitution for 13C / 37Cl / 81Br / 34S / 30Si, TIC-weighted scoring
   (∑(mz × intensity)_annotated / ∑(mz × intensity)_observed).

## High-Resolution vs Low-Resolution

The K2 HR detector classifies a library entry as truly high-resolution
only when its high-intensity peaks carry actual exact-mass information.
Specifically, an entry is HR if it has at least 2 "real-HR" peaks AND
at least one such peak is in the top 3 by intensity. A "real-HR" peak
has fractional m/z > 0.05, is NOT half-integer (excludes z=2
doubly-charged artifacts like 76.5, 160.5), and is NOT
1-decimal-rounded (excludes entries stored as 93.1, 91.1, etc.).

**Note about the test data:** The library spectra in this template
were designed under the pre-v3.0.21 HR auto-pass model. n-Decane and
2,4-Dimethylpentane peaks here are stored at integer m/z, so they
will be classified as LR by the current detector and routed through
the RHRMF path. That's the expected behavior — the validation harness
still confirms the matching pipeline runs end-to-end, but the
"high-resolution" categorization in earlier versions of this document
no longer applies. For a true HR test you would need to supply a
library entry with multiple sub-Da-precision peaks (e.g. exact-mass
fragments from an Orbitrap-derived library).

## Expected Results

After running the pipeline:
- **Features #1-3**: Should match library compounds (n-Decane, 2,4-Dimethylpentane, Benzene)
- **Feature #4**: Should have no matches (unknown compound)
- **Feature #5**: Should be filtered by BFF before matching

## Troubleshooting

If no matches are found:

1. **Check BFF filtering**: Verify that features #1-4 pass BFF. The output should show "Processed X/5 features..." where X > 0 if BFF is working.

2. **Check RI calibration**: The calibration file must convert RT values to RI. Lower RIs (652, 672, 750, 800) require extrapolation which may be less accurate.

3. **Check blank identifier**: The blank identifier "FieldBlank" should match columns "FieldBlank_01 Peak area" and "FieldBlank_02 Peak area" (case-insensitive).

4. **Check spectral scores**: The matching spectra are designed to produce dot > 500 and rev_dot > 600, but slight variations in the matching algorithm might affect scores.

5. **Check RHRMF scores**: For low-resolution library matches, RHRMF must be > 75. The library compounds have formulas, so RHRMF should be calculated.

## Notes

- The RI calibration file starts at C10 (RI 1000, RT 15.791 min), so lower RIs require extrapolation
- Feature #1 uses RT 15.791 which exactly matches the C10 calibration point
- Features #2-5 use extrapolated RT values which may have reduced accuracy
- All matching spectra are designed to be similar to library spectra but with slight variations to simulate real data
