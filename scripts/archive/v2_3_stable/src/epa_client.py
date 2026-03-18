import requests
import time

class EpaClient:
    def __init__(self, api_key=None):
        self.base_url = "https://api-ccte.epa.gov"
        self.api_key = api_key
        # Headers required by EPA API
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def search_dtxsid(self, search_term):
        """
        Resolves a CAS or Name to an EPA 'DTXSID' (DSSTox Substance ID).
        This ID is required for all other EPA queries.
        """
        if not self.api_key: return None
        
        # Endpoint: Chemical Search
        url = f"{self.base_url}/chemical/search/equal/{search_term}"
        try:
            r = requests.get(url, headers=self.headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data[0].get('dtxsid')
        except:
            pass
        return None

    def get_hazard_data(self, dtxsid):
        """
        Fetches Hazard data for a DTXSID.
        Returns a simplified dictionary compatible with our Visualizer.
        """
        if not self.api_key or not dtxsid: return None
        
        matrix = {
            "Carcinogenicity": 0,
            "Mutagenicity": 0,
            "Reprotoxicity": 0,
            "Acute Toxicity": 0,
            "Organ Damage": 0,
            "Environmental": 0
        }
        
        # Endpoint: Hazard Data (Human & Eco)
        # Note: EPA splits this into multiple endpoints (Hazard, ToxVal, etc.)
        # The 'Hazard' endpoint typically aggregates GHS-like scores.
        url = f"{self.base_url}/hazard/{dtxsid}"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                # Parse EPA specific JSON structure here.
                # NOTE: As I cannot run this without a live key, this is a 
                # template based on the Williams et al. schema.
                
                for record in data:
                    score = record.get('score', 0) # EPA often uses scores 0-1 or Low/Med/High
                    category = record.get('category', '').lower()
                    
                    # Map EPA categories to our Matrix
                    lvl = 0
                    if score == "High" or score == "Very High": lvl = 3
                    elif score == "Moderate": lvl = 2
                    
                    if "carc" in category: matrix["Carcinogenicity"] = max(matrix["Carcinogenicity"], lvl)
                    if "muta" in category or "geno" in category: matrix["Mutagenicity"] = max(matrix["Mutagenicity"], lvl)
                    if "repro" in category or "dev" in category: matrix["Reprotoxicity"] = max(matrix["Reprotoxicity"], lvl)
                    if "acute" in category: matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], lvl)
                    
                return matrix
        except:
            pass
            
        return None