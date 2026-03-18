#!/usr/bin/env python3
"""
Command-Line Interface for MS-DIAL/MZmine Level 2 Annotation Pipeline
Supports both MS-DIAL and MZmine input formats with automatic detection.
For GC-MS Suspect Screening workflows.
"""

import argparse
import sys
import os
import json
from datetime import datetime
from src.matching_engine import MatchingEngine
from src.reporter import ReportGenerator
from src.stats_engine import StatsEngine

def main():
    parser = argparse.ArgumentParser(
        description="MS-DIAL/MZmine Level 2 Compound Annotation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # MS-DIAL inputs
  python -m src.cli --quant Area.txt --msp Spectrum.msp --library unified_library.csv

  # MZmine inputs with RI calibration
  python -m src.cli --quant quant.csv --msp spectra.msp --library unified_library.csv \\
                      --ri-cal MSDial_RICal.txt

  # Custom blank identifier
  python -m src.cli --quant quant.csv --msp spectra.msp --library lib.csv \\
                      --blank-id "blank"

  # With EPA API key for toxicity data
  python -m src.cli --quant quant.csv --msp spectra.msp --library lib.csv \\
                      --api-key YOUR_KEY --output results/
        """
    )

    # Required arguments
    parser.add_argument(
        '--quant', '-q',
        required=True,
        help='Quantification file (.txt for MS-DIAL, .csv for MZmine)'
    )

    parser.add_argument(
        '--msp', '-m',
        required=True,
        help='MSP spectral file (.msp)'
    )

    parser.add_argument(
        '--library', '-l',
        required=True,
        help='Reference library file (.csv)'
    )

    # Optional arguments
    parser.add_argument(
        '--ri-cal', '-r',
        default=None,
        help='RI calibration file for MZmine data (tab-delimited: Carbon number, RT)'
    )

    parser.add_argument(
        '--blank-id', '-b',
        default='fieldblank',
        help='String to identify blank samples (case-insensitive). Default: "fieldblank"'
    )

    parser.add_argument(
        '--output', '-o',
        default='results',
        help='Output directory for results. Default: "results"'
    )

    parser.add_argument(
        '--name', '-n',
        default=None,
        help='Project name for reports'
    )

    parser.add_argument(
        '--api-key', '-k',
        default=None,
        help='EPA CompTox API key for toxicity data (optional)'
    )

    parser.add_argument(
        '--csv-only',
        action='store_true',
        help='Generate only CSV report (skip PDF)'
    )

    parser.add_argument(
        '--pdf-only',
        action='store_true',
        help='Generate only PDF report (skip CSV)'
    )

    parser.add_argument(
        '--grouping',
        default=None,
        help='JSON file containing sample grouping information'
    )

    # Internal Standard Normalization (v2.6.0)
    parser.add_argument(
        '--is-config',
        default=None,
        help='JSON file containing IS normalization configuration'
    )

    args = parser.parse_args()

    # Validate files exist
    if not os.path.exists(args.quant):
        print(f"Error: Quantification file not found: {args.quant}")
        sys.exit(1)

    if not os.path.exists(args.msp):
        print(f"Error: MSP file not found: {args.msp}")
        sys.exit(1)

    if not os.path.exists(args.library):
        print(f"Error: Library file not found: {args.library}")
        sys.exit(1)

    if args.ri_cal and not os.path.exists(args.ri_cal):
        print(f"Error: RI calibration file not found: {args.ri_cal}")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    print("="*70)
    print("MS-DIAL/MZmine Level 2 Compound Annotation Pipeline")
    print("="*70)
    print(f"Quantification: {args.quant}")
    print(f"MSP File:       {args.msp}")
    print(f"Library:        {args.library}")
    if args.ri_cal:
        print(f"RI Calibration: {args.ri_cal}")
    print(f"Blank ID:       '{args.blank_id}'")
    print(f"Output Dir:     {args.output}")
    print("="*70)

    try:
        # Load IS configuration if provided (v2.6.0)
        is_config = {}
        if args.is_config and os.path.exists(args.is_config):
            print(f"\n[*] Loading Internal Standard configuration from: {args.is_config}")
            try:
                with open(args.is_config, 'r') as f:
                    is_config = json.load(f)
                print(f"    [OK] IS normalization: {'enabled' if is_config.get('enabled') else 'disabled'}")
            except Exception as e:
                print(f"    [WARNING] Failed to load IS config: {e}")
                is_config = {}

        # Initialize engine
        print("\n[1/4] Initializing Matching Engine...")
        engine = MatchingEngine(
            data_dir="",
            quant_file=args.quant,
            msp_file=args.msp,
            library_file=args.library,
            ri_cal_file=args.ri_cal,
            blank_identifier=args.blank_id,
            is_config=is_config
        )

        # Load data
        print("\n[2/4] Loading and parsing input files...")
        engine.load_data()

        # Run matching
        print("\n[3/4] Running Level 2 matching...")
        engine.run_matching()

        results = engine.get_results()
        features = engine.parser.get_feature_list()

        if not results:
            print("\n[WARNING] No Level 2 matches found.")
            print("This could mean:")
            print("  - No features passed BFF filter")
            print("  - No spectral matches met Level 2 thresholds")
            print("  - RI matching window too strict")
            sys.exit(0)

        print(f"\n[OK] Found {len(results)} Level 2 matches!")

        # Generate reports with date-stamped filenames
        print("\n[4/4] Generating reports...")

        # Extract folder name from quant file path
        quant_dir = os.path.dirname(args.quant)
        if quant_dir:
            folder_name = os.path.basename(quant_dir)
        else:
            # If no directory, use basename of quant file without extension
            folder_name = os.path.splitext(os.path.basename(args.quant))[0]

        # Generate date stamp
        date_stamp = datetime.now().strftime("%Y%m%d")

        # Create filenames
        csv_filename = f"{folder_name}_matches_{date_stamp}.csv"
        pdf_filename = f"{folder_name}_report_{date_stamp}.pdf"

        # Get all sample columns for abundance export
        all_samples = engine.parser.blank_columns + engine.parser.sample_columns

        reporter = ReportGenerator(
            results, features,
            output_dir=args.output,
            api_key=args.api_key,
            sample_columns=all_samples
        )

        # Run Statistics if grouping is provided
        if args.grouping and os.path.exists(args.grouping):
            print("\n[*] Running group statistics...")
            try:
                with open(args.grouping, 'r') as f:
                    group_info = json.load(f)
                
                stats_engine = StatsEngine(group_info)
                stats_engine.calculate_stats(features)
                print(f"    [OK] Statistics calculated for {len(features)} features.")

                # Generate Global Volcano Plot
                print("    [*] Generating Global Volcano Plot...")
                viz = reporter.viz
                volcano_path = viz.create_volcano_plot(
                    features, 
                    title=f"Volcano Plot: {args.name or folder_name}", 
                    filename="global_volcano_plot.png"
                )
                if volcano_path:
                    print(f"    [OK] Volcano plot saved: {volcano_path}")
            except Exception as e:
                print(f"    [ERROR] Failed to calculate statistics: {e}")

        if not args.pdf_only:
            print("  - Generating CSV report...")
            csv_file = reporter.generate_csv(filename=csv_filename)
            print(f"    [OK] CSV saved: {csv_file}")

        if not args.csv_only:
            print("  - Generating PDF report...")
            pdf_file = reporter.generate_pdf(filename=pdf_filename)
            print(f"    [OK] PDF saved: {pdf_file}")

        print("\n" + "="*70)
        print("[OK] Analysis Complete!")
        print("="*70)
        print(f"Results saved to: {os.path.abspath(args.output)}")

    except KeyboardInterrupt:
        print("\n\n[WARNING] Analysis interrupted by user.")
        sys.exit(1)

    except Exception as e:
        print(f"\n\n[ERROR] Error during analysis:")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
