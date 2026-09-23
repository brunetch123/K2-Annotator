#!/usr/bin/env python3
"""
Command-Line Interface for the K2 Annotator Level 2 annotation pipeline
(MZmine / MS-DIAL deconvolution output -> Level-2 annotations).

Exit codes (v3.1.0):
    0   completed with at least one Level-2 match
    2   completed, but no feature received a Level-2 match (summaries,
        manifest and log are still written)
    1   error (bad input, missing calibration, no blanks, ...)
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

from src.version import __version__


class _Parser(argparse.ArgumentParser):
    """argparse exits with status 2 on usage errors; 2 is reserved for
    "completed with no matches", so usage errors exit 1 instead."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _positive_float(value):
    """argparse type for a strictly positive float."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}")
    if f <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {f}")
    return f


def build_parser():
    parser = _Parser(
        description=f"K2 Annotator {__version__} - MS-DIAL/MZmine Level 2 Compound Annotation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # MZmine inputs with RI calibration (required for MZmine data)
  python cli.py --quant quant.csv --msp spectra.msp --library unified_library.csv \\
                --ri-cal alkanes.txt

  # Sample classification from the GUI / a JSON file
  python cli.py ... --grouping sample_grouping.json

  # With EPA API key for toxicity data (or set K2_EPA_API_KEY)
  python cli.py ... --api-key YOUR_KEY --output results/
        """
    )
    parser.add_argument('--version', action='version', version=f"K2 Annotator {__version__}")

    parser.add_argument('--quant', '-q', required=True,
                        help='Quantification file (.txt for MS-DIAL, .csv for MZmine)')
    parser.add_argument('--msp', '-m', required=True, help='MSP spectral file (.msp)')
    parser.add_argument('--library', '-l', required=True, help='Reference library file (.csv or .msp)')

    parser.add_argument('--ri-cal', '-r', default=None,
                        help='Alkane RI calibration table (carbon number, RT). Required for MZmine data.')
    parser.add_argument('--ri-extrapolation', choices=['spline', 'linear'], default='spline',
                        help='How retention indices are derived for features eluting outside the alkane '
                             'calibration range: "spline" (default; the cubic spline is extended, as in '
                             'v3.0.x) or "linear" (van den Dool linear extrapolation from the terminal '
                             'alkane pair). Extrapolated features are flagged RI_Extrapolated=Yes either way.')

    parser.add_argument('--blank-id', '-b', default='fieldblank',
                        help='Substring identifying blank sample columns (case-insensitive). Default: "fieldblank"')
    parser.add_argument('--grouping', default=None,
                        help='JSON file with per-sample classification, either {name: {"type": "Blank"|"Sample"|'
                             '"Reference", ...}} (GUI format) or {name: "blank"|"sample"|"reference"}. '
                             'Overrides --blank-id for the listed samples.')
    parser.add_argument('--allow-no-blanks', action='store_true',
                        help='Run even if no blank column is identified (blank filtering is then a no-op). '
                             'Blank feature filtering is a mandatory Level-2 criterion; use with care.')

    parser.add_argument('--bff-mode', choices=['standard', 'adjusted'], default='standard',
                        help='Blank Feature Filtering rule. "standard" (default): c*(mean+3SD) per Koelmel '
                             'et al. 2022. "adjusted" (NOT part of the Koelmel framework): per-feature '
                             'Shapiro-Wilk gate between mean+3SD and median+3*1.4826*MAD.')
    parser.add_argument('--bff-c-factor', type=_positive_float, default=5.0,
                        help='Multiplier c applied to the BFF threshold rule. Default: 5.0.')

    parser.add_argument('--output', '-o', default='results', help='Output directory. Default: "results"')
    parser.add_argument('--name', '-n', default=None,
                        help='Run name used for output file names (default: name of the folder holding --quant)')
    parser.add_argument('--api-key', '-k', default=None,
                        help='EPA CompTox API key for hazard data (optional; K2_EPA_API_KEY env var is used if unset)')

    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument('--csv-only', action='store_true', help='Generate only CSV reports (skip PDF)')
    fmt.add_argument('--pdf-only', action='store_true', help='Generate only the PDF report (skip CSV)')
    parser.add_argument('--no-hazard', action='store_true',
                        help='Skip all EPA CompTox / PubChem lookups (hazard columns and structure images). '
                             'Lookups are also abandoned automatically for the rest of a run once an API '
                             'stops responding.')
    parser.add_argument('--keep-assets', action='store_true',
                        help='Keep the temp_assets/ folder (mirror plots, structure images) after the run')

    parser.add_argument('--is-config', default=None, help='JSON file containing IS normalization configuration')
    parser.add_argument('--surrogate-library', '-sl', default=None, help='Surrogate standard library (CSV/MSP)')
    parser.add_argument('--surrogate-config', default=None,
                        help='JSON file with surrogate configuration (spiked samples, ratios, groups)')
    parser.add_argument('--reference-samples', default=None,
                        help='Comma-separated reference sample names to exclude from suspect screening')

    parser.add_argument('--max-lib-peaks', type=int, default=20, metavar='N',
                        help='Trim every library compound to its N most intense peaks at load (default 20; '
                             '0 disables). Recorded in the run manifest.')
    return parser


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _load_json(path, what):
    """Load a JSON file that the user explicitly supplied; a missing or
    unreadable file is an error (v3.1.0, D-5), not a silent skip."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{what} file not found: {path}")
    with open(path, 'r', encoding='utf-8-sig') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{what} file {path} is not valid JSON: {e}")


def parse_grouping(grouping):
    """Turn a grouping dict into (sample_types, reference_samples).

    Accepts the GUI format {name: {"type": "Blank"|"Sample"|"Reference", ...}}
    and the flat format {name: "blank"|"sample"|"reference"}.  Reference
    samples are screened as samples for the BFF *column set* but are excluded
    from the BFF max-abundance (they are spiked references), so they are
    returned separately.
    """
    sample_types = {}
    references = []
    for name, info in grouping.items():
        typ = info.get('type', info.get('Type', '')) if isinstance(info, dict) else info
        typ = str(typ).strip().lower()
        if typ == 'blank':
            sample_types[name] = 'blank'
        elif typ == 'reference':
            sample_types[name] = 'sample'
            references.append(name)
        elif typ in ('sample', ''):
            sample_types[name] = 'sample'
        else:
            raise ValueError(f"grouping: unknown type {typ!r} for sample {name!r} "
                             f"(expected Blank, Sample or Reference)")
    return sample_types, references


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

    if not args.api_key:
        args.api_key = os.environ.get('K2_EPA_API_KEY') or None

    for label, path in (('Quantification', args.quant), ('MSP', args.msp), ('Library', args.library)):
        if not os.path.exists(path):
            print(f"Error: {label} file not found: {path}")
            return 1
    if args.ri_cal and not os.path.exists(args.ri_cal):
        print(f"Error: RI calibration file not found: {args.ri_cal}")
        return 1

    os.makedirs(args.output, exist_ok=True)

    print("=" * 70)
    print(f"K2 Annotator {__version__} - Level 2 Compound Annotation Pipeline")
    print("=" * 70)
    print(f"Quantification: {args.quant}")
    print(f"MSP File:       {args.msp}")
    print(f"Library:        {args.library}")
    if args.ri_cal:
        print(f"RI Calibration: {args.ri_cal}  (extrapolation: {args.ri_extrapolation})")
    print(f"Blank ID:       '{args.blank_id}'")
    if args.grouping:
        print(f"Grouping:       {args.grouping}")
    print(f"BFF Mode:       {args.bff_mode}")
    print(f"BFF c-factor:   {args.bff_c_factor}")
    print(f"Lib peak trim:  top-{args.max_lib_peaks or 'all'}")
    print(f"Output Dir:     {args.output}")
    print("=" * 70)

    try:
        # ---- configuration files -------------------------------------------
        is_config = {}
        if args.is_config:
            print(f"\n[*] Loading Internal Standard configuration from: {args.is_config}")
            is_config = _load_json(args.is_config, 'IS configuration')
            print(f"    [OK] IS normalization: {'enabled' if is_config.get('enabled') else 'disabled'}")

        surrogate_config = {}
        if args.surrogate_config:
            print(f"\n[*] Loading Surrogate Standard configuration from: {args.surrogate_config}")
            surrogate_config = _load_json(args.surrogate_config, 'Surrogate configuration')
            surrogate_config['enabled'] = True
            print(f"    [OK] Surrogate analysis enabled")
        if args.surrogate_library and not surrogate_config:
            surrogate_config = {
                'enabled': True, 'library_path': args.surrogate_library,
                'selected_compounds': None,
                'groups': {'Default': {'samples': [], 'references': []}},
                'spike_ratios': {}, 'spiked_samples': [], 'reference_samples': [],
            }
            print(f"\n[*] Surrogate library specified: {args.surrogate_library}")
        if args.surrogate_library:
            surrogate_config['library_path'] = args.surrogate_library

        # ---- sample classification (v3.1.0, D-1) --------------------------
        sample_types = None
        reference_samples = []
        if args.grouping:
            sample_types, reference_samples = parse_grouping(_load_json(args.grouping, 'Grouping'))
            print(f"    [OK] Grouping: {sum(1 for v in sample_types.values() if v == 'blank')} blank(s), "
                  f"{sum(1 for v in sample_types.values() if v == 'sample')} sample(s), "
                  f"{len(reference_samples)} reference(s)")
        if args.reference_samples:
            reference_samples += [s.strip() for s in args.reference_samples.split(',') if s.strip()]
        if surrogate_config.get('reference_samples'):
            reference_samples += list(surrogate_config['reference_samples'])
        reference_samples = list(dict.fromkeys(reference_samples))  # dedupe, keep order
        if reference_samples:
            print(f"\n[*] Reference samples excluded from suspect screening: {reference_samples}")

        # ---- engine ---------------------------------------------------------
        from src.matching_engine import MatchingEngine
        from src.reporter import ReportGenerator

        print("\n[1/4] Initializing Matching Engine...")
        engine = MatchingEngine(
            data_dir="",
            quant_file=args.quant,
            msp_file=args.msp,
            library_file=args.library,
            ri_cal_file=args.ri_cal,
            blank_identifier=args.blank_id,
            sample_types=sample_types,
            is_config=is_config,
            reference_samples=reference_samples,
            bff_mode=args.bff_mode,
            bff_c_factor=args.bff_c_factor,
            max_lib_peaks=args.max_lib_peaks,
            ri_extrapolation=args.ri_extrapolation,
            allow_no_blanks=args.allow_no_blanks,
        )

        print("\n[2/4] Loading and parsing input files...")
        engine.load_data()

        print("\n[3/4] Running Level 2 matching...")
        engine.run_matching()

        results = engine.get_results()
        features = engine.parser.get_feature_list()
        n_matches = sum(len(c) for c in results.values())

        if not results:
            print("\n[WARNING] No Level 2 matches found.")
            print("This could mean:")
            print("  - No features passed the blank filter (see the feature summary CSV)")
            print("  - No spectral matches met the Level 2 thresholds")
            print("  - The library has no entries within the RI window of the features")
        else:
            print(f"\n[OK] {len(results)} feature(s) with {n_matches} Level 2 match(es).")

        # ---- surrogate analysis ---------------------------------------------
        surrogate_analyzer = None
        if surrogate_config.get('enabled'):
            print("\n[3.5/4] Running Surrogate Standard Analysis...")
            from src.surrogate_analyzer import SurrogateAnalyzer
            from src.surrogate_reporter import SurrogateReporter
            surrogate_analyzer = SurrogateAnalyzer(
                features=features, surrogate_config=surrogate_config,
                sample_columns=engine.parser.sample_columns,
                blank_columns=engine.parser.blank_columns, is_config=is_config)
            if surrogate_analyzer.run_full_analysis():
                print("    [OK] Surrogate analysis complete!")
            else:
                print("    [WARNING] Surrogate analysis had issues")
                surrogate_analyzer = None

        # ---- reports ----------------------------------------------------------
        print("\n[4/4] Generating reports...")
        quant_dir = os.path.dirname(args.quant)
        folder_name = os.path.basename(quant_dir) if quant_dir else os.path.splitext(os.path.basename(args.quant))[0]
        run_name = args.name or folder_name
        date_stamp = datetime.now().strftime("%Y%m%d")
        csv_filename = f"{run_name}_matches_{date_stamp}.csv"
        pdf_filename = f"{run_name}_report_{date_stamp}.pdf"
        all_samples = engine.parser.blank_columns + engine.parser.sample_columns

        reporter = ReportGenerator(
            results, features, output_dir=args.output, api_key=args.api_key,
            sample_columns=all_samples, is_config=is_config,
            surrogate_analyzer=surrogate_analyzer,
            blank_columns=engine.parser.blank_columns,
            reference_samples=reference_samples,
            hazard_lookups=not args.no_hazard,
        )

        written = {}
        if not args.pdf_only:
            print("  - Generating CSV report...")
            written['matches_csv'] = reporter.generate_csv(filename=csv_filename)
            print(f"    [OK] CSV saved: {written['matches_csv']}")
            print("  - Generating summary CSVs (feature + match)...")
            feat_csv, match_csv = reporter.generate_summary_csvs(base_name=f"{run_name}_{date_stamp}")
            written['feature_summary_csv'] = feat_csv
            written['match_summary_csv'] = match_csv
            print(f"    [OK] Feature summary: {feat_csv}")
            print(f"    [OK] Match summary:   {match_csv}")
        if not args.csv_only:
            print("  - Generating PDF report...")
            written['report_pdf'] = reporter.generate_pdf(filename=pdf_filename)
            print(f"    [OK] PDF saved: {written['report_pdf']}")
        if surrogate_analyzer:
            print("  - Generating Surrogate Recovery report...")
            from src.surrogate_reporter import SurrogateReporter
            written['surrogate_csv'] = SurrogateReporter(
                surrogate_analyzer, output_dir=args.output, project_name=run_name).generate_csv()
            print(f"    [OK] Surrogate CSV saved: {written['surrogate_csv']}")
        if not args.keep_assets:
            reporter.cleanup()

        # ---- run manifest (v3.1.0, D-6) -------------------------------------
        from src.run_manifest import write_manifest
        cal = engine.parser.ri_calibrator
        extra = {
            'run_name': run_name,
            'exit_code': 0 if results else 2,
            'sample_classification': {
                'blanks': list(engine.parser.blank_columns),
                'samples': list(engine.parser.sample_columns),
                'reference_samples': list(reference_samples),
            },
            'library': dict(engine.library_parser.stats, path=args.library,
                            compounds=len(engine.library_parser.get_compounds())),
            'ri_calibration': cal.get_calibration_info() if cal else None,
            'counts': {
                'features': len(features),
                'features_passed_bff': sum(1 for f in features if f.passed_bff),
                'features_ri_extrapolated': sum(1 for f in features if getattr(f, 'ri_extrapolated', False)),
                'features_without_spectrum': engine.parser.n_features_without_spectrum,
                'features_with_level2_match': len(results),
                'level2_matches': n_matches,
            },
            'is_normalization': {k: v for k, v in is_config.items()
                                 if k in ('enabled', 'method', 'is_feature_id', 'is_values',
                                          'normalization_factors', 'target_mz', 'target_value')},
            'outputs': written,
            'external_apis': ('skipped (--no-hazard)' if args.no_hazard else reporter.viz.api_status()),
        }
        manifest_path = write_manifest(
            args.output, args,
            inputs={'quant': args.quant, 'msp': args.msp, 'library': args.library,
                    'ri_cal': args.ri_cal, 'grouping': args.grouping,
                    'is_config': args.is_config, 'surrogate_config': args.surrogate_config,
                    'surrogate_library': args.surrogate_library},
            extra=extra)
        print(f"    [OK] Run manifest: {manifest_path}")

        print("\n" + "=" * 70)
        print("[OK] Analysis Complete!" if results else "[OK] Analysis complete - NO Level 2 matches.")
        print("=" * 70)
        print(f"Results saved to: {os.path.abspath(args.output)}")
        return 0 if results else 2

    except KeyboardInterrupt:
        print("\n\n[WARNING] Analysis interrupted by user.")
        return 1
    except (ValueError, FileNotFoundError) as e:
        print(f"\n\n[ERROR] {e}")
        return 1
    except Exception as e:
        print(f"\n\n[ERROR] Error during analysis:")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
