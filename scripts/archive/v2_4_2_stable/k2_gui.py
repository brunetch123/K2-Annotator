#!/usr/bin/env python3
"""
K2 - GC-MS Analysis GUI
Professional wrapper for the GC-MS suspect screening pipeline
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import sys
import os
from pathlib import Path
import csv

# Import configuration management
from k2_config import K2Config, K2Project


class K2Application(tk.Tk):
    """Main K2 GUI Application"""

    def __init__(self):
        super().__init__()

        self.title("K2 - GC-MS Analysis")
        self.geometry("900x700")

        # Configuration and project management
        self.app_config = K2Config()
        self.project = K2Project()
        self.current_project_file = None

        # Theme initialization
        self.style = ttk.Style()
        self.apply_theme(self.app_config.get('theme', 'light'))

        # Apply saved geometry if available
        geometry = self.app_config.get('window_geometry', '900x700')
        self.geometry(geometry)

        # Set window icon if logo exists
        logo_path = Path(__file__).parent.parent / "K2Icon.png"
        if logo_path.exists():
            try:
                icon = tk.PhotoImage(file=str(logo_path))
                self.iconphoto(True, icon)
            except Exception as e:
                print(f"Could not load icon: {e}")

        # Create menu bar
        self.create_menu()

        # Container for different screens
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill='both', expand=True)

        # Store screen frames
        self.screens = {}
        self.current_screen = None

        # Pipeline state
        self.pipeline_config = {
            'entry_point': None,  # 'raw', 'mzml', 'msp'
            'input_folder': '',
            'output_folder': '',
            'project_name': '',
            'msconvert_path': self.app_config.get('msconvert_path', ''),
            'mzmine_path': self.app_config.get('mzmine_path', ''),
            'mzmine_user_file': self.app_config.get('mzmine_user_file', ''),
            'mzmine_batch_file': self.app_config.get('mzmine_batch_file', ''),
            'mzmine_threads': self.app_config.get('mzmine_threads', 2),
            'library_path': self.app_config.get('library_path', ''),
            'ri_cal_path': self.app_config.get('ri_cal_path', ''),
            'epa_api_key': self.app_config.get('epa_api_key', ''),
            'blank_identifier': self.app_config.get('blank_identifier', 'fieldblank'),
        }

        # Initialize screens
        self.init_screens()

        # Show welcome screen
        self.show_screen('welcome')

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_menu(self):
        """Create application menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self.new_project)
        file_menu.add_command(label="Open Project...", command=self.open_project)
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Load Preset...", command=self.load_preset)
        file_menu.add_command(label="Save Preset...", command=self.save_preset)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

        # View menu (for themes)
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Light Mode", command=lambda: self.apply_theme('light'))
        view_menu.add_command(label="Dark Mode", command=lambda: self.apply_theme('dark'))

        # Keyboard shortcuts
        self.bind('<Control-s>', lambda e: self.save_project())
        self.bind('<Control-o>', lambda e: self.open_project())
        self.bind('<Control-n>', lambda e: self.new_project())

    def init_screens(self):
        """Initialize all screen frames"""
        # Welcome screen
        self.screens['welcome'] = WelcomeScreen(self.main_container, self)

        # Pipeline entry selection
        self.screens['entry_select'] = EntrySelectScreen(self.main_container, self)

        # Project setup
        self.screens['project_setup'] = ProjectSetupScreen(self.main_container, self)

        # Sample Grouping
        self.screens['sample_grouping'] = SampleGroupingScreen(self.main_container, self)

        # MSConvert configuration
        self.screens['msconvert_config'] = MSConvertScreen(self.main_container, self)

        # MZmine configuration
        self.screens['mzmine_config'] = MZmineScreen(self.main_container, self)

        # Analysis parameters
        self.screens['analysis_params'] = AnalysisParamsScreen(self.main_container, self)

        # Execution screen
        self.screens['execution'] = ExecutionScreen(self.main_container, self)

        # Results viewer
        self.screens['results'] = ResultsScreen(self.main_container, self)

    def show_screen(self, screen_name):
        """Switch to a different screen"""
        # Hide current screen
        if self.current_screen:
            self.screens[self.current_screen].pack_forget()

        # Show new screen
        self.current_screen = screen_name
        self.screens[screen_name].pack(fill='both', expand=True, padx=20, pady=20)

        # Call screen's on_show method if it exists
        if hasattr(self.screens[screen_name], 'on_show'):
            self.screens[screen_name].on_show()

    def apply_theme(self, theme_name):
        """Apply the selected UI theme"""
        self.app_config.set('theme', theme_name)
        
        if theme_name == 'dark':
            bg_color = "#2d2d2d"
            fg_color = "#e1e1e1"
            header_color = "#3d3d3d"
            select_color = "#4a4a4a"
            accent_color = "#007acc"
            
            # Configure style for dark mode
            self.style.theme_use('clam')  # 'clam' is often more customizable than 'default' or 'alt'
            self.style.configure("TFrame", background=bg_color)
            self.style.configure("TLabel", background=bg_color, foreground=fg_color)
            self.style.configure("TButton", background=header_color, foreground=fg_color)
            self.style.map("TButton", background=[('active', select_color)])
            self.style.configure("Treeview", background=header_color, foreground=fg_color, fieldbackground=header_color)
            self.style.map("Treeview", background=[('selected', accent_color)])
            self.style.configure("TNotebook", background=bg_color, tabmargins=[2, 5, 2, 0])
            self.style.configure("TNotebook.Tab", background=header_color, foreground=fg_color, padding=[10, 2])
            self.style.map("TNotebook.Tab", background=[('selected', bg_color)], foreground=[('selected', accent_color)])
            self.style.configure("TEntry", fieldbackground=header_color, foreground=fg_color)
            self.style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
            self.style.configure("TRadiobutton", background=bg_color, foreground=fg_color)
            
            self.configure(bg=bg_color)
            
        else:
            # Revert to standard light theme
            self.style.theme_use('vista') if os.name == 'nt' else self.style.theme_use('default')
            self.configure(bg="SystemButtonFace") if os.name == 'nt' else self.configure(bg="#f0f0f0")

        # Notify screens if they are already initialized
        if hasattr(self, 'screens'):
            for screen in self.screens.values():
                if hasattr(screen, 'apply_theme'):
                    screen.apply_theme(theme_name)

    def new_project(self):
        """Start a new project"""
        # Reset pipeline config to defaults
        self.pipeline_config.update({
            'entry_point': None,
            'input_folder': '',
            'output_folder': '',
            'project_name': '',
        })
        # Explicitly clear transient data
        if 'sample_grouping' in self.pipeline_config:
            del self.pipeline_config['sample_grouping']
        if 'num_groups' in self.pipeline_config:
            del self.pipeline_config['num_groups']
            
        self.current_project_file = None
        self.project = K2Project()
        self.show_screen('entry_select')

    def open_project(self):
        """Open an existing .K2 project file"""
        filepath = filedialog.askopenfilename(
            title="Open K2 Project",
            filetypes=[("K2 Project", "*.K2"), ("All Files", "*.*")]
        )

        if filepath:
            project = K2Project()
            if project.load(filepath):
                self.project = project
                self.current_project_file = filepath

                # Load project configuration
                self.pipeline_config.update(project.get('pipeline_config', {}))
                self.pipeline_config['project_name'] = project.get('project_name', '')
                self.pipeline_config['input_folder'] = project.get('input_folder', '')
                self.pipeline_config['output_folder'] = project.get('output_folder', '')
                self.pipeline_config['entry_point'] = project.get('entry_point', '')

                # Check analysis status
                status = project.get('analysis_status', 'not_started')

                if status == 'completed':
                    # Show results
                    self.show_screen('results')
                    # Force reload results in the ResultsScreen
                    if 'results' in self.screens:
                        self.screens['results'].load_results()
                else:
                    # Show project setup to continue/rerun
                    self.show_screen('project_setup')

                messagebox.showinfo("Success", f"Loaded project: {project.get('project_name', 'Untitled')}")
            else:
                messagebox.showerror("Error", "Failed to load project file")

    def save_project(self):
        """Save current project"""
        if self.current_project_file:
            # If we are on ResultsScreen, ensure status is completed
            if self.current_screen == 'results':
                self.project.update_status('completed')
            self._save_to_file(self.current_project_file)
        else:
            self.save_project_as()

    def save_project_as(self):
        """Save project with new filename"""
        filepath = filedialog.asksaveasfilename(
            title="Save K2 Project",
            defaultextension=".K2",
            filetypes=[("K2 Project", "*.K2"), ("All Files", "*.*")]
        )

        if filepath:
            self._save_to_file(filepath)
            self.current_project_file = filepath

    def _save_to_file(self, filepath):
        """Internal method to save project"""
        # Capture current status before rewriting
        current_status = self.project.get('analysis_status', 'not_started')
        current_results = self.project.get('results', {})

        self.project.create_new(
            project_name=self.pipeline_config.get('project_name', 'Untitled'),
            entry_point=self.pipeline_config.get('entry_point', ''),
            input_folder=self.pipeline_config.get('input_folder', ''),
            output_folder=self.pipeline_config.get('output_folder', ''),
            config=self.pipeline_config
        )

        # Restore status and results
        if current_status == 'completed':
            self.project.update_status('completed')
            self.project.project_data['results'] = current_results

        if self.project.save(filepath):
            messagebox.showinfo("Success", "Project saved successfully")
        else:
            messagebox.showerror("Error", "Failed to save project")

    def load_preset(self):
        """Load configuration preset"""
        filepath = filedialog.askopenfilename(
            title="Load K2 Preset",
            filetypes=[("K2 Config", "*.K2config"), ("All Files", "*.*")]
        )

        if filepath:
            if self.app_config.load_preset(filepath):
                # Update pipeline config with loaded values
                for key in ['msconvert_path', 'mzmine_path', 'mzmine_user_file',
                           'mzmine_batch_file', 'mzmine_threads', 'library_path',
                           'ri_cal_path', 'epa_api_key', 'blank_identifier']:
                    self.pipeline_config[key] = self.app_config.get(key, '')

                messagebox.showinfo("Success", "Preset loaded successfully")
            else:
                messagebox.showerror("Error", "Failed to load preset")

    def save_preset(self):
        """Save current configuration as preset"""
        filepath = filedialog.asksaveasfilename(
            title="Save K2 Preset",
            defaultextension=".K2config",
            filetypes=[("K2 Config", "*.K2config"), ("All Files", "*.*")]
        )

        if filepath:
            # Update config with current values
            for key, value in self.pipeline_config.items():
                if key not in ['input_folder', 'output_folder', 'project_name', 'entry_point']:
                    self.app_config.set(key, value)

            if self.app_config.export_preset(filepath):
                messagebox.showinfo("Success", "Preset saved successfully")
            else:
                messagebox.showerror("Error", "Failed to save preset")

    def show_help(self):
        """Show user guide"""
        help_window = tk.Toplevel(self)
        help_window.title("K2 User Guide")
        help_window.geometry("700x500")

        # Add scrollable text
        text = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, font=('Arial', 10))
        text.pack(fill='both', expand=True, padx=10, pady=10)

        help_text = """
K2 - GC-MS Analysis User Guide

GETTING STARTED
1. First-time setup: Configure paths to external tools (MSConvert, MZmine)
2. Select your analysis entry point (.D, .mzML, or .MSP files)
3. Configure analysis parameters
4. Run analysis and view results

REQUIRED EXTERNAL SOFTWARE
- MSConvert: Part of ProteoWizard suite for raw data conversion
- MZmine: For feature detection and deconvolution
- Spectral Library: Reference library in .CSV or .MSP format
- RI Calibration File: Retention index calibration (optional)

WORKFLOW
• From .D files: Full pipeline (conversion → MZmine → matching)
• From .mzML files: Partial pipeline (MZmine → matching)
• From .MSP files: Matching only

PROJECT FILES
• .K2 files: Save complete analysis sessions
• .K2config files: Save configuration presets

For detailed documentation, see the included user guide PDF.
        """

        text.insert('1.0', help_text)
        text.config(state='disabled')

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About K2",
            "K2 - GC-MS Analysis\n\n"
            "Version 1.0\n\n"
            "A comprehensive tool for GC-MS suspect screening\n"
            "including feature detection, spectral matching, and\n"
            "retention index calibration.\n\n"
            "© 2026"
        )

    def on_closing(self):
        """Handle application closing"""
        # Save window geometry
        self.app_config.set('window_geometry', self.geometry())
        self.app_config.save_defaults()

        # Ask to save project if modified
        if self.current_project_file or self.pipeline_config.get('project_name'):
            result = messagebox.askyesnocancel("Save Project", "Do you want to save the current project?")
            if result is None:  # Cancel
                return
            elif result:  # Yes
                self.save_project()

        self.destroy()


# Import screen classes
from k2_screens import (
    WelcomeScreen,
    EntrySelectScreen,
    ProjectSetupScreen,
    SampleGroupingScreen,
    MSConvertScreen,
    MZmineScreen,
    AnalysisParamsScreen,
    ExecutionScreen,
    ResultsScreen
)


def main():
    """Main entry point"""
    app = K2Application()
    app.mainloop()


if __name__ == "__main__":
    main()
