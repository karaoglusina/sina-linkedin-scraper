#!/usr/bin/env python3
"""
LinkedIn Job Scraper - Simple GUI

A simple tkinter-based GUI wrapper for the LinkedIn job scraper.
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
import threading
import sys
import time
from typing import List

from .scraper import create_browser
from .parser import extract_job_data
from .output import save_as_json, save_as_markdown


class ScraperGUI:
    """Simple GUI for LinkedIn Job Scraper."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("LinkedIn Job Scraper")
        self.root.geometry("900x700")
        
        # State
        self.is_scraping = False
        self.scraping_thread = None
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Create the GUI layout."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)  # Log area expands
        
        # --- URL Input Section ---
        url_frame = ttk.LabelFrame(main_frame, text="Job URLs", padding="10")
        url_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        url_frame.columnconfigure(0, weight=1)
        
        # URL text area
        ttk.Label(url_frame, text="Enter LinkedIn job URLs (one per line):").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )
        
        self.url_text = scrolledtext.ScrolledText(
            url_frame, height=8, wrap=tk.WORD, font=("Courier", 10)
        )
        self.url_text.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Buttons for URL management
        btn_frame = ttk.Frame(url_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W)
        
        ttk.Button(btn_frame, text="Load from File", command=self._load_urls_from_file).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(btn_frame, text="Clear", command=self._clear_urls).pack(side=tk.LEFT)
        
        # --- Settings Section ---
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        settings_frame.columnconfigure(1, weight=1)
        
        # JSON output directory
        ttk.Label(settings_frame, text="JSON Output:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.json_dir_var = tk.StringVar(value="./output")
        json_entry = ttk.Entry(settings_frame, textvariable=self.json_dir_var)
        json_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(settings_frame, text="Browse", command=self._browse_json_dir).grid(
            row=0, column=2
        )
        
        # Markdown checkbox
        self.markdown_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Create Markdown files", variable=self.markdown_var,
            command=self._toggle_markdown
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Headless mode checkbox
        self.headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Run browser in background (headless mode)", 
            variable=self.headless_var
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Markdown output directory  
        ttk.Label(settings_frame, text="Markdown Output:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.md_dir_var = tk.StringVar(value="./output")
        self.md_entry = ttk.Entry(settings_frame, textvariable=self.md_dir_var)
        self.md_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.md_browse_btn = ttk.Button(
            settings_frame, text="Browse", command=self._browse_md_dir
        )
        self.md_browse_btn.grid(row=2, column=2)
        
        # --- Log Section ---
        log_frame = ttk.LabelFrame(main_frame, text="Progress Log", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # --- Control Buttons ---
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
        self.start_btn = ttk.Button(
            control_frame, text="Start Scraping", command=self._start_scraping
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(
            control_frame, text="Stop", command=self._stop_scraping, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT)
        
        ttk.Button(control_frame, text="Clear Log", command=self._clear_log).pack(
            side=tk.RIGHT
        )
    
    def _toggle_markdown(self):
        """Enable/disable markdown directory selection."""
        if self.markdown_var.get():
            self.md_entry.config(state=tk.NORMAL)
            self.md_browse_btn.config(state=tk.NORMAL)
        else:
            self.md_entry.config(state=tk.DISABLED)
            self.md_browse_btn.config(state=tk.DISABLED)
    
    def _browse_json_dir(self):
        """Browse for JSON output directory."""
        directory = filedialog.askdirectory(
            title="Select JSON Output Directory",
            initialdir=self.json_dir_var.get()
        )
        if directory:
            self.json_dir_var.set(directory)
    
    def _browse_md_dir(self):
        """Browse for Markdown output directory."""
        directory = filedialog.askdirectory(
            title="Select Markdown Output Directory",
            initialdir=self.md_dir_var.get()
        )
        if directory:
            self.md_dir_var.set(directory)
    
    def _load_urls_from_file(self):
        """Load URLs from a text file."""
        file_path = filedialog.askopenfilename(
            title="Select URL File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.url_text.insert(tk.END, content)
                self._log(f"Loaded URLs from: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")
    
    def _clear_urls(self):
        """Clear the URL text area."""
        self.url_text.delete(1.0, tk.END)
    
    def _clear_log(self):
        """Clear the log text area."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _log(self, message: str):
        """Add a message to the log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def _get_urls(self) -> List[str]:
        """Extract and validate URLs from the text area."""
        content = self.url_text.get(1.0, tk.END)
        urls = []
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Validate URL
            if self._is_valid_linkedin_url(line):
                urls.append(line)
            else:
                self._log(f"⚠️  Skipping invalid URL: {line[:50]}...")
        
        return urls
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validate that the URL is a LinkedIn job posting."""
        url_lower = url.lower()
        return "linkedin.com" in url_lower and "/jobs/view/" in url_lower
    
    def _start_scraping(self):
        """Start the scraping process in a separate thread."""
        urls = self._get_urls()
        
        if not urls:
            messagebox.showwarning("No URLs", "Please enter at least one valid LinkedIn job URL")
            return
        
        # Disable start button, enable stop button
        self.is_scraping = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Start scraping in a thread
        self.scraping_thread = threading.Thread(
            target=self._scrape_jobs, args=(urls,), daemon=True
        )
        self.scraping_thread.start()
    
    def _stop_scraping(self):
        """Stop the scraping process."""
        self.is_scraping = False
        self._log("⏹️  Stopping scraping...")
        self.stop_btn.config(state=tk.DISABLED)
    
    def _scrape_jobs(self, urls: List[str]):
        """Scrape jobs (runs in separate thread)."""
        json_dir = Path(self.json_dir_var.get())
        md_dir = Path(self.md_dir_var.get())
        create_markdown = self.markdown_var.get()
        headless = self.headless_var.get()
        
        successful = 0
        failed = 0
        failed_urls = []
        
        self._log(f"📋 Starting scrape of {len(urls)} jobs\n")
        
        try:
            # Create browser (reuse for all jobs)
            with create_browser(headless=headless) as browser:
                mode = "background" if headless else "visible"
                self._log(f"🌐 Browser launched ({mode})\n")
                
                for i, url in enumerate(urls, 1):
                    if not self.is_scraping:
                        self._log("\n⏹️  Scraping stopped by user")
                        break
                    
                    self._log(f"[{i}/{len(urls)}] Scraping: {url[:60]}...")
                    
                    try:
                        # Import here to avoid circular imports
                        from .scraper import navigate_to_job
                        
                        page = navigate_to_job(browser, url)
                        job_data = extract_job_data(page, url)
                        page.close()
                        
                        # Save JSON
                        save_as_json(job_data, json_dir)
                        
                        # Save Markdown if enabled
                        if create_markdown:
                            save_as_markdown(job_data, md_dir)
                        
                        self._log(f"  ✅ {job_data.title} at {job_data.company_name}")
                        successful += 1
                        
                        # Small delay between jobs
                        if i < len(urls) and self.is_scraping:
                            time.sleep(0.5)
                    
                    except Exception as e:
                        self._log(f"  ❌ Failed: {e}")
                        failed += 1
                        failed_urls.append(url)
        
        except Exception as e:
            self._log(f"\n❌ Fatal error: {e}")
        
        # Print summary
        self._log(f"\n{'='*50}")
        self._log(f"📊 Scraping complete!")
        self._log(f"   ✅ Successful: {successful}")
        self._log(f"   ❌ Failed: {failed}")
        
        if failed_urls:
            self._log(f"\n   Failed URLs:")
            for url in failed_urls:
                self._log(f"   - {url}")
        
        # Re-enable start button
        self.is_scraping = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)


def launch_gui():
    """Launch the GUI application."""
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
