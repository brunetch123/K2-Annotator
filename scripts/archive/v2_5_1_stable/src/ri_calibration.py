import pandas as pd
import numpy as np
from scipy.interpolate import CubicSpline
import os

class RICalibrator:
    """
    Converts retention times (RT) to retention indices (RI) using alkane standards.
    Supports Kovats Retention Index calculation.
    """
    def __init__(self, calibration_file=None):
        self.calibration_file = calibration_file
        self.carbon_numbers = []
        self.retention_times = []
        self.interpolator = None

        if calibration_file and os.path.exists(calibration_file):
            self.load_calibration(calibration_file)

    def load_calibration(self, filepath):
        """
        Loads alkane calibration data from a tab-delimited file.
        Expected format:
        Carbon number\tRT(min)
        10\t15.791
        11\t22.312
        ...
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"RI Calibration file not found: {filepath}")

        try:
            # Try reading with tab delimiter
            df = pd.read_csv(filepath, sep='\t')

            # Handle various column name formats
            if 'Carbon number' in df.columns and 'RT(min)' in df.columns:
                cn_col = 'Carbon number'
                rt_col = 'RT(min)'
            elif 'carbon_number' in df.columns and 'rt' in df.columns:
                cn_col = 'carbon_number'
                rt_col = 'rt'
            elif len(df.columns) >= 2:
                # Assume first column is carbon number, second is RT
                cn_col = df.columns[0]
                rt_col = df.columns[1]
            else:
                raise ValueError("Cannot identify carbon number and RT columns in calibration file")

            # Extract and sort by carbon number
            df = df[[cn_col, rt_col]].dropna()
            df = df.sort_values(by=cn_col)

            self.carbon_numbers = df[cn_col].astype(int).tolist()
            self.retention_times = df[rt_col].astype(float).tolist()

            if len(self.carbon_numbers) < 3:
                raise ValueError("RI Calibration requires at least 3 alkane standards")

            # Create interpolator (Cubic Spline for smooth interpolation)
            self.interpolator = CubicSpline(self.retention_times, self.carbon_numbers,
                                            extrapolate=True)

            print(f"RI Calibration loaded: {len(self.carbon_numbers)} alkane standards")
            print(f"RT range: {min(self.retention_times):.2f} - {max(self.retention_times):.2f} min")
            print(f"Carbon range: C{min(self.carbon_numbers)} - C{max(self.carbon_numbers)}")

        except Exception as e:
            raise ValueError(f"Error loading RI calibration file: {e}")

    def rt_to_ri(self, rt):
        """
        Converts a retention time (RT) to a retention index (RI) using Kovats equation.
        RI = 100 * N, where N is the carbon number interpolated from the calibration curve.

        Args:
            rt: Retention time in minutes (float or array-like)

        Returns:
            Retention index (float or np.array)
        """
        if self.interpolator is None:
            raise ValueError("RI Calibrator not initialized. Load a calibration file first.")

        # Handle single value or array
        if isinstance(rt, (list, tuple, np.ndarray)):
            rt = np.array(rt)
            carbon_n = self.interpolator(rt)
            return carbon_n * 100.0
        else:
            rt = float(rt)
            carbon_n = float(self.interpolator(rt))
            return carbon_n * 100.0

    def is_calibrated(self):
        """Returns True if calibration data has been loaded."""
        return self.interpolator is not None

    def get_calibration_info(self):
        """Returns dictionary with calibration information."""
        if not self.is_calibrated():
            return {"status": "Not calibrated"}

        return {
            "status": "Calibrated",
            "num_standards": len(self.carbon_numbers),
            "rt_range": (min(self.retention_times), max(self.retention_times)),
            "carbon_range": (min(self.carbon_numbers), max(self.carbon_numbers)),
            "file": self.calibration_file
        }
