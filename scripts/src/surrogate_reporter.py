"""
Surrogate Standard Recovery Reporter
v3.0.0 - Generates CSV, PDF, and GUI output for surrogate recovery data

This module provides functionality for:
- Generating CSV files with abundance, recovery, and match info tables
- Adding surrogate recovery pages to PDF reports
- Providing formatted data for GUI display
"""

import csv
import os
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas
    from src.surrogate_analyzer import SurrogateAnalyzer


class SurrogateReporter:
    """
    Generates reports for surrogate standard recovery analysis.
    
    Outputs:
    - CSV file with three sections (abundances, recoveries, match info)
    - PDF pages for inclusion in main report
    - Formatted data for GUI display
    """
    
    def __init__(self, analyzer: 'SurrogateAnalyzer', output_dir: str, project_name: str = ""):
        """
        Initialize the surrogate reporter.
        
        Args:
            analyzer: SurrogateAnalyzer instance with completed analysis
            output_dir: Directory for output files
            project_name: Project name for file naming
        """
        self.analyzer = analyzer
        self.output_dir = output_dir
        self.project_name = project_name or "Surrogate"
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def generate_csv(self, filename: Optional[str] = None) -> str:
        """
        Generate CSV file with surrogate recovery data.
        
        The CSV contains three sections separated by blank rows:
        1. Normalized Abundances (with group assignments)
        2. % Recoveries (samples only, with avg/stddev)
        3. Match Information (spectral matching details)
        
        Args:
            filename: Optional custom filename (default: SurrogateRecoveries_{project}_{date}.csv)
            
        Returns:
            Path to generated CSV file
        """
        if filename is None:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"SurrogateRecoveries_{self.project_name}_{date_str}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Get table data
        abundance_data = self.analyzer.get_abundance_table()
        recovery_data = self.analyzer.get_recovery_table()
        match_data = self.analyzer.get_match_info_table()
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # === Section 1: Normalized Abundances ===
            writer.writerow(["=== NORMALIZED ABUNDANCES ==="])
            writer.writerow([])
            
            # Group row
            writer.writerow(abundance_data['group_row'])
            
            # Header row
            writer.writerow(abundance_data['headers'])
            
            # Data rows
            for row in abundance_data['rows']:
                csv_row = [row.get(h, '') for h in abundance_data['headers']]
                writer.writerow(csv_row)
            
            writer.writerow([])
            writer.writerow([])
            
            # === Section 2: % Recoveries ===
            writer.writerow(["=== PERCENT RECOVERIES ==="])
            writer.writerow([])
            
            # Header row
            writer.writerow(recovery_data['headers'])
            
            # Data rows
            for row in recovery_data['rows']:
                csv_row = [row.get(h, '') for h in recovery_data['headers']]
                writer.writerow(csv_row)
            
            writer.writerow([])
            writer.writerow([])
            
            # === Section 3: Match Information ===
            writer.writerow(["=== MATCH INFORMATION ==="])
            writer.writerow([])
            
            # Header row
            writer.writerow(match_data['headers'])
            
            # Data rows
            for row in match_data['rows']:
                csv_row = [row.get(h, '') for h in match_data['headers']]
                writer.writerow(csv_row)
        
        print(f"Surrogate CSV Report generated: {filepath}")
        return filepath
    
    def generate_pdf_pages(self, canvas: 'Canvas', width: float, height: float) -> int:
        """
        Add surrogate recovery pages to an existing PDF report.
        
        Args:
            canvas: ReportLab canvas object
            width: Page width in points
            height: Page height in points
            
        Returns:
            Number of pages added
        """
        pages_added = 0
        
        # Get table data
        recovery_data = self.analyzer.get_recovery_table()
        match_data = self.analyzer.get_match_info_table()
        
        # === Page 1: Recovery Summary ===
        self._draw_recovery_page(canvas, width, height, recovery_data)
        canvas.showPage()
        pages_added += 1
        
        # === Page 2: Match Details ===
        self._draw_match_page(canvas, width, height, match_data)
        canvas.showPage()
        pages_added += 1
        
        return pages_added
    
    def _draw_recovery_page(self, c: 'Canvas', width: float, height: float, 
                            recovery_data: Dict[str, Any]) -> None:
        """Draw the recovery summary page."""
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Surrogate Standard Recovery Summary")
        c.setStrokeColor(colors.gray)
        c.line(50, height - 60, width - 50, height - 60)
        
        # Table setup
        cursor_y = height - 100
        line_height = 18
        col_widths = self._calculate_column_widths(recovery_data['headers'], width - 100)
        
        # Header row
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.HexColor('#2c3e50'))
        x = 50
        for i, header in enumerate(recovery_data['headers']):
            # Truncate long headers
            display_header = header[:12] + '..' if len(header) > 14 else header
            c.drawString(x, cursor_y, display_header)
            x += col_widths[i]
        
        cursor_y -= line_height
        c.setStrokeColor(colors.gray)
        c.line(50, cursor_y + 12, width - 50, cursor_y + 12)
        
        # Data rows
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        
        for row_idx, row in enumerate(recovery_data['rows']):
            if cursor_y < 80:
                # Need new page
                c.showPage()
                cursor_y = height - 50
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, cursor_y, "Surrogate Recovery Summary (continued)")
                cursor_y -= 30
                c.setFont("Helvetica", 8)
            
            # Alternate row background
            if row_idx % 2 == 0:
                c.setFillColor(colors.HexColor('#f8f9fa'))
                c.rect(50, cursor_y - 2, width - 100, line_height, fill=1, stroke=0)
            
            c.setFillColor(colors.black)
            x = 50
            for i, header in enumerate(recovery_data['headers']):
                val = row.get(header, '')
                # Color-code recoveries
                if header not in ['Compound', 'Average', 'StdDev'] and isinstance(val, (int, float)):
                    if val < 70 or val > 130:
                        c.setFillColor(colors.red)
                    elif val < 80 or val > 120:
                        c.setFillColor(colors.orange)
                    else:
                        c.setFillColor(colors.darkgreen)
                
                display_val = str(val)[:15] if val else ''
                c.drawString(x, cursor_y, display_val)
                c.setFillColor(colors.black)
                x += col_widths[i]
            
            cursor_y -= line_height
        
        # Footer note
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.gray)
        c.drawString(50, 40, "Recovery values: Green = 80-120%, Orange = 70-80% or 120-130%, Red = <70% or >130%")
    
    def _draw_match_page(self, c: 'Canvas', width: float, height: float,
                         match_data: Dict[str, Any]) -> None:
        """Draw the match information page."""
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Surrogate Standard Match Details")
        c.setStrokeColor(colors.gray)
        c.line(50, height - 60, width - 50, height - 60)
        
        # Table setup
        cursor_y = height - 100
        line_height = 18
        col_widths = self._calculate_column_widths(match_data['headers'], width - 100)
        
        # Header row
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.HexColor('#2c3e50'))
        x = 50
        for i, header in enumerate(match_data['headers']):
            display_header = header[:10] + '..' if len(header) > 12 else header
            c.drawString(x, cursor_y, display_header)
            x += col_widths[i]
        
        cursor_y -= line_height
        c.setStrokeColor(colors.gray)
        c.line(50, cursor_y + 12, width - 50, cursor_y + 12)
        
        # Data rows
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        
        for row_idx, row in enumerate(match_data['rows']):
            if cursor_y < 80:
                c.showPage()
                cursor_y = height - 50
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, cursor_y, "Surrogate Match Details (continued)")
                cursor_y -= 30
                c.setFont("Helvetica", 8)
            
            # Alternate row background
            if row_idx % 2 == 0:
                c.setFillColor(colors.HexColor('#f8f9fa'))
                c.rect(50, cursor_y - 2, width - 100, line_height, fill=1, stroke=0)
            
            # Check if no match
            is_no_match = row.get('Feature_ID') == 'No Match'
            
            if is_no_match:
                c.setFillColor(colors.red)
            else:
                c.setFillColor(colors.black)
            
            x = 50
            for i, header in enumerate(match_data['headers']):
                val = row.get(header, '')
                display_val = str(val)[:12] if val else ''
                c.drawString(x, cursor_y, display_val)
                x += col_widths[i]
            
            c.setFillColor(colors.black)
            cursor_y -= line_height
    
    def _calculate_column_widths(self, headers: list, total_width: float) -> list:
        """Calculate column widths based on header lengths."""
        # Weight by header length, with minimum width
        min_width = 45
        weights = [max(len(h), 5) for h in headers]
        total_weight = sum(weights)
        
        widths = []
        for w in weights:
            width = max(min_width, (w / total_weight) * total_width)
            widths.append(width)
        
        # Adjust to fit total width
        scale = total_width / sum(widths)
        return [w * scale for w in widths]
    
    def get_gui_data(self) -> Dict[str, Any]:
        """
        Get formatted data for GUI display.
        
        Returns:
            Dictionary with:
            - 'recovery_summary': Recovery table data
            - 'match_details': Match info table data
            - 'abundance_data': Abundance table data
            - 'summary_stats': Overall summary statistics
        """
        recovery_data = self.analyzer.get_recovery_table()
        match_data = self.analyzer.get_match_info_table()
        abundance_data = self.analyzer.get_abundance_table()
        
        # Calculate summary statistics
        total_compounds = len(self.analyzer.matches)
        matched_compounds = sum(1 for m in self.analyzer.matches.values() if m is not None)
        
        # Calculate average recovery across all compounds/samples
        all_recoveries = []
        for compound_recoveries in self.analyzer.recoveries.values():
            for val in compound_recoveries.values():
                if isinstance(val, (int, float)):
                    all_recoveries.append(val)
        
        if all_recoveries:
            import statistics
            avg_recovery = round(statistics.mean(all_recoveries), 1)
            std_recovery = round(statistics.stdev(all_recoveries), 1) if len(all_recoveries) > 1 else 0
        else:
            avg_recovery = None
            std_recovery = None
        
        return {
            'recovery_summary': recovery_data,
            'match_details': match_data,
            'abundance_data': abundance_data,
            'summary_stats': {
                'total_compounds': total_compounds,
                'matched_compounds': matched_compounds,
                'match_rate': round(matched_compounds / total_compounds * 100, 1) if total_compounds > 0 else 0,
                'average_recovery': avg_recovery,
                'recovery_stddev': std_recovery
            }
        }
