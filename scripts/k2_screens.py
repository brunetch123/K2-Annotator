"""
K2 GUI Screens
Individual screen implementations for the K2 application
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import sys
import os
from pathlib import Path
import csv
import json
from PIL import Image, ImageTk
from src.structure_helper import StructureHelper


def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    
    When running as a PyInstaller bundle, resources are extracted to a
    temporary folder (sys._MEIPASS). In development, use the project root.
    """
    if getattr(sys, 'frozen', False):
        # Running as bundled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running in normal Python environment (scripts/ -> project root)
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


class BaseScreen(ttk.Frame):
    """Base class for all screens"""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.header_frame = None
        self.title_label = None
        self.subtitle_label = None
        self.header_icon = None

    def apply_theme(self, theme_name):
        """Update any non-ttk widgets when theme changes"""
        pass

    def create_header(self, title, subtitle=""):
        """Create a header section"""
        self.header_frame = ttk.Frame(self)
        self.header_frame.pack(fill='x', pady=(0, 20))

        # Icon on the right
        icon_path = get_resource_path("K2Icon.png")
        if icon_path.exists():
            try:
                # Store icon to prevent garbage collection
                img = Image.open(icon_path)
                img = img.resize((32, 32), Image.Resampling.LANCZOS)
                self.header_icon = ImageTk.PhotoImage(img)
                icon_label = ttk.Label(self.header_frame, image=self.header_icon)
                icon_label.pack(side='right', anchor='ne', padx=10)
            except Exception as e:
                print(f"Could not load header icon: {e}")

        text_frame = ttk.Frame(self.header_frame)
        text_frame.pack(side='left', fill='both', expand=True)

        self.title_label = ttk.Label(
            text_frame,
            text=title,
            font=('Arial', 18, 'bold')
        )
        self.title_label.pack(anchor='w')

        if subtitle:
            self.subtitle_label = ttk.Label(
                text_frame,
                text=subtitle,
                font=('Arial', 10),
                foreground='gray'
            )
            self.subtitle_label.pack(anchor='w')

        return self.header_frame

    def create_button_row(self, buttons):
        """Create a row of buttons at the bottom"""
        button_frame = ttk.Frame(self)
        button_frame.pack(side='bottom', fill='x', pady=(20, 0))

        for i, (text, command) in enumerate(buttons):
            if i == len(buttons) - 1:
                # Last button (Next/Finish) on the right
                btn = ttk.Button(button_frame, text=text, command=command)
                btn.pack(side='right', padx=(5, 0))
            else:
                # Other buttons on the left
                btn = ttk.Button(button_frame, text=text, command=command)
                btn.pack(side='left', padx=(0, 5))

        return button_frame


class WelcomeScreen(BaseScreen):
    """Initial welcome screen - Load existing or start new"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Logo (if available) - centered
        logo_path = get_resource_path("K2Logo2.png")
        if logo_path.exists():
            try:
                self.logo_image = tk.PhotoImage(file=str(logo_path))
                logo_label = ttk.Label(self, image=self.logo_image)
                logo_label.pack(pady=(50, 10))
            except Exception as e:
                print(f"Could not load logo: {e}")
                title = ttk.Label(self, text="K2", font=('Arial', 48, 'bold'))
                title.pack(pady=(50, 10))
        
        # Introductory Message
        intro_frame = ttk.Frame(self)
        intro_frame.pack(pady=(0, 30))
        
        ttk.Label(
            intro_frame, 
            text="GC-MS Suspect Screening Software", 
            font=('Arial', 14, 'bold')
        ).pack()

        # Main options frame
        options_frame = ttk.Frame(self)
        options_frame.pack(expand=True, fill='x', padx=100)

        # New Analysis button
        new_btn = ttk.Button(
            options_frame,
            text="Start New Analysis",
            command=self.start_new,
            width=35
        )
        new_btn.pack(pady=10)

        # Load Project button
        load_btn = ttk.Button(
            options_frame,
            text="Load Existing Project (.K2)",
            command=self.app.open_project,
            width=35
        )
        load_btn.pack(pady=10)

        # Load Preset button
        preset_btn = ttk.Button(
            options_frame,
            text="Load Preset Configuration",
            command=self.app.load_preset,
            width=35
        )
        preset_btn.pack(pady=10)

        # Version Footer
        version_label = ttk.Label(
            self,
            text="Version 3.0.3 | 2026",
            font=('Arial', 9),
            foreground='gray'
        )
        version_label.pack(side='bottom', pady=20)

    def start_new(self):
        """Start a new analysis"""
        self.app.new_project()


class EntrySelectScreen(BaseScreen):
    """Select pipeline entry point"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "Select Analysis Entry Point",
            "Choose where to start in the analysis pipeline"
        )

        # Content frame
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # Selection variable
        self.entry_var = tk.StringVar(value='raw')

        # Option 1: .D files
        raw_frame = self.create_option_frame(
            content,
            'raw',
            "Instrument Files (.D)",
            "Start from Agilent raw data files\n"
            "Pipeline: Conversion → MZmine → Library Matching"
        )
        raw_frame.pack(fill='x', pady=10)

        # Option 2: .mzML files
        mzml_frame = self.create_option_frame(
            content,
            'mzml',
            "Instrument Files (.mzML)",
            "Start from converted mzML files\n"
            "Pipeline: MZmine → Library Matching"
        )
        mzml_frame.pack(fill='x', pady=10)

        # Option 3: .MSP files
        msp_frame = self.create_option_frame(
            content,
            'msp',
            "Deconvoluted Spectra (.MSP)",
            "Start from MZmine output files\n"
            "Pipeline: Library Matching Only"
        )
        msp_frame.pack(fill='x', pady=10)

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

    def create_option_frame(self, parent, value, title, description):
        """Create a selectable option frame"""
        frame = ttk.LabelFrame(parent, text="", padding=15)

        radio = ttk.Radiobutton(
            frame,
            text=title,
            variable=self.entry_var,
            value=value
        )
        radio.pack(anchor='w')
        radio.config(style='Option.TRadiobutton')

        desc_label = ttk.Label(
            frame,
            text=description,
            foreground='gray'
        )
        desc_label.pack(anchor='w', padx=(25, 0), pady=(5, 0))

        return frame

    def go_back(self):
        self.app.show_screen('welcome')

    def go_next(self):
        entry_point = self.entry_var.get()
        self.app.pipeline_config['entry_point'] = entry_point
        self.app.show_screen('project_setup')


