import pandas as pd
import numpy as np
import re
import os

class Feature:
    """
    Represents a single MS-DIAL alignment feature.
    """
    def __init__(self, alignment_id, retention_time, retention_index):
        self.id = int(alignment_id)
        self.rt = float(retention_time) if retention_time else 0.0
        self.ri = float(retention_index) if retention_index else 0.0
        
        # Data
        self.abundances = {} # {sample_name: float}
        self.spectrum = []   # List of (mz, intensity) tuples
        
        # Filtering Results
        self.bff_threshold = 0.0
        self.passed_bff = False
        self.max_sample_abundance = 0.0

    def calculate_bff(self, blank_cols, sample_cols, c_factor=5.0):
        """
        Calculates Blank Feature Filtering (BFF) threshold.
        Threshold = c * (Mean_Blanks + 3 * Std_Blanks)
        Passes if Max_Sample_Abundance > Threshold
        """
        # 1. Get Blank Statistics
        blank_vals = [self.abundances.get(b, 0.0) for b in blank_cols]
        
        if not blank_vals:
            # No blanks? Assume 0 background
            mean_b = 0.0
            std_b = 0.0
        else:
            mean_b = np.mean(blank_vals)
            # ddof=1 for Sample Std Dev (requires at least 2 blanks)
            std_b = np.std(blank_vals, ddof=1) if len(blank_vals) > 1 else 0.0

        # 2. Calculate Threshold
        self.bff_threshold = c_factor * (mean_b + (3 * std_b))
        
        # 3. Check Samples
        sample_vals = [self.abundances.get(s, 0.0) for s in sample_cols]
        self.max_sample_abundance = max(sample_vals) if sample_vals else 0.0
        
        # 4. Result
        if self.max_sample_abundance > self.bff_threshold:
            self.passed_bff = True
        else:
            self.passed_bff = False
    
    def __repr__(self):
        return f"<Feature ID={self.id} RT={self.rt:.2f} RI={self.ri:.1f} Peaks={len(self.spectrum)}>"

class MsDialParser:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.features = {} 
        self.sample_columns = []
        self.blank_columns = []
        
        # Metadata columns to explicitly ignore during abundance parsing
        self.ignore_cols = {
            "Alignment ID", "Average Rt(min)", "Average RI", "Quant mass", 
            "Metabolite name", "Fill %", "Reference RT", "Reference RI", 
            "Formula", "Ontology", "INCHIKEY", "SMILES", "Annotation tag (VS1.0)", 
            "RT/RI matched", "EI-MS matched", "Comment", "Manually modified for quantification",
            "Manually modified for annotation", "Total score", "RT similarity", "RI similarity",
            "Total spectrum similarity", "Dot product", "Reverse dot product", "Fragment presence %",
            "S/N average", "Spectrum reference file name", "EI spectrum", "Class", "File type",
            "Injection order", "Batch ID"
        }
        
    def parse_area_file(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r') as f:
            lines = f.readlines()

        if len(lines) < 5:
            print(f"Warning: {filename} has fewer than 5 lines. Skipping.")
            return

        # Row 1 (Index 1) is File Type (Blank vs Sample)
        # We use rstrip to keep leading tabs for alignment
        file_type_row = lines[1].rstrip('\n').split('\t')
        # Row 4 (Index 4) is Headers
        header_row = lines[4].rstrip('\n').split('\t')
        
        self.blank_columns = []
        self.sample_columns = []

        # Map columns
        for i, col_name in enumerate(header_row):
            if col_name in self.ignore_cols: continue
            
            if i < len(file_type_row):
                f_type = file_type_row[i]
                if f_type == 'Blank':
                    self.blank_columns.append(col_name)
                elif f_type == 'Sample':
                    self.sample_columns.append(col_name)

        print(f"Parsed Structure: Found {len(self.blank_columns)} Blanks and {len(self.sample_columns)} Samples.")

        # Load Data skipping metadata rows
        try:
            df = pd.read_csv(filepath, sep='\t', header=4)
        except Exception as e:
            print(f"Error reading {filename} with pandas: {e}")
            return
        
        for _, row in df.iterrows():
            # ID
            try:
                # Check if 'Alignment ID' exists and is valid
                if 'Alignment ID' not in row or pd.isna(row['Alignment ID']):
                    continue
                align_id = int(row['Alignment ID'])
            except (ValueError, TypeError):
                continue # Skip bad rows

            # RT/RI
            rt = row.get('Average Rt(min)', 0.0)
            ri_raw = row.get('Average RI', 0.0)
            ri = 0.0
            try:
                if not pd.isna(ri_raw) and ri_raw != 'null':
                    ri = float(ri_raw)
            except ValueError:
                ri = 0.0
                
            feat = Feature(align_id, rt, ri)
            
            # Extract abundances
            all_cols = self.blank_columns + self.sample_columns
            for col in all_cols:
                if col in row:
                    val = row[col]
                    # Robust Float Conversion
                    try:
                        if pd.isna(val) or val == 'null' or val == '' or isinstance(val, str):
                             # Try parsing string numbers, default to 0.0 if "Unknown"
                            feat.abundances[col] = float(val)
                        else:
                            feat.abundances[col] = float(val)
                    except (ValueError, TypeError):
                        feat.abundances[col] = 0.0
            
            self.features[feat.id] = feat
            
        print(f"Initialized {len(self.features)} features from Area file.")

    def parse_msp_file(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        current_id = None
        current_spectrum = []
        
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                if line.startswith('NAME:'):
                    if current_id is not None and current_id in self.features:
                        self.features[current_id].spectrum = current_spectrum
                    current_spectrum = []
                    
                    match = re.search(r'ID=(\d+)', line)
                    if match:
                        current_id = int(match.group(1))
                    else:
                        current_id = None
                        
                elif line[0].isdigit():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intent = float(parts[1])
                            current_spectrum.append((mz, intent))
                        except ValueError:
                            pass
        
        if current_id is not None and current_id in self.features:
            self.features[current_id].spectrum = current_spectrum
            
        print("Spectra parsing complete.")

    def get_feature_list(self):
        return list(self.features.values())