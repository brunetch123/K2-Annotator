"""
EPA CompTox API Client using official ctx-python package
v2.9.0 - Enhanced hazard data fetching with ToxValDB, genetox, and severity scoring

This module provides a wrapper around the ctx-python package to fetch comprehensive
hazard data including:
- Quantitative toxicity values (NOAEL, LOAEL, POD, RfD)
- Ecological toxicity (LC50, LD50)
- Genetic toxicity summary
- Computed severity index
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import warnings


@dataclass
class HazardProfile:
    """Comprehensive hazard data for a chemical"""
    dtxsid: str = ""
    
    # Quantitative toxicity (human health)
    noael: Optional[float] = None  # mg/kg-day
    loael: Optional[float] = None  # mg/kg-day
    pod: Optional[float] = None    # Point of Departure mg/kg-day
    rfd: Optional[float] = None    # Reference Dose mg/kg-day
    tox_source: str = ""           # Source of toxicity data
    
    # Ecological toxicity
    lc50: Optional[float] = None   # Fish LC50 (mg/L)
    ld50: Optional[float] = None   # Oral LD50 (mg/kg)
    
    # Genetic toxicity
    genetox_positive: int = 0      # Count of positive reports
    genetox_negative: int = 0      # Count of negative reports
    genetox_ames: str = ""         # Ames test result
    
    # Computed severity (1-5 scale)
    severity_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export"""
        return {
            'Tox_NOAEL': self.noael if self.noael else '',
            'Tox_LOAEL': self.loael if self.loael else '',
            'Tox_POD': self.pod if self.pod else '',
            'Tox_RfD': self.rfd if self.rfd else '',
            'Tox_Source': self.tox_source,
            'Eco_LC50': self.lc50 if self.lc50 else '',
            'Eco_LD50': self.ld50 if self.ld50 else '',
            'Genetox_Positive': self.genetox_positive if self.genetox_positive > 0 else '',
            'Genetox_Negative': self.genetox_negative if self.genetox_negative > 0 else '',
            'Genetox_Ames': self.genetox_ames,
            'Severity_Index': self.severity_index if self.severity_index > 0 else '',
        }


