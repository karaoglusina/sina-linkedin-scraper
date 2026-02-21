#!/usr/bin/env python3
"""
LinkedIn Job Scraper - Web-based GUI

A simple Flask-based web GUI that works across all platforms.
"""

from flask import Flask, render_template, request, jsonify, Response
from pathlib import Path
import json
import time
import random
import os
from threading import Thread, Lock
from queue import Queue
from typing import List, Dict

from .scraper import (
    create_browser, create_browser_persistent, setup_scraper_profile,
    navigate_to_job, DEFAULT_PROFILE_DIR,
)
from .parser import extract_job_data
from .output import save_as_json, save_as_markdown


# Get the directory where this file is located
current_dir = Path(__file__).parent

# Initialize Flask with explicit template folder
app = Flask(__name__, 
            template_folder=str(current_dir / 'templates'),
            static_folder=str(current_dir / 'static'))

# Global state for profile setup
_setup_running = False
_setup_lock = Lock()

# Global state
scraping_state = {
    'is_running': False,
    'progress': 0,
    'total': 0,
    'current_job': '',
    'logs': [],
    'successful': 0,
    'failed': 0,
    'failed_urls': []
}
state_lock = Lock()
log_queue = Queue()


def log_message(message: str):
    """Add a log message to the queue."""
    with state_lock:
        scraping_state['logs'].append(message)
    log_queue.put(message)


def is_valid_linkedin_url(url: str) -> bool:
    """Validate that the URL is a LinkedIn job posting."""
    url_lower = url.lower()
    return "linkedin.com" in url_lower and "/jobs/view/" in url_lower


def scrape_jobs_thread(
    urls: List[str],
    json_dir: Path,
    md_dir: Path,
    create_markdown: bool,
    headless: bool,
    use_profile: bool = False,
    profile_path: str = "",
):
    """Background thread for scraping jobs."""
    global scraping_state
    
    with state_lock:
        scraping_state['is_running'] = True
        scraping_state['progress'] = 0
        scraping_state['total'] = len(urls)
        scraping_state['successful'] = 0
        scraping_state['failed'] = 0
        scraping_state['failed_urls'] = []
    
    log_message(f"📋 Starting scrape of {len(urls)} jobs\n")

    # Choose the right browser context
    if use_profile:
        resolved_path = profile_path or DEFAULT_PROFILE_DIR
        browser_ctx = create_browser_persistent(profile_dir=resolved_path)
        log_message(f"👤 Using saved profile: {resolved_path}\n")
    else:
        browser_ctx = create_browser(headless=headless)
        mode = "background" if headless else "visible"
        log_message(f"🌐 Browser launched ({mode})\n")

    try:
        log_message("🔄 Launching browser, please wait...")
        with browser_ctx as browser:
            log_message("✅ Browser ready!\n")
            for i, url in enumerate(urls, 1):
                with state_lock:
                    if not scraping_state['is_running']:
                        log_message("\n⏹️  Scraping stopped by user")
                        break
                    scraping_state['progress'] = i
                    scraping_state['current_job'] = url[:60]
                
                log_message(f"[{i}/{len(urls)}] Scraping: {url[:60]}...")
                
                try:
                    log_message("  🌍 Navigating to page...")
                    page = navigate_to_job(browser, url)
                    log_message("  📄 Page loaded, extracting data...")
                    job_data = extract_job_data(page, url)
                    page.close()
                    
                    # Save JSON
                    save_as_json(job_data, json_dir)
                    
                    # Save Markdown if enabled
                    if create_markdown:
                        save_as_markdown(job_data, md_dir)
                    
                    log_message(f"  ✅ {job_data.title} at {job_data.company_name}")
                    
                    with state_lock:
                        scraping_state['successful'] += 1
                    
                    # Random delay between jobs to avoid bot detection
                    if i < len(urls) and scraping_state['is_running']:
                        delay = round(random.uniform(2.0, 5.0), 1)
                        log_message(f"  ⏳ Waiting {delay}s before next job...")
                        time.sleep(delay)
                
                except Exception as e:
                    log_message(f"  ❌ Failed: {e}")
                    with state_lock:
                        scraping_state['failed'] += 1
                        scraping_state['failed_urls'].append(url)
    
    except Exception as e:
        log_message(f"\n❌ Fatal error: {e}")
    
    # Print summary
    log_message(f"\n{'='*50}")
    log_message(f"📊 Scraping complete!")
    log_message(f"   ✅ Successful: {scraping_state['successful']}")
    log_message(f"   ❌ Failed: {scraping_state['failed']}")
    
    if scraping_state['failed_urls']:
        log_message(f"\n   Failed URLs:")
        for url in scraping_state['failed_urls']:
            log_message(f"   - {url}")
    
    with state_lock:
        scraping_state['is_running'] = False
        scraping_state['current_job'] = ''


