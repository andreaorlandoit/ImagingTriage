#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Program Name: elabora_arw.py
Version: 2025-06-27
Author: Andrea Orlando
Purpose: This script analyzes a folder containing .ARW and .XMP files,
         extracts rating and color label from the .XMP files, and moves the
         files into subfolders based on this metadata.
License: GPLv3
"""

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

def get_script_directory():
    """Returns the directory where the script is located."""
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def load_configuration():
    """Loads configuration from config.xml. If it doesn't exist, creates it."""
    config_path = os.path.join(get_script_directory(), CONFIG_FILE)
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        lang = root.find("language").text
        return {"language": lang}
    except (FileNotFoundError, ET.ParseError):
        return {"language": "en"} # Default to English

def save_configuration(language_code):
    """Saves the selected language to config.xml."""
    config_path = os.path.join(get_script_directory(), CONFIG_FILE)
    root = ET.Element("config", version="1.0")
    lang_element = ET.SubElement(root, "language")
    lang_element.text = language_code
    tree = ET.ElementTree(root)
    tree.write(config_path, encoding="utf-8", xml_declaration=True)

# --- Language Management ---
class LanguageManager:
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
        """Gets a string by key and formats it if necessary."""
        return self.strings.get(key, key).format(**kwargs)

# --- Core Logic ---
def process_directory(folder_to_process, progress_callback=None):
    stats = {
        "total_arw": 0,
        "processed_count": 0,
        "moved_to_missing": 0,
        "unclassified_no_xmp": 0,
        "unclassified_no_metadata": 0,
        "folder_distribution": defaultdict(int),
        "errors": []
    }

    if not os.path.isdir(folder_to_process):
        stats["errors"].append("The specified folder does not exist.")
        return stats

    arw_files = {}
    xmp_files = {}

    for filename in os.listdir(folder_to_process):
        if filename.lower().endswith(".arw"):
            base_name, _ = os.path.splitext(filename)
            arw_files[base_name] = os.path.join(folder_to_process, filename)
        elif filename.lower().endswith(".xmp"):
            base_name, _ = os.path.splitext(filename)
            xmp_files[base_name] = os.path.join(folder_to_process, filename)

    stats["total_arw"] = len(arw_files)
    missing_folder = os.path.join(folder_to_process, "RATING_MISSING")

    for i, (base_name, arw_path) in enumerate(arw_files.items()):
        if progress_callback:
            progress_callback(i + 1, stats["total_arw"])

        if base_name not in xmp_files:
            stats["unclassified_no_xmp"] += 1
            os.makedirs(missing_folder, exist_ok=True)
            shutil.move(arw_path, os.path.join(missing_folder, os.path.basename(arw_path)))
            stats["moved_to_missing"] += 1
            continue

        xmp_path = xmp_files[base_name]
        try:
            tree = ET.parse(xmp_path)
            root = tree.getroot()
            rdf_description = root.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')

            rating_value = None
            label_value = None
            if rdf_description is not None:
                rating_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Rating')
                label_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Label')

            folder_parts = []
            if rating_value:
                folder_parts.append(f"RATING_{rating_value}")
            if label_value:
                folder_parts.append(f"LABEL_{label_value}")

            if folder_parts:
                subfolder_name = "-".join(folder_parts)
                destination_folder = os.path.join(folder_to_process, subfolder_name)
                os.makedirs(destination_folder, exist_ok=True)
                
                shutil.move(arw_path, os.path.join(destination_folder, os.path.basename(arw_path)))
                shutil.move(xmp_path, os.path.join(destination_folder, os.path.basename(xmp_path)))
                
                stats["processed_count"] += 1
                stats["folder_distribution"][subfolder_name] += 1
            else:
                stats["unclassified_no_metadata"] += 1
                os.makedirs(missing_folder, exist_ok=True)
                shutil.move(arw_path, os.path.join(missing_folder, os.path.basename(arw_path)))
                shutil.move(xmp_path, os.path.join(missing_folder, os.path.basename(xmp_path)))
                stats["moved_to_missing"] += 1

        except FileNotFoundError:
            stats["errors"].append(f"File XMP not found (after initial scan): {xmp_path}")
        except ET.ParseError:
            stats["errors"].append(f"Error parsing XMP file: {xmp_path}")

    return stats

