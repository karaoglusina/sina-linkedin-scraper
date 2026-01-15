#!/usr/bin/env python3
"""
LinkedIn Job Scraper - Web-based GUI

A simple Flask-based web GUI that works across all platforms.
"""

from flask import Flask, render_template, request, jsonify, Response
from pathlib import Path
import json
import time
from threading import Thread, Lock
from queue import Queue
from typing import List, Dict

from .scraper import create_browser, navigate_to_job
from .parser import extract_job_data
from .output import save_as_json, save_as_markdown


app = Flask(__name__)

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


def scrape_jobs_thread(urls: List[str], json_dir: Path, md_dir: Path, create_markdown: bool, headless: bool):
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
    
    try:
        with create_browser(headless=headless) as browser:
            mode = "background" if headless else "visible"
            log_message(f"🌐 Browser launched ({mode})\n")
            
            for i, url in enumerate(urls, 1):
                with state_lock:
                    if not scraping_state['is_running']:
                        log_message("\n⏹️  Scraping stopped by user")
                        break
                    scraping_state['progress'] = i
                    scraping_state['current_job'] = url[:60]
                
                log_message(f"[{i}/{len(urls)}] Scraping: {url[:60]}...")
                
                try:
                    page = navigate_to_job(browser, url)
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
                    
                    # Small delay between jobs
                    if i < len(urls) and scraping_state['is_running']:
                        time.sleep(0.5)
                
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
    return render_template('index.html')


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
        args=(urls, json_dir, md_dir, create_markdown, headless),
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


def launch_web_gui(host='127.0.0.1', port=5000, debug=False):
    """Launch the web GUI."""
    print(f"\n🌐 LinkedIn Job Scraper Web GUI")
    print(f"   Open in browser: http://{host}:{port}")
    print(f"   Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    launch_web_gui()
