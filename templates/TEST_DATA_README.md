# Template and test data

## Files

| File | Purpose |
|---|---|
| `library_template.csv` | Three-compound spectral library, CSV format (`name, formula, ri, peaks_json, ...`) |
| `library_template.msp` | The same library in NIST-style MSP format |
| `test_quant.csv` | MZmine-style feature table with 5 features, 2 field blanks and 3 samples |
| `test_spectra.msp` | MZmine-style MSP with the spectra of the 5 features |
| `ri_calibration_template.txt` | n-Alkane calibration table (C7–C20) for `--ri-cal` |

Run the whole set from the `scripts/` directory:

```bash
python cli.py --quant ../templates/test_quant.csv --msp ../templates/test_spectra.msp \
              --library ../templates/library_template.csv \
              --ri-cal ../templates/ri_calibration_template.txt --blank-id fieldblank \
              --output ../results/template_run
```

Expected: features 1, 2 and 3 each receive one Level-2 match (n-Decane,
2,4-Dimethylpentane, Benzene); feature 4 has no library counterpart; feature 5
is removed by the blank feature filter. Exit code 0. A `run_manifest.json`,
the per-match CSV, and the feature/match summary CSVs are written.

All exact-mass values in these files are cation m/z values (monoisotopic mass
minus one electron), as a mass spectrometer reports them. It should be noted
that the templates shipped with versions before 3.1.0 held neutral masses.

## Test features

Retention times were chosen so that the alkane calibration gives exactly the
listed RI (cubic spline; RIs below C7 = 700 are extrapolated and flagged
`RI_Extrapolated = Yes`).

| # | Compound | RT (min) | RI | Blanks | Samples | Expected |
|---|---|---|---|---|---|---|
| 1 | n-Decane | 15.252 | 1000 | 150, 250 | 5200, 6800, 7500 | match (exact-mass library entry → HR path) |
| 2 | 2,4-Dimethylpentane | 7.293 | 672 | 100, 180 | 4800, 6200, 5800 | match (HR path; RI extrapolated) |
| 3 | Benzene | 6.913 | 652 | 120, 200 | 5500, 7200, 6800 | match (low-res library entry → RHRMF path; RI extrapolated) |
| 4 | Unknown | 10.002 | 800 | 180, 220 | 5800, 6400, 6000 | no match (nothing in the library near RI 800) |
| 5 | Contaminant | 8.883 | 750 | 8200, 7800 | 900, 1100, 950 | removed by BFF |

## BFF thresholds (c = 5)

threshold = 5 × (mean_blank + 3 × SD_blank), sample SD:

- Feature 1: 5 × (200 + 3 × 70.71) = 2060.7 < max sample 7500 → pass
- Feature 2: 5 × (140 + 3 × 56.57) = 1548.5 < 6200 → pass
- Feature 3: 5 × (160 + 3 × 56.57) = 1648.5 < 7200 → pass
- Feature 4: 5 × (200 + 3 × 28.28) = 1424.3 < 6400 → pass
- Feature 5: 5 × (8000 + 3 × 282.84) = 44242.6 > 1100 → fail

## Matching criteria exercised

See `docs/SCORING_METHODS.md` for the full definitions. In brief a match
requires: BFF pass; |ΔRI| ≤ 50 and ≤ 1.5 % of the feature RI; reverse dot
> 600 and forward dot > 500; then either RHRMF > 75 (low-resolution library
entry, formula required) or the 10 ppm peak-paired dot products > 600/500
(exact-mass library entry).

The n-Decane and 2,4-Dimethylpentane library entries carry four-decimal m/z
values and are classified exact-mass; Benzene is stored at integer m/z and is
classified low-resolution, so it demonstrates the RHRMF path.

## Library formats

CSV columns: `name, formula, ri, peaks_json` are required
(`peaks_json` = `[[mz, intensity], ...]`); every other column becomes
metadata (`cas`, `inchikey`, `source`, `instrument`, `comments`, ...).
An optional `resolution` column (`high`/`low`) overrides the automatic
exact-mass detection.

MSP records need `NAME`, a retention index (`RI`, `RetentionIndex`,
`Retention_index: SemiStdNP=...`, `Kovats`) and a peak list; `FORMULA` is
required for the RHRMF path. Peak lines may be `128 999`, `128 999;`,
`41 59; 43 999; 57 891;` or `(41 59)`. Records are separated by a blank
line or simply by the next `NAME:`.