# --- UI Classes ---
class ConfigWindow(tk.Toplevel):
    def __init__(self, parent, lang_manager):
        super().__init__(parent)
        self.master = parent # Keep a reference to the main window
        self.lang_manager = lang_manager
        self.title(lang_manager.get("config_window_title"))
        self.geometry("400x150")
        self.resizable(False, False)
        self.transient(parent)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        label = ttk.Label(main_frame, text=lang_manager.get("config_language_label"))
        label.pack(pady=5)

        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(main_frame, textvariable=self.lang_var, state="readonly")
        self.lang_combo.pack(pady=5, fill="x")

        self.populate_languages()

        save_button = ttk.Button(main_frame, text=lang_manager.get("config_save_button"), command=self.save_and_restart)
        save_button.pack(pady=10)

    def populate_languages(self):
        lang_dir = os.path.join(get_script_directory(), "lang")
        try:
            languages = [f.split('.')[0] for f in os.listdir(lang_dir) if f.endswith('.json')]
            self.lang_combo['values'] = languages
            current_lang = load_configuration()['language']
            if current_lang in languages:
                self.lang_combo.set(current_lang)
        except FileNotFoundError:
            self.lang_combo['values'] = ['en']
            self.lang_combo.set('en')

    def save_and_restart(self):
        selected_lang = self.lang_var.get()
        if selected_lang:
            save_configuration(selected_lang)
            messagebox.showinfo(self.lang_manager.get("config_window_title"), self.lang_manager.get("config_restart_notice"))
            
            subprocess.Popen([sys.executable] + sys.argv)
            self.master.destroy()

class ImageProcessorUI:
    def __init__(self, master, lang_manager, initial_folder=None):
        self.master = master
        self.lang = lang_manager
        master.title(self.lang.get("app_title"))
        master.geometry("800x220")
        master.resizable(False, False)

        self.folder_path = tk.StringVar()
        if initial_folder:
            self.folder_path.set(initial_folder)
        
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

        button_frame = ttk.Frame(master, padding="10")
        button_frame.grid(row=2, column=0, sticky="ew")
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

    def open_config(self):
        ConfigWindow(self.master, self.lang)

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
        self.progress_bar["value"] = 0
        
        self.processing_thread = threading.Thread(
            target=self.run_processing_logic,
            args=(folder_to_process,)
        )
        self.processing_thread.start()

    def run_processing_logic(self, folder_path):
        def progress_handler(current, total):
            self.master.after(0, self.update_progress, current, total)

        result_stats = process_directory(folder_path, progress_handler)
        self.master.after(0, self.on_processing_complete, result_stats)

    def update_progress(self, current, total):
        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar["value"] = percentage
            self.status_label.config(text=self.lang.get("status_processing", current=current, total=total))
        self.master.update_idletasks()

    def on_processing_complete(self, stats):
        self.button_process.config(state="normal")
        self.button_browse.config(state="normal")
        self.button_config.config(state="normal")
        self.progress_bar["value"] = 100
        self.status_label.config(text=self.lang.get("status_complete"))

        report = []
        report.append(self.lang.get("report_header"))
        report.append(self.lang.get("report_total_arw", count=stats['total_arw']))
        report.append(self.lang.get("report_moved_rated", count=stats['processed_count']))
        report.append(self.lang.get("report_moved_missing", count=stats['moved_to_missing']))
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
        
        messagebox.showinfo(self.lang.get("report_title"), "\n".join(report))
        self.status_label.config(text=self.lang.get("status_ready"))
        self.progress_bar["value"] = 0

if __name__ == "__main__":
    config = load_configuration()
    lang_manager = LanguageManager(config['language'])

    initial_folder = None
    if len(sys.argv) > 1:
        initial_folder = sys.argv[1]

    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('vista')
    
    ui = ImageProcessorUI(root, lang_manager, initial_folder)
    root.mainloop()
