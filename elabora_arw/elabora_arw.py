#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nome del Programma: elabora_arw.py
Versione: 2025-06-27
Autore: Andrea Orlando
Scopo: Questo script analizza una cartella contenente file .ARW e .XMP,
       estrae il valore del rating dai file .XMP e sposta i file .ARW
       in sottocartelle create in base al rating.
Licenza: GPLv3
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import xml.etree.ElementTree as ET
import shutil
import sys
import threading
from collections import defaultdict

def process_directory(folder_to_process, progress_callback=None):
    """
    Analizza una cartella, legge i rating dai file XMP e sposta i file ARW e XMP
    corrispondenti in sottocartelle basate sul rating.

    Args:
        folder_to_process (str): Il percorso della cartella da elaborare.
        progress_callback (function, optional): Funzione da chiamare per ogni file analizzato.

    Returns:
        dict: Un dizionario con le statistiche dettagliate dell'elaborazione.
    """
    stats = {
        "total_arw": 0,
        "processed_count": 0,
        "moved_to_missing": 0,
        "no_xmp_found": 0,
        "no_rating_in_xmp": 0,
        "rating_distribution": defaultdict(int),
        "errors": []
    }

    if not os.path.isdir(folder_to_process):
        stats["errors"].append("La cartella specificata non esiste.")
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
    missing_rating_folder = os.path.join(folder_to_process, "RATING_MISSING")

    for i, (base_name, arw_path) in enumerate(arw_files.items()):
        if progress_callback:
            progress_callback(i + 1, stats["total_arw"])

        if base_name not in xmp_files:
            stats["no_xmp_found"] += 1
            os.makedirs(missing_rating_folder, exist_ok=True)
            shutil.move(arw_path, os.path.join(missing_rating_folder, os.path.basename(arw_path)))
            stats["moved_to_missing"] += 1
            continue

        xmp_path = xmp_files[base_name]
        try:
            tree = ET.parse(xmp_path)
            root = tree.getroot()
            rdf_description = root.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')

            rating_value = None
            if rdf_description is not None:
                rating_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Rating')
            
            if rating_value is not None:
                subfolder_name = f"RATING_{rating_value}"
                destination_folder = os.path.join(folder_to_process, subfolder_name)
                os.makedirs(destination_folder, exist_ok=True)
                shutil.move(arw_path, os.path.join(destination_folder, os.path.basename(arw_path)))
                shutil.move(xmp_path, os.path.join(destination_folder, os.path.basename(xmp_path)))
                stats["processed_count"] += 1
                stats["rating_distribution"][rating_value] += 1
            else:
                stats["no_rating_in_xmp"] += 1
                os.makedirs(missing_rating_folder, exist_ok=True)
                shutil.move(arw_path, os.path.join(missing_rating_folder, os.path.basename(arw_path)))
                shutil.move(xmp_path, os.path.join(missing_rating_folder, os.path.basename(xmp_path)))
                stats["moved_to_missing"] += 1

        except FileNotFoundError:
            stats["errors"].append(f"File XMP non trovato (dopo la scansione iniziale): {xmp_path}")
        except ET.ParseError:
            stats["errors"].append(f"Errore di parsing nel file XMP: {xmp_path}")

    return stats


