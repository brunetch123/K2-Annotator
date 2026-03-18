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

    def create_volcano_plot(self, features, title, filename, p_threshold=0.05, fc_threshold=2.0):
        """
        Creates a volcano plot for all features.
        features: list of Feature objects with .stats
        """
        save_path = os.path.join(self.temp_dir, filename)
        
        log2fc = []
        neg_log10p = []
        names = []
        
        lfc_thresh = np.log2(fc_threshold)
        p_thresh_log = -np.log10(p_threshold)

        for f in features:
            if hasattr(f, 'stats') and f.stats.get('comparisons'):
                comp = f.stats['comparisons'][0]
                lfc = comp['log2fc']
                p = comp['p']
                
                log2fc.append(lfc)
                neg_log10p.append(-np.log10(p) if p > 0 else 0)
                names.append(getattr(f, 'name', str(f.id)))

        if not log2fc: return None

        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Color points by significance
        colors = []
        for lfc, p_val in zip(log2fc, neg_log10p):
            if p_val > p_thresh_log and abs(lfc) > lfc_thresh:
                colors.append('red')
            else:
                colors.append('gray')

        ax.scatter(log2fc, neg_log10p, c=colors, alpha=0.5, edgecolors='none', s=20)
        
        ax.axhline(p_thresh_log, color='blue', linestyle='--', alpha=0.5)
        ax.axvline(lfc_thresh, color='blue', linestyle='--', alpha=0.5)
        ax.axvline(-lfc_thresh, color='blue', linestyle='--', alpha=0.5)
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel("log2(Fold Change)", fontsize=10)
        ax.set_ylabel("-log10(p-value)", fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    def create_pca_plot(self, pca_results, grouping, title, filename):
        """
        Creates a PCA score plot.
        pca_results: dict from StatsEngine._calculate_pca
        grouping: dict of sample groupings
        """
        if not pca_results: return None
        save_path = os.path.join(self.temp_dir, filename)
        
        coords = np.array(pca_results['coords'])
        samples = pca_results['samples']
        var = pca_results['variance_ratio']
        
        if coords.shape[1] < 2: return None
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Color by group
        unique_groups = sorted(list(set(grouping[s]['group'] for s in samples)))
        colors = plt.cm.get_cmap('tab10', len(unique_groups))
        group_to_color = {g: colors(i) for i, g in enumerate(unique_groups)}
        
        for i, sample in enumerate(samples):
            group = grouping[sample]['group']
            ax.scatter(coords[i, 0], coords[i, 1], color=group_to_color[group], label=group if group not in ax.get_legend_handles_labels()[1] else "", s=50)
            ax.text(coords[i, 0], coords[i, 1], sample, fontsize=8, alpha=0.7)

        ax.set_xlabel(f"PC1 ({var[0]*100:.1f}%)")
        ax.set_ylabel(f"PC2 ({var[1]*100:.1f}%)")
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    def create_heatmap(self, features, samples, title, filename):
        """
        Creates a heatmap of top features.
        """
        save_path = os.path.join(self.temp_dir, filename)
        
        # Sort features by significance (ANOVA p or first comparison p)
        def get_p(f):
            if hasattr(f, 'stats'):
                return f.stats.get('anova_p', f.stats['comparisons'][0]['p'] if f.stats['comparisons'] else 1.0)
            return 1.0
        
        sorted_features = sorted(features, key=get_p)[:50] # Top 50
        if not sorted_features: return None
        
        data = []
        labels = []
        for f in sorted_features:
            row = [f.abundances.get(s, 0.0) for s in samples]
            # Log transform and scale
            row = np.log10(np.array(row) + 1)
            if np.std(row) > 0:
                row = (row - np.mean(row)) / np.std(row)
            data.append(row)
            labels.append(getattr(f, 'name', str(f.id))[:30])
        
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(data, aspect='auto', cmap='RdBu_r')
        
        ax.set_xticks(np.arange(len(samples)))
        ax.set_xticklabels(samples, rotation=45, ha='right', fontsize=8)
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        
        plt.colorbar(im, label='Z-score (log10 abundance)')
        ax.set_title(title, fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    def create_feature_boxplot(self, feature, groups, title, filename):
        """
        Boxplot for a single feature across groups.
        """
        save_path = os.path.join(self.temp_dir, filename)
        
        data_to_plot = []
        labels = []
        
        for g_name in sorted(groups.keys()):
            s_names = groups[g_name]
            vals = [feature.abundances.get(s, 0.0) for s in s_names]
            data_to_plot.append(vals)
            labels.append(g_name)
            
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.boxplot(data_to_plot, labels=labels)
        
        # Add jitter
        for i, vals in enumerate(data_to_plot):
            x = np.random.normal(i + 1, 0.04, size=len(vals))
            ax.scatter(x, vals, alpha=0.6, s=20)
            
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_ylabel("Abundance")
        
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