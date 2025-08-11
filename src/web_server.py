#!/usr/bin/env python3
"""
HTTP Server for TileMapDownloader

This module launches a full-featured HTTP server to display downloaded map tiles.
It provides advanced caching, multithreading support, and custom API endpoints.

Usage:
    python src/web_server.py

URL:
    http://localhost:8080 (Main web interface)
"""

import sys
import os

# Add src to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Change to project root directory
project_root = os.path.dirname(current_dir)
os.chdir(project_root)

from services.http_server_service import HTTPServerService
from exceptions.tile_downloader_exceptions import ServerError


def main():
    """
    Main function to start the HTTP server.
    
    This function:
    1. Initializes the HTTPServerService
    2. Configures the multithreaded server
    3. Runs an HTTP server on port 8080
    4. Allows viewing downloaded map tiles via a web interface
    """
    try:
        # Initialize server service with correct base directory
        server_service = HTTPServerService(port=8080, base_directory=".")
        
        # Start the server
        server_service.start()
        
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()