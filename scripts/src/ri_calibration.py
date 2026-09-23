"""
Retention-time -> retention-index calibration from an n-alkane series.

Inside the calibrated RT range the RI is a cubic-spline interpolation of
carbon number against retention time (RI = 100 x carbon number), as described
in the NYCSS supporting information (Fig. S5).

Outside the range the behaviour is selectable (v3.1.0, review finding S-RI-1):

  extrapolation='spline'  (default) the spline's terminal cubic polynomial is
                          extended, which reproduces v3.0.x behaviour exactly
                          but is unbounded (it can even go negative on a
                          calibration with a hold-shaped start);
  extrapolation='linear'  van den Dool & Kratz style linear extrapolation from
                          the two terminal alkanes on that side.

Either way, callers can ask `is_in_range(rt)` and the parser flags every
feature whose RI was extrapolated (`Feature.ri_extrapolated`), which is
reported in the output tables.  The recommended remedy for any Level-2 feature
outside the range is to extend the alkane series, not to trust either
extrapolation.
"""
import os

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

EXTRAPOLATION_MODES = ('spline', 'linear')


class RICalibrator:
    """
    Converts retention times (RT) to retention indices (RI) using alkane standards.
    """

    def __init__(self, calibration_file=None, extrapolation='spline'):
        if extrapolation not in EXTRAPOLATION_MODES:
            raise ValueError(f"extrapolation must be one of {EXTRAPOLATION_MODES}, "
                             f"got {extrapolation!r}")
        self.calibration_file = calibration_file
        self.extrapolation = extrapolation
        self.carbon_numbers = []
        self.retention_times = []
        self.interpolator = None

        if calibration_file:
            # v3.1.0 (D-4): a supplied-but-missing file used to be ignored
            # silently, leaving every feature with RI 0 and no matches.
            self.load_calibration(calibration_file)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    @staticmethod
    def _read_table(filepath):
        """Read a two-column (carbon number, RT) table.

        Accepts tab, comma, semicolon or whitespace delimiters, with or
        without a header line (v3.1.0, D-4: a header-less file used to lose
        its first alkane to the header).
        """
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as fh:
            lines = [ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith('#')]
        if not lines:
            raise ValueError("calibration file is empty")

        def split(line):
            for sep in ('\t', ',', ';'):
                if sep in line:
                    return [t.strip() for t in line.split(sep)]
            return line.split()

        rows = [split(ln) for ln in lines]
        # Drop a header line only if its first two cells are not numeric.
        try:
            float(rows[0][0]); float(rows[0][1])
        except (ValueError, IndexError):
            rows = rows[1:]
        table = []
        for i, r in enumerate(rows, 1):
            if len(r) < 2:
                raise ValueError(f"line {i}: expected at least 2 columns (carbon number, RT), got {r!r}")
            try:
                table.append((float(r[0]), float(r[1])))
            except ValueError:
                raise ValueError(f"line {i}: non-numeric value in {r!r}")
        return table

    def load_calibration(self, filepath):
        """
        Loads alkane calibration data.  Expected content (header optional):
            Carbon number\tRT(min)
            10\t15.791
            11\t22.312
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"RI Calibration file not found: {filepath}")

        try:
            table = self._read_table(filepath)
        except ValueError as e:
            raise ValueError(f"Error loading RI calibration file {filepath}: {e}")

        table.sort(key=lambda t: t[0])
        cns = [t[0] for t in table]
        rts = [t[1] for t in table]

        if len(cns) < 3:
            raise ValueError("RI Calibration requires at least 3 alkane standards")
        if any(abs(c - round(c)) > 1e-9 or c <= 0 for c in cns):
            raise ValueError(f"carbon numbers must be positive integers, got {cns}")
        if len(set(cns)) != len(cns):
            dup = sorted({c for c in cns if cns.count(c) > 1})
            raise ValueError(f"duplicate carbon numbers in calibration file: {[int(d) for d in dup]}")
        if any(b <= a for a, b in zip(rts, rts[1:])):
            raise ValueError("retention times must increase strictly with carbon number; "
                             f"got {list(zip([int(c) for c in cns], rts))}")

        self.carbon_numbers = [int(c) for c in cns]
        self.retention_times = [float(r) for r in rts]
        self.interpolator = CubicSpline(self.retention_times, self.carbon_numbers,
                                        extrapolate=True)

        print(f"RI Calibration loaded: {len(self.carbon_numbers)} alkane standards")
        print(f"RT range: {self.rt_range[0]:.2f} - {self.rt_range[1]:.2f} min")
        print(f"Carbon range: C{min(self.carbon_numbers)} - C{max(self.carbon_numbers)}")
        print(f"[RI] Features eluting outside {self.rt_range[0]:.2f}-{self.rt_range[1]:.2f} min "
              f"will be EXTRAPOLATED ({self.extrapolation}) and flagged RI_Extrapolated=Yes. "
              f"Extend the alkane series to avoid this.")

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------
    @property
    def rt_range(self):
        """(first alkane RT, last alkane RT) or None when not calibrated."""
        if not self.retention_times:
            return None
        return (self.retention_times[0], self.retention_times[-1])

    def is_in_range(self, rt):
        """True when `rt` lies within the calibrated alkane RT range."""
        if self.interpolator is None:
            raise ValueError("RI Calibrator not initialized. Load a calibration file first.")
        lo, hi = self.rt_range
        return bool(lo <= float(rt) <= hi)

    def _linear_outside(self, rt):
        rts, cns = self.retention_times, self.carbon_numbers
        if rt < rts[0]:
            slope = (cns[1] - cns[0]) / (rts[1] - rts[0])
            return cns[0] + (rt - rts[0]) * slope
        slope = (cns[-1] - cns[-2]) / (rts[-1] - rts[-2])
        return cns[-1] + (rt - rts[-1]) * slope

    def rt_to_ri(self, rt):
        """
        Retention time (min) -> retention index (100 x interpolated carbon number).
        Accepts a scalar or an array-like; returns float or np.ndarray.
        """
        if self.interpolator is None:
            raise ValueError("RI Calibrator not initialized. Load a calibration file first.")

        scalar = not isinstance(rt, (list, tuple, np.ndarray))
        arr = np.atleast_1d(np.asarray(rt, dtype=float))
        carbon_n = self.interpolator(arr)
        if self.extrapolation == 'linear':
            lo, hi = self.rt_range
            outside = (arr < lo) | (arr > hi)
            if np.any(outside):
                carbon_n = np.array(carbon_n, dtype=float)
                carbon_n[outside] = [self._linear_outside(float(t)) for t in arr[outside]]
        ri = carbon_n * 100.0
        return float(ri[0]) if scalar else ri

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
            "rt_range": self.rt_range,
            "carbon_range": (min(self.carbon_numbers), max(self.carbon_numbers)),
            "extrapolation": self.extrapolation,
            "file": self.calibration_file,
        }
