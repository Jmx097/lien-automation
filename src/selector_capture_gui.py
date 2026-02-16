#!/usr/bin/env python3
"""
Selector Capture Tool - Desktop GUI Version
A simple tkinter application for capturing CSS selectors from county recorder sites
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import sys
import subprocess
import threading
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class SelectorCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Federal Tax Lien - Selector Capture Tool")
        self.root.geometry("800x900")
        self.root.configure(bg='#f0f0f0')
        
        # Sites configuration
        self.sites = {
            "11": {
                "name": "AZ - Maricopa County",
                "url": "https://recorder.maricopa.gov/recording/document-search.html",
                "state": "AZ",
                "county": "Maricopa"
            },
            "13": {
                "name": "TX - Dallas County",
                "url": "https://dallas.tx.publicsearch.us/",
                "state": "TX",
                "county": "Dallas"
            },
            "15": {
                "name": "FL - Miami-Dade County",
                "url": "https://onlineservices.miamidadeclerk.gov/officialrecords",
                "state": "FL",
                "county": "Miami-Dade"
            }
        }
        
        self.current_site_id = None
        self.browser_process = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg='#2c3e50', height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        title = tk.Label(header, text="Federal Tax Lien Automation", 
                        font=('Arial', 16, 'bold'), fg='white', bg='#2c3e50')
        title.pack(pady=15)
        
        subtitle = tk.Label(header, text="CSS Selector Capture Tool", 
                           font=('Arial', 10), fg='#bdc3c7', bg='#2c3e50')
        subtitle.pack()
        
        # Main container
        main = tk.Frame(self.root, bg='#f0f0f0')
        main.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Site Selection
        site_frame = tk.LabelFrame(main, text="Step 1: Select Site", 
                                   font=('Arial', 11, 'bold'), bg='#f0f0f0')
        site_frame.pack(fill='x', pady=(0, 15))
        
        self.site_var = tk.StringVar(value="")
        for site_id, site_info in self.sites.items():
            rb = tk.Radiobutton(site_frame, text=site_info['name'], 
                               variable=self.site_var, value=site_id,
                               font=('Arial', 10), bg='#f0f0f0',
                               command=self.on_site_selected)
            rb.pack(anchor='w', padx=10, pady=2)
        
        # Browser Control
        browser_frame = tk.LabelFrame(main, text="Step 2: Open Browser", 
                                      font=('Arial', 11, 'bold'), bg='#f0f0f0')
        browser_frame.pack(fill='x', pady=(0, 15))
        
        self.open_browser_btn = tk.Button(browser_frame, text="🌐 Open Site in Browser",
                                          command=self.open_browser,
                                          font=('Arial', 11), bg='#3498db', fg='white',
                                          width=25, height=2, state='disabled')
        self.open_browser_btn.pack(pady=10)
        
        self.site_url_label = tk.Label(browser_frame, text="Select a site first",
                                       font=('Arial', 9), fg='#7f8c8d', bg='#f0f0f0')
        self.site_url_label.pack()
        
        # Instructions
        inst_frame = tk.LabelFrame(main, text="How to Find Selectors", 
                                   font=('Arial', 11, 'bold'), bg='#f0f0f0')
        inst_frame.pack(fill='x', pady=(0, 15))
        
        instructions = """1. Open Chrome DevTools (F12)