class CTXClient:
    """
    Wrapper around ctx-python for EPA CompTox API access.
    
    Provides methods to:
    - Resolve CAS numbers to DTXSIDs
    - Fetch comprehensive hazard profiles including quantitative toxicity,
      ecological data, and genetic toxicity summaries
    - Compute severity indices based on toxicity thresholds
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the CTX client.
        
        Args:
            api_key: EPA CCTE API key (request from ccte_api@epa.gov)
        """
        self.api_key = api_key
        self._ctx_available = False
        self._chem = None
        self._haz = None
        
        # Try to import ctx-python
        try:
            import ctxpy as ctx
            self._chem = ctx.Chemical(x_api_key=api_key)
            self._haz = ctx.Hazard(x_api_key=api_key)
            self._ctx_available = True
        except ImportError:
            warnings.warn(
                "ctx-python not installed. Enhanced hazard data will not be available. "
                "Install with: pip install ctx-python"
            )
        except Exception as e:
            warnings.warn(f"Failed to initialize ctx-python: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if ctx-python is available and initialized"""
        return self._ctx_available
    
    def resolve_dtxsid(self, cas: str) -> Optional[str]:
        """
        Convert CAS number to DTXSID (DSSTox Substance Identifier).
        
        Args:
            cas: CAS registry number (e.g., "71-43-2")
            
        Returns:
            DTXSID string or None if not found
        """
        if not self._ctx_available or not cas:
            return None
        
        try:
            result = self._chem.search(by='equals', query=cas)
            if result is not None and not result.empty:
                return result.iloc[0].get('dtxsid')
        except Exception as e:
            # Silently fail - not all CAS numbers are in CompTox
            pass
        
        return None
    
    def get_hazard_profile(self, cas: str) -> HazardProfile:
        """
        Get comprehensive hazard data for a chemical by CAS number.
        
        Args:
            cas: CAS registry number
            
        Returns:
            HazardProfile with all available data
        """
        profile = HazardProfile()
        
        if not self._ctx_available or not cas:
            return profile
        
        # First resolve CAS to DTXSID
        dtxsid = self.resolve_dtxsid(cas)
        if not dtxsid:
            return profile
        
        profile.dtxsid = dtxsid
        
        # Fetch human toxicity values
        self._fetch_human_tox(profile, dtxsid)
        
        # Fetch ecological toxicity
        self._fetch_eco_tox(profile, dtxsid)
        
        # Fetch genetic toxicity summary
        self._fetch_genetox(profile, dtxsid)
        
        # Compute severity index
        profile.severity_index = self._compute_severity(profile)
        
        return profile
    
    def _fetch_human_tox(self, profile: HazardProfile, dtxsid: str) -> None:
        """Fetch human health toxicity values from ToxValDB"""
        try:
            human_df = self._haz.search_toxvaldb(by='human', dtxsid=dtxsid)
            
            if human_df is None or human_df.empty:
                return
            
            # Find most protective NOAEL (lowest value)
            noael_mask = human_df['toxvalType'].str.contains('NOAEL', case=False, na=False)
            if noael_mask.any():
                noael_df = human_df[noael_mask]
                noael_df = noael_df[noael_df['toxvalNumeric'].notna()]
                if not noael_df.empty:
                    min_idx = noael_df['toxvalNumeric'].idxmin()
                    profile.noael = float(noael_df.loc[min_idx, 'toxvalNumeric'])
                    profile.tox_source = str(noael_df.loc[min_idx, 'source']) if 'source' in noael_df.columns else ''
            
            # Find lowest LOAEL
            loael_mask = human_df['toxvalType'].str.contains('LOAEL', case=False, na=False)
            if loael_mask.any():
                loael_df = human_df[loael_mask]
                loael_df = loael_df[loael_df['toxvalNumeric'].notna()]
                if not loael_df.empty:
                    profile.loael = float(loael_df['toxvalNumeric'].min())
            
            # Find POD (Point of Departure)
            pod_mask = human_df['toxvalType'].str.contains('POD|BMD', case=False, na=False)
            if pod_mask.any():
                pod_df = human_df[pod_mask]
                pod_df = pod_df[pod_df['toxvalNumeric'].notna()]
                if not pod_df.empty:
                    profile.pod = float(pod_df['toxvalNumeric'].min())
            
            # Find Reference Dose (RfD)
            rfd_mask = human_df['toxvalType'].str.contains('RfD|RfC', case=False, na=False)
            if rfd_mask.any():
                rfd_df = human_df[rfd_mask]
                rfd_df = rfd_df[rfd_df['toxvalNumeric'].notna()]
                if not rfd_df.empty:
                    profile.rfd = float(rfd_df['toxvalNumeric'].min())
                    # RfD source is often more authoritative
                    if 'source' in rfd_df.columns:
                        min_idx = rfd_df['toxvalNumeric'].idxmin()
                        profile.tox_source = str(rfd_df.loc[min_idx, 'source'])
                        
        except Exception as e:
            # Silently continue - data may not be available for all chemicals
            pass
    
    def _fetch_eco_tox(self, profile: HazardProfile, dtxsid: str) -> None:
        """Fetch ecological toxicity values"""
        try:
            eco_df = self._haz.search_toxvaldb(by='eco', dtxsid=dtxsid)
            
            if eco_df is None or eco_df.empty:
                return
            
            # Find LC50 (aquatic toxicity)
            lc50_mask = eco_df['toxvalType'].str.contains('LC50', case=False, na=False)
            if lc50_mask.any():
                lc50_df = eco_df[lc50_mask]
                lc50_df = lc50_df[lc50_df['toxvalNumeric'].notna()]
                if not lc50_df.empty:
                    profile.lc50 = float(lc50_df['toxvalNumeric'].min())
            
            # Find LD50 (oral toxicity)
            ld50_mask = eco_df['toxvalType'].str.contains('LD50', case=False, na=False)
            if ld50_mask.any():
                ld50_df = eco_df[ld50_mask]
                ld50_df = ld50_df[ld50_df['toxvalNumeric'].notna()]
                if not ld50_df.empty:
                    profile.ld50 = float(ld50_df['toxvalNumeric'].min())
                    
        except Exception:
            pass
    
    def _fetch_genetox(self, profile: HazardProfile, dtxsid: str) -> None:
        """Fetch genetic toxicity summary"""
        try:
            genetox_df = self._haz.search_toxvaldb(by='genetox', dtxsid=dtxsid)
            
            if genetox_df is None or genetox_df.empty:
                return
            
            # Get first row (summary data)
            row = genetox_df.iloc[0]
            
            # Extract counts
            if 'reportsPositive' in row:
                val = row['reportsPositive']
                if val is not None and str(val).strip() not in ['', 'NA', '<NA>']:
                    try:
                        profile.genetox_positive = int(float(val))
                    except (ValueError, TypeError):
                        pass
            
            if 'reportsNegative' in row:
                val = row['reportsNegative']
                if val is not None and str(val).strip() not in ['', 'NA', '<NA>']:
                    try:
                        profile.genetox_negative = int(float(val))
                    except (ValueError, TypeError):
                        pass
            
            # Ames test result
            if 'ames' in row:
                val = row['ames']
                if val is not None and str(val).strip() not in ['', '-', 'NA', '<NA>']:
                    profile.genetox_ames = str(val).strip()
                    
        except Exception:
            pass
    
    def _compute_severity(self, profile: HazardProfile) -> int:
        """
        Compute a severity index (1-5) based on toxicity values.
        
        Scoring criteria:
        - NOAEL < 1 mg/kg-day: Severity 5 (very high)
        - NOAEL < 10 mg/kg-day: Severity 4 (high)
        - NOAEL < 100 mg/kg-day: Severity 3 (moderate)
        - Ames positive: +1 severity
        - >5 positive genetox reports: +1 severity
        - LC50 < 1 mg/L (very toxic to aquatic life): +1 severity
        
        Returns:
            Integer 1-5, where 5 is most severe
        """
        score = 1
        
        # Score based on NOAEL (lower = more toxic)
        if profile.noael is not None:
            if profile.noael < 1:
                score = max(score, 5)
            elif profile.noael < 10:
                score = max(score, 4)
            elif profile.noael < 100:
                score = max(score, 3)
            elif profile.noael < 1000:
                score = max(score, 2)
        
        # Score based on RfD (lower = more concern)
        if profile.rfd is not None:
            if profile.rfd < 0.0001:  # < 0.1 µg/kg-day
                score = max(score, 5)
            elif profile.rfd < 0.001:
                score = max(score, 4)
            elif profile.rfd < 0.01:
                score = max(score, 3)
        
        # Genotoxicity concerns
        if profile.genetox_ames.lower() == 'positive':
            score = min(5, score + 1)
        
        if profile.genetox_positive > 10:
            score = min(5, score + 1)
        elif profile.genetox_positive > 5:
            score = max(score, 3)
        
        # Ecological toxicity
        if profile.lc50 is not None and profile.lc50 < 1:
            score = max(score, 4)
        
        if profile.ld50 is not None and profile.ld50 < 50:
            score = max(score, 4)
        
        return score


# Singleton instance for module-level access
_client_instance: Optional[CTXClient] = None


def get_client(api_key: str) -> CTXClient:
    """Get or create a CTXClient instance"""
    global _client_instance
    if _client_instance is None or _client_instance.api_key != api_key:
        _client_instance = CTXClient(api_key)
    return _client_instance
