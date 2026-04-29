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


def _draw_table_paginated(c, page_w, page_h, title, subtitle, headers,
                          rows, font_size=7, rows_per_page=32,
                          max_compound_chars=40):
    """Draw a table across as many pages as needed, calling showPage()
    after each page. Truncates the second column (typically a name) to
    keep the table from blowing up horizontally."""
    if not rows:
        # Still emit a page so the user knows the table was attempted.
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, page_h - 50, title)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, page_h - 70, "(no rows)")
        c.showPage()
        return

    # Compute uniform column widths from the available landscape width.
    avail_w = page_w - 80
    n_cols = len(headers)
    col_w = avail_w / n_cols

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.white]),
    ])

    total_pages = (len(rows) + rows_per_page - 1) // rows_per_page

    for page_idx in range(total_pages):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, page_h - 40, title)
        c.setFont("Helvetica", 9)
        page_label = f"Page {page_idx + 1} of {total_pages}"
        c.drawString(40, page_h - 56, f"{subtitle}    ({page_label})")

        chunk = rows[page_idx * rows_per_page:(page_idx + 1) * rows_per_page]
        # Truncate Compound_Name (col index 2) so a long IUPAC name
        # doesn't push everything else off the page.
        display = []
        for r in chunk:
            r2 = list(r)
            if len(r2) > 2 and isinstance(r2[2], str):
                r2[2] = _truncate(r2[2], max_compound_chars)
            display.append(r2)

        data = [headers] + display
        table = Table(data, colWidths=[col_w] * n_cols, repeatRows=1)
        table.setStyle(style)
        tw, th = table.wrapOn(c, avail_w, page_h - 100)
        table.drawOn(c, 40, page_h - 80 - th)
        c.showPage()


def render_summary_pdf_pages(c, feature_map, results, sample_columns,
                             blank_columns=None):
    """Render the two summary tables on the canvas in landscape, then
    restore portrait orientation for whatever the caller draws next.

    Caller must NOT have already drawn anything on the current page.
    """
    landscape_size = landscape(letter)
    lw, lh = landscape_size
    portrait_size = letter

    c.setPageSize(landscape_size)

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
    _draw_table_paginated(
        c, lw, lh,
        "Feature Detection Summary",
        feat_subtitle,
        feat_headers, feat_rows,
        font_size=6, rows_per_page=36,
    )

    # ---- Table 2: Match Summary ----
    match_headers, match_rows = build_match_summary(results, feature_map)
    match_subtitle = (
        f"{len(match_rows)} library match(es). One row per (feature, "
        f"candidate) pair. RHRMF reads N/A for high-res library entries."
    )
    _draw_table_paginated(
        c, lw, lh,
        "Match Summary",
        match_subtitle,
        match_headers, match_rows,
        font_size=7, rows_per_page=30,
    )

    # Restore portrait so the per-match detail pages render normally.
    c.setPageSize(portrait_size)