2. Click the picker tool (🔍) in top-left
3. Click the element you want to capture
4. Right-click the highlighted element in DevTools
5. Copy → Copy selector
6. Paste it in the field below"""
        
        inst_text = tk.Label(inst_frame, text=instructions, 
                            font=('Courier', 9), bg='#f0f0f0', justify='left')
        inst_text.pack(anchor='w', padx=10, pady=5)
        
        # Search Form Selectors
        search_frame = tk.LabelFrame(main, text="Search Form Selectors", 
                                     font=('Arial', 11, 'bold'), bg='#f0f0f0')
        search_frame.pack(fill='x', pady=(0, 10))
        
        self.search_fields = {}
        search_fields_config = [
            ("document_type_dropdown", "Document Type Dropdown:", 
             "Select 'Federal Tax Lien'"),
            ("date_from_input", "Date 'From' Input:", 
             "Start date field"),
            ("date_to_input", "Date 'To' Input:", 
             "End date field"),
            ("search_button", "Search Button:", 
             "Submit search")
        ]
        
        for field_id, label, placeholder in search_fields_config:
            row = tk.Frame(search_frame, bg='#f0f0f0')
            row.pack(fill='x', padx=10, pady=3)
            
            lbl = tk.Label(row, text=label, font=('Arial', 9), 
                          width=22, anchor='w', bg='#f0f0f0')
            lbl.pack(side='left')
            
            entry = tk.Entry(row, font=('Arial', 9), width=50)
            entry.pack(side='left', fill='x', expand=True, padx=(5, 0))
            entry.insert(0, placeholder)
            entry.bind('<FocusIn>', lambda e, ent=entry: self.on_entry_focus(e, ent))
            self.search_fields[field_id] = entry
        
        # Results Table Selectors
        results_frame = tk.LabelFrame(main, text="Results Table Selectors (Search First!)", 
                                      font=('Arial', 11, 'bold'), bg='#f0f0f0')
        results_frame.pack(fill='x', pady=(0, 10))
        
        self.results_fields = {}
        results_fields_config = [
            ("table_container", "Table Container:", 
             "Wrapper around results"),
            ("rows", "Row Selector:", 
             "e.g., 'tbody tr' or '.result-row'"),
            ("date_column", "Date Column:", 
             "e.g., 'td:nth-child(1)'"),
            ("document_link", "Document Link:", 
             "Link to view document"),
            ("next_page_button", "Next Page Button:", 
             "Optional - leave blank if none")
        ]
        
        for field_id, label, placeholder in results_fields_config:
            row = tk.Frame(results_frame, bg='#f0f0f0')
            row.pack(fill='x', padx=10, pady=3)
            
            lbl = tk.Label(row, text=label, font=('Arial', 9), 
                          width=22, anchor='w', bg='#f0f0f0')
            lbl.pack(side='left')
            
            entry = tk.Entry(row, font=('Arial', 9), width=50)
            entry.pack(side='left', fill='x', expand=True, padx=(5, 0))
            entry.insert(0, placeholder)
            entry.bind('<FocusIn>', lambda e, ent=entry: self.on_entry_focus(e, ent))
            self.results_fields[field_id] = entry
        
        # Document Page Selectors
        doc_frame = tk.LabelFrame(main, text="Document Page Selectors (Open a Doc First!)", 
                                  font=('Arial', 11, 'bold'), bg='#f0f0f0')
        doc_frame.pack(fill='x', pady=(0, 15))
        
        self.doc_fields = {}
        doc_fields_config = [
            ("pdf_download_link", "PDF Download Link:", 
             "Download button/link"),
            ("document_details", "Document Details:", 
             "Info container"),
            ("recorder_stamp", "Recorder Stamp Date:", 
             "Optional - recorded date on doc")
        ]
        
        for field_id, label, placeholder in doc_fields_config:
            row = tk.Frame(doc_frame, bg='#f0f0f0')
            row.pack(fill='x', padx=10, pady=3)
            
            lbl = tk.Label(row, text=label, font=('Arial', 9), 
                          width=22, anchor='w', bg='#f0f0f0')
            lbl.pack(side='left')
            
            entry = tk.Entry(row, font=('Arial', 9), width=50)
            entry.pack(side='left', fill='x', expand=True, padx=(5, 0))
            entry.insert(0, placeholder)
            entry.bind('<FocusIn>', lambda e, ent=entry: self.on_entry_focus(e, ent))
            self.doc_fields[field_id] = entry
        
        # Action Buttons
        btn_frame = tk.Frame(main, bg='#f0f0f0')
        btn_frame.pack(fill='x')
        
        self.save_btn = tk.Button(btn_frame, text="💾 Save Selectors",
                                  command=self.save_selectors,
                                  font=('Arial', 12, 'bold'), bg='#27ae60', fg='white',
                                  width=20, height=2)
        self.save_btn.pack(side='left', padx=(0, 10))
        
        self.clear_btn = tk.Button(btn_frame, text="🔄 Clear All",
                                   command=self.clear_all,
                                   font=('Arial', 11), bg='#95a5a6', fg='white',
                                   width=15, height=2)
        self.clear_btn.pack(side='left', padx=(0, 10))
        
        self.load_btn = tk.Button(btn_frame, text="📂 Load Existing",
                                  command=self.load_existing,
                                  font=('Arial', 11), bg='#9b59b6', fg='white',
                                  width=15, height=2)
        self.load_btn.pack(side='left')
        
        # Status Bar
        self.status_var = tk.StringVar(value="Ready - Select a site to begin")
        status = tk.Label(self.root, textvariable=self.status_var, 
                         font=('Arial', 9), bg='#34495e', fg='white',
                         anchor='w', padx=10)
        status.pack(fill='x', side='bottom')
        
    def on_entry_focus(self, event, entry):
        """Clear placeholder on focus"""
        if entry.get() in ["Select a site first", "Document Type Dropdown:", 
                          "Date 'From' Input:", "Date 'To' Input:",
                          "Search Button:", "Wrapper around results",
                          "e.g., 'tbody tr'", "e.g., 'td:nth-child(1)'",
                          "Link to view document", "Optional - leave blank",
                          "Download button/link", "Info container",
                          "Optional - recorded date"]:
            entry.delete(0, 'end')
    
    def on_site_selected(self):
        """Handle site selection"""
        site_id = self.site_var.get()
        if site_id:
            site = self.sites[site_id]
            self.current_site_id = site_id
            self.open_browser_btn.config(state='normal')
            self.site_url_label.config(text=f"URL: {site['url']}")
            self.status_var.set(f"Selected: {site['name']} - Click 'Open Browser' to start")
    
    def open_browser(self):
        """Open browser to selected site"""
        if not self.current_site_id:
            messagebox.showwarning("No Site Selected", "Please select a site first")
            return
        
        if not PLAYWRIGHT_AVAILABLE:
            messagebox.showerror("Playwright Not Installed", 
                                "Run: pip install playwright && playwright install")
            return
        
        site = self.sites[self.current_site_id]
        
        def launch_browser():
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    page = browser.new_page(viewport={"width": 1400, "height": 900})
                    page.goto(site['url'])
                    self.status_var.set(f"Browser opened for {site['name']} - Perform search, then fill in selectors")
                    # Keep browser open until user closes it
                    page.wait_for_timeout(1000)  # Give it a moment
            except Exception as e:
                self.status_var.set(f"Error opening browser: {str(e)}")
        
        # Launch browser in separate thread so UI doesn't freeze
        thread = threading.Thread(target=launch_browser)
        thread.daemon = True
        thread.start()
        
        self.status_var.set(f"Opening {site['name']}...")
    
    def get_field_values(self):
        """Get all field values"""
        return {
            "search_form": {k: v.get() for k, v in self.search_fields.items()},
            "results_table": {k: v.get() for k, v in self.results_fields.items()},
            "document_page": {k: v.get() for k, v in self.doc_fields.items()}
        }
    
    def save_selectors(self):
        """Save selectors to JSON file"""
        if not self.current_site_id:
            messagebox.showwarning("No Site Selected", "Please select a site first")
            return
        
        site = self.sites[self.current_site_id]
        selectors = self.get_field_values()
        
        # Check if any fields are empty/placeholders
        empty_fields = []
        for section, fields in selectors.items():
            for field, value in fields.items():
                if not value or value in ["", "Select a site first"]:
                    if field != "next_page_button" and field != "recorder_stamp":
                        empty_fields.append(f"{section}.{field}")
        
        if empty_fields:
            result = messagebox.askyesno("Empty Fields Detected", 
                f"The following fields are empty:\n\n" + 
                "\n".join(empty_fields[:5]) + 
                ("\n...and more" if len(empty_fields) > 5 else "") +
                "\n\nSave anyway?")
            if not result:
                return
        
        # Load existing data if present
        output_file = Path("captured_selectors.json")
        data = {}
        if output_file.exists():
            with open(output_file) as f:
                data = json.load(f)
        
        # Add/update current site
        data[self.current_site_id] = {
            "name": site['name'],
            "url": site['url'],
            "state": site['state'],
            "county": site['county'],
            "selectors": selectors
        }
        
        # Save
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.status_var.set(f"✅ Saved selectors for {site['name']}")
        messagebox.showinfo("Success", 
                           f"Selectors saved for {site['name']}!\n\n"
                           f"File: {output_file.absolute()}\n\n"
                           f"Upload this file to OpenClaw when done with all sites.")
    
    def clear_all(self):
        """Clear all input fields"""
        for entry in self.search_fields.values():
            entry.delete(0, 'end')
        for entry in self.results_fields.values():
            entry.delete(0, 'end')
        for entry in self.doc_fields.values():
            entry.delete(0, 'end')
        self.status_var.set("All fields cleared")
    
    def load_existing(self):
        """Load existing selectors from file"""
        output_file = Path("captured_selectors.json")
        if not output_file.exists():
            messagebox.showinfo("No File Found", 
                               "No existing selectors file found. Start fresh!")
            return
        
        try:
            with open(output_file) as f:
                data = json.load(f)
            
            if not self.current_site_id:
                messagebox.showwarning("No Site Selected", 
                                      "Select a site first, then load")
                return
            
            if self.current_site_id not in data:
                messagebox.showinfo("No Data", 
                                   f"No saved selectors for site {self.current_site_id}")
                return
            
            site_data = data[self.current_site_id]
            selectors = site_data.get("selectors", {})
            
            # Populate fields
            for field_id, value in selectors.get("search_form", {}).items():
                if field_id in self.search_fields:
                    self.search_fields[field_id].delete(0, 'end')
                    self.search_fields[field_id].insert(0, value)
            
            for field_id, value in selectors.get("results_table", {}).items():
                if field_id in self.results_fields:
                    self.results_fields[field_id].delete(0, 'end')
                    self.results_fields[field_id].insert(0, value)
            
            for field_id, value in selectors.get("document_page", {}).items():
                if field_id in self.doc_fields:
                    self.doc_fields[field_id].delete(0, 'end')
                    self.doc_fields[field_id].insert(0, value)
            
            self.status_var.set(f"✅ Loaded existing selectors for {site_data['name']}")
            messagebox.showinfo("Success", f"Loaded selectors for {site_data['name']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {str(e)}")


def main():
    root = tk.Tk()
    app = SelectorCaptureApp(root)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()