class ImageProcessorUI:
    def __init__(self, master, initial_folder=None):
        self.master = master
        master.title("Elabora Immagini ARW :: Suddivisione per Rating")
        master.geometry("800x200")
        master.resizable(False, False)

        self.folder_path = tk.StringVar()
        if initial_folder:
            self.folder_path.set(initial_folder)
        
        self.processing_thread = None

        # --- UI Widgets ---
        # Riga 0: Frame per input
        input_frame = ttk.Frame(master, padding="10")
        input_frame.grid(row=0, column=0, sticky="ew")
        input_frame.columnconfigure(1, weight=1)

        self.label_folder = ttk.Label(input_frame, text="Cartella da elaborare:")
        self.label_folder.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")

        self.entry_folder = ttk.Entry(input_frame, textvariable=self.folder_path, width=80)
        self.entry_folder.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.button_browse = ttk.Button(input_frame, text="Sfoglia...", command=self.browse_folder)
        self.button_browse.grid(row=0, column=2, padx=(5, 0), pady=5, sticky="e")

        # Riga 1: Frame per progress bar
        progress_frame = ttk.Frame(master, padding="10")
        progress_frame.grid(row=1, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(progress_frame, text="Pronto.")
        self.status_label.grid(row=0, column=0, sticky="w")
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(5,0))

        # Riga 2: Frame per bottoni
        button_frame = ttk.Frame(master, padding="10")
        button_frame.grid(row=2, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)

        self.button_process = ttk.Button(button_frame, text="Elabora", command=self.start_processing)
        self.button_process.grid(row=0, column=0, sticky="ew")

        self.button_cancel = ttk.Button(button_frame, text="Esci", command=master.quit)
        self.button_cancel.grid(row=0, column=1, sticky="e", padx=(10,0))

        master.columnconfigure(0, weight=1)

    def browse_folder(self):
        initial_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        folder_selected = filedialog.askdirectory(initialdir=initial_dir)
        if folder_selected:
            self.folder_path.set(folder_selected)

    def start_processing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning("Attenzione", "Un'elaborazione è già in corso.")
            return

        folder_to_process = self.folder_path.get()
        if not os.path.isdir(folder_to_process):
            messagebox.showerror("Errore", "Selezionare una cartella valida.")
            return

        self.button_process.config(state="disabled")
        self.button_browse.config(state="disabled")
        self.progress_bar["value"] = 0
        
        self.processing_thread = threading.Thread(
            target=self.run_processing_logic,
            args=(folder_to_process,)
        )
        self.processing_thread.start()

    def run_processing_logic(self, folder_path):
        """Esegue la logica in un thread separato e notifica la UI."""
        def progress_handler(current, total):
            self.master.after(0, self.update_progress, current, total)

        result_stats = process_directory(folder_path, progress_handler)
        self.master.after(0, self.on_processing_complete, result_stats)

    def update_progress(self, current, total):
        if total > 0:
            percentage = (current / total) * 100
            self.progress_bar["value"] = percentage
            self.status_label.config(text=f"Elaborazione: {current}/{total}...")
        self.master.update_idletasks()

    def on_processing_complete(self, stats):
        self.button_process.config(state="normal")
        self.button_browse.config(state="normal")
        self.progress_bar["value"] = 100
        self.status_label.config(text="Completato.")

        # Costruisci il report finale
        report = []
        report.append(f"--- Report Elaborazione ---")
        report.append(f"File ARW totali trovati: {stats['total_arw']}")
        report.append(f"File spostati con rating: {stats['processed_count']}")
        report.append(f"File spostati senza rating (in RATING_MISSING): {stats['moved_to_missing']}")
        report.append("")
        report.append("Dettaglio file ignorati o senza rating:")
        report.append(f"  - Senza .XMP corrispondente: {stats['no_xmp_found']}")
        report.append(f"  - Con .XMP ma senza tag Rating: {stats['no_rating_in_xmp']}")
        report.append("")
        report.append("Distribuzione Rating:")
        if stats['rating_distribution']:
            for rating, count in sorted(stats['rating_distribution'].items()):
                report.append(f"  - Rating '{rating}': {count} file")
        else:
            report.append("  - Nessun file con rating è stato spostato.")

        if stats["errors"]:
            report.append("\n--- Errori ---")
            for error in stats["errors"]:
                report.append(f"- {error}")
        
        messagebox.showinfo("Elaborazione Completata", "\n".join(report))
        self.status_label.config(text="Pronto.")
        self.progress_bar["value"] = 0


if __name__ == "__main__":
    initial_folder = None
    if len(sys.argv) > 1:
        initial_folder = sys.argv[1]

    root = tk.Tk()
    # Usa i widget a tema di ttk per un look più moderno
    style = ttk.Style(root)
    style.theme_use('vista') # 'clam', 'alt', 'default', 'classic', 'vista', 'xpnative'
    
    ui = ImageProcessorUI(root, initial_folder)
    root.mainloop()