class ProjectSetupScreen(BaseScreen):
    """Project setup: name, input/output folders"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "Project Setup",
            "Configure project name and file locations"
        )

        # Content frame
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # Input folder
        input_frame = ttk.LabelFrame(content, text="Input Folder", padding=15)
        input_frame.pack(fill='x', pady=10)

        self.input_var = tk.StringVar()
        input_entry = ttk.Entry(input_frame, textvariable=self.input_var, width=50)
        input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        input_btn = ttk.Button(input_frame, text="Browse...", command=self.browse_input)
        input_btn.pack(side='right')

        # Entry type hint
        self.input_hint = ttk.Label(
            input_frame,
            text="Select folder containing .D files",
            foreground='gray'
        )
        self.input_hint.pack(anchor='w', pady=(5, 0))

        # Project name
        name_frame = ttk.LabelFrame(content, text="Project Name", padding=15)
        name_frame.pack(fill='x', pady=10)

        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=50)
        name_entry.pack(fill='x')

        name_hint = ttk.Label(
            name_frame,
            text="Default: input folder name (editable)",
            foreground='gray'
        )
        name_hint.pack(anchor='w', pady=(5, 0))

        # Output folder
        output_frame = ttk.LabelFrame(content, text="Output Folder", padding=15)
        output_frame.pack(fill='x', pady=10)

        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=50)
        output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        output_btn = ttk.Button(output_frame, text="Browse...", command=self.browse_output)
        output_btn.pack(side='right')

        output_hint = ttk.Label(
            output_frame,
            text="Where to save analysis results and outputs",
            foreground='gray'
        )
        output_hint.pack(anchor='w', pady=(5, 0))

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

    def on_show(self):
        """Called when screen is shown"""
        # Update hint based on entry point
        entry_point = self.app.pipeline_config.get('entry_point', 'raw')
        hints = {
            'raw': "Select folder containing .D files",
            'mzml': "Select folder containing .mzML files",
            'msp': "Select folder containing MZmine output (.MSP + .CSV)"
        }
        self.input_hint.config(text=hints.get(entry_point, "Select input folder"))

        # Load saved values if available
        self.input_var.set(self.app.pipeline_config.get('input_folder', ''))
        self.output_var.set(self.app.pipeline_config.get('output_folder', ''))
        self.name_var.set(self.app.pipeline_config.get('project_name', ''))

    def browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_var.set(folder)
            # Auto-populate project name if empty
            if not self.name_var.get():
                self.name_var.set(Path(folder).name)

    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_var.set(folder)

    def go_back(self):
        self.app.show_screen('entry_select')

    def go_next(self):
        # Validate inputs
        if not self.input_var.get():
            messagebox.showerror("Error", "Please select an input folder")
            return

        if not self.output_var.get():
            messagebox.showerror("Error", "Please select an output folder")
            return

        if not self.name_var.get():
            messagebox.showerror("Error", "Please enter a project name")
            return

        # Save to config
        self.app.pipeline_config['input_folder'] = self.input_var.get()
        self.app.pipeline_config['output_folder'] = self.output_var.get()
        self.app.pipeline_config['project_name'] = self.name_var.get()

        # Determine next screen based on entry point
        entry_point = self.app.pipeline_config['entry_point']

        # Show Analysis Params screen first (so blank identifier can be used in grouping)
        self.app.show_screen('analysis_params')


class SampleClassificationScreen(BaseScreen):
    """Screen for classifying samples as Blanks, Samples, or References and configuring IS normalization (v3.0.0)"""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        # v3.0.0: Extended sample data structure
        self.samples = []  # List of dicts: {'name': str, 'type': str, 'spiked': bool, 'spike_ratio': float, 'group': str}
        self._updating_ui = False
        self.is_values = {}  # {sample_name: float} for IS normalization
        self.groups = ['Default']  # v3.0.0: List of surrogate groups

        self.create_header(
            "Sample Classification & Internal Standard",
            "Classify samples and configure internal standard normalization (optional)"
        )

        # Create buttons FIRST so they're reserved at bottom (pack order matters with expand=True)
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

        # Main content area with scrollable container
        main_container = ttk.Frame(self)
        main_container.pack(fill='both', expand=True)

        # Top section: Sample Classification
        sample_section = ttk.LabelFrame(main_container, text="Sample Classification", padding=15)
        sample_section.pack(fill='both', expand=True, padx=10, pady=10)

        # Content area for sample table
        content = ttk.Frame(sample_section)
        content.pack(fill='both', expand=True)

        # Left side: Table
        table_container = ttk.Frame(content)
        table_container.pack(side='left', fill='both', expand=True, padx=(0, 10))

        # Instructions
        ttk.Label(table_container, text="Double-click cells to edit. Use Right-click for bulk actions.", font=('Arial', 9, 'italic')).pack(anchor='w')

        table_frame = ttk.Frame(table_container)
        table_frame.pack(fill='both', expand=True)

        # v3.0.0: Extended columns for surrogate recovery
        self.tree = ttk.Treeview(
            table_frame,
            columns=('name', 'type', 'spiked', 'spike_ratio', 'group'),
            show='headings',
            selectmode='extended',
            height=8
        )
        self.tree.heading('name', text='Sample Name')
        self.tree.heading('type', text='Type')
        self.tree.heading('spiked', text='Spiked')
        self.tree.heading('spike_ratio', text='Spike Ratio')
        self.tree.heading('group', text='Group')

        self.tree.column('name', width=200)
        self.tree.column('type', width=90)
        self.tree.column('spiked', width=60, anchor='center')
        self.tree.column('spike_ratio', width=80, anchor='center')
        self.tree.column('group', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Events
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)

        # Right side: Edit panel
        edit_panel = ttk.LabelFrame(content, text="Edit Selected", padding=15, width=280)
        edit_panel.pack(side='right', fill='y', padx=(10, 0))

        # Type selection - v3.0.0: Added Reference option
        ttk.Label(edit_panel, text="Type:").pack(anchor='w')
        self.type_var = tk.StringVar(value="Sample")
        self.type_cb = ttk.Combobox(edit_panel, textvariable=self.type_var, values=["Sample", "Blank", "Reference"], state='readonly')
        self.type_cb.pack(fill='x', pady=(0, 10))
        self.type_cb.bind('<<ComboboxSelected>>', self.update_selected_type)

        # v3.0.0: Spiked checkbox
        self.spiked_var = tk.BooleanVar(value=False)
        self.spiked_check = ttk.Checkbutton(
            edit_panel, 
            text="Spiked with Surrogates",
            variable=self.spiked_var,
            command=self.update_selected_spiked
        )
        self.spiked_check.pack(anchor='w', pady=(0, 10))

        # v3.0.0: Spike ratio
        ratio_frame = ttk.Frame(edit_panel)
        ratio_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(ratio_frame, text="Spike Ratio:").pack(side='left')
        self.ratio_var = tk.StringVar(value="1.0")
        self.ratio_entry = ttk.Entry(ratio_frame, textvariable=self.ratio_var, width=8)
        self.ratio_entry.pack(side='left', padx=(5, 0))
        self.ratio_entry.bind('<FocusOut>', self.update_selected_ratio)
        self.ratio_entry.bind('<Return>', self.update_selected_ratio)

        # v3.0.0: Group selection
        group_frame = ttk.Frame(edit_panel)
        group_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(group_frame, text="Group:").pack(side='left')
        self.group_var = tk.StringVar(value="Default")
        self.group_cb = ttk.Combobox(group_frame, textvariable=self.group_var, values=self.groups, width=10)
        self.group_cb.pack(side='left', padx=(5, 0))
        self.group_cb.bind('<<ComboboxSelected>>', self.update_selected_group)

        # Bulk action buttons
        ttk.Separator(edit_panel, orient='horizontal').pack(fill='x', pady=10)
        
        copy_btn = ttk.Button(edit_panel, text="Copy to Selected Rows", command=self.copy_to_selected)
        copy_btn.pack(fill='x', pady=5)
        
        fill_btn = ttk.Button(edit_panel, text="Fill Down", command=self.fill_down)
        fill_btn.pack(fill='x', pady=5)

        # v3.0.0: Group management
        ttk.Separator(edit_panel, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(edit_panel, text="Group Management:", font=('Arial', 9, 'bold')).pack(anchor='w')
        
        group_mgmt_frame = ttk.Frame(edit_panel)
        group_mgmt_frame.pack(fill='x', pady=5)
        
        self.new_group_var = tk.StringVar()
        ttk.Entry(group_mgmt_frame, textvariable=self.new_group_var, width=10).pack(side='left')
        ttk.Button(group_mgmt_frame, text="Add", command=self.add_group).pack(side='left', padx=2)

        # Context menu - v3.0.0: Added Reference option
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Copy values to all selected", command=self.copy_to_selected)
        self.menu.add_command(label="Fill Down (from first selected)", command=self.fill_down)
        self.menu.add_separator()
        self.menu.add_command(label="Set as Sample", command=lambda: self.set_bulk_type("Sample"))
        self.menu.add_command(label="Set as Blank", command=lambda: self.set_bulk_type("Blank"))
        self.menu.add_command(label="Set as Reference", command=lambda: self.set_bulk_type("Reference"))
        self.menu.add_separator()
        self.menu.add_command(label="Mark as Spiked", command=lambda: self.set_bulk_spiked(True))
        self.menu.add_command(label="Mark as Not Spiked", command=lambda: self.set_bulk_spiked(False))

        # Bottom section: Internal Standard Normalization (v2.8.0)
        self.is_section = ttk.LabelFrame(main_container, text="Internal Standard Normalization (Optional)", padding=15)
        self.is_section.pack(fill='both', expand=True, padx=10, pady=10)

        # Enable checkbox
        enable_frame = ttk.Frame(self.is_section)
        enable_frame.pack(fill='x', pady=(0, 15))

        self.enable_var = tk.BooleanVar(value=False)
        enable_check = ttk.Checkbutton(
            enable_frame,
            text="Enable Internal Standard Normalization",
            variable=self.enable_var,
            command=self.toggle_is_enable
        )
        enable_check.pack(anchor='w')

        ttk.Label(
            enable_frame,
            text="Note: Normalization is applied BEFORE Blank Feature Filtering (BFF)",
            font=('Arial', 9, 'italic'),
            foreground='gray'
        ).pack(anchor='w', padx=(25, 0))

        # Method selection frame (initially disabled)
        self.method_frame = ttk.LabelFrame(self.is_section, text="Normalization Method", padding=15)
        self.method_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.method_var = tk.StringVar(value='manual')

        # Manual entry
        manual_radio = ttk.Radiobutton(
            self.method_frame,
            text="Manual Entry",
            variable=self.method_var,
            value='manual',
            command=self.update_method_display
        )
        manual_radio.grid(row=0, column=0, sticky='w', padx=5, pady=5)

        # Auto by m/z + RI
        mz_ri_radio = ttk.Radiobutton(
            self.method_frame,
            text="Auto-detect by m/z + RI",
            variable=self.method_var,
            value='mz_ri',
            command=self.update_method_display
        )
        mz_ri_radio.grid(row=1, column=0, sticky='w', padx=5, pady=5)

        # Auto by MSP
        msp_radio = ttk.Radiobutton(
            self.method_frame,
            text="Auto-detect by MSP Spectrum",
            variable=self.method_var,
            value='msp',
            command=self.update_method_display
        )
        msp_radio.grid(row=2, column=0, sticky='w', padx=5, pady=5)

        # --- Manual Entry Panel ---
        self.manual_panel = ttk.Frame(self.method_frame)
        self.manual_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        ttk.Label(
            self.manual_panel,
            text="Enter IS peak area for each sample (or import CSV):",
            font=('Arial', 9, 'bold')
        ).pack(anchor='w', pady=(0, 5))

        # Buttons for CSV
        button_row = ttk.Frame(self.manual_panel)
        button_row.pack(fill='x', pady=(0, 5))

        ttk.Button(button_row, text="Download Template CSV", command=self.download_template).pack(side='left', padx=(0, 5))
        ttk.Button(button_row, text="Import CSV", command=self.import_csv).pack(side='left', padx=(0, 5))
        ttk.Button(button_row, text="Export Current", command=self.export_csv).pack(side='left')

        # Table for manual entry
        table_frame_is = ttk.Frame(self.manual_panel)
        table_frame_is.pack(fill='both', expand=True)

        self.is_table = ttk.Treeview(
            table_frame_is,
            columns=('sample', 'is_value'),
            show='headings',
            height=6
        )
        self.is_table.heading('sample', text='Sample Name')
        self.is_table.heading('is_value', text='IS Peak Area')
        self.is_table.column('sample', width=300)
        self.is_table.column('is_value', width=150)

        scrollbar_is = ttk.Scrollbar(table_frame_is, orient='vertical', command=self.is_table.yview)
        self.is_table.configure(yscrollcommand=scrollbar_is.set)

        self.is_table.pack(side='left', fill='both', expand=True)
        scrollbar_is.pack(side='right', fill='y')

        self.is_table.bind('<Double-1>', self.edit_is_value)

        # --- m/z + RI Panel ---
        self.mz_ri_panel = ttk.Frame(self.method_frame)
        self.mz_ri_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        # RI/RT selection (v2.7.0)
        rt_selection_frame = ttk.Frame(self.mz_ri_panel)
        rt_selection_frame.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))

        ttk.Label(rt_selection_frame, text="Match by:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 10))
        self.use_rt_mz_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(rt_selection_frame, text="Retention Index (RI)", variable=self.use_rt_mz_var, value=False, command=self.update_rt_labels_mz).pack(side='left', padx=5)
        ttk.Radiobutton(rt_selection_frame, text="Retention Time (RT)", variable=self.use_rt_mz_var, value=True, command=self.update_rt_labels_mz).pack(side='left', padx=5)

        ttk.Label(self.mz_ri_panel, text="Target m/z:", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.target_mz_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.target_mz_var, width=15).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(self.mz_ri_panel, text="m/z Tolerance:", font=('Arial', 9, 'bold')).grid(row=1, column=2, sticky='w', pady=5, padx=(15, 0))
        self.mz_tol_var = tk.DoubleVar(value=0.5)
        ttk.Entry(self.mz_ri_panel, textvariable=self.mz_tol_var, width=10).grid(row=1, column=3, sticky='w', padx=5, pady=5)

        self.target_ri_label = ttk.Label(self.mz_ri_panel, text="Target RI:", font=('Arial', 9, 'bold'))
        self.target_ri_label.grid(row=2, column=0, sticky='w', pady=5)
        self.target_ri_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.target_ri_var, width=15).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        self.ri_tol_label = ttk.Label(self.mz_ri_panel, text="RI Tolerance:", font=('Arial', 9, 'bold'))
        self.ri_tol_label.grid(row=2, column=2, sticky='w', pady=5, padx=(15, 0))
        self.ri_tol_var = tk.DoubleVar(value=50.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.ri_tol_var, width=10).grid(row=2, column=3, sticky='w', padx=5, pady=5)

        ttk.Label(
            self.mz_ri_panel,
            text="The software will find the feature with highest abundance matching these criteria.",
            font=('Arial', 8, 'italic'),
            foreground='gray'
        ).grid(row=3, column=0, columnspan=4, sticky='w', pady=(10, 0))

        # --- MSP Panel ---
        self.msp_panel = ttk.Frame(self.method_frame)
        self.msp_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        # RI/RT selection (v2.7.0)
        rt_selection_frame_msp = ttk.Frame(self.msp_panel)
        rt_selection_frame_msp.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        ttk.Label(rt_selection_frame_msp, text="Match by:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 10))
        self.use_rt_msp_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(rt_selection_frame_msp, text="Retention Index (RI)", variable=self.use_rt_msp_var, value=False, command=self.update_rt_labels_msp).pack(side='left', padx=5)
        ttk.Radiobutton(rt_selection_frame_msp, text="Retention Time (RT)", variable=self.use_rt_msp_var, value=True, command=self.update_rt_labels_msp).pack(side='left', padx=5)

        ttk.Label(self.msp_panel, text="IS Spectrum File (.msp):", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.is_msp_var = tk.StringVar(value='')
        ttk.Entry(self.msp_panel, textvariable=self.is_msp_var, width=40).grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        ttk.Button(self.msp_panel, text="Browse...", command=self.browse_is_msp).grid(row=1, column=2, sticky='w', pady=5)

        self.msp_panel.columnconfigure(1, weight=1)

        self.msp_tol_label = ttk.Label(self.msp_panel, text="RI Tolerance:", font=('Arial', 9, 'bold'))
        self.msp_tol_label.grid(row=2, column=0, sticky='w', pady=5)
        self.msp_ri_tol_var = tk.DoubleVar(value=50.0)
        ttk.Entry(self.msp_panel, textvariable=self.msp_ri_tol_var, width=10).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(
            self.msp_panel,
            text="The software will match the spectrum to features using spectral similarity.",
            font=('Arial', 8, 'italic'),
            foreground='gray'
        ).grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))

        # Initialize state
        self.update_method_display()
        self.toggle_is_enable()
        # Note: Buttons created at top of __init__ to ensure they appear at bottom

    def on_show(self):
        """Scan input folder and populate table, and load IS config"""
        input_folder = Path(self.app.pipeline_config.get('input_folder', ''))
        entry_point = self.app.pipeline_config.get('entry_point', 'raw')
        blank_id = self.app.pipeline_config.get('blank_identifier', 'fieldblank').lower()

        if not input_folder.exists():
            return

        found_names = []
        if entry_point == 'raw':
            from gcms_pipeline import find_d_files
            found_names = [f.stem for f in find_d_files(input_folder)]
        elif entry_point == 'mzml':
            from gcms_pipeline import find_mzml_files
            found_names = [f.stem for f in find_mzml_files(input_folder)]
        elif entry_point == 'msp':
            from gcms_pipeline import find_mzmine_outputs
            quant_file, _ = find_mzmine_outputs(input_folder)
            if quant_file and quant_file.exists():
                try:
                    import pandas as pd
                    df = pd.read_csv(quant_file, nrows=0)
                    metadata_cols = ['row ID', 'row m/z', 'row retention time', 'row ion mobility',
                                    'row ion mobility unit', 'row CCS', 'correlation group ID',
                                    'annotation network number', 'best ion', 'auto MS2 verify',
                                    'identified by n=', 'partners', 'neutral M mass']
                    found_names = [col.replace(' Peak area', '') for col in df.columns 
                                  if col not in metadata_cols and ' Peak area' in col]
                except Exception:
                    pass

        existing_grouping = self.app.pipeline_config.get('sample_grouping', {})
        existing_is_config = self.app.pipeline_config.get('is_config', {})
        surrogate_config = self.app.pipeline_config.get('surrogate_config', {})
        surrogate_enabled = surrogate_config.get('enabled', False)

        # v3.0.0: Load existing groups
        if surrogate_config.get('groups'):
            self.groups = list(surrogate_config['groups'].keys())
            if 'Default' not in self.groups:
                self.groups.insert(0, 'Default')
        else:
            self.groups = ['Default']
        self.group_cb['values'] = self.groups

        self.samples = []
        self._updating_ui = True
        try:
            for name in found_names:
                if name in existing_grouping:
                    # Load existing classification (v3.0.0: extended structure)
                    existing = existing_grouping[name]
                    self.samples.append({
                        'name': name,
                        'type': existing.get('type', 'Sample'),
                        'spiked': existing.get('spiked', False),
                        'spike_ratio': existing.get('spike_ratio', 1.0),
                        'group': existing.get('group', 'Default')
                    })
                else:
                    # v3.0.0: Auto-detect sample type including Reference
                    name_lower = name.lower()
                    if blank_id in name_lower:
                        stype = "Blank"
                        spiked = False
                    elif 'ref' in name_lower:
                        stype = "Reference"
                        spiked = True  # Auto-check spiked for references
                    else:
                        stype = "Sample"
                        spiked = False
                    
                    self.samples.append({
                        'name': name,
                        'type': stype,
                        'spiked': spiked,
                        'spike_ratio': 1.0,
                        'group': 'Default'
                    })

            self.refresh_table()
        finally:
            self._updating_ui = False

        # Load IS config if exists
        if existing_is_config:
            self.enable_var.set(existing_is_config.get('enabled', False))
            self.method_var.set(existing_is_config.get('method', 'manual'))
            if existing_is_config.get('method') == 'manual':
                self.is_values = existing_is_config.get('is_values', {}).copy()
            elif existing_is_config.get('method') == 'mz_ri':
                self.target_mz_var.set(existing_is_config.get('target_mz', 0.0))
                self.mz_tol_var.set(existing_is_config.get('mz_tolerance', 0.5))
                self.target_ri_var.set(existing_is_config.get('target_value', 0.0))
                self.ri_tol_var.set(existing_is_config.get('value_tolerance', 50.0))
                self.use_rt_mz_var.set(existing_is_config.get('use_rt', False))
            elif existing_is_config.get('method') == 'msp':
                self.is_msp_var.set(existing_is_config.get('msp_file', ''))
                self.msp_ri_tol_var.set(existing_is_config.get('value_tolerance', 50.0))
                self.use_rt_msp_var.set(existing_is_config.get('use_rt', False))

        # Initialize IS values for all samples
        for sample in self.samples:
            if sample['name'] not in self.is_values:
                self.is_values[sample['name']] = 0.0

        self.refresh_is_table()
        self.update_method_display()
        self.toggle_is_enable()

    def refresh_table(self):
        """Redraw the table and apply colors (v3.0.0: extended columns)"""
        self.tree.delete(*self.tree.get_children())
        
        self.tree.tag_configure('blank', background='#f0f0f0', foreground='#888888')
        self.tree.tag_configure('reference', background='#e8f4e8', foreground='#2d6a2d')
        self.tree.tag_configure('spiked', background='#fff8e8')

        for i, s in enumerate(self.samples):
            tags = []
            if s['type'] == 'Blank':
                tags.append('blank')
            elif s['type'] == 'Reference':
                tags.append('reference')
            elif s.get('spiked', False):
                tags.append('spiked')
            
            # v3.0.0: Display all columns
            spiked_display = '✓' if s.get('spiked', False) else ''
            ratio_display = f"{s.get('spike_ratio', 1.0):.2f}"
            group_display = s.get('group', 'Default')
                
            self.tree.insert('', 'end', iid=str(i), 
                           values=(s['name'], s['type'], spiked_display, ratio_display, group_display), 
                           tags=tags)

    def refresh_is_table(self):
        """Refresh the IS values table"""
        self.is_table.delete(*self.is_table.get_children())

        for sample, value in sorted(self.is_values.items()):
            self.is_table.insert('', 'end', values=(sample, f"{value:.2f}"))

    def on_select(self, event):
        if self._updating_ui:
            return
            
        selection = self.tree.selection()
        if not selection:
            return
        
        idx = int(selection[0])
        s = self.samples[idx]
        
        self._updating_ui = True
        try:
            self.type_var.set(s['type'])
            # v3.0.0: Update new fields
            self.spiked_var.set(s.get('spiked', False))
            self.ratio_var.set(str(s.get('spike_ratio', 1.0)))
            self.group_var.set(s.get('group', 'Default'))
        finally:
            self._updating_ui = False

    def update_selected_type(self, event=None):
        if self._updating_ui: return
        selection = self.tree.selection()
        new_val = self.type_var.get()
        
        self._updating_ui = True
        try:
            for iid in selection:
                idx = int(iid)
                self.samples[idx]['type'] = new_val
                # v3.0.0: Auto-set spiked for Reference type
                if new_val == 'Reference':
                    self.samples[idx]['spiked'] = True
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    # v3.0.0: New methods for surrogate fields
    def update_selected_spiked(self, event=None):
        """Update spiked status for selected samples"""
        if self._updating_ui: return
        selection = self.tree.selection()
        new_val = self.spiked_var.get()
        
        self._updating_ui = True
        try:
            for iid in selection:
                idx = int(iid)
                self.samples[idx]['spiked'] = new_val
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    def update_selected_ratio(self, event=None):
        """Update spike ratio for selected samples"""
        if self._updating_ui: return
        selection = self.tree.selection()
        try:
            new_val = float(self.ratio_var.get())
        except ValueError:
            new_val = 1.0
            self.ratio_var.set("1.0")
        
        self._updating_ui = True
        try:
            for iid in selection:
                idx = int(iid)
                self.samples[idx]['spike_ratio'] = new_val
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    def update_selected_group(self, event=None):
        """Update group for selected samples"""
        if self._updating_ui: return
        selection = self.tree.selection()
        new_val = self.group_var.get()
        
        self._updating_ui = True
        try:
            for iid in selection:
                idx = int(iid)
                self.samples[idx]['group'] = new_val
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    def set_bulk_spiked(self, spiked):
        """Set spiked status for selected samples"""
        self.spiked_var.set(spiked)
        self.update_selected_spiked()

    def add_group(self):
        """Add a new surrogate group"""
        new_group = self.new_group_var.get().strip()
        if new_group and new_group not in self.groups:
            self.groups.append(new_group)
            self.group_cb['values'] = self.groups
            self.new_group_var.set('')

    def set_bulk_type(self, stype):
        self.type_var.set(stype)
        self.update_selected_type()

    def copy_to_selected(self):
        """Copy current UI values to all selected rows (v3.0.0: extended)"""
        self.update_selected_type()
        self.update_selected_spiked()
        self.update_selected_ratio()
        self.update_selected_group()

    def fill_down(self):
        """Fill values from the first selected row to all subsequent selected rows"""
        selection = self.tree.selection()
        if len(selection) < 2: return
        
        first_idx = int(selection[0])
        template = self.samples[first_idx].copy()
        
        self._updating_ui = True
        try:
            for iid in selection[1:]:
                idx = int(iid)
                self.samples[idx]['type'] = template['type']
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    def show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def on_double_click(self, event):
        """Handle direct cell editing"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        
        column = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        idx = int(iid)
        
        # Get cell bounding box
        x, y, w, h = self.tree.bbox(iid, column)
        
        # Create editor based on column
        if column == "#2": # Type
            self._show_cell_combobox(iid, column, x, y, w, h, ["Sample", "Blank"], "type")

    def _show_cell_combobox(self, iid, column, x, y, w, h, values, key):
        cb = ttk.Combobox(self.tree, values=values, state='readonly')
        cb.set(self.samples[int(iid)][key])
        cb.place(x=x, y=y, width=w, height=h)
        cb.focus()
        
        def finish(event=None):
            val = cb.get()
            self.samples[int(iid)][key] = val
            cb.destroy()
            self.refresh_table()
            
        cb.bind('<<ComboboxSelected>>', finish)
        cb.bind('<FocusOut>', lambda e: cb.destroy())
        cb.bind('<Escape>', lambda e: cb.destroy())

    def toggle_is_enable(self):
        """Enable/disable method frame based on checkbox"""
        if self.enable_var.get():
            self._enable_widgets(self.method_frame)
        else:
            self._disable_widgets(self.method_frame)

    def _enable_widgets(self, parent):
        """Recursively enable all widgets"""
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                self._enable_widgets(child)
            else:
                try:
                    child.configure(state='normal')
                except Exception:
                    pass

    def _disable_widgets(self, parent):
        """Recursively disable all widgets"""
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                self._disable_widgets(child)
            else:
                try:
                    child.configure(state='disabled')
                except Exception:
                    pass

    def update_method_display(self):
        """Show/hide panels based on selected method"""
        method = self.method_var.get()

        # Hide all panels
        self.manual_panel.grid_remove()
        self.mz_ri_panel.grid_remove()
        self.msp_panel.grid_remove()

        # Show selected panel
        if method == 'manual':
            self.manual_panel.grid()
        elif method == 'mz_ri':
            self.mz_ri_panel.grid()
        elif method == 'msp':
            self.msp_panel.grid()

    def edit_is_value(self, event):
        """Edit IS value in table"""
        region = self.is_table.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.is_table.identify_column(event.x)
        if column != "#2":  # Only edit IS value column
            return

        item = self.is_table.identify_row(event.y)
        if not item:
            return

        # Get current values
        values = self.is_table.item(item, 'values')
        sample_name = values[0]
        current_value = values[1]

        # Get cell bounding box
        x, y, w, h = self.is_table.bbox(item, column)

        # Create entry widget
        entry = ttk.Entry(self.is_table)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()

        def save_value(event=None):
            try:
                new_value = float(entry.get())
                self.is_values[sample_name] = new_value
                self.refresh_is_table()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number")
            entry.destroy()

        entry.bind('<Return>', save_value)
        entry.bind('<FocusOut>', lambda e: entry.destroy())
        entry.bind('<Escape>', lambda e: entry.destroy())

    def download_template(self):
        """Generate and download CSV template"""
        filepath = filedialog.asksaveasfilename(
            title="Save IS Template",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Sample_Name', 'IS_Peak_Area'])
                    for sample in sorted(self.is_values.keys()):
                        writer.writerow([sample, 0.0])

                messagebox.showinfo("Success", f"Template saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template:\n{e}")

    def import_csv(self):
        """Import IS values from CSV"""
        filepath = filedialog.askopenfilename(
            title="Import IS Values",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sample = row.get('Sample_Name', row.get('Sample', ''))
                        value = row.get('IS_Peak_Area', row.get('IS_Value', '0'))

                        if sample in self.is_values:
                            try:
                                self.is_values[sample] = float(value)
                            except (ValueError, TypeError):
                                pass

                self.refresh_is_table()
                messagebox.showinfo("Success", "IS values imported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import CSV:\n{e}")

    def export_csv(self):
        """Export current IS values to CSV"""
        filepath = filedialog.asksaveasfilename(
            title="Export IS Values",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Sample_Name', 'IS_Peak_Area'])
                    for sample, value in sorted(self.is_values.items()):
                        writer.writerow([sample, value])

                messagebox.showinfo("Success", f"IS values exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export CSV:\n{e}")

    def browse_is_msp(self):
        """Browse for IS MSP file"""
        filepath = filedialog.askopenfilename(
            title="Select IS Spectrum File",
            filetypes=[("MSP Files", "*.msp"), ("All Files", "*.*")]
        )

        if filepath:
            self.is_msp_var.set(filepath)

    def update_rt_labels_mz(self):
        """Update labels for m/z+RI panel based on RI/RT selection (v2.7.0)"""
        if self.use_rt_mz_var.get():
            # Use RT
            self.target_ri_label.config(text="Target RT (min):")
            self.ri_tol_label.config(text="RT Tolerance (min):")
            self.ri_tol_var.set(0.1)  # Default RT tolerance in minutes
        else:
            # Use RI
            self.target_ri_label.config(text="Target RI:")
            self.ri_tol_label.config(text="RI Tolerance:")
            self.ri_tol_var.set(50.0)  # Default RI tolerance

    def update_rt_labels_msp(self):
        """Update labels for MSP panel based on RI/RT selection (v2.7.0)"""
        if self.use_rt_msp_var.get():
            # Use RT
            self.msp_tol_label.config(text="RT Tolerance (min):")
            self.msp_ri_tol_var.set(0.1)  # Default RT tolerance in minutes
        else:
            # Use RI
            self.msp_tol_label.config(text="RI Tolerance:")
            self.msp_ri_tol_var.set(50.0)  # Default RI tolerance

    def go_back(self):
        # v3.0.0: Go back to surrogate config screen
        entry_point = self.app.pipeline_config['entry_point']
        if entry_point in ['raw', 'mzml']:
            self.app.show_screen('mzmine_config')
        else:
            self.app.show_screen('surrogate_config')

    def go_next(self):
        # Save classification to config (v3.0.0: extended structure)
        grouping = {s['name']: s for s in self.samples}
        self.app.pipeline_config['sample_grouping'] = grouping

        # v3.0.0: Update surrogate config with sample information
        surrogate_config = self.app.pipeline_config.get('surrogate_config', {})
        if surrogate_config.get('enabled', False):
            # Build groups structure
            groups = {}
            for group_name in self.groups:
                groups[group_name] = {'samples': [], 'references': []}
            
            # Populate groups with spiked samples and references
            spike_ratios = {}
            spiked_samples = []
            reference_samples = []
            
            for s in self.samples:
                if s.get('spiked', False):
                    spiked_samples.append(s['name'])
                    spike_ratios[s['name']] = s.get('spike_ratio', 1.0)
                    
                    group = s.get('group', 'Default')
                    if group not in groups:
                        groups[group] = {'samples': [], 'references': []}
                    
                    if s['type'] == 'Reference':
                        groups[group]['references'].append(s['name'])
                        reference_samples.append(s['name'])
                    else:
                        groups[group]['samples'].append(s['name'])
            
            surrogate_config['groups'] = groups
            surrogate_config['spike_ratios'] = spike_ratios
            surrogate_config['spiked_samples'] = spiked_samples
            surrogate_config['reference_samples'] = reference_samples
            
            self.app.pipeline_config['surrogate_config'] = surrogate_config

        # Build IS config (v2.8.0: integrated into this screen)
        is_config = {
            'enabled': self.enable_var.get()
        }

        if is_config['enabled']:
            method = self.method_var.get()
            is_config['method'] = method

            if method == 'manual':
                # Check if any IS values were provided
                if not any(v > 0 for v in self.is_values.values()):
                    result = messagebox.askyesno(
                        "No IS Values",
                        "No IS values have been entered. Continue without normalization?",
                        icon='warning'
                    )
                    if not result:
                        return
                    is_config['enabled'] = False
                else:
                    is_config['is_values'] = self.is_values.copy()

            elif method == 'mz_ri':
                target_mz = self.target_mz_var.get()
                target_value = self.target_ri_var.get()
                use_rt = self.use_rt_mz_var.get()

                if target_mz <= 0 or target_value <= 0:
                    param_name = "RT" if use_rt else "RI"
                    messagebox.showerror("Invalid Input", f"Please enter valid m/z and {param_name} values (> 0)")
                    return

                is_config['target_mz'] = target_mz
                is_config['mz_tolerance'] = self.mz_tol_var.get()
                is_config['target_value'] = target_value
                is_config['value_tolerance'] = self.ri_tol_var.get()
                is_config['use_rt'] = use_rt

            elif method == 'msp':
                msp_file = self.is_msp_var.get()

                if not msp_file or not Path(msp_file).exists():
                    messagebox.showerror("Invalid File", "Please select a valid MSP file")
                    return

                is_config['msp_file'] = msp_file
                is_config['value_tolerance'] = self.msp_ri_tol_var.get()
                is_config['use_rt'] = self.use_rt_msp_var.get()

        # Store in pipeline config
        self.app.pipeline_config['is_config'] = is_config

        # Navigate directly to execution (v2.8.0: removed separate IS screen)
        self.app.show_screen('execution')


class InternalStandardScreen(BaseScreen):
    """Internal Standard Normalization Configuration (v2.6.0)"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "Internal Standard Normalization",
            "Normalize feature abundances using internal standard peak areas (optional)"
        )

        # Main content area with scroll
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Enable checkbox
        enable_frame = ttk.Frame(main_frame)
        enable_frame.pack(fill='x', pady=(0, 15))

        self.enable_var = tk.BooleanVar(value=False)
        enable_check = ttk.Checkbutton(
            enable_frame,
            text="Enable Internal Standard Normalization",
            variable=self.enable_var,
            command=self.toggle_enable
        )
        enable_check.pack(anchor='w')

        ttk.Label(
            enable_frame,
            text="Note: Normalization is applied BEFORE Blank Feature Filtering (BFF)",
            font=('Arial', 9, 'italic'),
            foreground='gray'
        ).pack(anchor='w', padx=(25, 0))

        # Method selection frame (initially disabled)
        self.method_frame = ttk.LabelFrame(main_frame, text="Normalization Method", padding=15)
        self.method_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.method_var = tk.StringVar(value='manual')

        # Manual entry
        manual_radio = ttk.Radiobutton(
            self.method_frame,
            text="Manual Entry",
            variable=self.method_var,
            value='manual',
            command=self.update_method_display
        )
        manual_radio.grid(row=0, column=0, sticky='w', padx=5, pady=5)

        # Auto by m/z + RI
        mz_ri_radio = ttk.Radiobutton(
            self.method_frame,
            text="Auto-detect by m/z + RI",
            variable=self.method_var,
            value='mz_ri',
            command=self.update_method_display
        )
        mz_ri_radio.grid(row=1, column=0, sticky='w', padx=5, pady=5)

        # Auto by MSP
        msp_radio = ttk.Radiobutton(
            self.method_frame,
            text="Auto-detect by MSP Spectrum",
            variable=self.method_var,
            value='msp',
            command=self.update_method_display
        )
        msp_radio.grid(row=2, column=0, sticky='w', padx=5, pady=5)

        # --- Manual Entry Panel ---
        self.manual_panel = ttk.Frame(self.method_frame)
        self.manual_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        ttk.Label(
            self.manual_panel,
            text="Enter IS peak area for each sample (or import CSV):",
            font=('Arial', 9, 'bold')
        ).pack(anchor='w', pady=(0, 5))

        # Buttons for CSV
        button_row = ttk.Frame(self.manual_panel)
        button_row.pack(fill='x', pady=(0, 5))

        ttk.Button(button_row, text="Download Template CSV", command=self.download_template).pack(side='left', padx=(0, 5))
        ttk.Button(button_row, text="Import CSV", command=self.import_csv).pack(side='left', padx=(0, 5))
        ttk.Button(button_row, text="Export Current", command=self.export_csv).pack(side='left')

        # Table for manual entry
        table_frame = ttk.Frame(self.manual_panel)
        table_frame.pack(fill='both', expand=True)

        self.is_table = ttk.Treeview(
            table_frame,
            columns=('sample', 'is_value'),
            show='headings',
            height=8
        )
        self.is_table.heading('sample', text='Sample Name')
        self.is_table.heading('is_value', text='IS Peak Area')
        self.is_table.column('sample', width=300)
        self.is_table.column('is_value', width=150)

        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.is_table.yview)
        self.is_table.configure(yscrollcommand=scrollbar.set)

        self.is_table.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.is_table.bind('<Double-1>', self.edit_is_value)

        # --- m/z + RI Panel ---
        self.mz_ri_panel = ttk.Frame(self.method_frame)
        self.mz_ri_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        # RI/RT selection (v2.7.0)
        rt_selection_frame = ttk.Frame(self.mz_ri_panel)
        rt_selection_frame.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))

        ttk.Label(rt_selection_frame, text="Match by:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 10))
        self.use_rt_mz_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(rt_selection_frame, text="Retention Index (RI)", variable=self.use_rt_mz_var, value=False, command=self.update_rt_labels_mz).pack(side='left', padx=5)
        ttk.Radiobutton(rt_selection_frame, text="Retention Time (RT)", variable=self.use_rt_mz_var, value=True, command=self.update_rt_labels_mz).pack(side='left', padx=5)

        ttk.Label(self.mz_ri_panel, text="Target m/z:", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.target_mz_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.target_mz_var, width=15).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(self.mz_ri_panel, text="m/z Tolerance:", font=('Arial', 9, 'bold')).grid(row=1, column=2, sticky='w', pady=5, padx=(15, 0))
        self.mz_tol_var = tk.DoubleVar(value=0.5)
        ttk.Entry(self.mz_ri_panel, textvariable=self.mz_tol_var, width=10).grid(row=1, column=3, sticky='w', padx=5, pady=5)

        self.target_ri_label = ttk.Label(self.mz_ri_panel, text="Target RI:", font=('Arial', 9, 'bold'))
        self.target_ri_label.grid(row=2, column=0, sticky='w', pady=5)
        self.target_ri_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.target_ri_var, width=15).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        self.ri_tol_label = ttk.Label(self.mz_ri_panel, text="RI Tolerance:", font=('Arial', 9, 'bold'))
        self.ri_tol_label.grid(row=2, column=2, sticky='w', pady=5, padx=(15, 0))
        self.ri_tol_var = tk.DoubleVar(value=50.0)
        ttk.Entry(self.mz_ri_panel, textvariable=self.ri_tol_var, width=10).grid(row=2, column=3, sticky='w', padx=5, pady=5)

        ttk.Label(
            self.mz_ri_panel,
            text="The software will find the feature with highest abundance matching these criteria.",
            font=('Arial', 8, 'italic'),
            foreground='gray'
        ).grid(row=3, column=0, columnspan=4, sticky='w', pady=(10, 0))

        # --- MSP Panel ---
        self.msp_panel = ttk.Frame(self.method_frame)
        self.msp_panel.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=10)

        # RI/RT selection (v2.7.0)
        rt_selection_frame_msp = ttk.Frame(self.msp_panel)
        rt_selection_frame_msp.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        ttk.Label(rt_selection_frame_msp, text="Match by:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 10))
        self.use_rt_msp_var = tk.BooleanVar(value=False)
        ttk.Radiobutton(rt_selection_frame_msp, text="Retention Index (RI)", variable=self.use_rt_msp_var, value=False, command=self.update_rt_labels_msp).pack(side='left', padx=5)
        ttk.Radiobutton(rt_selection_frame_msp, text="Retention Time (RT)", variable=self.use_rt_msp_var, value=True, command=self.update_rt_labels_msp).pack(side='left', padx=5)

        ttk.Label(self.msp_panel, text="IS Spectrum File (.msp):", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.is_msp_var = tk.StringVar(value='')
        ttk.Entry(self.msp_panel, textvariable=self.is_msp_var, width=40).grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        ttk.Button(self.msp_panel, text="Browse...", command=self.browse_is_msp).grid(row=1, column=2, sticky='w', pady=5)

        self.msp_panel.columnconfigure(1, weight=1)

        self.msp_tol_label = ttk.Label(self.msp_panel, text="RI Tolerance:", font=('Arial', 9, 'bold'))
        self.msp_tol_label.grid(row=2, column=0, sticky='w', pady=5)
        self.msp_ri_tol_var = tk.DoubleVar(value=50.0)
        ttk.Entry(self.msp_panel, textvariable=self.msp_ri_tol_var, width=10).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(
            self.msp_panel,
            text="The software will match the spectrum to features using spectral similarity.",
            font=('Arial', 8, 'italic'),
            foreground='gray'
        ).grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))

        # Navigation buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

        # Initialize state
        self.is_values = {}  # {sample_name: float}
        self.update_method_display()
        self.toggle_enable()

    def on_show(self):
        """Populate sample list when screen is shown"""
        # Get sample list from app config
        grouping = self.app.pipeline_config.get('sample_grouping', {})
        if grouping:
            self.is_values = {}
            for sample_name, sample_info in grouping.items():
                # Initialize with 0 or preserve existing value
                if sample_name not in self.is_values:
                    self.is_values[sample_name] = 0.0

            self.refresh_table()

    def toggle_enable(self):
        """Enable/disable method frame based on checkbox"""
        if self.enable_var.get():
            self._enable_widgets(self.method_frame)
        else:
            self._disable_widgets(self.method_frame)

    def _enable_widgets(self, parent):
        """Recursively enable all widgets"""
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                self._enable_widgets(child)
            else:
                try:
                    child.configure(state='normal')
                except Exception:
                    pass

    def _disable_widgets(self, parent):
        """Recursively disable all widgets"""
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                self._disable_widgets(child)
            else:
                try:
                    child.configure(state='disabled')
                except Exception:
                    pass

    def update_method_display(self):
        """Show/hide panels based on selected method"""
        method = self.method_var.get()

        # Hide all panels
        self.manual_panel.grid_remove()
        self.mz_ri_panel.grid_remove()
        self.msp_panel.grid_remove()

        # Show selected panel
        if method == 'manual':
            self.manual_panel.grid()
        elif method == 'mz_ri':
            self.mz_ri_panel.grid()
        elif method == 'msp':
            self.msp_panel.grid()

    def refresh_table(self):
        """Refresh the IS values table"""
        self.is_table.delete(*self.is_table.get_children())

        for sample, value in sorted(self.is_values.items()):
            self.is_table.insert('', 'end', values=(sample, f"{value:.2f}"))

    def edit_is_value(self, event):
        """Edit IS value in table"""
        region = self.is_table.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.is_table.identify_column(event.x)
        if column != "#2":  # Only edit IS value column
            return

        item = self.is_table.identify_row(event.y)
        if not item:
            return

        # Get current values
        values = self.is_table.item(item, 'values')
        sample_name = values[0]
        current_value = values[1]

        # Get cell bounding box
        x, y, w, h = self.is_table.bbox(item, column)

        # Create entry widget
        entry = ttk.Entry(self.is_table)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()

        def save_value(event=None):
            try:
                new_value = float(entry.get())
                self.is_values[sample_name] = new_value
                self.refresh_table()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number")
            entry.destroy()

        entry.bind('<Return>', save_value)
        entry.bind('<FocusOut>', lambda e: entry.destroy())
        entry.bind('<Escape>', lambda e: entry.destroy())

    def download_template(self):
        """Generate and download CSV template"""
        filepath = filedialog.asksaveasfilename(
            title="Save IS Template",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Sample_Name', 'IS_Peak_Area'])
                    for sample in sorted(self.is_values.keys()):
                        writer.writerow([sample, 0.0])

                messagebox.showinfo("Success", f"Template saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template:\n{e}")

    def import_csv(self):
        """Import IS values from CSV"""
        filepath = filedialog.askopenfilename(
            title="Import IS Values",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sample = row.get('Sample_Name', row.get('Sample', ''))
                        value = row.get('IS_Peak_Area', row.get('IS_Value', '0'))

                        if sample in self.is_values:
                            try:
                                self.is_values[sample] = float(value)
                            except (ValueError, TypeError):
                                pass

                self.refresh_table()
                messagebox.showinfo("Success", "IS values imported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import CSV:\n{e}")

    def export_csv(self):
        """Export current IS values to CSV"""
        filepath = filedialog.asksaveasfilename(
            title="Export IS Values",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if filepath:
            try:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Sample_Name', 'IS_Peak_Area'])
                    for sample, value in sorted(self.is_values.items()):
                        writer.writerow([sample, value])

                messagebox.showinfo("Success", f"IS values exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export CSV:\n{e}")

    def browse_is_msp(self):
        """Browse for IS MSP file"""
        filepath = filedialog.askopenfilename(
            title="Select IS Spectrum File",
            filetypes=[("MSP Files", "*.msp"), ("All Files", "*.*")]
        )

        if filepath:
            self.is_msp_var.set(filepath)

    def update_rt_labels_mz(self):
        """Update labels for m/z+RI panel based on RI/RT selection (v2.7.0)"""
        if self.use_rt_mz_var.get():
            # Use RT
            self.target_ri_label.config(text="Target RT (min):")
            self.ri_tol_label.config(text="RT Tolerance (min):")
            self.ri_tol_var.set(0.1)  # Default RT tolerance in minutes
        else:
            # Use RI
            self.target_ri_label.config(text="Target RI:")
            self.ri_tol_label.config(text="RI Tolerance:")
            self.ri_tol_var.set(50.0)  # Default RI tolerance

    def update_rt_labels_msp(self):
        """Update labels for MSP panel based on RI/RT selection (v2.7.0)"""
        if self.use_rt_msp_var.get():
            # Use RT
            self.msp_tol_label.config(text="RT Tolerance (min):")
            self.msp_ri_tol_var.set(0.1)  # Default RT tolerance in minutes
        else:
            # Use RI
            self.msp_tol_label.config(text="RI Tolerance:")
            self.msp_ri_tol_var.set(50.0)  # Default RI tolerance

    def go_back(self):
        """Go back to sample grouping"""
        self.app.show_screen('sample_grouping')

    def go_next(self):
        """Validate and proceed"""
        # Build IS config
        is_config = {
            'enabled': self.enable_var.get()
        }

        if is_config['enabled']:
            method = self.method_var.get()
            is_config['method'] = method

            if method == 'manual':
                # Check if any IS values were provided
                if not any(v > 0 for v in self.is_values.values()):
                    result = messagebox.askyesno(
                        "No IS Values",
                        "No IS values have been entered. Continue without normalization?",
                        icon='warning'
                    )
                    if not result:
                        return
                    is_config['enabled'] = False
                else:
                    is_config['is_values'] = self.is_values.copy()

            elif method == 'mz_ri':
                target_mz = self.target_mz_var.get()
                target_value = self.target_ri_var.get()
                use_rt = self.use_rt_mz_var.get()

                if target_mz <= 0 or target_value <= 0:
                    param_name = "RT" if use_rt else "RI"
                    messagebox.showerror("Invalid Input", f"Please enter valid m/z and {param_name} values (> 0)")
                    return

                is_config['target_mz'] = target_mz
                is_config['mz_tolerance'] = self.mz_tol_var.get()
                is_config['target_value'] = target_value
                is_config['value_tolerance'] = self.ri_tol_var.get()
                is_config['use_rt'] = use_rt  # v2.7.0: RT or RI selection

            elif method == 'msp':
                msp_file = self.is_msp_var.get()

                if not msp_file or not Path(msp_file).exists():
                    messagebox.showerror("Invalid File", "Please select a valid MSP file")
                    return

                is_config['msp_file'] = msp_file
                is_config['value_tolerance'] = self.msp_ri_tol_var.get()
                is_config['use_rt'] = self.use_rt_msp_var.get()  # v2.7.0: RT or RI selection

        # Store in pipeline config
        self.app.pipeline_config['is_config'] = is_config

        # Navigate to execution
        self.app.show_screen('execution')


class MSConvertScreen(BaseScreen):
    """MSConvert configuration"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "MSConvert Configuration",
            "Locate msconvert.exe for raw data conversion"
        )

        # Content
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # Info box
        info_frame = ttk.Frame(content)
        info_frame.pack(fill='x', pady=(0, 20))

        info_text = (
            "MSConvert is required to convert Agilent .D files to mzML format.\n"
            "It is part of the ProteoWizard suite.\n\n"
            "Download from: http://proteowizard.sourceforge.net/"
        )

        info_label = ttk.Label(
            info_frame,
            text=info_text,
            foreground='blue',
            justify='left'
        )
        info_label.pack(anchor='w')

        # Path selection
        path_frame = ttk.LabelFrame(content, text="MSConvert Path", padding=15)
        path_frame.pack(fill='x', pady=10)

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        path_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        browse_btn = ttk.Button(path_frame, text="Browse...", command=self.browse_path)
        browse_btn.pack(side='right')

        hint_label = ttk.Label(
            path_frame,
            text="Typically: C:\\...\\msconvert.exe",
            foreground='gray'
        )
        hint_label.pack(anchor='w', pady=(5, 0))

        # Save as default checkbox
        self.save_default_var = tk.BooleanVar(value=True)
        save_check = ttk.Checkbutton(
            content,
            text="Save this path as default for future sessions",
            variable=self.save_default_var
        )
        save_check.pack(anchor='w', pady=10)

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

    def on_show(self):
        """Load saved path"""
        saved_path = self.app.pipeline_config.get('msconvert_path', '')
        if not saved_path:
            # Try to find in local software folder
            local_path = Path(__file__).parent.parent / "software" / "pwiz-bin" / "msconvert.exe"
            if local_path.exists():
                saved_path = str(local_path)

        self.path_var.set(saved_path)

    def browse_path(self):
        filepath = filedialog.askopenfilename(
            title="Select msconvert.exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if filepath:
            self.path_var.set(filepath)

    def go_back(self):
        self.app.show_screen('analysis_params')

    def go_next(self):
        path = self.path_var.get()

        if not path:
            messagebox.showerror("Error", "Please select msconvert.exe")
            return

        if not Path(path).exists():
            messagebox.showerror("Error", f"File not found: {path}")
            return

        # Save to config
        self.app.pipeline_config['msconvert_path'] = path

        if self.save_default_var.get():
            self.app.app_config.set('msconvert_path', path)
            self.app.app_config.save_defaults()

        # Next: MZmine config
        self.app.show_screen('mzmine_config')


class MZmineScreen(BaseScreen):
    """MZmine configuration"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "MZmine Configuration",
            "Configure MZmine for feature detection and deconvolution"
        )

        # Content
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # MZmine console path
        mzmine_frame = ttk.LabelFrame(content, text="MZmine Console", padding=15)
        mzmine_frame.pack(fill='x', pady=10)

        self.mzmine_var = tk.StringVar()
        mzmine_entry = ttk.Entry(mzmine_frame, textvariable=self.mzmine_var, width=50)
        mzmine_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        mzmine_btn = ttk.Button(mzmine_frame, text="Browse...", command=self.browse_mzmine)
        mzmine_btn.pack(side='right')

        # User file
        user_frame = ttk.LabelFrame(content, text="User File (.mzuser)", padding=15)
        user_frame.pack(fill='x', pady=10)

        self.user_var = tk.StringVar()
        user_entry = ttk.Entry(user_frame, textvariable=self.user_var, width=50)
        user_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        user_btn = ttk.Button(user_frame, text="Browse...", command=self.browse_user)
        user_btn.pack(side='right')

        # Batch file
        batch_frame = ttk.LabelFrame(content, text="Batch File (.mzbatch)", padding=15)
        batch_frame.pack(fill='x', pady=10)

        self.batch_var = tk.StringVar()
        batch_entry = ttk.Entry(batch_frame, textvariable=self.batch_var, width=50)
        batch_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        batch_btn = ttk.Button(batch_frame, text="Browse...", command=self.browse_batch)
        batch_btn.pack(side='right')

        # Thread count
        threads_frame = ttk.LabelFrame(content, text="Thread Count", padding=15)
        threads_frame.pack(fill='x', pady=10)

        self.threads_var = tk.IntVar(value=2)
        threads_spin = ttk.Spinbox(
            threads_frame,
            from_=1,
            to=16,
            textvariable=self.threads_var,
            width=10
        )
        threads_spin.pack(anchor='w')

        # Save as default
        self.save_default_var = tk.BooleanVar(value=True)
        save_check = ttk.Checkbutton(
            content,
            text="Save these settings as default",
            variable=self.save_default_var
        )
        save_check.pack(anchor='w', pady=10)

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

    def on_show(self):
        """Load saved paths"""
        # Try local paths first
        mzmine_path = self.app.pipeline_config.get('mzmine_path', '')
        if not mzmine_path:
            local = Path(__file__).parent.parent / "software" / "mzmine" / "mzmine_console.exe"
            if local.exists():
                mzmine_path = str(local)

        user_path = self.app.pipeline_config.get('mzmine_user_file', '')
        if not user_path:
            local = get_resource_path("users" / Path("default.mzuser"))
            if local.exists():
                user_path = str(local)

        batch_path = self.app.pipeline_config.get('mzmine_batch_file', '')
        if not batch_path:
            local = get_resource_path("config" / Path("gc_ei_workflow.mzbatch"))
            if local.exists():
                batch_path = str(local)

        self.mzmine_var.set(mzmine_path)
        self.user_var.set(user_path)
        self.batch_var.set(batch_path)
        self.threads_var.set(self.app.pipeline_config.get('mzmine_threads', 2))

    def browse_mzmine(self):
        filepath = filedialog.askopenfilename(
            title="Select mzmine_console.exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if filepath:
            self.mzmine_var.set(filepath)

    def browse_user(self):
        filepath = filedialog.askopenfilename(
            title="Select MZmine User File",
            filetypes=[("MZmine User", "*.mzuser"), ("All Files", "*.*")]
        )
        if filepath:
            self.user_var.set(filepath)

    def browse_batch(self):
        filepath = filedialog.askopenfilename(
            title="Select MZmine Batch File",
            filetypes=[("MZmine Batch", "*.mzbatch"), ("All Files", "*.*")]
        )
        if filepath:
            self.batch_var.set(filepath)

    def go_back(self):
        entry_point = self.app.pipeline_config['entry_point']
        if entry_point == 'raw':
            self.app.show_screen('msconvert_config')
        else:
            self.app.show_screen('analysis_params')

    def go_next(self):
        # Validate
        if not self.mzmine_var.get() or not Path(self.mzmine_var.get()).exists():
            messagebox.showerror("Error", "Please select a valid mzmine_console.exe")
            return

        if not self.user_var.get() or not Path(self.user_var.get()).exists():
            messagebox.showerror("Error", "Please select a valid user file")
            return

        if not self.batch_var.get() or not Path(self.batch_var.get()).exists():
            messagebox.showerror("Error", "Please select a valid batch file")
            return

        # Save to config
        self.app.pipeline_config['mzmine_path'] = self.mzmine_var.get()
        self.app.pipeline_config['mzmine_user_file'] = self.user_var.get()
        self.app.pipeline_config['mzmine_batch_file'] = self.batch_var.get()
        self.app.pipeline_config['mzmine_threads'] = self.threads_var.get()

        if self.save_default_var.get():
            self.app.app_config.set('mzmine_path', self.mzmine_var.get())
            self.app.app_config.set('mzmine_user_file', self.user_var.get())
            self.app.app_config.set('mzmine_batch_file', self.batch_var.get())
            self.app.app_config.set('mzmine_threads', self.threads_var.get())
            self.app.app_config.save_defaults()

        # Next: Sample Grouping
        self.app.show_screen('sample_grouping')


class AnalysisParamsScreen(BaseScreen):
    """Final analysis parameters before execution"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "Analysis Parameters",
            "Configure library matching and annotation settings"
        )

        # Content
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # Library path
        lib_frame = ttk.LabelFrame(content, text="Spectral Library (.CSV or .MSP)", padding=15)
        lib_frame.pack(fill='x', pady=10)

        self.library_var = tk.StringVar()
        lib_entry = ttk.Entry(lib_frame, textvariable=self.library_var, width=50)
        lib_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        lib_btn = ttk.Button(lib_frame, text="Browse...", command=self.browse_library)
        lib_btn.pack(side='right')

        # RI calibration
        ri_frame = ttk.LabelFrame(content, text="RI Calibration File (Optional)", padding=15)
        ri_frame.pack(fill='x', pady=10)

        self.ri_var = tk.StringVar()
        ri_entry = ttk.Entry(ri_frame, textvariable=self.ri_var, width=50)
        ri_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ri_btn = ttk.Button(ri_frame, text="Browse...", command=self.browse_ri)
        ri_btn.pack(side='right')

        # EPA API Key
        api_frame = ttk.LabelFrame(content, text="EPA CompTox API Key (Optional)", padding=15)
        api_frame.pack(fill='x', pady=10)

        self.api_var = tk.StringVar()
        api_entry = ttk.Entry(api_frame, textvariable=self.api_var, width=50)
        api_entry.pack(fill='x')

        api_hint = ttk.Label(
            api_frame,
            text="For toxicity data enrichment",
            foreground='gray'
        )
        api_hint.pack(anchor='w', pady=(5, 0))

        # Blank identifier
        blank_frame = ttk.LabelFrame(content, text="Blank Sample Identifier", padding=15)
        blank_frame.pack(fill='x', pady=10)

        self.blank_var = tk.StringVar(value='fieldblank')
        blank_entry = ttk.Entry(blank_frame, textvariable=self.blank_var, width=50)
        blank_entry.pack(fill='x')

        blank_hint = ttk.Label(
            blank_frame,
            text="String to identify blank samples (case-insensitive)",
            foreground='gray'
        )
        blank_hint.pack(anchor='w', pady=(5, 0))

        # BFF mode (v3.0.4)
        bff_frame = ttk.LabelFrame(content, text="Blank Feature Filtering (BFF) Mode", padding=15)
        bff_frame.pack(fill='x', pady=10)

        self.bff_mode_var = tk.StringVar(value='standard')
        ttk.Radiobutton(
            bff_frame,
            text="Standard (mean + 3*SD) — legacy default",
            variable=self.bff_mode_var,
            value='standard'
        ).pack(anchor='w')
        ttk.Radiobutton(
            bff_frame,
            text="Adjusted (Shapiro-gated; robust median + 3*1.4826*MAD when blanks are non-normal)",
            variable=self.bff_mode_var,
            value='adjusted'
        ).pack(anchor='w')

        bff_hint = ttk.Label(
            bff_frame,
            text="Adjusted mode reduces false-negative filtering when sparse high-magnitude "
                 "blank detections inflate the SD.",
            foreground='gray',
            wraplength=600,
            justify='left'
        )
        bff_hint.pack(anchor='w', pady=(5, 0))

        # BFF threshold multiplier (c-factor)
        cfactor_row = ttk.Frame(bff_frame)
        cfactor_row.pack(fill='x', pady=(10, 0))
        ttk.Label(cfactor_row, text="Threshold multiplier (c):").pack(side='left')
        self.bff_cfactor_var = tk.StringVar(value='5.0')
        ttk.Entry(cfactor_row, textvariable=self.bff_cfactor_var, width=8).pack(side='left', padx=(8, 0))
        ttk.Label(
            cfactor_row,
            text="Applied as c*(threshold). Default 5.0 = legacy. Try 1 or 2 to relax.",
            foreground='gray'
        ).pack(side='left', padx=(8, 0))

        # Save preset button
        preset_frame = ttk.Frame(content)
        preset_frame.pack(fill='x', pady=20)

        preset_btn = ttk.Button(
            preset_frame,
            text="Save Current Configuration as Preset",
            command=self.app.save_preset
        )
        preset_btn.pack(anchor='w')

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

    def on_show(self):
        """Load saved values"""
        # Get library path from config - NEVER use fallback paths that could
        # contain developer-specific paths. Users should browse for their own files.
        lib_path = self.app.pipeline_config.get('library_path', '')
        ri_path = self.app.pipeline_config.get('ri_cal_path', '')

        self.library_var.set(lib_path)
        self.ri_var.set(ri_path)
        self.api_var.set(self.app.pipeline_config.get('epa_api_key', ''))
        self.blank_var.set(self.app.pipeline_config.get('blank_identifier', 'fieldblank'))
        self.bff_mode_var.set(self.app.pipeline_config.get('bff_mode', 'standard'))
        self.bff_cfactor_var.set(str(self.app.pipeline_config.get('bff_c_factor', 5.0)))

    def browse_library(self):
        filepath = filedialog.askopenfilename(
            title="Select Spectral Library",
            filetypes=[("Library Files", "*.csv *.msp"), ("CSV", "*.csv"), ("MSP", "*.msp"), ("All Files", "*.*")]
        )
        if filepath:
            self.library_var.set(filepath)

    def browse_ri(self):
        filepath = filedialog.askopenfilename(
            title="Select RI Calibration File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            self.ri_var.set(filepath)

    def go_back(self):
        self.app.show_screen('project_setup')

    def go_next(self):
        # Validate
        if not self.library_var.get() or not Path(self.library_var.get()).exists():
            messagebox.showerror("Error", "Please select a valid library file")
            return

        if not self.blank_var.get():
            messagebox.showerror("Error", "Please enter a blank identifier")
            return

        # Validate BFF c-factor (must be a positive number)
        try:
            cfactor = float(self.bff_cfactor_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("Error",
                f"BFF c-factor must be a number (got '{self.bff_cfactor_var.get()}')")
            return
        if cfactor <= 0:
            messagebox.showerror("Error", f"BFF c-factor must be > 0 (got {cfactor})")
            return

        # Save to config
        self.app.pipeline_config['library_path'] = self.library_var.get()
        self.app.pipeline_config['ri_cal_path'] = self.ri_var.get()
        self.app.pipeline_config['epa_api_key'] = self.api_var.get()
        self.app.pipeline_config['blank_identifier'] = self.blank_var.get()
        self.app.pipeline_config['bff_mode'] = self.bff_mode_var.get()
        self.app.pipeline_config['bff_c_factor'] = cfactor

        # Save defaults
        self.app.app_config.set('library_path', self.library_var.get())
        self.app.app_config.set('ri_cal_path', self.ri_var.get())
        self.app.app_config.set('epa_api_key', self.api_var.get())
        self.app.app_config.set('blank_identifier', self.blank_var.get())
        self.app.app_config.set('bff_mode', self.bff_mode_var.get())
        self.app.app_config.set('bff_c_factor', cfactor)
        self.app.app_config.save_defaults()

        # v3.0.0: Always go to surrogate config screen next
        self.app.show_screen('surrogate_config')


class SurrogateConfigScreen(BaseScreen):
    """
    Screen for configuring surrogate standard recovery analysis (v3.0.0)
    
    Allows users to:
    - Enable/disable surrogate recovery calculation
    - Select a surrogate standard library (CSV/MSP)
    - Include/exclude specific compounds from the library
    """

    def __init__(self, parent, app):
        super().__init__(parent, app)
        
        self.library_compounds = []  # List of compounds from loaded library
        self.selected_compounds = set()  # Names of selected compounds
        
        self.create_header(
            "Surrogate Standard Recovery",
            "Configure surrogate standard matching and recovery calculation (optional)"
        )
        
        # Main content
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)
        
        # Enable checkbox
        enable_frame = ttk.Frame(content)
        enable_frame.pack(fill='x', pady=(0, 15))
        
        self.enable_var = tk.BooleanVar(value=False)
        enable_check = ttk.Checkbutton(
            enable_frame,
            text="Calculate Surrogate Standard Recoveries",
            variable=self.enable_var,
            command=self.toggle_enable
        )
        enable_check.pack(anchor='w')
        
        ttk.Label(
            enable_frame,
            text="Match labeled surrogate standards and calculate % recovery relative to reference samples",
            font=('Arial', 9, 'italic'),
            foreground='gray'
        ).pack(anchor='w', padx=(25, 0))
        
        # Surrogate Library Frame (initially disabled)
        self.library_frame = ttk.LabelFrame(content, text="Surrogate Standard Library", padding=15)
        self.library_frame.pack(fill='x', pady=10)
        
        # Library path
        path_frame = ttk.Frame(self.library_frame)
        path_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(path_frame, text="Library Path:").pack(side='left')
        
        self.library_var = tk.StringVar()
        self.library_entry = ttk.Entry(path_frame, textvariable=self.library_var, width=50)
        self.library_entry.pack(side='left', fill='x', expand=True, padx=(10, 10))
        
        self.browse_btn = ttk.Button(path_frame, text="Browse...", command=self.browse_library)
        self.browse_btn.pack(side='right')
        
        ttk.Label(
            self.library_frame,
            text="Use CSV or MSP format (same format as suspect screening library)",
            font=('Arial', 9, 'italic'),
            foreground='gray'
        ).pack(anchor='w')
        
        # Compound Selection Frame
        self.compound_frame = ttk.LabelFrame(content, text="Compound Selection", padding=15)
        self.compound_frame.pack(fill='both', expand=True, pady=10)
        
        # Compound table
        table_frame = ttk.Frame(self.compound_frame)
        table_frame.pack(fill='both', expand=True)
        
        self.compound_tree = ttk.Treeview(
            table_frame,
            columns=('selected', 'name', 'ri', 'formula'),
            show='headings',
            selectmode='extended',
            height=10
        )
        self.compound_tree.heading('selected', text='Include')
        self.compound_tree.heading('name', text='Compound Name')
        self.compound_tree.heading('ri', text='RI')
        self.compound_tree.heading('formula', text='Formula')
        
        self.compound_tree.column('selected', width=60, anchor='center')
        self.compound_tree.column('name', width=250)
        self.compound_tree.column('ri', width=80, anchor='center')
        self.compound_tree.column('formula', width=120, anchor='center')
        
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.compound_tree.yview)
        self.compound_tree.configure(yscrollcommand=scrollbar.set)
        
        self.compound_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Double-click to toggle
        self.compound_tree.bind('<Double-1>', self.toggle_compound)
        
        # Button row for compound selection
        btn_frame = ttk.Frame(self.compound_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        self.select_all_btn = ttk.Button(btn_frame, text="Select All", command=self.select_all)
        self.select_all_btn.pack(side='left', padx=(0, 5))
        
        self.deselect_all_btn = ttk.Button(btn_frame, text="Deselect All", command=self.deselect_all)
        self.deselect_all_btn.pack(side='left')
        
        self.load_btn = ttk.Button(btn_frame, text="Load Library", command=self.load_library)
        self.load_btn.pack(side='right')
        
        # Status label
        self.status_label = ttk.Label(
            self.compound_frame,
            text="No library loaded",
            foreground='gray'
        )
        self.status_label.pack(anchor='w', pady=(10, 0))
        
        # Initially disable library section
        self._set_library_section_state('disabled')
        
        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])
    
    def on_show(self):
        """Load saved surrogate config"""
        surrogate_config = self.app.pipeline_config.get('surrogate_config', {})
        
        self.enable_var.set(surrogate_config.get('enabled', False))
        self.library_var.set(surrogate_config.get('library_path', ''))
        
        # Restore selected compounds if available
        selected = surrogate_config.get('selected_compounds', [])
        if selected:
            self.selected_compounds = set(selected)
        
        # Update UI state
        self.toggle_enable()
        
        # If library path is set, try to load it
        if self.library_var.get():
            self.load_library()
    
    def toggle_enable(self):
        """Enable/disable surrogate library section"""
        if self.enable_var.get():
            self._set_library_section_state('normal')
        else:
            self._set_library_section_state('disabled')
    
    def _set_library_section_state(self, state):
        """Set the state of library section widgets"""
        self.library_entry.configure(state=state)
        self.browse_btn.configure(state=state)
        self.load_btn.configure(state=state)
        self.select_all_btn.configure(state=state)
        self.deselect_all_btn.configure(state=state)
    
    def browse_library(self):
        """Browse for surrogate library file"""
        filepath = filedialog.askopenfilename(
            title="Select Surrogate Standard Library",
            filetypes=[
                ("Library Files", "*.csv *.msp"),
                ("CSV", "*.csv"),
                ("MSP", "*.msp"),
                ("All Files", "*.*")
            ]
        )
        if filepath:
            self.library_var.set(filepath)
            self.load_library()
    
    def load_library(self):
        """Load and display compounds from the library"""
        library_path = self.library_var.get()
        if not library_path or not os.path.exists(library_path):
            self.status_label.config(text="Invalid library path", foreground='red')
            return
        
        try:
            from src.library_parser import LibraryParser
            
            parser = LibraryParser(library_path)
            parser.load_library()
            self.library_compounds = parser.get_compounds()
            
            # Clear existing items
            for item in self.compound_tree.get_children():
                self.compound_tree.delete(item)
            
            # If no previous selection, select all by default
            if not self.selected_compounds:
                self.selected_compounds = {c.name for c in self.library_compounds}
            
            # Add compounds to tree
            for comp in self.library_compounds:
                is_selected = comp.name in self.selected_compounds
                self.compound_tree.insert('', 'end', values=(
                    '✓' if is_selected else '',
                    comp.name,
                    f"{comp.ri:.1f}",
                    comp.formula or ''
                ))
            
            self.status_label.config(
                text=f"Loaded {len(self.library_compounds)} compounds ({len(self.selected_compounds)} selected)",
                foreground='green'
            )
            
        except Exception as e:
            self.status_label.config(text=f"Error loading library: {e}", foreground='red')
            self.library_compounds = []
    
    def toggle_compound(self, event=None):
        """Toggle selection of double-clicked compound"""
        selection = self.compound_tree.selection()
        if not selection:
            return
        
        for item in selection:
            values = self.compound_tree.item(item, 'values')
            compound_name = values[1]
            
            if compound_name in self.selected_compounds:
                self.selected_compounds.discard(compound_name)
                new_values = ('', values[1], values[2], values[3])
            else:
                self.selected_compounds.add(compound_name)
                new_values = ('✓', values[1], values[2], values[3])
            
            self.compound_tree.item(item, values=new_values)
        
        self._update_status()
    
    def select_all(self):
        """Select all compounds"""
        self.selected_compounds = {c.name for c in self.library_compounds}
        self._refresh_tree_selection()
        self._update_status()
    
    def deselect_all(self):
        """Deselect all compounds"""
        self.selected_compounds.clear()
        self._refresh_tree_selection()
        self._update_status()
    
    def _refresh_tree_selection(self):
        """Update tree view to reflect current selection"""
        for item in self.compound_tree.get_children():
            values = self.compound_tree.item(item, 'values')
            compound_name = values[1]
            is_selected = compound_name in self.selected_compounds
            new_values = ('✓' if is_selected else '', values[1], values[2], values[3])
            self.compound_tree.item(item, values=new_values)
    
    def _update_status(self):
        """Update the status label"""
        if self.library_compounds:
            self.status_label.config(
                text=f"Loaded {len(self.library_compounds)} compounds ({len(self.selected_compounds)} selected)",
                foreground='green' if self.selected_compounds else 'orange'
            )
    
    def go_back(self):
        """Go back to analysis parameters"""
        self.app.show_screen('analysis_params')
    
    def go_next(self):
        """Save config and proceed"""
        # Build surrogate config
        surrogate_config = {
            'enabled': self.enable_var.get(),
            'library_path': self.library_var.get() if self.enable_var.get() else '',
            'selected_compounds': list(self.selected_compounds) if self.enable_var.get() else [],
            'groups': {'Default': {'samples': [], 'references': []}},  # Will be populated in sample classification
            'spike_ratios': {},
            'spiked_samples': [],
            'reference_samples': []
        }
        
        # Validate if enabled
        if surrogate_config['enabled']:
            if not surrogate_config['library_path'] or not os.path.exists(surrogate_config['library_path']):
                messagebox.showerror("Error", "Please select a valid surrogate library file")
                return
            
            if not surrogate_config['selected_compounds']:
                messagebox.showwarning("Warning", "No compounds selected. Please select at least one surrogate compound.")
                return
        
        self.app.pipeline_config['surrogate_config'] = surrogate_config
        
        # Determine next screen based on entry point
        entry_point = self.app.pipeline_config['entry_point']
        if entry_point == 'raw':
            self.app.show_screen('msconvert_config')
        elif entry_point == 'mzml':
            self.app.show_screen('mzmine_config')
        else:  # msp
            self.app.show_screen('sample_grouping')


class ExecutionScreen(BaseScreen):
    """Execution screen with live console output"""

    def __init__(self, parent, app):
        super().__init__(parent, app)

        self.create_header(
            "Running Analysis",
            "Please wait while the pipeline processes your data"
        )

        # Progress label
        self.status_label = ttk.Label(
            self,
            text="Initializing...",
            font=('Arial', 10, 'bold')
        )
        self.status_label.pack(pady=10)

        # Console output
        console_frame = ttk.LabelFrame(self, text="Console Output", padding=10)
        console_frame.pack(fill='both', expand=True, pady=10)

        self.console = scrolledtext.ScrolledText(
            console_frame,
            wrap=tk.WORD,
            font=('Courier', 9),
            bg='black',
            fg='white'
        )
        self.console.pack(fill='both', expand=True)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        self.progress.pack(fill='x', pady=10)

        # Buttons (initially hidden)
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side='bottom', fill='x', pady=(20, 0))

        self.cancel_btn = ttk.Button(
            self.button_frame,
            text="Cancel",
            command=self.cancel_execution,
            state='disabled'
        )
        self.cancel_btn.pack(side='left')

        self.view_results_btn = ttk.Button(
            self.button_frame,
            text="View Results",
            command=self.view_results
        )
        self.view_results_btn.pack(side='right')
        self.view_results_btn.pack_forget()  # Hide initially

        # Execution state
        self.process = None
        self.running = False

    def on_show(self):
        """Start execution when screen is shown"""
        self.console.delete('1.0', tk.END)
        self.status_label.config(text="Initializing...")
        self.progress.start()
        self.cancel_btn.config(state='normal')
        self.view_results_btn.pack_forget()

        # Start execution in thread
        self.running = True
        thread = threading.Thread(target=self.run_pipeline, daemon=True)
        thread.start()

    def apply_theme(self, theme_name):
        """Update console colors for theme"""
        if theme_name == 'dark':
            self.console.config(bg="#1e1e1e", fg="#e1e1e1", insertbackground="white")
        else:
            self.console.config(bg="white", fg="black", insertbackground="black")

    def run_pipeline(self):
        """Execute the pipeline"""
        try:
            # Build command
            config = self.app.pipeline_config
            pipeline_script = Path(__file__).parent / "gcms_pipeline.py"

            cmd = [sys.executable, str(pipeline_script)]

            # Add entry point
            entry_point = config['entry_point']
            if entry_point == 'raw':
                cmd.extend(['--from-raw', config['input_folder']])
            elif entry_point == 'mzml':
                cmd.extend(['--from-mzml', config['input_folder']])
            else:  # msp
                cmd.extend(['--from-mzmine', config['input_folder']])

            # Add other parameters
            cmd.extend(['--name', config['project_name']])
            cmd.extend(['--threads', str(config['mzmine_threads'])])
            cmd.extend(['--library', config['library_path']])
            cmd.extend(['--blank-id', config['blank_identifier']])
            cmd.extend(['--bff-mode', config.get('bff_mode', 'standard')])
            cmd.extend(['--bff-c-factor', str(config.get('bff_c_factor', 5.0))])
            cmd.extend(['--output', config['output_folder']])

            if config.get('ri_cal_path'):
                cmd.extend(['--ri-cal', config['ri_cal_path']])

            if config.get('epa_api_key'):
                cmd.extend(['--api-key', config['epa_api_key']])

            # Add grouping
            if config.get('sample_grouping'):
                grouping_file = Path(config['output_folder']) / "sample_grouping.json"
                try:
                    with open(grouping_file, 'w') as f:
                        json.dump(config['sample_grouping'], f)
                    cmd.extend(['--grouping', str(grouping_file)])
                except Exception as e:
                    self.log_console(f"Warning: Could not save grouping file: {e}\n")

            # Add IS configuration (v2.6.0)
            if config.get('is_config'):
                is_config_file = Path(config['output_folder']) / "is_config.json"
                try:
                    with open(is_config_file, 'w') as f:
                        json.dump(config['is_config'], f)
                    cmd.extend(['--is-config', str(is_config_file)])
                except Exception as e:
                    self.log_console(f"Warning: Could not save IS config file: {e}\n")

            # Add surrogate configuration (v3.0.0)
            surrogate_config = config.get('surrogate_config', {})
            if surrogate_config.get('enabled'):
                # Save surrogate config to JSON file
                surrogate_config_file = Path(config['output_folder']) / "surrogate_config.json"
                try:
                    with open(surrogate_config_file, 'w') as f:
                        json.dump(surrogate_config, f)
                    cmd.extend(['--surrogate-config', str(surrogate_config_file)])
                    self.log_console(f"Surrogate recovery analysis enabled\n")
                except Exception as e:
                    self.log_console(f"Warning: Could not save surrogate config file: {e}\n")
                
                # Add surrogate library path
                if surrogate_config.get('library_path'):
                    cmd.extend(['--surrogate-library', surrogate_config['library_path']])
                
                # Add reference samples
                if surrogate_config.get('reference_samples'):
                    ref_samples = ','.join(surrogate_config['reference_samples'])
                    cmd.extend(['--reference-samples', ref_samples])

            self.log_console(f"Command: {' '.join(cmd)}\n\n")
            self.update_status("Running pipeline...")

            # Execute
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Stream output
            for line in self.process.stdout:
                if not self.running:
                    break
                self.log_console(line)

            self.process.wait()

            if self.process.returncode == 0:
                self.update_status("Analysis Complete!")
                self.log_console("\n✓ Analysis completed successfully!\n")
                self.on_completion(success=True)
            else:
                self.update_status("Analysis Failed")
                self.log_console(f"\n✗ Analysis failed with exit code {self.process.returncode}\n")
                self.on_completion(success=False)

        except Exception as e:
            self.update_status("Error")
            self.log_console(f"\n✗ Error: {str(e)}\n")
            self.on_completion(success=False)

    def log_console(self, text):
        """Add text to console"""
        def update():
            self.console.insert(tk.END, text)
            self.console.see(tk.END)

        self.console.after(0, update)

    def update_status(self, text):
        """Update status label"""
        self.status_label.after(0, lambda: self.status_label.config(text=text))

    def on_completion(self, success):
        """Handle completion"""
        self.progress.stop()
        self.cancel_btn.config(state='disabled')

        if success:
            self.view_results_btn.pack(side='right')

            # Update project
            output_folder = Path(self.app.pipeline_config['output_folder'])
            project_name = self.app.pipeline_config['project_name']

            # Find results in the selected output folder
            # gcms_pipeline.py creates results in: {base_output}/results/{run_name}
            # We need to find the run_name subfolder. Since run_name has a timestamp, 
            # we look for folders starting with project_name
            
            results_base = output_folder / "results"
            if results_base.exists():
                # Find the most recent subfolder matching project_name
                subfolders = [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith(project_name)]
                if subfolders:
                    # Sort by modification time to get the newest one
                    latest_results_dir = max(subfolders, key=os.path.getmtime)
                    
                    csv_files = list(latest_results_dir.glob("*.csv"))
                    pdf_files = list(latest_results_dir.glob("*.pdf"))

                    if csv_files:
                        csv_file = csv_files[0]
                        pdf_file = pdf_files[0] if pdf_files else ""

                        # Count matches
                        match_count = 0
                        try:
                            with open(csv_file, 'r', encoding='utf-8') as f:
                                match_count = sum(1 for _ in f) - 1  # Subtract header
                        except (IOError, OSError):
                            pass

                        self.app.project.set_results(csv_file, pdf_file, match_count)
                        self.app.save_project() # Auto-save on completion

    def cancel_execution(self):
        """Cancel running execution"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.running = False
            self.update_status("Cancelled")
            self.log_console("\n✗ Analysis cancelled by user\n")

    def view_results(self):
        """Go to results screen"""
        self.app.show_screen('results')


class ResultsScreen(BaseScreen):
    """Interactive results viewer"""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.matches = []
        self.current_match = None
        self.viz = None
        self.struct_img = None
        self.plot_img = None

        self.create_header(
            "Analysis Results",
            "Interactive results viewer"
        )

        # Create main paned window
        main_paned = ttk.PanedWindow(self, orient='horizontal')
        main_paned.pack(fill='both', expand=True)

        # Left panel: Match list
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        list_label = ttk.Label(left_frame, text="Found Matches", font=('Arial', 10, 'bold'))
        list_label.pack(anchor='w', pady=(0, 5))

        # Treeview for matches
        self.tree = ttk.Treeview(
            left_frame,
            columns=('name', 'score', 'ri'),
            show='tree headings',
            selectmode='browse'
        )
        self.tree.heading('name', text='Compound')
        self.tree.heading('score', text='Score')
        self.tree.heading('ri', text='RI')
        self.tree.column('#0', width=40)
        self.tree.column('name', width=180)
        self.tree.column('score', width=60)
        self.tree.column('ri', width=60)

        scrollbar = ttk.Scrollbar(left_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', self.on_match_select)

        # Right panel: Visuals and Details
        right_panel = ttk.Frame(main_paned)
        main_paned.add(right_panel, weight=3)

        # Top of right panel: Visuals (Spectral Plot and Structure)
        visuals_frame = ttk.Frame(right_panel)
        visuals_frame.pack(side='top', fill='x', padx=5, pady=5)

        # Structure image
        self.struct_label = ttk.Label(visuals_frame, text="Structure")
        self.struct_label.pack(side='left', padx=5)
        
        # Spectral mirror plot
        self.plot_label = ttk.Label(visuals_frame, text="Spectral Mirror Plot")
        self.plot_label.pack(side='left', fill='x', expand=True, padx=5)

        # Bottom of right panel: Notebook for textual details
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Tab 1: Identification Summary
        ident_tab = ttk.Frame(self.notebook)
        self.notebook.add(ident_tab, text='Identification Summary')

        self.ident_text = scrolledtext.ScrolledText(
            ident_tab,
            wrap=tk.WORD,
            font=('Arial', 11),
            padx=10,
            pady=10
        )
        self.ident_text.pack(fill='both', expand=True)

        # Tab 2: Sample Data
        sample_data_tab = ttk.Frame(self.notebook)
        self.notebook.add(sample_data_tab, text='Sample Data')

        # Top part of Sample Data: Statistics and Export
        stats_outer = ttk.Frame(sample_data_tab)
        stats_outer.pack(fill='x', padx=10, pady=5)
        
        stats_frame = ttk.Frame(stats_outer)
        stats_frame.pack(side='left', fill='x', expand=True)
        
        self.stats_label = ttk.Label(stats_frame, text="Summary Statistics", font=('Arial', 10, 'bold'))
        self.stats_label.pack(anchor='w')
        
        self.stats_text = ttk.Label(stats_frame, text="", font=('Courier', 10))
        self.stats_text.pack(anchor='w', padx=10)

        export_sample_btn = ttk.Button(stats_outer, text="Export Table to CSV", command=self.export_compound_sample_data)
        export_sample_btn.pack(side='right', anchor='n', pady=5)

        # Bottom part of Sample Data: Table
        table_frame = ttk.Frame(sample_data_tab)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # v2.8.0: Added IS Area and Normalization Factor columns
        self.sample_tree = ttk.Treeview(
            table_frame,
            columns=('name', 'type', 'abundance', 'is_area', 'is_norm_factor'),
            show='headings',
            selectmode='none'
        )
        self.sample_tree.heading('name', text='Sample/Blank Name')
        self.sample_tree.heading('type', text='Type')
        self.sample_tree.heading('abundance', text='Feature Abundance')
        self.sample_tree.heading('is_area', text='IS Area')
        self.sample_tree.heading('is_norm_factor', text='IS Norm Factor')
        self.sample_tree.column('name', width=200)
        self.sample_tree.column('type', width=80)
        self.sample_tree.column('abundance', width=130)
        self.sample_tree.column('is_area', width=100)
        self.sample_tree.column('is_norm_factor', width=120)

        sample_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.sample_tree.yview)
        self.sample_tree.configure(yscrollcommand=sample_scroll.set)
        
        self.sample_tree.pack(side='left', fill='both', expand=True)
        sample_scroll.pack(side='right', fill='y')

        # Tab 3: Metadata
        metadata_tab = ttk.Frame(self.notebook)
        self.notebook.add(metadata_tab, text='Metadata')

        self.metadata_all_text = scrolledtext.ScrolledText(
            metadata_tab,
            wrap=tk.WORD,
            font=('Courier', 10),
            padx=10,
            pady=10
        )
        self.metadata_all_text.pack(fill='both', expand=True)

        # Note: Global Statistics tab removed in v2.7.0
        # Export CSV for external statistical analysis

        # v3.0.0: Surrogate Recovery tab (created dynamically in on_show if enabled)
        self.surrogate_tab = None
        self.surrogate_tree = None
        self.surrogate_detail_text = None
        self.surrogate_stats_label = None

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(side='bottom', fill='x', pady=(10, 0))

        export_csv_btn = ttk.Button(button_frame, text="Open CSV Report", command=self.open_csv)
        export_csv_btn.pack(side='left', padx=(0, 5))

        export_pdf_btn = ttk.Button(button_frame, text="Open PDF Report", command=self.open_pdf)
        export_pdf_btn.pack(side='left')

        new_btn = ttk.Button(button_frame, text="New Analysis", command=self.app.new_project)
        new_btn.pack(side='right')

    def on_show(self):
        """Called when screen is shown"""
        self.load_results()
        self.apply_theme(self.app.app_config.get('theme', 'light'))
        
        # v3.0.0: Load surrogate results if available
        self._setup_surrogate_tab()

    def apply_theme(self, theme_name):
        """Update text area colors for theme"""
        if theme_name == 'dark':
            bg = "#1e1e1e"
            fg = "#e1e1e1"
        else:
            bg = "white"
            fg = "black"

        for txt in [self.ident_text, self.metadata_all_text]:
            txt.config(bg=bg, fg=fg, insertbackground=fg)

    def load_results(self):
        """Load results from CSV file"""
        results = self.app.project.get('results', {})
        csv_file = results.get('csv_file', '')

        if not csv_file or not Path(csv_file).exists():
            # Try to find results in the expected location
            project_name = self.app.pipeline_config.get('project_name', '')
            output_folder = Path(self.app.pipeline_config.get('output_folder', 'results'))
            results_base = output_folder / "results"
            
            if results_base.exists():
                subfolders = [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith(project_name)]
                if subfolders:
                    latest_results_dir = max(subfolders, key=os.path.getmtime)
                    csv_files = list(latest_results_dir.glob("*.csv"))
                    if csv_files:
                        csv_file = str(csv_files[0])

        if csv_file and Path(csv_file).exists():
            try:
                # Initialize structure helper if not already done (v2.7.0: replaced Visualizer)
                if not self.viz:
                    temp_dir = Path(csv_file).parent / "temp_assets"
                    api_key = self.app.pipeline_config.get('epa_api_key')
                    self.viz = StructureHelper(str(temp_dir), api_key=api_key)

                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.matches = list(reader)

                # Populate tree
                self.tree.delete(*self.tree.get_children())

                for i, match in enumerate(self.matches):
                    self.tree.insert(
                        '',
                        'end',
                        iid=str(i),
                        text=str(i+1),
                        values=(
                            match.get('Compound_Name', 'Unknown'),
                            match.get('RevDot', '0'),
                            match.get('RI_Lib', '0')
                        )
                    )

                # Select first match
                if self.matches:
                    self.tree.selection_set('0')
                    self.on_match_select(None)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load results: {e}")
        else:
            # Clear if no results
            self.tree.delete(*self.tree.get_children())
            self.ident_text.delete('1.0', tk.END)
            self.sample_tree.delete(*self.sample_tree.get_children())
            self.metadata_all_text.delete('1.0', tk.END)

    # Note: Statistics methods removed in v2.7.0 (refresh_stats_plots, _display_image, update_feature_boxplot)

    # v3.0.0: Surrogate Recovery Tab
    def _setup_surrogate_tab(self):
        """Create or update the surrogate recovery tab if surrogate analysis was enabled"""
        surrogate_config = self.app.pipeline_config.get('surrogate_config', {})
        
        # Check if surrogate analysis was enabled
        if not surrogate_config.get('enabled', False):
            # Remove tab if it exists
            if self.surrogate_tab:
                try:
                    self.notebook.forget(self.surrogate_tab)
                except Exception:
                    pass
                self.surrogate_tab = None
            return
        
        # Try to find surrogate results file
        project_name = self.app.pipeline_config.get('project_name', '')
        output_folder = Path(self.app.pipeline_config.get('output_folder', 'results'))
        results_base = output_folder / "results"
        
        surrogate_csv = None
        if results_base.exists():
            # Look for SurrogateRecoveries_*.csv
            csv_pattern = f"SurrogateRecoveries_{project_name}*.csv"
            subfolders = [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith(project_name)]
            if subfolders:
                latest_results_dir = max(subfolders, key=os.path.getmtime)
                surrogate_files = list(latest_results_dir.glob("SurrogateRecoveries*.csv"))
                if surrogate_files:
                    surrogate_csv = str(surrogate_files[0])
        
        # Also check app.surrogate_results from recent analysis
        surrogate_data = getattr(self.app, 'surrogate_results', None)
        
        if not surrogate_csv and not surrogate_data:
            return
        
        # Create tab if it doesn't exist
        if not self.surrogate_tab:
            self.surrogate_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.surrogate_tab, text='Surrogate Recovery')
            
            # Summary stats at top
            stats_frame = ttk.Frame(self.surrogate_tab)
            stats_frame.pack(fill='x', padx=10, pady=10)
            
            self.surrogate_stats_label = ttk.Label(
                stats_frame, 
                text="Surrogate Recovery Summary",
                font=('Arial', 10, 'bold')
            )
            self.surrogate_stats_label.pack(anchor='w')
            
            # Recovery table
            table_frame = ttk.Frame(self.surrogate_tab)
            table_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            self.surrogate_tree = ttk.Treeview(
                table_frame,
                columns=('compound', 'avg', 'std', 'feature_id', 'revdot'),
                show='headings',
                height=10
            )
            self.surrogate_tree.heading('compound', text='Compound')
            self.surrogate_tree.heading('avg', text='Avg % Recovery')
            self.surrogate_tree.heading('std', text='Std Dev')
            self.surrogate_tree.heading('feature_id', text='Feature ID')
            self.surrogate_tree.heading('revdot', text='RevDot Score')
            
            self.surrogate_tree.column('compound', width=200)
            self.surrogate_tree.column('avg', width=120, anchor='center')
            self.surrogate_tree.column('std', width=80, anchor='center')
            self.surrogate_tree.column('feature_id', width=80, anchor='center')
            self.surrogate_tree.column('revdot', width=80, anchor='center')
            
            scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.surrogate_tree.yview)
            self.surrogate_tree.configure(yscrollcommand=scroll.set)
            
            self.surrogate_tree.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')
            
            self.surrogate_tree.bind('<<TreeviewSelect>>', self._on_surrogate_select)
            
            # Detail text
            detail_frame = ttk.LabelFrame(self.surrogate_tab, text="Match Details", padding=10)
            detail_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            self.surrogate_detail_text = scrolledtext.ScrolledText(
                detail_frame,
                wrap=tk.WORD,
                font=('Courier', 9),
                height=8
            )
            self.surrogate_detail_text.pack(fill='both', expand=True)
            
            # Export button
            btn_frame = ttk.Frame(self.surrogate_tab)
            btn_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Button(btn_frame, text="Export Surrogate CSV", command=self._export_surrogate_csv).pack(side='left')
        
        # Populate data
        self._populate_surrogate_tab(surrogate_csv, surrogate_data)
    
    def _populate_surrogate_tab(self, csv_path, surrogate_data):
        """Populate surrogate tab from CSV or in-memory data"""
        if not self.surrogate_tree:
            return
        
        self.surrogate_tree.delete(*self.surrogate_tree.get_children())
        self._surrogate_match_info = {}  # Store for detail view
        
        if surrogate_data:
            # Use in-memory data from SurrogateAnalyzer
            try:
                from src.surrogate_reporter import SurrogateReporter
                reporter = SurrogateReporter(surrogate_data, '', '')
                gui_data = reporter.get_gui_data()
                
                recovery_data = gui_data.get('recovery_summary', {})
                match_data = gui_data.get('match_details', {})
                stats = gui_data.get('summary_stats', {})
                
                # Update stats label
                self.surrogate_stats_label.config(
                    text=f"Surrogate Recovery: {stats.get('matched_compounds', 0)}/{stats.get('total_compounds', 0)} matched | "
                         f"Average: {stats.get('average_recovery', 'N/A')}% ± {stats.get('recovery_stddev', 'N/A')}%"
                )
                
                # Populate tree
                for row in recovery_data.get('rows', []):
                    compound = row.get('Compound', '')
                    avg = row.get('Average', 'N/A')
                    std = row.get('StdDev', 'N/A')
                    
                    # Find matching match info
                    match_info = next((m for m in match_data.get('rows', []) if m.get('Compound') == compound), {})
                    feat_id = match_info.get('Feature_ID', '-')
                    revdot = match_info.get('RevDot', '-')
                    
                    item_id = self.surrogate_tree.insert('', 'end', values=(compound, avg, std, feat_id, revdot))
                    self._surrogate_match_info[item_id] = match_info
                    
            except Exception as e:
                print(f"[WARNING] Error populating surrogate tab: {e}")
        
        elif csv_path and Path(csv_path).exists():
            # Parse CSV file (contains three sections)
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Find recovery section
                in_recovery = False
                recovery_headers = []
                recovery_rows = []
                
                in_match = False
                match_headers = []
                match_rows = []
                
                for line in lines:
                    line = line.strip()
                    if '=== PERCENT RECOVERIES ===' in line:
                        in_recovery = True
                        in_match = False
                        continue
                    elif '=== MATCH INFORMATION ===' in line:
                        in_recovery = False
                        in_match = True
                        continue
                    elif line.startswith('==='):
                        in_recovery = False
                        in_match = False
                        continue
                    
                    if not line:
                        continue
                    
                    parts = line.split(',')
                    if in_recovery:
                        if not recovery_headers:
                            recovery_headers = parts
                        else:
                            recovery_rows.append(parts)
                    elif in_match:
                        if not match_headers:
                            match_headers = parts
                        else:
                            match_rows.append(parts)
                
                # Build match lookup
                match_lookup = {}
                if match_headers:
                    comp_idx = match_headers.index('Compound') if 'Compound' in match_headers else 0
                    for row in match_rows:
                        if len(row) > comp_idx:
                            match_lookup[row[comp_idx]] = dict(zip(match_headers, row))
                
                # Populate tree
                if recovery_headers:
                    comp_idx = recovery_headers.index('Compound') if 'Compound' in recovery_headers else 0
                    avg_idx = recovery_headers.index('Average') if 'Average' in recovery_headers else 1
                    std_idx = recovery_headers.index('StdDev') if 'StdDev' in recovery_headers else 2
                    
                    for row in recovery_rows:
                        if len(row) > comp_idx:
                            compound = row[comp_idx]
                            avg = row[avg_idx] if len(row) > avg_idx else 'N/A'
                            std = row[std_idx] if len(row) > std_idx else 'N/A'
                            
                            match_info = match_lookup.get(compound, {})
                            feat_id = match_info.get('Feature_ID', '-')
                            revdot = match_info.get('RevDot', '-')
                            
                            item_id = self.surrogate_tree.insert('', 'end', values=(compound, avg, std, feat_id, revdot))
                            self._surrogate_match_info[item_id] = match_info
                
                # Update stats
                total = len(recovery_rows)
                matched = sum(1 for r in recovery_rows if len(r) > 1 and r[1] not in ['N/A', 'No Match', ''])
                self.surrogate_stats_label.config(text=f"Surrogate Recovery: {matched}/{total} compounds with valid recoveries")
                
            except Exception as e:
                print(f"[WARNING] Error loading surrogate CSV: {e}")
    
    def _on_surrogate_select(self, event):
        """Handle surrogate compound selection"""
        selection = self.surrogate_tree.selection()
        if not selection or not self.surrogate_detail_text:
            return
        
        match_info = self._surrogate_match_info.get(selection[0], {})
        
        self.surrogate_detail_text.delete('1.0', tk.END)
        
        if match_info:
            text = "Match Details\n"
            text += "=" * 40 + "\n"
            for key, value in match_info.items():
                text += f"{key}: {value}\n"
        else:
            text = "No match details available"
        
        self.surrogate_detail_text.insert('1.0', text)
    
    def _export_surrogate_csv(self):
        """Export surrogate data to CSV"""
        surrogate_data = getattr(self.app, 'surrogate_results', None)
        if surrogate_data:
            try:
                from src.surrogate_reporter import SurrogateReporter
                output_dir = self.app.pipeline_config.get('output_folder', '.')
                project_name = self.app.pipeline_config.get('project_name', 'Results')
                reporter = SurrogateReporter(surrogate_data, output_dir, project_name)
                filepath = reporter.generate_csv()
                messagebox.showinfo("Export Complete", f"Surrogate data exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export surrogate data: {e}")
        else:
            messagebox.showinfo("No Data", "No surrogate data available for export")

    def on_match_select(self, event):
        """Handle match selection"""
        selection = self.tree.selection()
        if not selection:
            return

        idx = int(selection[0])
        match = self.matches[idx]
        self.current_match = match

        # Update Identification Summary tab
        self.ident_text.delete('1.0', tk.END)
        
        summary = f"Compound: {match.get('Compound_Name', 'Unknown')}\n"
        summary += f"Formula: {match.get('Formula', 'N/A')}\n"
        summary += f"CAS: {match.get('CAS', 'N/A')}\n"
        summary += f"InChIKey: {match.get('InChIKey', 'N/A')}\n"
        summary += "-" * 40 + "\n"
        summary += f"Retention Index (Lib): {match.get('RI_Lib', 'N/A')}\n"
        summary += f"Retention Index (Exp): {match.get('RI_Exp', 'N/A')}\n"
        summary += f"RI Error: {match.get('RI_Err', 'N/A')} ({match.get('RI_Err%', '0')} %)\n"
        summary += "-" * 40 + "\n"
        summary += f"Spectral Score (RevDot): {match.get('RevDot', '0')}\n"
        summary += f"Spectral Score (FwdDot): {match.get('FwdDot', '0')}\n"
        summary += f"High Res Match: {match.get('HighRes?', 'No')}\n"
        summary += f"RHRMF Score: {match.get('RHRMF', 'N/A')}\n"
        summary += "-" * 40 + "\n"
        # Hazard information from CSV (populated during analysis if CAS available)
        summary += f"Hazard Summary: {match.get('Hazard_Summary', 'No data')}\n"
        summary += f"EPA Link: {match.get('EPA_Link', 'N/A')}\n"
        
        self.ident_text.insert('1.0', summary)

        # Update Sample Data tab
        self.sample_tree.delete(*self.sample_tree.get_children())
        
        abundance_fields = [k for k in match.keys() if k.startswith('Abundance_')]
        
        # Try to get grouping from multiple sources for robustness
        grouping = self.app.pipeline_config.get('sample_grouping')
        if not grouping:
            grouping = self.app.project.get('pipeline_config', {}).get('sample_grouping', {})
        
        # v2.8.0: Check if IS normalization was used
        is_enabled = match.get('IS_Normalized', 'No') == 'Yes'
        
        display_data = [] # List of (name, type, abundance, is_area, is_norm_factor)
        
        for fld in abundance_fields:
            s_name = fld.replace('Abundance_', '')
            val = float(match.get(fld, 0))
            stype = grouping.get(s_name, {}).get('type', 'Sample')
            
            # v2.8.0: Get IS area and normalization factor if available
            is_area = ""
            is_norm_factor = ""
            if is_enabled:
                is_area_key = f"IS_Area_{s_name}"
                is_factor_key = f"IS_NormFactor_{s_name}"
                is_area_val = match.get(is_area_key, '')
                is_factor_val = match.get(is_factor_key, '')
                
                # Handle IS Area - check for empty string, None, or "0"/"0.00"
                if is_area_val and str(is_area_val).strip() and str(is_area_val).strip() not in ['0', '0.0', '0.00', '0.000']:
                    try:
                        area_float = float(is_area_val)
                        if area_float > 0:
                            is_area = f"{area_float:,.0f}"
                    except (ValueError, TypeError):
                        # If conversion fails, try to display as-is if it's not empty
                        if str(is_area_val).strip():
                            is_area = str(is_area_val)
                
                # Handle normalization factor
                if is_factor_val and str(is_factor_val).strip():
                    try:
                        factor_float = float(is_factor_val)
                        is_norm_factor = f"{factor_float:.4f}"
                    except (ValueError, TypeError):
                        is_norm_factor = str(is_factor_val)
            
            display_data.append((s_name, stype, val, is_area, is_norm_factor))
                
        # Populate table and calculate stats from display_data
        sample_abundances = []
        for name, stype, val, is_area, is_norm_factor in display_data:
            self.sample_tree.insert('', 'end', values=(name, stype, f"{val:,.0f}", is_area, is_norm_factor))
            if stype == "Sample":
                sample_abundances.append(val)
            
        # Update statistics
        bff_thresh = float(match.get('BFF_Threshold', 0))
        
        detected_count = sum(1 for a in sample_abundances if a > bff_thresh)
        total_samples = len(sample_abundances)
        det_freq = (detected_count / total_samples * 100) if total_samples > 0 else 0
        
        max_ab = max(sample_abundances) if sample_abundances else 0
        min_ab = min(sample_abundances) if sample_abundances else 0
        mean_ab = sum(sample_abundances)/total_samples if total_samples > 0 else 0
        
        stats = f"BFF Threshold: {bff_thresh:,.0f}\n"
        stats += f"Detection Frequency: {det_freq:.1f}% ({detected_count}/{total_samples} samples > BFF)\n"
        stats += f"Max Abundance: {max_ab:,.0f} | Min Abundance: {min_ab:,.0f} | Mean Abundance: {mean_ab:,.0f}"
        
        self.stats_text.config(text=stats)

        # Update Metadata (All Fields filtered) tab
        self.metadata_all_text.delete('1.0', tk.END)
        
        # Filter out fields already in sample data or main summary if requested
        # User said "include all information that was not present in original sample"
        # Original sample data: Feature ID, RT, RI_Exp, Abundances, IS_Area, IS_NormFactor (v2.8.0)
        excluded_prefixes = ['Abundance_', 'Feature ID', 'RT', 'RI_Exp', 'IS_Area_', 'IS_NormFactor_']
        
        metadata_lines = []
        for k, v in match.items():
            if any(k.startswith(p) for p in excluded_prefixes) or k in excluded_prefixes:
                continue
            metadata_lines.append(f"{k}: {v}")
            
        self.metadata_all_text.insert('1.0', "\n".join(metadata_lines))

        # Update Visuals
        self.update_visuals(match)

    def _sanitize_filename(self, name):
        """Sanitize a string for use in filenames"""
        import re
        # Remove or replace invalid characters
        sanitized = re.sub(r'[\\/*?:"<>|,\s]', '_', name)
        # Limit length
        return sanitized[:50]

    def update_visuals(self, match):
        """Update structure and plot images"""
        if not self.viz:
            return

        name = match.get('Compound_Name', 'Unknown')
        inchikey = match.get('InChIKey', '')
        feat_id = match.get('Feature ID', 'feat')
        
        # v3.0.1: Get Library_Entry_ID for unique plot identification
        lib_idx = match.get('Library_Entry_ID', '')
        
        # Create identifiers for finding files
        sanitized_name = self._sanitize_filename(name)
        unique_id = f"{feat_id}_{sanitized_name}"
        
        # Structure - use unique filename per compound match (same compound = same structure)
        struct_path = self.viz.get_structure_image(inchikey, name, f"struct_{unique_id}.png")
        if struct_path and os.path.exists(struct_path):
            try:
                img = Image.open(struct_path)
                img = img.resize((250, 250), Image.LANCZOS)
                self.struct_img = ImageTk.PhotoImage(img)
                self.struct_label.config(image=self.struct_img, text="")
            except Exception:
                self.struct_label.config(image='', text="Error Loading Structure")
        else:
            self.struct_label.config(image='', text="No Structure")

        # Plot - Try multiple filename formats for compatibility
        # v3.0.1: Library_Entry_ID is the primary identifier for unique plots
        plot_found = False
        temp_dir = Path(self.viz.temp_dir)
        
        # Build search patterns - prioritize library_index format (v3.0.1+)
        plot_patterns = []
        if lib_idx:
            plot_patterns.append(f"plot_{feat_id}_lib{lib_idx}.png")  # v3.0.1: Library index format
        plot_patterns.extend([
            f"plot_{unique_id}.png",  # Legacy unique format
            f"plot_{feat_id}_{sanitized_name}.png",  # Alternative legacy format
            f"plot_{feat_id}.png",  # Very old format (for backward compatibility)
        ])
        
        for pattern in plot_patterns:
            plot_path = temp_dir / pattern
            if plot_path.exists():
                try:
                    img = Image.open(plot_path)
                    img = img.resize((700, 300), Image.LANCZOS)
                    self.plot_img = ImageTk.PhotoImage(img)
                    self.plot_label.config(image=self.plot_img, text="")
                    plot_found = True
                    break
                except Exception:
                    continue
            
            # Also try in parent directory (results folder)
            csv_file = self.app.project.get('results', {}).get('csv_file', '')
            if csv_file:
                parent_temp = Path(csv_file).parent / "temp_assets"
                alt_path = parent_temp / pattern
                if alt_path.exists():
                    try:
                        img = Image.open(alt_path)
                        img = img.resize((700, 300), Image.LANCZOS)
                        self.plot_img = ImageTk.PhotoImage(img)
                        self.plot_label.config(image=self.plot_img, text="")
                        plot_found = True
                        break
                    except Exception:
                        continue
        
        if not plot_found:
            self.plot_label.config(image='', text="Spectral Plot Not Available\n(Plots are generated during PDF report creation)")

    def open_csv(self):
        """Open CSV report in default application"""
        results = self.app.project.get('results', {})
        csv_file = results.get('csv_file', '')

        if csv_file and Path(csv_file).exists():
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(csv_file)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', csv_file])
            else:  # Linux
                subprocess.run(['xdg-open', csv_file])
        else:
            messagebox.showwarning("Not Found", "CSV file not found")

    def open_pdf(self):
        """Open PDF report in default application"""
        results = self.app.project.get('results', {})
        pdf_file = results.get('pdf_file', '')

        if pdf_file and Path(pdf_file).exists():
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(pdf_file)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', pdf_file])
            else:  # Linux
                subprocess.run(['xdg-open', pdf_file])
        else:
            messagebox.showwarning("Not Found", "PDF file not found")

    def export_compound_sample_data(self):
        """Export the current compound's sample table to a CSV file (v2.8.0: includes IS columns)"""
        if not self.current_match:
            messagebox.showwarning("No Selection", "Please select a compound first.")
            return
            
        compound_name = self.current_match.get('Compound_Name', 'Unknown').replace(' ', '_')
        # Sanitize filename
        import re
        compound_name = re.sub(r'[\\/*?:"<>|]', "", compound_name)
        feat_id = self.current_match.get('Feature ID', 'unknown')
        
        default_filename = f"SampleData_{compound_name}_{feat_id}.csv"
        
        filepath = filedialog.asksaveasfilename(
            title="Export Sample Data",
            initialfile=default_filename,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # v2.8.0: Include IS columns in export
                    writer.writerow(['Sample/Blank Name', 'Type', 'Feature Abundance', 'IS Area', 'IS Norm Factor'])
                    
                    for item in self.sample_tree.get_children():
                        # The abundances in tree are formatted with commas, we should remove them for CSV
                        vals = list(self.sample_tree.item(item)['values'])
                        if len(vals) >= 3:
                            # Remove commas from abundance value
                            vals[2] = str(vals[2]).replace(',', '')
                        # Remove commas from IS area if present
                        if len(vals) >= 4 and vals[3]:
                            vals[3] = str(vals[3]).replace(',', '')
                        writer.writerow(vals)
                        
                messagebox.showinfo("Success", f"Data exported successfully to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export data: {e}")
