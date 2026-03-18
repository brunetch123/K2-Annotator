import csv
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from src.visualizer import Visualizer

class ReportGenerator:
    def __init__(self, results, features, output_dir="results", api_key=None, sample_columns=None):
        self.results = results
        self.feature_map = {f.id: f for f in features}
        self.output_dir = output_dir
        self.sample_columns = sample_columns or []  # List of sample column names for abundance export
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.viz = Visualizer(os.path.join(output_dir, "temp_assets"), api_key=api_key)

    def generate_csv(self, filename="Level2_Matches.csv"):
        filepath = os.path.join(self.output_dir, filename)

        # Base headers
        headers = [
            "Feature ID", "RT", "RI_Exp", "RI_Lib", "RI_Err", "RI_Err%",
            "Compound_Name", "Formula", "HighRes?", "RHRMF", "RevDot", "FwdDot",
            "MaxAbundance", "BFF_Threshold",
            "Log2FC", "P-value",
            "CAS", "InChIKey",
            "Source", "Instrument", "Comments",
            "EPA_Link", "Hazard_Summary"
        ]

        # Add sample abundance columns
        for sample in self.sample_columns:
            headers.append(f"Abundance_{sample}")

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for feat_id, candidates in self.results.items():
                orig = self.feature_map.get(feat_id)
                if not orig: continue

                for cand in candidates:
                    comp = cand.compound
                    meta = comp.metadata

                    cas = meta.get('cas', '')
                    inchikey = meta.get('inchikey', '')

                    _, summary, epa_link = self.viz.get_hazard_matrix(inchikey, comp.name, cas)

                    ri_pct = (cand.ri_error / orig.ri * 100) if orig.ri else 0

                    # Extract stats
                    log2fc = "N/A"
                    p_val = "N/A"
                    if hasattr(orig, 'stats') and orig.stats.get('comparisons'):
                        comp_data = orig.stats['comparisons'][0] # Take first comparison
                        log2fc = f"{comp_data['log2fc']:.2f}"
                        p_val = f"{comp_data['p']:.4f}"

                    row = [
                        feat_id,
                        f"{orig.rt:.3f}",
                        f"{orig.ri:.1f}",
                        f"{comp.ri:.1f}",
                        f"{cand.ri_error:.2f}",
                        f"{ri_pct:.2f}",
                        comp.name,
                        comp.formula,
                        "Yes" if cand.is_high_res_match else "No",
                        f"{cand.rhrmf_score:.1f}",
                        cand.reverse_dot_product,
                        cand.dot_product,
                        f"{orig.max_sample_abundance:.0f}",
                        f"{orig.bff_threshold:.0f}",
                        log2fc,
                        p_val,
                        cas,
                        inchikey,
                        meta.get('source', ''),
                        meta.get('instrument_type', ''),
                        meta.get('comments_raw', ''),
                        epa_link,
                        "; ".join(summary)
                    ]

                    # Add abundance values for each sample
                    for sample in self.sample_columns:
                        abundance = orig.abundances.get(sample, 0.0)
                        row.append(f"{abundance:.2f}")

                    writer.writerow(row)

        print(f"CSV Report generated: {filepath}")
        return filepath

    def generate_pdf(self, filename="Level2_Report.pdf"):
        filepath = os.path.join(self.output_dir, filename)
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        print("Generating PDF Report...")
        
        count = 0
        
        for feat_id, candidates in self.results.items():
            orig = self.feature_map.get(feat_id)
            if not orig: continue
            
            for cand in candidates:
                comp = cand.compound
                meta = comp.metadata
                count += 1
                print(f"Processing Match {count}...", end='\r')
                
                # --- HEADER ---
                c.setFont("Helvetica-Bold", 14)
                title = comp.name[:70] + ("..." if len(comp.name)>70 else "")
                c.drawString(50, height - 50, f"Match: {title}")
                c.setStrokeColor(colors.gray)
                c.line(50, height - 60, width - 50, height - 60)
                
                # --- LEFT COL: Identifiers (Y: 700 down) ---
                cursor_y = height - 90
                line_h = 14
                
                c.setFont("Helvetica-Bold", 10)
                c.drawString(50, cursor_y, "Identity & Metadata:")
                c.setFont("Helvetica", 10)
                cursor_y -= line_h
                
                def draw_kv(label, val):
                    nonlocal cursor_y
                    c.drawString(60, cursor_y, f"{label}: {val}"[:60])
                    cursor_y -= line_h

                draw_kv("Feature ID", feat_id)
                draw_kv("Formula", comp.formula)
                draw_kv("CAS", meta.get('cas', 'N/A'))
                draw_kv("Source", meta.get('source', 'N/A'))
                draw_kv("Instrument", meta.get('instrument_type', 'N/A'))
                # Removed Ion Mode as requested
                draw_kv("Comment", meta.get('comments_raw', '')[:50])
                
                # --- RIGHT COL: Structure ---
                struct_path = self.viz.get_structure_image(
                    meta.get('inchikey'), comp.name, f"struct_{feat_id}.png"
                )
                if struct_path:
                    try:
                        # mask='auto' fixes the grey background issue with transparency
                        c.drawImage(struct_path, 400, height - 200, width=120, height=120, 
                                  preserveAspectRatio=True, mask='auto')
                    except: pass

                # --- MIDDLE BLOCK: Detailed Confidence Scores (Y: ~550) ---
                score_y = height - 260
                
                # Gray Background Box
                c.setFillColor(colors.whitesmoke)
                c.rect(50, score_y - 80, width - 100, 95, fill=1, stroke=1)
                c.setFillColor(colors.black)
                
                c.setFont("Helvetica-Bold", 11)
                c.drawString(60, score_y, "CONFIDENCE METRICS (Level 2 Criteria)")
                c.setFont("Helvetica", 9)
                
                # Row 1: RI Data
                ri_err = cand.ri_error
                ri_pct = (ri_err / orig.ri * 100) if orig.ri else 0
                row1_y = score_y - 20
                c.drawString(70, row1_y, f"Feature RI: {orig.ri:.1f}")
                c.drawString(200, row1_y, f"Library RI: {comp.ri:.1f}")
                c.drawString(330, row1_y, f"RI Error: {ri_err:.1f} ({ri_pct:.2f}%)")
                
                # Row 2: Spectral Scores
                row2_y = score_y - 35
                c.drawString(70, row2_y, f"Rev Dot Product: {cand.reverse_dot_product}")
                c.drawString(200, row2_y, f"Fwd Dot Product: {cand.dot_product}")
                res_type = "High Res" if cand.is_high_res_match else "Low Res"
                c.drawString(330, row2_y, f"Lib Type: {res_type}")
                
                # Row 3: Advanced Validations
                row3_y = score_y - 50
                rhrmf_val = "N/A" if cand.is_high_res_match else f"{cand.rhrmf_score:.1f}"
                c.drawString(70, row3_y, f"RHRMF Score: {rhrmf_val}")
                c.drawString(200, row3_y, f"Abundance: {orig.max_sample_abundance:.1e}")
                c.drawString(330, row3_y, f"BFF Thresh: {orig.bff_threshold:.1e}")

                # Row 4: Statistics (New)
                if hasattr(orig, 'stats') and orig.stats.get('comparisons'):
                    row4_y = score_y - 65
                    comp_data = orig.stats['comparisons'][0]
                    c.drawString(70, row4_y, f"Comparison: {comp_data['a']} vs {comp_data['b']}")
                    c.drawString(200, row4_y, f"Log2FC: {comp_data['log2fc']:.2f}")
                    c.drawString(330, row4_y, f"P-value: {comp_data['p']:.4f}")

                # --- HAZARD SECTION (Y: ~380) ---
                haz_y = score_y - 100
                c.setFont("Helvetica-Bold", 10)
                c.drawString(50, haz_y, "Hazard Identification:")
                
                cas_val = meta.get('cas', '')
                
                if not cas_val:
                    # No Comptox Match Case
                    c.setFont("Helvetica-Oblique", 10)
                    c.setFillColor(colors.gray)
                    c.drawString(60, haz_y - 20, "No Comptox/CAS match found. Data unavailable.")
                    c.setFillColor(colors.black)
                    # Adjust cursor for plot
                    plot_y_start = haz_y - 60
                else:
                    # Fetch Matrix
                    matrix, summary, epa_url = self.viz.get_hazard_matrix(
                        meta.get('inchikey'), comp.name, cas_val
                    )
                    
                    # Draw Badges
                    badge_x = 50
                    badge_y = haz_y - 35
                    badge_w = 80
                    badge_h = 20
                    
                    for category, level in matrix.items():
                        if level == 3: color = colors.red
                        elif level == 2: color = colors.orange
                        else: color = colors.lightgrey # Use lightgrey instead of whitesmoke for visibility
                        
                        c.setFillColor(color)
                        c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
                        
                        c.setFillColor(colors.white if level >= 2 else colors.black)
                        c.setFont("Helvetica-Bold", 7)
                        c.drawCentredString(badge_x + badge_w/2, badge_y + 6, category)
                        
                        badge_x += badge_w + 5
                        if badge_x > 500:
                            badge_x = 50
                            badge_y -= 25

                    # Link
                    c.setFillColor(colors.blue)
                    c.setFont("Helvetica", 9)
                    link_y = badge_y - 15
                    c.drawString(50, link_y, ">> View Full Data on EPA CompTox Dashboard")
                    c.linkURL(epa_url, (50, link_y, 300, link_y + 10))
                    c.setFillColor(colors.black)
                    plot_y_start = link_y - 20

                # --- MIRROR PLOT ---
                # Draw at bottom
                plot_path = self.viz.create_mirror_plot(
                    orig.spectrum, comp.spectrum, 
                    f"Spectral Comparison (Ref: {comp.name})",
                    f"plot_{feat_id}.png"
                )
                if plot_path:
                    # Dynamic placement based on hazard section height
                    # Use a fixed bottom anchor to ensure it fits
                    c.drawImage(plot_path, 50, 50, width=500, height=220, preserveAspectRatio=False)

                c.showPage()

        c.save()
        print(f"\nPDF Report saved: {filepath}")