@app.route('/')
def index():
    """Serve the main page."""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <h1>Template Error</h1>
        <p>Error loading template: {e}</p>
        <p>Template folder: {app.template_folder}</p>
        <p>Current dir: {os.getcwd()}</p>
        """, 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'template_folder': app.template_folder,
        'templates_exist': os.path.exists(app.template_folder)
    })


@app.route('/api/start', methods=['POST'])
def start_scraping():
    """Start scraping jobs."""
    global scraping_state
    
    with state_lock:
        if scraping_state['is_running']:
            return jsonify({'error': 'Scraping already in progress'}), 400
    
    data = request.json
    urls_text = data.get('urls', '')
    json_dir = Path(data.get('json_dir', './output'))
    md_dir = Path(data.get('md_dir', './output'))
    create_markdown = data.get('create_markdown', True)
    headless = data.get('headless', True)
    use_profile = data.get('use_profile', False)
    profile_path = data.get('profile_path', '')
    
    # Parse and validate URLs
    urls = []
    for line in urls_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if is_valid_linkedin_url(line):
            urls.append(line)
        else:
            log_message(f"⚠️  Skipping invalid URL: {line[:50]}...")
    
    if not urls:
        return jsonify({'error': 'No valid URLs provided'}), 400
    
    # Clear logs
    with state_lock:
        scraping_state['logs'] = []
    
    # Start scraping thread
    thread = Thread(
        target=scrape_jobs_thread,
        args=(urls, json_dir, md_dir, create_markdown, headless, use_profile, profile_path),
        daemon=True
    )
    thread.start()
    
    return jsonify({'success': True, 'total': len(urls)})


@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Stop scraping jobs."""
    with state_lock:
        if not scraping_state['is_running']:
            return jsonify({'error': 'No scraping in progress'}), 400
        scraping_state['is_running'] = False
    
    log_message("⏹️  Stopping scraping...")
    return jsonify({'success': True})


@app.route('/api/status')
def get_status():
    """Get current scraping status."""
    with state_lock:
        return jsonify(scraping_state.copy())


@app.route('/api/logs/stream')
def stream_logs():
    """Stream logs using Server-Sent Events."""
    def generate():
        # First, send existing logs
        with state_lock:
            for log in scraping_state['logs']:
                yield f"data: {json.dumps({'message': log})}\n\n"
        
        # Then stream new logs
        while True:
            try:
                message = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'message': message})}\n\n"
            except:
                # Send keepalive
                yield f"data: {json.dumps({'keepalive': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    """Clear the logs."""
    with state_lock:
        scraping_state['logs'] = []
    return jsonify({'success': True})


@app.route('/api/setup-profile', methods=['POST'])
def start_profile_setup():
    """
    Open a visible Playwright browser so the user can log into LinkedIn.
    The session is saved to the profile directory and reused for scraping.
    """
    global _setup_running

    with _setup_lock:
        if _setup_running:
            return jsonify({'error': 'Profile setup already in progress'}), 400
        _setup_running = True

    data = request.json or {}
    profile_dir = data.get('profile_dir', DEFAULT_PROFILE_DIR)

    def run_setup():
        global _setup_running
        try:
            with setup_scraper_profile(profile_dir=profile_dir) as context:
                # Wait until the user closes the browser window.
                # When the window is closed the context becomes disconnected and
                # context.pages raises an exception — that's our exit signal.
                try:
                    while context.pages:
                        time.sleep(0.5)
                except Exception:
                    pass  # Browser was closed by the user — normal exit
        except Exception as e:
            print(f"Profile setup error: {e}")
        finally:
            with _setup_lock:
                _setup_running = False

    thread = Thread(target=run_setup, daemon=True)
    thread.start()
    return jsonify({'success': True, 'profile_dir': profile_dir})


@app.route('/api/setup-profile/status')
def setup_profile_status():
    """Check whether the profile setup browser is currently open."""
    return jsonify({'is_running': _setup_running})


def launch_web_gui(host='127.0.0.1', port=5001, debug=False):
    """Launch the web GUI."""
    import socket
    
    # Check if port is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    sock.close()
    
    if result == 0:
        print(f"⚠️  Port {port} is already in use. Trying port {port + 1}...")
        port = port + 1
    
    print(f"\n🌐 LinkedIn Job Scraper Web GUI")
    print(f"   Open in browser: http://{host}:{port}")
    print(f"   Press Ctrl+C to stop\n")
    
    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n❌ Error: Port {port} is already in use.")
            print(f"   Try running with a different port:")
            print(f"   python web_gui.py --port {port + 1}\n")
        else:
            raise


if __name__ == '__main__':
    launch_web_gui()
