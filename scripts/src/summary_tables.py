"""
Summary tables (v3.0.6).

Two post-analysis overview tables, written as standalone CSV files and
prepended to the PDF report:

  1. Feature Detection Summary — every observed feature with detection
     frequency (% of samples with abundance > 0) and per-sample abundance.
  2. Match Summary — every library match with the feature it matched and
     the matching scores.

Sample-column attribution: blanks are excluded from frequency/mean/max
statistics (so a feature seen only in blanks does not register as
"detected"), but abundances for blank columns are still echoed in the
per-column section of the CSV/PDF for QA.
"""

import csv
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import Table, TableStyle


# ----------------------------------------------------------------------
# Data preparation
# ----------------------------------------------------------------------

def build_feature_summary(feature_map, sample_columns, blank_columns=None):
    """Return (headers, rows) for the per-feature detection summary.

    Frequency / mean / max are computed over `sample_columns` only.
    Blank-column abundances are still echoed in the per-column section
    so users can spot blank-only features at a glance.
    """
    blank_columns = list(blank_columns or [])
    sample_columns = list(sample_columns or [])
    all_cols = blank_columns + sample_columns
    n_samples = len(sample_columns)

    headers = [
        "Feature_ID", "RT", "RI",
        "Detection_Frequency_%", "Samples_Detected", "Total_Samples",
        "Mean_Sample_Abundance", "Max_Sample_Abundance",
        "Passed_BFF",
    ] + [f"Abundance_{c}" for c in all_cols]

    rows = []
    for feat in sorted(feature_map.values(), key=lambda x: x.id):
        sample_abunds = [float(feat.abundances.get(s, 0.0)) for s in sample_columns]
        all_abunds = [float(feat.abundances.get(c, 0.0)) for c in all_cols]

        detected = sum(1 for a in sample_abunds if a > 0)
        freq = (detected / n_samples * 100) if n_samples > 0 else 0.0
        mean_ab = (sum(sample_abunds) / n_samples) if n_samples > 0 else 0.0
        max_ab = max(sample_abunds) if sample_abunds else 0.0

        row = [
            feat.id,
            f"{feat.rt:.2f}",
            f"{feat.ri:.1f}",
            f"{freq:.1f}",
            detected,
            n_samples,
            f"{mean_ab:.0f}",
            f"{max_ab:.0f}",
            "Yes" if getattr(feat, 'passed_bff', False) else "No",
        ] + [f"{a:.0f}" for a in all_abunds]
        rows.append(row)
    return headers, rows


def build_match_summary(results, feature_map):
    """Return (headers, rows) for the per-match summary.

    One row per (feature, candidate) pair. Sequential Match_# is assigned
    in the same iteration order the detail PDF uses, so the indices line
    up between the two reports.
    """
    headers = [
        "Match_#", "Feature_ID", "Compound_Name", "Library_Entry_ID",
        "Formula", "RevDot", "FwdDot", "RHRMF", "HighRes",
        "Feature_RI", "Library_RI", "RI_Error", "RI_Err_%",
        "Max_Sample_Abundance", "BFF_Threshold",
    ]

    rows = []
    match_num = 0
    for feat_id, candidates in results.items():
        orig = feature_map.get(feat_id)
        if not orig:
            continue
        for cand in candidates:
            match_num += 1
            comp = cand.compound
            ri_err = cand.ri_error
            ri_pct = (ri_err / orig.ri * 100) if orig.ri else 0.0
            rhrmf_val = "N/A" if cand.is_high_res_match else f"{cand.rhrmf_score:.1f}"
            rows.append([
                match_num,
                feat_id,
                comp.name,
                getattr(comp, 'library_index', '') or '',
                comp.formula,
                cand.reverse_dot_product,
                cand.dot_product,
                rhrmf_val,
                "Yes" if cand.is_high_res_match else "No",
                f"{orig.ri:.1f}",
                f"{comp.ri:.1f}",
                f"{ri_err:.1f}",
                f"{ri_pct:.2f}",
                f"{orig.max_sample_abundance:.0f}",
                f"{orig.bff_threshold:.0f}",
            ])
    return headers, rows


# ----------------------------------------------------------------------
# CSV writing
# ----------------------------------------------------------------------

def write_csv(filepath, headers, rows):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return filepath


# ----------------------------------------------------------------------
# PDF rendering
# ----------------------------------------------------------------------

