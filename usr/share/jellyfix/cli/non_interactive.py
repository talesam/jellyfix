#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cli/non_interactive.py - Non-interactive CLI mode
#

"""
Non-interactive (scriptable) CLI mode.

This mode is designed for automation and scripts. It reads
configuration from command-line flags and executes without
user interaction.

Usage:
    jellyfix -w /path/to/library --execute --yes
"""

from pathlib import Path

from ..core.scanner import LibraryScanner
from ..core.renamer import Renamer
from ..utils.logger import get_logger
from ..utils.i18n import _


class NonInteractiveCLI:
    """Non-interactive CLI handler"""
    
    def __init__(self, config):
        """
        Initialize non-interactive CLI.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = get_logger()
    
    def run(self):
        """Run non-interactive mode"""
        
        # Validate working directory
        if not self.config.work_dir:
            self.logger.error(_("Error: No working directory specified"))
            self.logger.info(_("Use: --workdir /path/to/directory"))
            return 1

        workdir = Path(self.config.work_dir)
        if not workdir.exists() or not workdir.is_dir():
            self.logger.error(_("Error: Directory does not exist: %s") % workdir)
            return 1
        
        # Show banner
        if not self.config.quiet:
            self._show_banner()
        
        # Scan library
        self.logger.info(_("Scanning: %s") % workdir)
        scanner = LibraryScanner()
        scan_result = scanner.scan(workdir)
        
        # Show scan results
        self.logger.info(
            _("Found: %d videos, %d subtitles") % 
            (len(scan_result.video_files), len(scan_result.subtitle_files))
        )
        
        # Plan operations
        self.logger.info(_("Planning operations..."))
        renamer = Renamer()
        renamer.plan_operations(workdir, scan_result)
        
        operations_count = len(renamer.operations)
        self.logger.info(_("%d operations planned") % operations_count)
        
        if operations_count == 0:
            self.logger.info(_("Nothing to do"))
            return 0

        # Show operations preview
        if not self.config.quiet:
            self._show_operations_preview(renamer.operations)
        
        # Determine if should execute
        if self.config.dry_run:
            self.logger.warning(_("DRY-RUN mode: No changes will be made"))
            self.logger.info(_("Use --execute to apply changes"))
            return 0

        # Execute operations
        self.logger.info(_("Executing %d operations...") % operations_count)
        stats = renamer.execute_operations(dry_run=False)
        
        # Show results
        self.logger.info("")
        self.logger.info(_("Execution completed:"))
        if stats['renamed'] > 0:
            self.logger.info(_("  Renamed: %d") % stats['renamed'])
        if stats['moved'] > 0:
            self.logger.info(_("  Moved: %d") % stats['moved'])
        if stats['deleted'] > 0:
            self.logger.info(_("  Deleted: %d") % stats['deleted'])
        if stats['cleaned'] > 0:
            self.logger.info(_("  Cleaned folders: %d") % stats['cleaned'])
        if stats['failed'] > 0:
            self.logger.warning(_("  Failed: %d") % stats['failed'])
        if stats['skipped'] > 0:
            self.logger.warning(_("  Skipped: %d") % stats['skipped'])
        
        return 0

    def _show_operations_preview(self, operations):
        """Show compact operations preview with color-coded operation types"""
        from rich.console import Console
        from rich.text import Text

        console = Console()

        console.print()
        console.print(_("Operations:"), style="bold cyan")
        console.print()

        # Color scheme per operation type
        OP_STYLES = {
            "delete": ("bold red", "🗑️  DELETE"),
            "move_rename": ("bold yellow", "📦✏️  MOVE+RENAME"),
            "move": ("bold blue", "📦 MOVE"),
            "rename": ("bold green", "✏️  RENAME"),
        }

        for i, op in enumerate(operations, 1):
            style, label = OP_STYLES.get(op.operation_type, ("white", op.operation_type.upper()))

            if op.operation_type == 'delete':
                num = Text(f"  {i:>3}. ", style="bold white")
                tag = Text(f"[{label}] ", style=style)
                name = Text(str(op.source.name), style="red")
                console.print(num + tag + name)
            else:
                num = Text(f"  {i:>3}. ", style="bold white")
                tag = Text(f"[{label}]", style=style)
                console.print(num + tag)
                console.print(f"        {op.source.name}", style="dim")
                if op.destination:
                    console.print(f"        → {op.destination.name}", style="green")

        console.print()
    
    def _show_banner(self):
        """Show application banner"""
        
        banner = f"""
{'='*60}
       JELLYFIX - Jellyfin Library Organizer       
{'='*60}
"""
        print(banner)
