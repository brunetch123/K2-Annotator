"""
K2 Configuration Management
Handles .K2config (presets) and .K2 (project) file formats
"""

import json
import os
from pathlib import Path
from datetime import datetime


# Keys whose values are filesystem paths. Validated at load time so a user
# whose previous install lived at a different location (or who copied their
# config across machines) doesn't see stale absolute paths populate the GUI.
PATH_KEYS = (
    'msconvert_path',
    'mzmine_path',
    'mzmine_user_file',
    'mzmine_batch_file',
    'library_path',
    'ri_cal_path',
)

# Keys excluded from exported .K2config presets:
#   - epa_api_key: secret; never share across users
#   - last_input_folder / last_output_folder: per-machine browse history
#   - window_geometry: per-display state
# Without this filter, exporting a preset for a colleague would leak the
# user's API key and bake in paths that are meaningless on their system.
PRESET_EXCLUDED_KEYS = (
    'epa_api_key',
    'last_input_folder',
    'last_output_folder',
    'window_geometry',
)


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
            'bff_mode': 'standard',
            'bff_c_factor': 5.0,
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

        # If it's the first run, ensure we start with clean defaults
        # This prevents developer paths from being loaded into distributed builds
        if self.first_run:
            self.config = self.defaults.copy()
            print("First run detected - using clean default configuration")

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
        self._prune_invalid_paths()

    def _prune_invalid_paths(self):
        """
        Reset any PATH_KEYS pointing at files that don't exist on this machine.

        Saved configs frequently outlive the install location they were captured
        in (repo moved, OneDrive synced to a new machine, software dir
        reinstalled). Without this, the GUI re-populates with absolute paths
        the current user can't browse to.
        """
        cleared = []
        for key in PATH_KEYS:
            val = self.config.get(key, '')
            if val and not Path(val).exists():
                self.config[key] = ''
                cleared.append(key)
        if cleared:
            print(f"Cleared {len(cleared)} stale path(s) from saved config: "
                  f"{', '.join(cleared)}")

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
        """Export current configuration as a .K2config preset.

        Sensitive (API keys) and ephemeral (window geometry, last-used folders)
        keys are stripped — see PRESET_EXCLUDED_KEYS — so a preset can be
        shared safely with collaborators.
        """
        sanitized = {k: v for k, v in self.config.items()
                     if k not in PRESET_EXCLUDED_KEYS}
        preset = {
            'format_version': '1.0',
            'created': datetime.now().isoformat(),
            'config': sanitized
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(preset, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting preset: {e}")
            return False

    def load_preset(self, filepath):
        """Load configuration from a .K2config preset.

        Path-type keys whose targets don't exist on this machine are blanked
        after merge, so paths from a colleague's environment don't bleed into
        the GUI here.
        """
        try:
            with open(filepath, 'r') as f:
                preset = json.load(f)

            if 'config' in preset:
                self.config.update(preset['config'])
                self._prune_invalid_paths()
                return True
            else:
                print("Invalid preset format")
                return False
        except Exception as e:
            print(f"Error loading preset: {e}")
            return False

    def reset_to_defaults(self):
        """Wipe the in-memory config back to clean factory defaults and
        persist the cleared state to disk. Useful when the user wants to
        scrub stale paths/secrets from a previous install."""
        self.config = self.defaults.copy()
        self.save_defaults()


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