def _truncate(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


# Short display headers used only in the PDF. Verbose CSV headers stay
# in the per-row CSVs because spreadsheet columns can be widened freely
# but PDF columns can't. Mapping is positional: the i-th display header
# is shown above the i-th data column.
_FEATURE_PDF_HEADERS_FIXED = [
    "Feat #", "RT", "RI",
    "Det %", "Det N", "Tot N",
    "Mean Abd", "Max Abd",
    "BFF",
]
_MATCH_PDF_HEADERS = [
    "Match #", "Feat #", "Compound", "Lib ID",
    "Formula", "RevDot", "FwdDot", "RHRMF", "HiRes",
    "Feat RI", "Lib RI", "RI Err", "RI Err %",
    "Max Abd", "BFF Thr",
]
# Proportional column widths (relative). Wider for compound names and
# headers we know are long; narrow for compact numeric fields.
_MATCH_COL_WEIGHTS = [
    0.6, 0.6, 3.0, 0.7,
    0.9, 0.9, 0.9, 0.8, 0.7,
    0.9, 0.9, 0.9, 0.9,
    1.2, 1.0,
]
_FEATURE_FIXED_COL_WEIGHTS = [
    0.7, 0.8, 0.9,
    0.9, 0.7, 0.7,
    1.3, 1.3,
    0.7,
]


def _proportional_widths(weights, avail_w):
    total = float(sum(weights))
    if total <= 0:
        return [avail_w / len(weights)] * len(weights)
    return [avail_w * (w / total) for w in weights]


def _draw_table_paginated(c, page_w, page_h, title, subtitle,
                          display_headers, rows, col_widths,
                          font_size=7, rows_per_page=32,
                          truncate_col=None, truncate_chars=40):
    """Draw a table across as many pages as needed, calling showPage()
    after each page.

    display_headers: short labels used only for the PDF header row.
    col_widths: explicit per-column widths (must match len(display_headers)).
    truncate_col: optional column index to truncate (e.g. compound name).
    """
    if not rows:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, page_h - 40, title)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(40, page_h - 60, "(no rows)")
        c.showPage()
        return

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), font_size + 1),  # header slightly larger
        ('FONTSIZE', (0, 1), (-1, -1), font_size),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.white]),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ])

    total_pages = (len(rows) + rows_per_page - 1) // rows_per_page
    avail_w = sum(col_widths)

    for page_idx in range(total_pages):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, page_h - 40, title)
        c.setFont("Helvetica", 9)
        page_label = f"Page {page_idx + 1} of {total_pages}"
        c.drawString(40, page_h - 56, f"{subtitle}    ({page_label})")

        chunk = rows[page_idx * rows_per_page:(page_idx + 1) * rows_per_page]
        display = []
        for r in chunk:
            r2 = list(r)
            if (truncate_col is not None and len(r2) > truncate_col
                    and isinstance(r2[truncate_col], str)):
                r2[truncate_col] = _truncate(r2[truncate_col], truncate_chars)
            display.append(r2)

        data = [display_headers] + display
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(style)
        tw, th = table.wrapOn(c, avail_w, page_h - 100)
        table.drawOn(c, 40, page_h - 80 - th)
        c.showPage()


def render_summary_pdf_pages(c, feature_map, results, sample_columns,
                             blank_columns=None):
    """Render the two summary tables on the canvas in landscape, then
    restore portrait orientation for whatever the caller draws next.

    Caller must NOT have already drawn anything on the current page.

    The portrait restoration is in a `finally` block so a partial
    failure mid-rendering doesn't leave the canvas stuck in landscape
    and corrupt the per-match pages that follow.
    """
    landscape_size = landscape(letter)
    lw, lh = landscape_size
    portrait_size = letter

    avail_w = lw - 80  # left/right margins of 40

    c.setPageSize(landscape_size)
    try:
        # ---- Table 1: Feature Detection Summary ----
        feat_headers, feat_rows = build_feature_summary(
            feature_map, sample_columns, blank_columns
        )
        n_samples = len(sample_columns or [])
        feat_subtitle = (
            f"{len(feat_rows)} features. Detection frequency = % of "
            f"{n_samples} sample column(s) with abundance > 0. "
            f"Blank columns are echoed but excluded from the statistic."
        )
        # Build display headers: short labels for the fixed columns, then
        # one column per blank/sample with the abundance prefix stripped
        # so the column header is just the sample name.
        n_fixed = len(_FEATURE_PDF_HEADERS_FIXED)  # number of stat columns
        sample_cols_in_table = feat_headers[n_fixed:]  # "Abundance_<name>"
        sample_display = [h.replace("Abundance_", "") for h in sample_cols_in_table]
        feat_display_headers = list(_FEATURE_PDF_HEADERS_FIXED) + sample_display
        # Proportional widths: fixed columns use defined weights, sample
        # columns share the remaining width equally.
        n_samples_in_table = len(sample_cols_in_table)
        sample_weight = 1.0
        feat_weights = (list(_FEATURE_FIXED_COL_WEIGHTS)
                        + [sample_weight] * n_samples_in_table)
        feat_widths = _proportional_widths(feat_weights, avail_w)
        _draw_table_paginated(
            c, lw, lh,
            "Feature Detection Summary",
            feat_subtitle,
            feat_display_headers, feat_rows,
            col_widths=feat_widths,
            font_size=6, rows_per_page=36,
        )

        # ---- Table 2: Match Summary ----
        _, match_rows = build_match_summary(results, feature_map)
        match_subtitle = (
            f"{len(match_rows)} library match(es). One row per (feature, "
            f"candidate) pair. RHRMF reads N/A for high-res library entries."
        )
        match_widths = _proportional_widths(_MATCH_COL_WEIGHTS, avail_w)
        _draw_table_paginated(
            c, lw, lh,
            "Match Summary",
            match_subtitle,
            _MATCH_PDF_HEADERS, match_rows,
            col_widths=match_widths,
            font_size=7, rows_per_page=30,
            truncate_col=2, truncate_chars=36,
        )
    finally:
        # Always return the canvas to portrait so the caller's
        # per-match pages render at the expected size, even if a table
        # render raised partway through.
        c.setPageSize(portrait_size)
