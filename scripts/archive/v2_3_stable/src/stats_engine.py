import numpy as np
import pandas as pd
from scipy import stats

class StatsEngine:
    """Handles group statistics for GC-MS features"""

    def __init__(self, sample_grouping):
        """
        sample_grouping: dict {sample_name: {'type': 'Sample'/'Blank', 'group': 'Group1'}}
        """
        self.grouping = sample_grouping

    def calculate_stats(self, features):
        """
        Calculate statistics for all features.
        Adds 'stats' attribute to each feature.
        """
        # Get list of unique groups (excluding Blanks if needed, but usually we compare Sample groups)
        groups = {}
        for name, info in self.grouping.items():
            if info['type'] == 'Sample':
                g = info['group']
                if g not in groups:
                    groups[g] = []
                groups[g].append(name)

        group_names = sorted(list(groups.keys()))
        
        for feat in features:
            feat_stats = {
                'group_means': {},
                'group_stds': {},
                'comparisons': [] # list of {group_a, group_b, fold_change, p_value}
            }

            # 1. Calculate Group Stats
            group_data = {}
            for g_name, s_names in groups.items():
                vals = [feat.abundances.get(s_name, 0.0) for s_name in s_names]
                
                group_data[g_name] = vals
                feat_stats['group_means'][g_name] = np.mean(vals) if vals else 0.0
                feat_stats['group_stds'][g_name] = np.std(vals, ddof=1) if len(vals) > 1 else 0.0

            # 2. Pairwise Comparisons (if exactly 2 groups, otherwise maybe ANOVA)
            if len(group_names) == 2:
                g1, g2 = group_names
                v1 = group_data[g1]
                v2 = group_data[g2]
                
                fc = (np.mean(v2) / np.mean(v1)) if np.mean(v1) > 0 else 0.0
                
                # T-test
                try:
                    t_stat, p_val = stats.ttest_ind(v1, v2)
                except:
                    p_val = 1.0
                
                feat_stats['comparisons'].append({
                    'a': g1, 'b': g2,
                    'fc': fc,
                    'log2fc': np.log2(fc) if fc > 0 else 0.0,
                    'p': p_val
                })
            
            elif len(group_names) > 2:
                # ANOVA
                try:
                    data_lists = [group_data[g] for g in group_names]
                    f_stat, p_val = stats.f_oneway(*data_lists)
                except:
                    p_val = 1.0
                
                feat_stats['anova_p'] = p_val
                
                # Still do pairwise log2FC relative to first group or Control if exists
                control_group = 'Control' if 'Control' in group_names else group_names[0]
                for g in group_names:
                    if g == control_group: continue
                    v_ctrl = group_data[control_group]
                    v_curr = group_data[g]
                    fc = (np.mean(v_curr) / np.mean(v_ctrl)) if np.mean(v_ctrl) > 0 else 0.0
                    feat_stats['comparisons'].append({
                        'a': control_group, 'b': g,
                        'fc': fc,
                        'log2fc': np.log2(fc) if fc > 0 else 0.0,
                        'p': p_val # ANOVA P as a proxy or do post-hoc? Let's stick to simple for now.
                    })

            feat.stats = feat_stats
        
        return features
