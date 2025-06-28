#!/usr/bin/env python
# -*- coding: utf-8 -*-


Program Name: ImagingTriage
Version: 2025-06-27
Author: Andrea Orlando
Purpose: This script analyzes a folder containing image files and their .XMP sidecars,
         extracts rating and color label metadata, and moves the files into
         subfolders. It supports configurable file types.
License: GPLv3


import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import xml.etree.ElementTree as ET
import shutil
import sys
import threading
import json
import subprocess
from collections import defaultdict

# --- Configuration Management ---
CONFIG_FILE = "config.xml"
DEFAULT_EXTENSIONS = "arw,arq,axr,jpg,jpeg,tif,tiff,heif"

def get_script_directory():
    """Returns the directory where the script is located."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def load_configuration():
    """Loads configuration from config.xml. Returns defaults if not found or invalid."""
    config_path = os.path.join(get_script_directory(), CONFIG_FILE)
    config = {"language": "en", "extensions": DEFAULT_EXTENSIONS}
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        config["language"] = root.find("language").text
        config["extensions"] = root.find("supported_extensions").text
    except (FileNotFoundError, ET.ParseError, AttributeError):
        # If file or tags are missing, defaults are used
        pass
    return config

def save_configuration(language_code, extensions_string):
    """Saves the configuration to config.xml after sanitizing inputs."""
    config_path = os.path.join(get_script_directory(), CONFIG_FILE)
    root = ET.Element("config", version="1.1")
    
    # Save language
    lang_element = ET.SubElement(root, "language")
    lang_element.text = language_code
    
    # Sanitize and save extensions
    sanitized_extensions = sanitize_extensions(extensions_string)
    ext_element = ET.SubElement(root, "supported_extensions")
    ext_element.text = sanitized_extensions
    
    tree = ET.ElementTree(root)
    tree.write(config_path, encoding="utf-8", xml_declaration=True)

def sanitize_extensions(ext_string):
    """Cleans and validates the user-provided extension string."""
    if not ext_string:
        return DEFAULT_EXTENSIONS
    
    # Split, strip whitespace, remove leading dots, filter out empty strings
    extensions = [ext.strip().lstrip('.') for ext in ext_string.lower().split(',')]
    valid_extensions = [ext for ext in extensions if ext]
    
    if not valid_extensions:
        return DEFAULT_EXTENSIONS
        
    return ",".join(valid_extensions)

# --- Language Management ---
class LanguageManager:
    # ... (class is unchanged)
    def __init__(self, language_code):
        self.strings = {}
        self.load_language(language_code)

    def load_language(self, language_code):
        lang_file = os.path.join(get_script_directory(), "lang", f"{language_code}.json")
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
        except FileNotFoundError:
            if language_code != 'en':
                self.load_language('en')
            else:
                self.strings = {"app_title": "Error: Language file not found"}

    def get(self, key, **kwargs):
        return self.strings.get(key, key).format(**kwargs)

# --- Core Logic ---
def gather_files_back(folder_to_process, progress_callback=None):
    # ... (function is unchanged)
    stats = {
        "moved_count": 0,
        "deleted_folders": 0,
        "errors": []
    }
    
    subfolders = [d for d in os.listdir(folder_to_process) 
                  if os.path.isdir(os.path.join(folder_to_process, d)) and 
                  (d.startswith("RATING_") or d.startswith("LABEL_"))]

    total_files_to_move = 0
    for subfolder in subfolders:
        total_files_to_move += len(os.listdir(os.path.join(folder_to_process, subfolder)))

    moved_files_count = 0
    for subfolder_name in subfolders:
        subfolder_path = os.path.join(folder_to_process, subfolder_name)
        for filename in os.listdir(subfolder_path):
            source_path = os.path.join(subfolder_path, filename)
            dest_path = os.path.join(folder_to_process, filename)

            if os.path.exists(dest_path):
                stats["errors"].append(f"{filename}")
                continue

            shutil.move(source_path, dest_path)
            stats["moved_count"] += 1
            moved_files_count += 1
            if progress_callback:
                progress_callback(moved_files_count, total_files_to_move)

        if not os.listdir(subfolder_path):
            os.rmdir(subfolder_path)
            stats["deleted_folders"] += 1
            
    return stats

def process_directory(folder_to_process, supported_extensions, inhibit_move_unrated, progress_callback=None):
    """
    Analyzes a folder for files with supported extensions, reads their XMP metadata,
    and moves them accordingly.
    """
    stats = {
        "total_images": 0,
        "processed_count": 0,
        "moved_to_missing": 0,
        "intentionally_ignored": 0,
        "unclassified_no_xmp": 0,
        "unclassified_no_metadata": 0,
        "folder_distribution": defaultdict(int),
        "errors": []
    }

    if not os.path.isdir(folder_to_process):
        stats["errors"].append("The specified folder does not exist.")
        return stats

    image_files = {}
    xmp_files = {}
    supported_ext_tuple = tuple(f".{ext}" for ext in supported_extensions.split(','))

    for filename in os.listdir(folder_to_process):
        if filename.lower().endswith(supported_ext_tuple):
            base_name, _ = os.path.splitext(filename)
            image_files[base_name] = os.path.join(folder_to_process, filename)
        elif filename.lower().endswith(".xmp"):
            base_name, _ = os.path.splitext(filename)
            xmp_files[base_name] = os.path.join(folder_to_process, filename)

    stats["total_images"] = len(image_files)
    missing_folder = os.path.join(folder_to_process, "RATING_MISSING")

    for i, (base_name, image_path) in enumerate(image_files.items()):
        if progress_callback:
            progress_callback(i + 1, stats["total_images"])

        is_rated = False
        rating_value = None
        label_value = None

        if base_name in xmp_files:
            xmp_path = xmp_files[base_name]
            try:
                tree = ET.parse(xmp_path)
                root = tree.getroot()
                rdf_description = root.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')

                if rdf_description is not None:
                    rating_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Rating')
                    label_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Label')

                    if (rating_value and rating_value != '0') or (label_value and label_value.lower() != 'none'):
                        is_rated = True

            except (FileNotFoundError, ET.ParseError) as e:
                stats["errors"].append(f"Error processing {os.path.basename(xmp_path)}: {e}")
                is_rated = False
        
        if is_rated:
            folder_parts = []
            if rating_value and rating_value != '0':
                folder_parts.append(f"RATING_{rating_value}")
            if label_value and label_value.lower() != 'none':
                folder_parts.append(f"LABEL_{label_value}")
            
            subfolder_name = "-".join(folder_parts)
            destination_folder = os.path.join(folder_to_process, subfolder_name)
            os.makedirs(destination_folder, exist_ok=True)
            
            shutil.move(image_path, os.path.join(destination_folder, os.path.basename(image_path)))
            if base_name in xmp_files:
                shutil.move(xmp_files[base_name], os.path.join(destination_folder, os.path.basename(xmp_files[base_name])))
            
            stats["processed_count"] += 1
            stats["folder_distribution"][subfolder_name] += 1
        else:
            if base_name not in xmp_files:
                stats["unclassified_no_xmp"] += 1
            else:
                stats["unclassified_no_metadata"] += 1

            if inhibit_move_unrated:
                stats["intentionally_ignored"] += 1
                continue
            
            os.makedirs(missing_folder, exist_ok=True)
            shutil.move(image_path, os.path.join(missing_folder, os.path.basename(image_path)))
            if base_name in xmp_files:
                shutil.move(xmp_files[base_name], os.path.join(missing_folder, os.path.basename(xmp_files[base_name])))
            stats["moved_to_missing"] += 1

    return stats

# --- UI Classes ---
class ReportWindow(tk.Toplevel):
    # ... (class is unchanged)
    def __init__(self, parent, title, report_string):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x500")
        self.resizable(True, True)
        self.transient(parent)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        text_widget = tk.Text(text_frame, wrap="word", font=("Courier New", 10))
        text_widget.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text_widget.config(yscrollcommand=scrollbar.set)

        text_widget.insert("1.0", report_string)
        text_widget.config(state="disabled")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        
        ok_button = ttk.Button(button_frame, text="OK", command=self.destroy)
        ok_button.pack()

class ConfigWindow(tk.Toplevel):
    def __init__(self, parent, lang_manager, current_config):
        super().__init__(parent)
        self.master = parent
        self.lang_manager = lang_manager
        self.title(lang_manager.get("config_window_title"))
        self.geometry("450x200")
        self.resizable(False, False)
        self.transient(parent)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Language selection
        lang_label = ttk.Label(main_frame, text=lang_manager.get("config_language_label"))
        lang_label.pack(pady=(0,5), anchor="w")

        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(main_frame, textvariable=self.lang_var, state="readonly")
        self.lang_combo.pack(pady=(0,10), fill="x")

        # Extensions input
        ext_label = ttk.Label(main_frame, text=lang_manager.get("config_extensions_label"))
        ext_label.pack(pady=(10,5), anchor="w")

        self.ext_var = tk.StringVar()
        self.ext_entry = ttk.Entry(main_frame, textvariable=self.ext_var)
        self.ext_entry.pack(pady=(0,10), fill="x")

        self.populate_fields(current_config)

        save_button = ttk.Button(main_frame, text=lang_manager.get("config_save_button"), command=self.save_and_restart)
        save_button.pack(pady=10)

    def populate_fields(self, current_config):
        # Populate languages
        lang_dir = os.path.join(get_script_directory(), "lang")
        try:
            languages = [f.split('.')[0] for f in os.listdir(lang_dir) if f.endswith('.json')]
            self.lang_combo['values'] = languages
            self.lang_var.set(current_config['language'])
        except FileNotFoundError:
            self.lang_combo['values'] = ['en']
            self.lang_var.set('en')
        
        # Populate extensions
        self.ext_var.set(current_config['extensions'])

    def save_and_restart(self):
        selected_lang = self.lang_var.get()
        extensions_str = self.ext_var.get()
        
        save_configuration(selected_lang, extensions_str)
        messagebox.showinfo(self.lang_manager.get("config_window_title"), self.lang_manager.get("config_restart_notice"))
        subprocess.Popen([sys.executable] + sys.argv)
        self.master.destroy()

class ImageProcessorUI:
    def __init__(self, master, lang_manager, config, initial_folder=None):
        self.master = master
        self.lang = lang_manager
        self.config = config
        master.title(self.lang.get("app_title"))
        master.geometry("800x240")
        master.resizable(False, False)

        self.folder_path = tk.StringVar()
        if initial_folder:
            self.folder_path.set(initial_folder)
        
        self.gather_mode = tk.BooleanVar()
        self.inhibit_move_mode = tk.BooleanVar()
        self.processing_thread = None

        # --- UI Widgets ---
        input_frame = ttk.Frame(master, padding="10")
        input_frame.grid(row=0, column=0, sticky="ew")
        input_frame.columnconfigure(1, weight=1)

        self.label_folder = ttk.Label(input_frame, text=self.lang.get("folder_label"))
        self.label_folder.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")

        self.entry_folder = ttk.Entry(input_frame, textvariable=self.folder_path, width=80)
        self.entry_folder.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.button_browse = ttk.Button(input_frame, text=self.lang.get("browse_button"), command=self.browse_folder)
        self.button_browse.grid(row=0, column=2, padx=(5, 0), pady=5, sticky="e")

        progress_frame = ttk.Frame(master, padding="10")
        progress_frame.grid(row=1, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(progress_frame, text=self.lang.get("status_ready"))
        self.status_label.grid(row=0, column=0, sticky="w")
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5,0))

        options_frame = ttk.Frame(master, padding=(10,0,10,10))
        options_frame.grid(row=2, column=0, sticky="w")
        
        self.gather_checkbox = ttk.Checkbutton(options_frame, text=self.lang.get("gather_checkbox_label"), variable=self.gather_mode, command=self.toggle_options)
        self.gather_checkbox.pack(side="top", anchor="w")

        self.inhibit_move_checkbox = ttk.Checkbutton(options_frame, text=self.lang.get("inhibit_move_checkbox_label"), variable=self.inhibit_move_mode)
        self.inhibit_move_checkbox.pack(side="top", anchor="w", pady=(5,0))

        button_frame = ttk.Frame(master, padding="10")
        button_frame.grid(row=3, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)

        self.button_process = ttk.Button(button_frame, text=self.lang.get("process_button"), command=self.start_processing)
        self.button_process.grid(row=0, column=0, columnspan=2, sticky="ew")

        action_frame = ttk.Frame(button_frame)
        action_frame.grid(row=0, column=2, sticky="e")

        self.button_config = ttk.Button(action_frame, text=self.lang.get("config_button"), command=self.open_config)
        self.button_config.pack(side="left", padx=(10, 5))

        self.button_cancel = ttk.Button(action_frame, text=self.lang.get("exit_button"), command=master.quit)
        self.button_cancel.pack(side="left")

        master.columnconfigure(0, weight=1)

    def toggle_options(self):
        if self.gather_mode.get():
            self.inhibit_move_checkbox.config(state="disabled")
        else:
            self.inhibit_move_checkbox.config(state="normal")

    def open_config(self):
        ConfigWindow(self.master, self.lang, self.config)

    def browse_folder(self):
        initial_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        folder_selected = filedialog.askdirectory(initialdir=initial_dir)
        if folder_selected:
            self.folder_path.set(folder_selected)

    def start_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning(self.lang.get("app_title"), self.lang.get("warning_already_running"))
            return

        folder_to_process = self.folder_path.get()
        if not os.path.isdir(folder_to_process):
            messagebox.showerror(self.lang.get("app_title"), self.lang.get("error_folder_not_exists"))
            return

        self.button_process.config(state="disabled")
        self.button_browse.config(state="disabled")
        self.button_config.config(state="disabled")
        self.gather_checkbox.config(state="disabled")
        self.inhibit_move_checkbox.config(state="disabled")
        self.progress_bar["value"] = 0
        
        if self.gather_mode.get():
            target_function = self.run_gather_logic
            args = (folder_to_process,)
        else:
            target_function = self.run_processing_logic
            args = (folder_to_process, self.config['extensions'], self.inhibit_move_mode.get())

        self.processing_thread = threading.Thread(target=target_function, args=args)
        self.processing_thread.start()

    def run_processing_logic(self, folder_path, extensions, inhibit_move):
        def progress_handler(current, total):
            self.master.after(0, self.update_progress, current, total)

        result_stats = process_directory(folder_path, extensions, inhibit_move, progress_handler)
        self.master.after(0, self.on_processing_complete, result_stats)

    def run_gather_logic(self, folder_path):
        def progress_handler(current, total):
            self.master.after(0, self.update_progress, current, total)

        result_stats = gather_files_back(folder_path, progress_handler)
        self.master.after(0, self.on_gather_complete, result_stats)

    def update_progress(self, current, total):
        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar["value"] = percentage
            self.status_label.config(text=self.lang.get("status_processing", current=current, total=total))
        self.master.update_idletasks()

    def on_processing_complete(self, stats):
        self.reset_ui_state()
        report = []
        report.append(self.lang.get("report_header"))
        report.append(self.lang.get("report_total_arw", count=stats['total_images']))
        report.append(self.lang.get("report_moved_rated", count=stats['processed_count']))
        report.append(self.lang.get("report_moved_missing", count=stats['moved_to_missing']))
        if stats['intentionally_ignored'] > 0:
            report.append(self.lang.get("report_intentionally_ignored", count=stats['intentionally_ignored']))
        report.append("")
        report.append(self.lang.get("report_ignored_header"))
        report.append(self.lang.get("report_ignored_no_xmp", count=stats['unclassified_no_xmp']))
        report.append(self.lang.get("report_ignored_no_rating_tag", count=stats['unclassified_no_metadata']))
        report.append("")
        report.append(self.lang.get("report_folder_distribution"))
        if stats['folder_distribution']:
            for folder, count in sorted(stats['folder_distribution'].items()):
                report.append(self.lang.get("report_folder_line", folder_name=folder, count=count))
        else:
            report.append(self.lang.get("report_no_files_moved"))

        if stats["errors"]:
            error_list = "\n".join([f"- {e}" for e in stats["errors"]])
            report.append(self.lang.get("report_errors_header"))
            report.append(error_list)
        
        ReportWindow(self.master, self.lang.get("report_title"), "\n".join(report))

    def on_gather_complete(self, stats):
        self.reset_ui_state()
        report = []
        report.append(self.lang.get("gather_report_header"))
        report.append(self.lang.get("gather_report_moved", count=stats['moved_count']))
        report.append(self.lang.get("gather_report_deleted", count=stats['deleted_folders']))

        if stats["errors"]:
            error_list = "\n".join([f"- {self.lang.get('gather_error_conflict', filename=e)}" for e in stats["errors"]])
            report.append(self.lang.get("report_errors_header"))
            report.append(error_list)

        ReportWindow(self.master, self.lang.get("gather_report_title"), "\n".join(report))

    def reset_ui_state(self):
        self.button_process.config(state="normal")
        self.button_browse.config(state="normal")
        self.button_config.config(state="normal")
        self.gather_checkbox.config(state="normal")
        self.inhibit_move_checkbox.config(state="normal")
        self.toggle_options()
        self.progress_bar["value"] = 100
        self.status_label.config(text=self.lang.get("status_complete"))
        self.master.after(2000, lambda: self.status_label.config(text=self.lang.get("status_ready")))
        self.master.after(2000, lambda: self.progress_bar.config(value=0))

if __name__ == "__main__":
    config = load_configuration()
    lang_manager = LanguageManager(config['language'])

    initial_folder = None
    if len(sys.argv) > 1:
        initial_folder = sys.argv[1]

    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('vista')
    
    ui = ImageProcessorUI(root, lang_manager, config, initial_folder)
    root.mainloop()