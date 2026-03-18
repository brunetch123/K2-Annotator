"""
K2 Configuration Management
Handles .K2config (presets) and .K2 (project) file formats
"""

import json
import os
from pathlib import Path
from datetime import datetime


class K2Config:
    """Manages user preferences and configuration presets"""

    def __init__(self, config_file=None):
        # Default configuration
        self.defaults = {
            'msconvert_path': '',
            'mzmine_path': '',
            'mzmine_user_file': '',
            'mzmine_batch_file': '',
            'mzmine_threads': 2,
            'library_path': '',
            'ri_cal_path': '',
            'epa_api_key': '',
            'blank_identifier': 'fieldblank',
            'last_input_folder': '',
            'last_output_folder': '',
            'window_geometry': '1400x900',
            'theme': 'light',
        }

        self.config = self.defaults.copy()
        self.first_run = False

        # User config file location
        if config_file:
            self.config_file = Path(config_file)
        else:
            # Default location in user's home directory
            home = Path.home()
            self.config_dir = home / '.k2'
            if not self.config_dir.exists():
                self.config_dir.mkdir(exist_ok=True)
                self.first_run = True
            
            self.config_file = self.config_dir / 'k2_defaults.json'
            if not self.config_file.exists():
                self.first_run = True

        self.load_defaults()
        
        # If it's the first run, ensure we don't have any leftover paths from previous sessions 
        # that might have been accidentally saved in a different location
        if self.first_run:
            self.config = self.defaults.copy()

    def load_defaults(self):
        """Load default configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
                    print(f"Loaded defaults from {self.config_file}")
            except Exception as e:
                print(f"Warning: Could not load defaults: {e}")

    def save_defaults(self):
        """Save current configuration as defaults"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Saved defaults to {self.config_file}")
        except Exception as e:
            print(f"Error saving defaults: {e}")

    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value

    def export_preset(self, filepath):
        """Export current configuration as a .K2config preset"""
        preset = {
            'format_version': '1.0',
            'created': datetime.now().isoformat(),
            'config': self.config.copy()
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(preset, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting preset: {e}")
            return False

    def load_preset(self, filepath):
        """Load configuration from a .K2config preset"""
        try:
            with open(filepath, 'r') as f:
                preset = json.load(f)

            if 'config' in preset:
                self.config.update(preset['config'])
                return True
            else:
                print("Invalid preset format")
                return False
        except Exception as e:
            print(f"Error loading preset: {e}")
            return False


class K2Project:
    """Manages .K2 project files (saved analysis sessions)"""

    def __init__(self):
        self.project_data = {
            'format_version': '1.0',
            'created': None,
            'modified': None,
            'project_name': '',
            'entry_point': '',  # 'raw', 'mzml', or 'msp'
            'input_folder': '',
            'output_folder': '',
            'pipeline_config': {},
            'analysis_status': 'not_started',  # 'running', 'completed', 'error'
            'results': {
                'csv_file': '',
                'pdf_file': '',
                'match_count': 0,
            }
        }

    def create_new(self, project_name, entry_point, input_folder, output_folder, config):
        """Create a new project"""
        self.project_data.update({
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'project_name': project_name,
            'entry_point': entry_point,
            'input_folder': str(input_folder),
            'output_folder': str(output_folder),
            'pipeline_config': config,
            'analysis_status': 'not_started',
        })

    def save(self, filepath):
        """Save project to .K2 file"""
        self.project_data['modified'] = datetime.now().isoformat()

        try:
            with open(filepath, 'w') as f:
                json.dump(self.project_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False

    def load(self, filepath):
        """Load project from .K2 file"""
        try:
            with open(filepath, 'r') as f:
                self.project_data = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading project: {e}")
            return False

    def update_status(self, status):
        """Update analysis status"""
        self.project_data['analysis_status'] = status
        self.project_data['modified'] = datetime.now().isoformat()

    def set_results(self, csv_file, pdf_file, match_count):
        """Store results information"""
        self.project_data['results'] = {
            'csv_file': str(csv_file),
            'pdf_file': str(pdf_file),
            'match_count': match_count,
        }
        self.project_data['analysis_status'] = 'completed'

    def get(self, key, default=None):
        """Get project data"""
        return self.project_data.get(key, default)
