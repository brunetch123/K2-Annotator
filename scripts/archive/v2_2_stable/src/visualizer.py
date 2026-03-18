import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import pubchempy as pcp
import os
import requests
import numpy as np
from src.epa_client import EpaClient

class Visualizer:
    def __init__(self, temp_dir="temp_images", api_key=None):
        """
        api_key: The EPA CCTE API key passed from the main app.
        """
        self.temp_dir = temp_dir
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        # Initialize EPA Client with the dynamic key
        self.epa = EpaClient(api_key)

    # --- Plotting ---
    def create_mirror_plot(self, feat_spectrum, lib_spectrum, title, filename):
        save_path = os.path.join(self.temp_dir, filename)
        
        def normalize(peaks):
            if not peaks: return [], []
            max_i = max(i for m, i in peaks)
            return [m for m, i in peaks], [(i/max_i)*100 for m, i in peaks]

        fmz, fint = normalize(feat_spectrum)
        lmz, lint = normalize(lib_spectrum)
        lint_neg = [-x for x in lint]
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.vlines(fmz, 0, fint, color='#1f77b4', label='Feature (Exp)', linewidth=1.5)
        ax.vlines(lmz, 0, lint_neg, color='#d62728', label='Library (Ref)', linewidth=1.5)
        ax.axhline(0, color='black', linewidth=1.0)
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel("m/z", fontsize=10)
        ax.set_ylabel("Relative Intensity (%)", fontsize=10)
        ax.set_ylim(-110, 110)
        
        ticks = [-100, -50, 0, 50, 100]
        ax.set_yticks(ticks)
        ax.set_yticklabels([str(abs(t)) for t in ticks])
        
        ax.legend(loc='upper right', fontsize='medium')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    def create_volcano_plot(self, features, title, filename):
        """
        Creates a volcano plot for all features.
        features: list of Feature objects with .stats
        """
        save_path = os.path.join(self.temp_dir, filename)
        
        log2fc = []
        neg_log10p = []
        names = []
        
        for f in features:
            if hasattr(f, 'stats') and f.stats.get('comparisons'):
                comp = f.stats['comparisons'][0]
                log2fc.append(comp['log2fc'])
                p = comp['p']
                neg_log10p.append(-np.log10(p) if p > 0 else 0)
                names.append(getattr(f, 'name', str(f.id)))

        if not log2fc: return None

        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Color points by significance
        colors = []
        for lfc, p_val in zip(log2fc, neg_log10p):
            if p_val > 1.3 and abs(lfc) > 1: # p < 0.05 and |FC| > 2
                colors.append('red')
            else:
                colors.append('gray')

        ax.scatter(log2fc, neg_log10p, c=colors, alpha=0.5, edgecolors='none')
        
        ax.axhline(1.3, color='blue', linestyle='--', alpha=0.5) # p = 0.05
        ax.axvline(1, color='blue', linestyle='--', alpha=0.5)  # FC = 2
        ax.axvline(-1, color='blue', linestyle='--', alpha=0.5) # FC = 0.5
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel("log2(Fold Change)", fontsize=10)
        ax.set_ylabel("-log10(p-value)", fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    # --- Structure ---
    def get_structure_image(self, inchikey, name, filename):
        save_path = os.path.join(self.temp_dir, filename)
        if os.path.exists(save_path): return save_path

        cid = None
        try:
            if inchikey and len(inchikey) > 5:
                res = pcp.get_compounds(inchikey, 'inchikey')
                if res: cid = res[0].cid
            if not cid and name:
                res = pcp.get_compounds(name, 'name')
                if res: cid = res[0].cid
            if cid:
                # Use direct REST API for high-resolution (large) image
                url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=large"
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        with open(save_path, 'wb') as f:
                            f.write(r.content)
                        return save_path
                except:
                    pass
                
                # Fallback to pubchempy default
                pcp.download('PNG', save_path, cid, overwrite=True)
                return save_path
        except:
            pass
        return None

    # --- Hazards ---
    def get_hazard_matrix(self, inchikey, name, cas):
        matrix = {
            "Carcinogenicity": 0, "Mutagenicity": 0, "Reprotoxicity": 0,
            "Acute Toxicity": 0, "Organ Damage": 0, "Environmental": 0
        }
        summary_text = []
        epa_url = f"https://comptox.epa.gov/dashboard/search/details?search={cas}" if cas else "https://comptox.epa.gov/dashboard/"
        
        # 1. Try EPA First (if key exists)
        if self.epa.api_key:
            dtxsid = None
            if cas: dtxsid = self.epa.search_dtxsid(cas)
            if not dtxsid and name: dtxsid = self.epa.search_dtxsid(name)
            
            if dtxsid:
                epa_url = f"https://comptox.epa.gov/dashboard/chemical/details/{dtxsid}"
                epa_matrix = self.epa.get_hazard_data(dtxsid)
                if epa_matrix:
                    return epa_matrix, ["Source: EPA CCTE"], epa_url

        # 2. PubChem Fallback
        cid = None
        try:
            if inchikey: 
                c = pcp.get_compounds(inchikey, 'inchikey')
                if c: cid = c[0].cid
            if not cid and name:
                c = pcp.get_compounds(name, 'name')
                if c: cid = c[0].cid
            
            if not cid: return matrix, ["No Data"], epa_url

            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification"
            r = requests.get(url, timeout=5)
            data = r.json()
            
            h_codes = set()
            def extract_codes(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "StringWithMarkup":
                            for item in v:
                                txt = item.get("String", "")
                                if txt.startswith("H") and txt[1:4].isdigit():
                                    h_codes.add(int(txt[1:4]))
                        elif isinstance(v, (dict, list)):
                            extract_codes(v)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_codes(item)

            extract_codes(data)
            
            for h in h_codes:
                if h in [350, 351]: matrix["Carcinogenicity"] = 3 if h == 350 else 2
                if h in [340, 341]: matrix["Mutagenicity"] = 3 if h == 340 else 2
                if h in [360, 361, 362]: matrix["Reprotoxicity"] = 3 if h == 360 else 2
                if h in [300, 310, 330]: matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], 3)
                elif h in [301, 311, 331]: matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], 2)
                if h in [370, 372]: matrix["Organ Damage"] = 3
                elif h in [371, 373]: matrix["Organ Damage"] = max(matrix["Organ Damage"], 2)
                if h >= 400: matrix["Environmental"] = 2

            if any(v > 0 for v in matrix.values()):
                if matrix["Carcinogenicity"] > 0: summary_text.append("Carcinogen")
                if matrix["Mutagenicity"] > 0: summary_text.append("Mutagen")
                if matrix["Reprotoxicity"] > 0: summary_text.append("Reprotoxic")
                if matrix["Acute Toxicity"] == 3: summary_text.append("Fatal")
                if matrix["Organ Damage"] > 0: summary_text.append("Organ Damage")
            else:
                summary_text.append("No GHS Data")

        except Exception:
            summary_text = ["Data Fetch Error"]
            
        return matrix, summary_text[:4], epa_url