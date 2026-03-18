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
        icon_path = Path(__file__).parent.parent / "K2Icon.png"
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
        logo_path = Path(__file__).parent.parent / "K2Logo2.png"
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
            text="Version 2.7.0 | 2026",
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
    """Screen for classifying samples as Blanks or Samples"""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.samples = []  # List of dicts: {'name': str, 'type': str}
        self._updating_ui = False

        self.create_header(
            "Sample Classification",
            "Classify samples as Blanks or Samples for BFF calculation"
        )

        # Content area
        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        # Left side: Table
        table_container = ttk.Frame(content)
        table_container.pack(side='left', fill='both', expand=True, padx=(0, 10))

        # Instructions
        ttk.Label(table_container, text="Double-click cells to edit. Use Right-click for bulk actions.", font=('Arial', 9, 'italic')).pack(anchor='w')

        table_frame = ttk.Frame(table_container)
        table_frame.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=('name', 'type'),
            show='headings',
            selectmode='extended'
        )
        self.tree.heading('name', text='Sample Name')
        self.tree.heading('type', text='Type')

        self.tree.column('name', width=350)
        self.tree.column('type', width=150)

        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Events
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)

        # Right side: Edit panel
        edit_panel = ttk.LabelFrame(content, text="Edit Selected", padding=15, width=250)
        edit_panel.pack(side='right', fill='y', padx=(10, 0))

        ttk.Label(edit_panel, text="Type:").pack(anchor='w')
        self.type_var = tk.StringVar(value="Sample")
        self.type_cb = ttk.Combobox(edit_panel, textvariable=self.type_var, values=["Sample", "Blank"], state='readonly')
        self.type_cb.pack(fill='x', pady=(0, 20))
        self.type_cb.bind('<<ComboboxSelected>>', self.update_selected_type)

        # Bulk action buttons
        ttk.Separator(edit_panel, orient='horizontal').pack(fill='x', pady=10)
        
        copy_btn = ttk.Button(edit_panel, text="Copy to Selected Rows", command=self.copy_to_selected)
        copy_btn.pack(fill='x', pady=5)
        
        fill_btn = ttk.Button(edit_panel, text="Fill Down", command=self.fill_down)
        fill_btn.pack(fill='x', pady=5)

        # Buttons
        self.create_button_row([
            ("Back", self.go_back),
            ("Next", self.go_next)
        ])

        # Context menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Copy values to all selected", command=self.copy_to_selected)
        self.menu.add_command(label="Fill Down (from first selected)", command=self.fill_down)
        self.menu.add_separator()
        self.menu.add_command(label="Set as Sample", command=lambda: self.set_bulk_type("Sample"))
        self.menu.add_command(label="Set as Blank", command=lambda: self.set_bulk_type("Blank"))

    def on_show(self):
        """Scan input folder and populate table"""
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
                except:
                    pass

        existing_grouping = self.app.pipeline_config.get('sample_grouping', {})

        self.samples = []
        self._updating_ui = True
        try:
            for name in found_names:
                if name in existing_grouping:
                    # Load existing classification (only name and type)
                    self.samples.append({
                        'name': name,
                        'type': existing_grouping[name].get('type', 'Sample')
                    })
                else:
                    stype = "Blank" if blank_id in name.lower() else "Sample"
                    self.samples.append({
                        'name': name,
                        'type': stype
                    })

            self.refresh_table()
        finally:
            self._updating_ui = False

    def refresh_table(self):
        """Redraw the table and apply colors"""
        self.tree.delete(*self.tree.get_children())
        
        self.tree.tag_configure('blank', background='#f0f0f0', foreground='#888888')

        for i, s in enumerate(self.samples):
            tags = []
            if s['type'] == 'Blank':
                tags.append('blank')
                
            self.tree.insert('', 'end', iid=str(i), values=(s['name'], s['type']), tags=tags)

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
            self.refresh_table()
            self.tree.selection_set(selection)
        finally:
            self._updating_ui = False

    def set_bulk_type(self, stype):
        self.type_var.set(stype)
        self.update_selected_type()

    def copy_to_selected(self):
        """Copy current UI values to all selected rows"""
        self.update_selected_type()

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

    def go_back(self):
        entry_point = self.app.pipeline_config['entry_point']
        if entry_point in ['raw', 'mzml']:
            self.app.show_screen('mzmine_config')
        else:
            self.app.show_screen('analysis_params')

    def go_next(self):
        # Save classification to config
        grouping = {s['name']: s for s in self.samples}
        self.app.pipeline_config['sample_grouping'] = grouping

        # Go to Internal Standard screen
        self.app.show_screen('internal_standard')


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
                except:
                    pass

    def _disable_widgets(self, parent):
        """Recursively disable all widgets"""
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                self._disable_widgets(child)
            else:
                try:
                    child.configure(state='disabled')
                except:
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
                            except:
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
            local = Path(__file__).parent.parent / "users" / "brunetch.mzuser"
            if local.exists():
                user_path = str(local)

        batch_path = self.app.pipeline_config.get('mzmine_batch_file', '')
        if not batch_path:
            local = Path(__file__).parent.parent / "config" / "gc_ei_workflow.mzbatch"
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
        lib_path = self.app.pipeline_config.get('library_path', '')
        if not lib_path:
            local = Path(__file__).parent.parent / "unified_library_20251013.csv"
            if local.exists():
                lib_path = str(local)

        ri_path = self.app.pipeline_config.get('ri_cal_path', '')
        if not ri_path:
            local = Path(__file__).parent.parent / "MSDial_RICal.txt"
            if local.exists():
                ri_path = str(local)

        self.library_var.set(lib_path)
        self.ri_var.set(ri_path)
        self.api_var.set(self.app.pipeline_config.get('epa_api_key', ''))
        self.blank_var.set(self.app.pipeline_config.get('blank_identifier', 'fieldblank'))

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

        # Save to config
        self.app.pipeline_config['library_path'] = self.library_var.get()
        self.app.pipeline_config['ri_cal_path'] = self.ri_var.get()
        self.app.pipeline_config['epa_api_key'] = self.api_var.get()
        self.app.pipeline_config['blank_identifier'] = self.blank_var.get()

        # Save defaults
        self.app.app_config.set('library_path', self.library_var.get())
        self.app.app_config.set('ri_cal_path', self.ri_var.get())
        self.app.app_config.set('epa_api_key', self.api_var.get())
        self.app.app_config.set('blank_identifier', self.blank_var.get())
        self.app.app_config.save_defaults()

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
                        except:
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

        self.sample_tree = ttk.Treeview(
            table_frame,
            columns=('name', 'type', 'abundance'),
            show='headings',
            selectmode='none'
        )
        self.sample_tree.heading('name', text='Sample/Blank Name')
        self.sample_tree.heading('type', text='Type')
        self.sample_tree.heading('abundance', text='Abundance')
        self.sample_tree.column('name', width=250)
        self.sample_tree.column('type', width=100)
        self.sample_tree.column('abundance', width=150)

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
        summary += f"Log2 Fold Change: {match.get('Log2FC', 'N/A')}\n"
        summary += f"P-value: {match.get('P-value', 'N/A')}\n"
        summary += "-" * 40 + "\n"
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
        
        display_data = [] # List of (name, type, abundance)
        
        for fld in abundance_fields:
            s_name = fld.replace('Abundance_', '')
            val = float(match.get(fld, 0))
            stype = grouping.get(s_name, {}).get('type', 'Sample')
            display_data.append((s_name, stype, val))
                
        # Populate table and calculate stats from display_data
        sample_abundances = []
        for name, stype, val in display_data:
            self.sample_tree.insert('', 'end', values=(name, stype, f"{val:,.0f}"))
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
        # Original sample data: Feature ID, RT, RI_Exp, Abundances
        excluded_prefixes = ['Abundance_', 'Feature ID', 'RT', 'RI_Exp']
        
        metadata_lines = []
        for k, v in match.items():
            if any(k.startswith(p) for p in excluded_prefixes) or k in excluded_prefixes:
                continue
            metadata_lines.append(f"{k}: {v}")
            
        self.metadata_all_text.insert('1.0', "\n".join(metadata_lines))

        # Update Visuals
        self.update_visuals(match)

    def update_visuals(self, match):
        """Update structure and plot images"""
        if not self.viz:
            return

        name = match.get('Compound_Name', 'Unknown')
        inchikey = match.get('InChIKey', '')
        feat_id = match.get('Feature ID', 'feat')
        
        # Structure
        struct_path = self.viz.get_structure_image(inchikey, name, f"struct_{feat_id}.png")
        if struct_path and os.path.exists(struct_path):
            try:
                img = Image.open(struct_path)
                img = img.resize((250, 250), Image.LANCZOS)
                self.struct_img = ImageTk.PhotoImage(img)
                self.struct_label.config(image=self.struct_img, text="")
            except:
                self.struct_label.config(image='', text="Error Loading Structure")
        else:
            self.struct_label.config(image='', text="No Structure")

        # Plot 
        plot_found = False
        temp_dir = Path(self.viz.temp_dir)
        # Try finding mirror plot (generated by PDF reporter)
        possible_plots = list(temp_dir.glob(f"plot_{feat_id}.png"))
        if possible_plots:
            try:
                plot_path = possible_plots[0]
                img = Image.open(plot_path)
                # Resize for display
                img = img.resize((700, 300), Image.LANCZOS)
                self.plot_img = ImageTk.PhotoImage(img)
                self.plot_label.config(image=self.plot_img, text="")
                plot_found = True
            except:
                pass
        
        if not plot_found:
            self.plot_label.config(image='', text="Spectral Plot Not Available in GUI\n(Check PDF for full comparison)")

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
        """Export the current compound's sample table to a CSV file"""
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
                    writer.writerow(['Sample/Blank Name', 'Type', 'Abundance'])
                    
                    for item in self.sample_tree.get_children():
                        # The abundances in tree are formatted with commas, we should remove them for CSV
                        vals = list(self.sample_tree.item(item)['values'])
                        if len(vals) >= 3:
                            vals[2] = str(vals[2]).replace(',', '')
                        writer.writerow(vals)
                        
                messagebox.showinfo("Success", f"Data exported successfully to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export data: {e}")
