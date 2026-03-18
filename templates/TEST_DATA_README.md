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

For a match to be found:
1. Feature must pass BFF filter
2. RI must be within ±50 units of library compound
3. RI % error must be < 1.5%
4. Forward dot product > 500
5. Reverse dot product > 600
6. **High-res libraries**: Automatically pass (bypass RHRMF)
7. **Low-res libraries**: RHRMF score > 75

## High-Resolution vs Low-Resolution

**High-Resolution Library Compounds** (bypass RHRMF):
- **n-Decane**: Has decimal precision in m/z values (>0.05), detected as high-res
- **2,4-Dimethylpentane**: Has decimal precision in m/z values, detected as high-res

**Low-Resolution Library Compound** (requires RHRMF > 75):
- **Benzene**: Integer m/z values, detected as low-res
- Feature spectrum uses exact masses that can be explained by C6H6 formula:
  - 78.0469 (C6H6+), 77.0391 (C6H5+), 76.0313 (C6H4+), 52.0313 (C4H4+), etc.
  - All major peaks are explainable from C6H6, so RHRMF should be > 75

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
