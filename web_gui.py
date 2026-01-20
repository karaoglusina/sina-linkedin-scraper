#!/usr/bin/env python3
"""
LinkedIn Job Scraper - Web GUI Launcher

Launch the web-based GUI interface (works on all platforms).
"""

import argparse
from src.web_gui import launch_web_gui

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Launch LinkedIn Job Scraper Web GUI')
    parser.add_argument('--port', type=int, default=5001, 
                        help='Port to run the server on (default: 5001)')
    parser.add_argument('--host', default='127.0.0.1',
                        help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    
    args = parser.parse_args()
    launch_web_gui(host=args.host, port=args.port, debug=args.debug)
