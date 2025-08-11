#!/usr/bin/env python3
"""
Tile Map Downloader - Main Entry Point
A clean, SOLID-compliant implementation for downloading map tiles
"""

import sys
import os
import logging

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.tile_download_manager import TileDownloadManager
from exceptions.tile_downloader_exceptions import TileDownloaderException
from infrastructure.logging import LoggingManager


def main():
    """Main entry point for the tile downloader application"""
    try:
        # Setup logging (defaults)
        LoggingManager.setup_logging({})
        logger = logging.getLogger(__name__)
        
        logger.info("Starting TileMapDownloader")
        
        # Create and run the download manager
        manager = TileDownloadManager()
        manager.run_from_command_line()
        
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
        sys.exit(1)
    except TileDownloaderException as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Please check your configuration and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main() 