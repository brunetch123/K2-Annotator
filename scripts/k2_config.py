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

# Keys stripped from the pipeline_config block of a saved .K2 project file
# (v3.1.0). The API key is a secret and must never be persisted alongside
# shareable project data; it lives only in the running session and in
# ~/.k2/credentials.json (see K2Config.save_defaults).
PROJECT_EXCLUDED_KEYS = (
    'epa_api_key',
)

# Name of the environment variable through which the GUI/pipeline hand the
# EPA CompTox API key to cli.py (never on a command line).
API_KEY_ENV = 'K2_EPA_API_KEY'


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
            # v3.1.0: when True the GUI passes --mzmine-import-threads 1
            # (serialised mzML import; more stable on Windows, slower).
            'mzmine_serial_import': False,
            'library_path': '',
            'ri_cal_path': '',
            'epa_api_key': '',
            'blank_identifier': 'fieldblank',
            'bff_mode': 'standard',
            'bff_c_factor': 5.0,
            # v3.1.0: library peak trimming (--max-lib-peaks; 0 = disabled)
            'max_lib_peaks': 20,
            # v3.1.0: RI extrapolation mode outside the alkane range
            'ri_extrapolation': 'spline',
            # v3.1.0: permit runs with zero blank samples (--allow-no-blanks)
            'allow_no_blanks': False,
            'last_input_folder': '',
            'last_output_folder': '',
            'window_geometry': '1400x900',
            'theme': 'light',
        }

        self.config = self.defaults.copy()
        self.first_run = False

        # User config file location
        self.credentials_file = None
        if config_file:
            self.config_file = Path(config_file)
            # v3.1.0: secrets live next to the config file, never inside it
            self.credentials_file = self.config_file.parent / 'credentials.json'
        else:
            # Default location in user's home directory
            home = Path.home()
            self.config_dir = home / '.k2'
            if not self.config_dir.exists():
                self.config_dir.mkdir(exist_ok=True)
                self.first_run = True
            
            self.config_file = self.config_dir / 'k2_defaults.json'
            self.credentials_file = self.config_dir / 'credentials.json'
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
        # v3.1.0: the API key is kept in a separate credentials file. A key
        # found in an older k2_defaults.json is still honoured here and is
        # migrated out of that file on the next save_defaults().
        if self.credentials_file is not None and self.credentials_file.exists():
            try:
                with open(self.credentials_file, 'r') as f:
                    creds = json.load(f)
                if isinstance(creds, dict) and creds.get('epa_api_key'):
                    self.config['epa_api_key'] = creds['epa_api_key']
            except Exception as e:
                print(f"Warning: Could not load credentials: {e}")
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
        """Save current configuration as defaults.

        v3.1.0: the EPA API key is never written to k2_defaults.json. It is
        stored in a separate ~/.k2/credentials.json (or removed from it
        when blank) so the defaults file can be shared or attached to bug
        reports without leaking the secret.
        """
        try:
            public = {k: v for k, v in self.config.items() if k != 'epa_api_key'}
            with open(self.config_file, 'w') as f:
                json.dump(public, f, indent=2)
            print(f"Saved defaults to {self.config_file}")
        except Exception as e:
            print(f"Error saving defaults: {e}")

        if self.credentials_file is None:
            return
        api_key = self.config.get('epa_api_key', '') or ''
        try:
            if api_key:
                creds = {
                    '_comment': 'K2 Annotator credentials. This file holds '
                                'your EPA CompTox API key in plain text; do '
                                'not share it. Delete the file (or clear the '
                                'key in the GUI) to forget the key. The same '
                                'key can instead be supplied via the '
                                f'{API_KEY_ENV} environment variable.',
                    'epa_api_key': api_key,
                }
                with open(self.credentials_file, 'w') as f:
                    json.dump(creds, f, indent=2)
            elif self.credentials_file.exists():
                self.credentials_file.unlink()
        except Exception as e:
            print(f"Error saving credentials: {e}")

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
        """Save project to .K2 file.

        v3.1.0: secrets (PROJECT_EXCLUDED_KEYS, i.e. the EPA API key) are
        stripped from pipeline_config before writing so a .K2 file can be
        shared freely.
        """
        self.project_data['modified'] = datetime.now().isoformat()

        try:
            data = dict(self.project_data)
            cfg = data.get('pipeline_config')
            if isinstance(cfg, dict):
                data['pipeline_config'] = {k: v for k, v in cfg.items()
                                           if k not in PROJECT_EXCLUDED_KEYS}
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
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
