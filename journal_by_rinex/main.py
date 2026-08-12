#!/usr/bin/env python3

import os
import fnmatch
import glob
import random
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import pypandoc
import yaml
from journal_by_rinex.functions import get_info, journal_generator

RINEX_OBS_PATTERNS = ('*.??o', '*.??O')

MEASUREMENT_OPTIONS = [
    "No tripod, to base",
    "No tripod, to phase center",
    "Tripod, slant",
    "Tripod, to base",
    "Tripod, to phase center",
    "Not specified",
]

SAVE_MODES = ('custom', 'source')

# Default randomization range for GDOP/PDOP
DEFAULT_DOP_MIN = '1.5'
DEFAULT_DOP_MAX = '2.0'

# Default config file(s), loaded automatically on startup if present
DEFAULT_CONFIG_FILES = ('config.yaml', 'config.yml')

# Maps config/metadata field names to the corresponding file_info key
FIELD_TO_INFO_KEY = {
    'organization': 'organization',
    'object': 'object',
    'operator': 'operator',
    'geodetic_mark_type': 'centre type',
    'benchmark_type': 'benchmark type',
    'gdop': 'gdop',
    'pdop': 'pdop',
}

ANTENNA_HEIGHT_TYPES = {
    'No tripod, to base': 'base',
    'No tripod, to phase center': 'phase',
    'Tripod, slant': 'tripod_slant',
    'Tripod, to base': 'tripod_base',
    'Tripod, to phase center': 'tripod_phase',
    'Not specified': None,
}

class FileProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GNSS Observation Journal from RINEX Data")
        self.files = []
        self.save_path = ""

        # Text parameter variables
        self.organization = tk.StringVar(value='Enter organization name')
        self.object_name = tk.StringVar(value='Enter object name')
        self.operator = tk.StringVar(value='Enter operator full name')
        self.benchmark_type = tk.StringVar(value='Enter benchmark type and description')
        self.center_type = tk.StringVar(value='Enter geodetic mark type and description')
        self.gdop = tk.StringVar(value='Enter GDOP')
        self.pdop = tk.StringVar(value='Enter PDOP')

        # GDOP/PDOP randomization: when enabled, each file gets its own
        # random value drawn from [min, max] instead of the fixed value above
        self.gdop_random = tk.BooleanVar(value=False)
        self.gdop_min = tk.StringVar(value=DEFAULT_DOP_MIN)
        self.gdop_max = tk.StringVar(value=DEFAULT_DOP_MAX)
        self.pdop_random = tk.BooleanVar(value=False)
        self.pdop_min = tk.StringVar(value=DEFAULT_DOP_MIN)
        self.pdop_max = tk.StringVar(value=DEFAULT_DOP_MAX)

        # Radiobutton selection variable
        self.measurement_type = tk.StringVar(value="No tripod, to base")

        # Output location selection variable
        self.save_mode = tk.StringVar(value="custom")

        # Per-file metadata overrides loaded from config file_rules (see apply_config)
        self.file_rules = []

        # When enabled, a YAML config with the resolved parameters of every
        # processed file is saved after processing (see save_processed_config)
        self.save_yaml = tk.BooleanVar(value=False)

        # Build the interface
        self.create_widgets()

        # Silently apply a config.yaml/config.yml from the current directory, if present
        self.load_default_config()

    def create_widgets(self):
        # Text input fields
        self.create_text_input("Organization", self.organization, 0, 0)
        self.create_text_input("Object", self.object_name, 1, 0)
        self.create_text_input("Operator", self.operator, 2, 0)
        self.create_text_input("Geodetic mark type", self.benchmark_type, 3, 0)
        self.create_text_input("Benchmark type", self.center_type, 4, 0)
        # GDOP/PDOP live in their own frame (rather than the shared column
        # grid) so their width isn't stretched by the long radiobutton
        # labels further down the same column - keeps entry and Range
        # controls tight against the label instead of pushed far right.
        dop_frame = tk.Frame(self.root)
        dop_frame.grid(row=0, column=2, rowspan=2, columnspan=2, sticky=tk.W, padx=10)

        self.gdop_entry, self.gdop_min_entry, self.gdop_max_entry = self.create_dop_controls(
            dop_frame, 0, "GDOP", self.gdop, self.gdop_random, self.gdop_min, self.gdop_max)
        self.pdop_entry, self.pdop_min_entry, self.pdop_max_entry = self.create_dop_controls(
            dop_frame, 1, "PDOP", self.pdop, self.pdop_random, self.pdop_min, self.pdop_max)

        # Radiobuttons for output location
        tk.Label(self.root, text="Save results to:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=(15, 0))
        tk.Radiobutton(
            self.root, text="Custom folder", variable=self.save_mode,
            value="custom", command=self.update_save_mode
        ).grid(row=7, column=0, sticky=tk.W, padx=10)
        tk.Radiobutton(
            self.root, text="Next to source RINEX file", variable=self.save_mode,
            value="source", command=self.update_save_mode
        ).grid(row=7, column=1, sticky=tk.W, padx=10)

        # Buttons for loading/saving YAML config files
        self.load_config_button = tk.Button(self.root, text="Load config (YAML)", command=self.load_config)
        self.load_config_button.grid(row=8, column=0, pady=5, sticky=tk.W, padx=10)

        self.save_config_button = tk.Button(self.root, text="Save config (YAML)", command=self.save_config)
        self.save_config_button.grid(row=8, column=1, pady=5, sticky=tk.W, padx=10)

        self.file_rules_label = tk.Label(self.root, text="Per-file rules: 0 loaded")
        self.file_rules_label.grid(row=8, column=2, pady=5, sticky=tk.W, padx=10)

        tk.Checkbutton(
            self.root, text="Save YAML", variable=self.save_yaml
        ).grid(row=8, column=3, pady=5, sticky=tk.W, padx=10)

        # Radiobuttons for measurement type on the right side
        tk.Label(self.root, text="Measurement type:").grid(row=2, column=2, sticky=tk.W, padx=10, pady=5)

        for idx, option in enumerate(MEASUREMENT_OPTIONS):
            column = 2 if idx % 2 == 0 else 3  # Alternate columns
            row = 3 + idx // 2                 # Move to next row for each pair
            tk.Radiobutton(
                self.root, text=option, variable=self.measurement_type, value=option
            ).grid(row=row, column=column, sticky=tk.W, padx=10, pady=2)

        # Buttons for adding files and selecting the save path
        self.add_files_button = tk.Button(self.root, text="Add files", command=self.add_files)
        self.add_files_button.grid(row=10, column=0, pady=5)

        self.add_folder_button = tk.Button(self.root, text="Add folder (recursive)", command=self.add_folder_recursive)
        self.add_folder_button.grid(row=10, column=1, pady=5)

        self.save_path_button = tk.Button(self.root, text="Select save path", command=self.select_save_path)
        self.save_path_button.grid(row=10, column=2, pady=5)

        # Selected files list
        self.files_list_label = tk.Label(self.root, text="Selected files:")
        self.files_list_label.grid(row=11, column=0, columnspan=1, pady=(10, 0))
        self.files_list_text = tk.Text(self.root, height=5, width=50, state='disabled')
        self.files_list_text.grid(row=12, column=0, columnspan=2, pady=5)

        # Save path display
        self.save_path_label = tk.Label(self.root, text="Save path:")
        self.save_path_label.grid(row=11, column=2, columnspan=1, pady=(10, 0))
        self.save_path_text = tk.Entry(self.root, width=60, state='disabled')
        self.save_path_text.grid(row=12, column=2, columnspan=2, pady=5)

        # Progress bar shown while processing files
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.root, orient='horizontal', mode='determinate', variable=self.progress_var
        )
        self.progress_bar.grid(row=13, column=0, columnspan=4, sticky=tk.EW, padx=10, pady=(10, 0))

        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.grid(row=14, column=0, columnspan=4, pady=(0, 5))

        # Process button
        self.process_button = tk.Button(self.root, text="Process files", command=self.process_files)
        self.process_button.grid(row=15, column=0, columnspan=1, pady=10)

        # Reset button
        self.reset_button = tk.Button(self.root, text="Reset", command=self.reset)
        self.reset_button.grid(row=15, column=1, pady=5)

        # Close button
        self.close_button = tk.Button(self.root, text="Close", command=self.root.destroy)
        self.close_button.grid(row=15, column=2, columnspan=2, pady=5)

        # Developer signature at the bottom of the window
        developer_email = tk.Label(
            self.root, text="by roman.sermiagin@gmail.com",
            font=("Arial", 10, "italic"),
            anchor="w",
            justify="left",
            cursor="hand2"
        )
        developer_email.grid(row=20, column=0, columnspan=1, pady=10, sticky="w")

        developer_label = tk.Label(
            self.root, text="http://github.com/skimprem/journal_by_rinex",
            font=("Arial", 10, "italic"),
            anchor="w",
            justify="left",
            cursor="hand2"
        )
        developer_label.grid(row=20, column=3, columnspan=3, pady=10, sticky="w")

        # Clickable link
        def open_github(event):
            import webbrowser
            webbrowser.open_new("http://github.com/skimprem/journal_by_rinex")

        developer_label.bind("<Button-1>", open_github)

    def create_text_input(self, label_text, variable, row, column, width=30):
        """Creates a labeled text entry field."""
        label = tk.Label(self.root, text=label_text)
        label.grid(row=row, column=column, sticky=tk.W, padx=10, pady=5)
        entry = tk.Entry(self.root, textvariable=variable, width=width)
        entry.grid(row=row, column=column + 1, padx=5, pady=5)
        return entry

    def create_dop_controls(self, frame, row, label_text, variable, random_var, min_var, max_var):
        """Builds one GDOP/PDOP row (label, fixed-value entry, and a "Range"
        checkbox with min/max entries) inside the given frame, using the
        frame's own local grid so its width stays tight regardless of
        other, wider content elsewhere in the window."""
        tk.Label(frame, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=5)
        entry = tk.Entry(frame, textvariable=variable, width=10)
        entry.grid(row=row, column=1, padx=(2, 10), pady=5)

        min_entry = tk.Entry(frame, textvariable=min_var, width=6, state='disabled')
        max_entry = tk.Entry(frame, textvariable=max_var, width=6, state='disabled')

        def on_toggle():
            self.update_random_mode(entry, random_var, min_entry, max_entry)

        tk.Checkbutton(
            frame, text="Range:", variable=random_var, command=on_toggle
        ).grid(row=row, column=2, sticky=tk.W)
        min_entry.grid(row=row, column=3, padx=2)
        tk.Label(frame, text="-").grid(row=row, column=4)
        max_entry.grid(row=row, column=5, padx=2)

        return entry, min_entry, max_entry

    def update_random_mode(self, fixed_entry, random_var, min_entry, max_entry):
        if random_var.get():
            fixed_entry.config(state='disabled')
            min_entry.config(state='normal')
            max_entry.config(state='normal')
        else:
            fixed_entry.config(state='normal')
            min_entry.config(state='disabled')
            max_entry.config(state='disabled')

    def add_files(self):
        # Open the file selection dialog
        new_files = filedialog.askopenfilenames(title="Select files", filetypes=(("All files", "*.*"),))
        for file in new_files:
            if file not in self.files:
                self.files.append(file)
        self.update_files_list()

    def add_folder_recursive(self):
        # Recursively search for RINEX files (*.??o / *.??O) in the selected folder
        folder = filedialog.askdirectory(title="Select folder to search for RINEX files")
        if not folder:
            return

        found_files = []
        for dirpath, _, filenames in os.walk(folder):
            for filename in filenames:
                if any(fnmatch.fnmatch(filename, pattern) for pattern in RINEX_OBS_PATTERNS):
                    found_files.append(os.path.join(dirpath, filename))

        new_files = [f for f in found_files if f not in self.files]
        self.files.extend(new_files)
        self.update_files_list()

        messagebox.showinfo(
            "Search complete",
            f"Files found: {len(found_files)}\nNew files added: {len(new_files)}"
        )

    def select_save_path(self):
        # Open the folder selection dialog
        self.save_path = filedialog.askdirectory(title="Select folder to save to")
        self.update_save_path()

    def update_save_mode(self):
        # Enable/disable the save path button depending on the selected mode
        if self.save_mode.get() == "source":
            self.save_path_button.config(state="disabled")
        else:
            self.save_path_button.config(state="normal")

    def load_default_config(self):
        # Silently apply config.yaml/config.yml from the current directory, if present
        for config_file in DEFAULT_CONFIG_FILES:
            if os.path.isfile(config_file):
                try:
                    self.apply_config(self.read_config_file(config_file))
                except (yaml.YAMLError, OSError):
                    pass
                break

    def load_config(self):
        # Load one or more YAML config files chosen by the user and apply them.
        # When several files are selected, they are merged in order, so later
        # files override values from earlier ones.
        config_files = filedialog.askopenfilenames(
            title="Select YAML config file(s)",
            filetypes=(("YAML files", "*.yaml *.yml"), ("All files", "*.*"))
        )
        if not config_files:
            return

        config = {}
        try:
            for config_file in config_files:
                config.update(self.read_config_file(config_file))
        except (yaml.YAMLError, OSError) as e:
            messagebox.showerror("Config Error", f"Could not read config file: {e}")
            return

        self.apply_config(config)
        messagebox.showinfo("Config loaded", f"Loaded {len(config_files)} config file(s).")

    @staticmethod
    def read_config_file(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def apply_config(self, config):
        string_var_map = {
            'organization': self.organization,
            'object': self.object_name,
            'operator': self.operator,
            'geodetic_mark_type': self.benchmark_type,
            'benchmark_type': self.center_type,
            'gdop': self.gdop,
            'pdop': self.pdop,
        }
        for key, var in string_var_map.items():
            if config.get(key) is not None:
                var.set(str(config[key]))

        measurement_type = config.get('measurement_type')
        if measurement_type is not None:
            if measurement_type in MEASUREMENT_OPTIONS:
                self.measurement_type.set(measurement_type)
            else:
                messagebox.showwarning(
                    "Invalid config value",
                    f"Unknown measurement_type: {measurement_type!r}"
                )

        for prefix, random_var, min_var, max_var, fixed_entry in (
            ('gdop', self.gdop_random, self.gdop_min, self.gdop_max, self.gdop_entry),
            ('pdop', self.pdop_random, self.pdop_min, self.pdop_max, self.pdop_entry),
        ):
            if config.get(f'{prefix}_random') is not None:
                random_var.set(bool(config[f'{prefix}_random']))
            if config.get(f'{prefix}_min') is not None:
                min_var.set(str(config[f'{prefix}_min']))
            if config.get(f'{prefix}_max') is not None:
                max_var.set(str(config[f'{prefix}_max']))
            min_entry = self.gdop_min_entry if prefix == 'gdop' else self.pdop_min_entry
            max_entry = self.gdop_max_entry if prefix == 'gdop' else self.pdop_max_entry
            self.update_random_mode(fixed_entry, random_var, min_entry, max_entry)

        save_mode = config.get('save_mode')
        if save_mode is not None:
            if save_mode in SAVE_MODES:
                self.save_mode.set(save_mode)
                self.update_save_mode()
            else:
                messagebox.showwarning("Invalid config value", f"Unknown save_mode: {save_mode!r}")

        save_path = config.get('save_path')
        if save_path:
            self.save_path = save_path
            self.update_save_path()

        file_rules = config.get('file_rules')
        if file_rules is not None:
            if isinstance(file_rules, list) and all(
                isinstance(rule, dict) and 'pattern' in rule for rule in file_rules
            ):
                self.file_rules = file_rules
            else:
                messagebox.showwarning(
                    "Invalid config value",
                    "file_rules must be a list of mappings, each with a 'pattern' key."
                )
        self.update_file_rules_label()

    def update_file_rules_label(self):
        self.file_rules_label.config(text=f"Per-file rules: {len(self.file_rules)} loaded")

    @staticmethod
    def parse_dop_range(min_str, max_str, label):
        try:
            lo = float(min_str)
            hi = float(max_str)
        except ValueError:
            messagebox.showerror("Invalid range", f"{label} min/max must be numbers.")
            return None
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi

    @staticmethod
    def file_matches_rule(file_path, pattern):
        # Match against the file's basename, or its full path (with forward
        # slashes) for patterns that include a directory part.
        basename = os.path.basename(file_path)
        normalized_path = os.path.abspath(file_path).replace(os.sep, '/')
        return fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(normalized_path, pattern)

    def save_config(self):
        # Save the current form values to a YAML config file for later reuse
        config_file = filedialog.asksaveasfilename(
            title="Save config as",
            defaultextension=".yaml",
            filetypes=(("YAML files", "*.yaml *.yml"), ("All files", "*.*"))
        )
        if not config_file:
            return

        config = {
            'organization': self.organization.get(),
            'object': self.object_name.get(),
            'operator': self.operator.get(),
            'geodetic_mark_type': self.benchmark_type.get(),
            'benchmark_type': self.center_type.get(),
            'gdop': self.gdop.get(),
            'pdop': self.pdop.get(),
            'gdop_random': self.gdop_random.get(),
            'gdop_min': self.gdop_min.get(),
            'gdop_max': self.gdop_max.get(),
            'pdop_random': self.pdop_random.get(),
            'pdop_min': self.pdop_min.get(),
            'pdop_max': self.pdop_max.get(),
            'measurement_type': self.measurement_type.get(),
            'save_mode': self.save_mode.get(),
        }
        if self.save_mode.get() == 'custom' and self.save_path:
            config['save_path'] = self.save_path
        if self.file_rules:
            config['file_rules'] = self.file_rules

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
        except OSError as e:
            messagebox.showerror("Config Error", f"Could not save config file: {e}")
            return

        messagebox.showinfo("Config saved", f"Configuration saved to {config_file}")

    def save_processed_config(self, processed_records):
        # Save the exact resolved parameters of every processed file as
        # file_rules, one per file, matched by its exact absolute path.
        # Editing the values and reloading this file (via "Load config
        # (YAML)") re-applies the corrected parameters individually to
        # each of these files on the next run.
        config_file = filedialog.asksaveasfilename(
            title="Save processed files config as",
            defaultextension=".yaml",
            initialfile=f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml",
            filetypes=(("YAML files", "*.yaml *.yml"), ("All files", "*.*"))
        )
        if not config_file:
            return

        config = {
            'file_rules': [
                {
                    'pattern': glob.escape(os.path.abspath(file)).replace(os.sep, '/'),
                    **metadata,
                }
                for file, metadata in processed_records
            ]
        }

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
        except OSError as e:
            messagebox.showerror("Config Error", f"Could not save processed files config: {e}")
            return

        messagebox.showinfo(
            "Processed config saved",
            f"Saved parameters for {len(processed_records)} file(s) to {config_file}.\n"
            "Edit the values as needed, then load this file via "
            "\"Load config (YAML)\" before the next run."
        )

    def update_files_list(self):
        # Refresh the file list in the interface
        self.files_list_text.config(state='normal')
        self.files_list_text.delete(1.0, tk.END)
        for file in self.files:
            self.files_list_text.insert(tk.END, file + "\n")
        self.files_list_text.config(state='disabled')

    def update_save_path(self):
        # Refresh the save path field in the interface
        self.save_path_text.config(state='normal')
        self.save_path_text.delete(0, tk.END)
        self.save_path_text.insert(0, self.save_path)
        self.save_path_text.config(state='disabled')

    def convert_tex_to_docx(self, tex_file_path, output_dir):
        # Define the output .docx file path
        docx_file_path = os.path.join(output_dir, os.path.splitext(os.path.basename(tex_file_path))[0]+'.docx')

        try:
            # Convert .tex to .docx using pypandoc
            pypandoc.convert_file(tex_file_path, 'docx', outputfile=docx_file_path)
        except Exception as e:
            print(f"Error converting {tex_file_path} to docx: {e}")

    def process_files(self):
        if not self.files:
            messagebox.showwarning("No files", "Please add files to process.")
            return

        if self.save_mode.get() == "custom" and not self.save_path:
            messagebox.showwarning("No save path", "Please select a folder to save to.")
            return

        gdop_range = None
        if self.gdop_random.get():
            gdop_range = self.parse_dop_range(self.gdop_min.get(), self.gdop_max.get(), "GDOP")
            if gdop_range is None:
                return

        pdop_range = None
        if self.pdop_random.get():
            pdop_range = self.parse_dop_range(self.pdop_min.get(), self.pdop_max.get(), "PDOP")
            if pdop_range is None:
                return

        base_metadata = {
            'organization': self.organization.get(),
            'object': self.object_name.get(),
            'operator': self.operator.get(),
            'geodetic_mark_type': self.benchmark_type.get(),
            'benchmark_type': self.center_type.get(),
            'gdop': self.gdop.get(),
            'pdop': self.pdop.get(),
            'measurement_type': self.measurement_type.get(),
        }

        processed_records = []

        failed_files = []

        total_files = len(self.files)
        self.progress_bar['maximum'] = total_files
        self.progress_var.set(0)
        self.process_button.config(state='disabled')

        for index, file in enumerate(self.files, start=1):
            self.progress_label.config(text=f"Processing {index}/{total_files}: {os.path.basename(file)}")
            self.root.update_idletasks()
            try:
                file_info = get_info(file)

                # Start from the global form values, draw fresh random
                # GDOP/PDOP for this file if enabled, then let any matching
                # file_rules override individual fields for this specific file
                file_metadata = dict(base_metadata)
                if gdop_range is not None:
                    file_metadata['gdop'] = f'{random.uniform(*gdop_range):.2f}'
                if pdop_range is not None:
                    file_metadata['pdop'] = f'{random.uniform(*pdop_range):.2f}'
                for rule in self.file_rules:
                    if self.file_matches_rule(file, rule['pattern']):
                        file_metadata.update({k: v for k, v in rule.items() if k != 'pattern'})

                measurement_type = file_metadata['measurement_type']
                if measurement_type not in ANTENNA_HEIGHT_TYPES:
                    raise ValueError(f"Unknown measurement_type {measurement_type!r}")
                file_info['antenna height type'] = ANTENNA_HEIGHT_TYPES[measurement_type]

                for field_key, info_key in FIELD_TO_INFO_KEY.items():
                    file_info[info_key] = file_metadata.get(field_key, '')

                if self.save_mode.get() == "source":
                    output_dir = os.path.dirname(os.path.abspath(file))
                else:
                    output_dir = self.save_path

                marker_name = file_info['marker name'].strip()
                if not marker_name:
                    # MARKER NAME is blank in the RINEX header; fall back to
                    # the source file's own name so output isn't silently
                    # lost/broken, and keep file_info consistent so the map
                    # image and the journal itself use the same name
                    marker_name = os.path.splitext(os.path.basename(file))[0]
                    print(f'Warning! Empty MARKER NAME in {file}, using source filename "{marker_name}" instead.')
                file_info['marker name'] = marker_name

                save_file = os.path.join(output_dir, marker_name)
                journal_generator(file_info, save_file)
                self.convert_tex_to_docx(save_file + '.tex', output_dir)

                processed_records.append((file, file_metadata))
            except Exception as e:
                print(f'Error processing {file}: {e}')
                failed_files.append((file, str(e)))

            self.progress_var.set(index)
            self.root.update_idletasks()

        self.progress_label.config(text="")
        self.process_button.config(state='normal')

        if failed_files:
            failure_list = "\n".join(f"- {os.path.basename(f)}: {err}" for f, err in failed_files)
            messagebox.showwarning(
                "Processing complete with errors",
                f"Processed {len(processed_records)} file(s) successfully.\n"
                f"{len(failed_files)} file(s) failed:\n{failure_list}"
            )
        else:
            messagebox.showinfo("Processing complete", "Files were successfully processed and saved.")

        if self.save_yaml.get() and processed_records:
            self.save_processed_config(processed_records)

        self.files.clear()
        self.update_files_list()
        self.save_path = ""
        self.update_save_path()
        self.progress_var.set(0)

    def reset(self):
        # Reset the file list and save path
        self.files = []
        self.save_path = ""
        self.update_files_list()
        self.update_save_path()
        self.progress_var.set(0)
        self.progress_label.config(text="")


def run_app():
    root = tk.Tk()
    app = FileProcessorApp(root)
    root.mainloop()

if __name__ == "__main__":
    run_app()
