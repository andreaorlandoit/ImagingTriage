#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nome del Programma: elabora_arw.py
Versione: 2025-05-11
Autore: Andrea Orlando
Scopo: Questo script analizza una cartella contenente file .ARW e .XMP,
       estrae il valore del rating dai file .XMP e sposta i file .ARW
       in sottocartelle create in base al rating.
Licenza: GPLv3
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import xml.etree.ElementTree as ET
import shutil
import sys  # Importa il modulo sys per gestire gli argomenti da riga di comando

class ImageProcessorUI:
    def __init__(self, master, initial_folder=None):
        self.master = master
        master.title("Elabora Immagini ARW :: Suddivisione in sotto-cartelle per Rating")
        master.geometry("800x120")
        master.resizable(False, False)

        self.folder_path = tk.StringVar()
        if initial_folder:
            self.folder_path.set(initial_folder)

        # Riga 1: Label, Entry, Button
        self.label_folder = tk.Label(master, text="Cartella da elaborare:")
        self.label_folder.grid(row=0, column=0, padx=5, pady=10, sticky="w")

        self.entry_folder = tk.Entry(master, textvariable=self.folder_path, width=60)
        self.entry_folder.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.button_browse = tk.Button(master, text="Sfoglia...", command=self.browse_folder)
        self.button_browse.grid(row=0, column=2, padx=5, pady=10, sticky="e")

        # Riga 2: Buttons
        self.button_process = tk.Button(master, text="Elabora", command=self.process_folder)
        self.button_process.grid(row=1, column=0, columnspan=2, padx=5, pady=10, sticky="ew")

        self.button_cancel = tk.Button(master, text="Annulla", command=master.quit)
        self.button_cancel.grid(row=1, column=2, padx=5, pady=10, sticky="ew")

        # Configurazione del layout per far espandere l'Entry
        master.grid_columnconfigure(1, weight=1)

    def browse_folder(self):
        initial_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        folder_selected = filedialog.askdirectory(initialdir=initial_dir)
        if folder_selected:
            self.folder_path.set(folder_selected)

    def process_folder(self):
        folder_to_process = self.folder_path.get()
        if not os.path.isdir(folder_to_process):
            messagebox.showerror("Errore", "La cartella specificata non esiste.")
            return

        arw_files = {}
        xmp_files = {}

        # Scansiona la cartella per file .ARW e .XMP
        for filename in os.listdir(folder_to_process):
            if filename.lower().endswith(".arw"):
                base_name, _ = os.path.splitext(filename)
                arw_files[base_name] = os.path.join(folder_to_process, filename)
            elif filename.lower().endswith(".xmp"):
                base_name, _ = os.path.splitext(filename)
                xmp_files[base_name] = os.path.join(folder_to_process, filename)

        processed_count = 0
        for base_name, arw_path in arw_files.items():
            if base_name in xmp_files:
                xmp_path = xmp_files[base_name]
                try:
                    tree = ET.parse(xmp_path)
                    root = tree.getroot()
                    # Trova l'elemento rdf:Description che contiene l'attributo xmp:Rating
                    rdf_description = root.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')

                    if rdf_description is not None:
                        rating_value = rdf_description.get('{http://ns.adobe.com/xap/1.0/}Rating')
                        subfolder_name = f"RATING_{rating_value}"
                        destination_folder = os.path.join(folder_to_process, subfolder_name)
                        os.makedirs(destination_folder, exist_ok=True)
                        shutil.move(arw_path, os.path.join(destination_folder, os.path.basename(arw_path)))
                        shutil.move(xmp_path, os.path.join(destination_folder, os.path.basename(xmp_path)))
                        processed_count += 1
                except FileNotFoundError:
                    messagebox.showerror("Errore", f"File XMP non trovato: {xmp_path}")
                except ET.ParseError:
                    messagebox.showerror("Errore", f"Errore durante la lettura del file XMP: {xmp_path}")

        message = f"Elaborazione completata. Spostati {processed_count} file ARW."
        messagebox.showinfo("Completato", message)
        self.master.destroy()

if __name__ == "__main__":
    initial_folder = None
    if len(sys.argv) > 1:
        initial_folder = sys.argv[1]

    root = tk.Tk()
    ui = ImageProcessorUI(root, initial_folder)
    root.mainloop()