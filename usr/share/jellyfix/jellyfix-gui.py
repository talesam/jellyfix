#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# jellyfix-gui.py - Entry point for Jellyfix GUI
#

"""
Jellyfix GUI - Graphical Interface for Jellyfin Library Organizer

Modern GTK4+libadwaita interface for managing your Jellyfin media library.
"""

import sys
import gi
from pathlib import Path

# Check GTK version requirements
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

# Add parent directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from jellyfix.utils.config import Config, set_config, APP_VERSION
from jellyfix.utils.logger import Logger, set_logger
from jellyfix.gui import JellyfixApplication


def main():
    """Main entry point for GUI"""
    # Create default configuration for GUI mode
    # Don't specify boolean options here - let them load from saved config
    config = Config(
        work_dir=Path.cwd(),  # Start with current directory, will be changed via GUI
        dry_run=False,  # Execute operations for real when Apply is clicked
        interactive=False,  # GUI handles interaction via SearchDialog, not CLI prompts
        verbose=False,
        quiet=False,
        log_file=None,
        auto_confirm=False
    )
    # Note: Other settings (rename_por2, remove_non_media, etc.) will be loaded
    # from ~/.jellyfix/config.json automatically by Config.__post_init__

    # Set global config
    set_config(config)

    # Initialize logger
    logger = Logger(
        log_file=config.log_file,
        verbose=config.verbose,
        quiet=config.quiet
    )
    set_logger(logger)

    logger.info(f"Starting Jellyfix GUI v{APP_VERSION}")

    # Create and run GTK application
    try:
        app = JellyfixApplication()
        return app.run(sys.argv)
    except Exception as e:
        logger.error(f"Failed to start GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
