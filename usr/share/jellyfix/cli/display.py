#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cli/display.py - Rich-based display formatting for CLI
#

"""
Display utilities for CLI using Rich library.

This module provides functions to format and display information
in the terminal using the Rich library for beautiful output.
"""

from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..core.scanner import ScanResult
from ..core.renamer import Renamer, RenameOperation
from ..utils.i18n import _


# Initialize console
console = Console()


def show_banner(version: str = "1.0.0"):
    """
    Display application banner.
    
    Args:
        version: Application version
    """
    console.clear()
    banner = Text()
    banner.append("\n╔══════════════════════════════════════════════════════════╗\n", style="bold blue")
    banner.append("║                                                          ║\n", style="bold blue")
    banner.append("║          ", style="bold blue")
    banner.append("         🎬  JELLYFIX  🎬", style="bold magenta")
    banner.append("                       ║\n", style="bold blue")
    banner.append("║                                                          ║\n", style="bold blue")
    banner.append("║     ", style="bold blue")
    banner.append("Intelligent Jellyfin Library Organizer", style="cyan")
    banner.append("           ║\n", style="bold blue")
    banner.append("║                                                          ║\n", style="bold blue")
    banner.append("╚══════════════════════════════════════════════════════════╝\n", style="bold blue")
    console.print(banner)


def show_scan_results(result: ScanResult):
    """
    Display library scan results.

    Args:
        result: ScanResult object with scan data
    """
    console.clear()
    console.print("\n")
    console.print(Panel.fit(
        "📊 " + _("Scan Results"),
        style="bold green",
        border_style="green"
    ))

    # Main statistics table with tree-like structure
    stats_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    stats_table.add_column(_("Category"), style="cyan")
    stats_table.add_column(_("Count"), justify="right", style="magenta")

    # Video files
    stats_table.add_row("📹 " + _("Video files"), str(len(result.video_files)))
    stats_table.add_row("  ├─ 🎬 " + _("Movies"), str(result.total_movies))
    stats_table.add_row("  └─ 📺 " + _("Episodes"), str(result.total_episodes))

    # Subtitles with breakdown
    stats_table.add_row("📝 " + _("Subtitles"), str(len(result.subtitle_files)))
    stats_table.add_row("  ├─ " + _("Variants"), str(len(result.variant_subtitles)))
    stats_table.add_row("  ├─ " + _("No language"), str(len(result.no_lang_subtitles)))
    stats_table.add_row("  ├─ " + _("Foreign"), str(len(result.foreign_subtitles)))
    stats_table.add_row("  └─ " + _("With language"), str(len(result.kept_subtitles)))

    # Images
    stats_table.add_row("🖼️  " + _("Images"), str(len(result.image_files)))

    # NFO files
    stats_table.add_row("📄 " + _("NFO files"), str(len(result.nfo_files)))

    # Other files
    stats_table.add_row("❓ " + _("Other"), str(len(result.other_files)))

    console.print(stats_table)

    # Suggested actions panel
    if result.variant_subtitles or result.no_lang_subtitles or result.foreign_subtitles:
        console.print("\n")
        actions_text = "[yellow]💡 " + _("Suggested actions:") + "[/yellow]\n\n"

        if result.variant_subtitles:
            actions_text += f"• {len(result.variant_subtitles)} " + _("subtitle variants (.lang2, .lang3) can be processed") + "\n"

        if result.no_lang_subtitles:
            actions_text += f"• {len(result.no_lang_subtitles)} " + _("subtitles without language code") + "\n"

        if result.foreign_subtitles:
            actions_text += f"• {len(result.foreign_subtitles)} " + _("foreign subtitles can be removed") + "\n"

        console.print(Panel(
            actions_text,
            title=_("Suggestions"),
            border_style="yellow"
        ))


def show_operation_preview(renamer: Renamer, limit: int = 20):
    """
    Display preview of planned operations.

    Args:
        renamer: Renamer object with planned operations
        limit: Maximum number of operations to display
    """
    operations = renamer.operations
    total = len(operations)

    if total == 0:
        console.clear()
        console.print("\n✓ " + _("No operations needed. Everything is already organized!") + "\n", style="bold green")
        return

    console.clear()
    console.print("\n")
    console.print(Panel.fit(
        f"📋 " + _("Operation Preview ({} files)").format(total),
        style="bold yellow",
        border_style="yellow"
    ))

    # Group by operation type
    renames = [op for op in operations if op.operation_type == 'rename']
    moves = [op for op in operations if op.operation_type == 'move']
    move_renames = [op for op in operations if op.operation_type == 'move_rename']
    deletes = [op for op in operations if op.operation_type == 'delete']

    # Show limited operations in list format with colors
    preview_ops = operations[:limit]

    # ANSI color codes
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    print()
    for i, op in enumerate(preview_ops, 1):
        if op.operation_type == 'delete':
            print(f"{BOLD}{CYAN}{i}.{RESET} {RED}🗑️  DELETE:{RESET} {op.source.name}")
        elif op.operation_type == 'move_rename':
            print(f"{BOLD}{CYAN}{i}.{RESET} {MAGENTA}📦✏️  MOVE+RENAME:{RESET}")
            print(f"   {DIM}From:{RESET} {YELLOW}{op.source}{RESET}")
            print(f"   {DIM}To:{RESET}   {GREEN}{op.destination}{RESET}")
        elif op.operation_type == 'move':
            print(f"{BOLD}{CYAN}{i}.{RESET} {MAGENTA}📦 MOVE:{RESET}")
            print(f"   {DIM}From:{RESET} {YELLOW}{op.source}{RESET}")
            print(f"   {DIM}To:{RESET}   {GREEN}{op.destination}{RESET}")
        else:  # rename
            print(f"{BOLD}{CYAN}{i}.{RESET} {CYAN}✏️  RENAME:{RESET}")
            print(f"   {DIM}From:{RESET} {YELLOW}{op.source.name}{RESET}")
            print(f"   {DIM}To:{RESET}   {GREEN}{op.destination.name}{RESET}")
        print()

    # Show truncation notice
    if total > limit:
        console.print(f"\n[dim]... " + _("and {} more operations").format(total - limit) + "[/dim]\n")

    # Summary table
    console.print("\n")
    summary = Table.grid(padding=(0, 2))

    if len(move_renames) > 0:
        summary.add_row(
            f"[cyan]📦✏️  " + _("Move + Rename:") + "[/cyan]",
            f"[bold]{len(move_renames)}[/bold]"
        )
    if len(moves) > 0:
        summary.add_row(
            f"[cyan]📦 " + _("Move:") + "[/cyan]",
            f"[bold]{len(moves)}[/bold]"
        )
    if len(renames) > 0:
        summary.add_row(
            f"[cyan]✏️  " + _("Rename:") + "[/cyan]",
            f"[bold]{len(renames)}[/bold]"
        )
    if len(deletes) > 0:
        summary.add_row(
            f"[cyan]🗑️  " + _("Remove:") + "[/cyan]",
            f"[bold red]{len(deletes)}[/bold red]"
        )

    console.print(Panel(summary, title=_("Summary"), border_style="cyan"))


def _show_operation_summary(operations: List[RenameOperation]):
    """
    Show summary of operations by type.
    
    Args:
        operations: List of RenameOperation objects
    """
    # Count by type
    counts = {}
    for op in operations:
        op_type = op.operation_type
        counts[op_type] = counts.get(op_type, 0) + 1
    
    # Create summary
    summary = Table(title=_("Summary"), box=box.ROUNDED, show_header=False)
    summary.add_column("Type", style="cyan")
    summary.add_column("Count", justify="right", style="yellow")
    
    type_names = {
        'move_rename': '📦✏️  ' + _('Move + Rename'),
        'move': '📦 ' + _('Move'),
        'rename': '✏️  ' + _('Rename'),
        'delete': '🗑️  ' + _('Delete')
    }
    
    for op_type, count in sorted(counts.items()):
        name = type_names.get(op_type, op_type)
        summary.add_row(name, str(count))
    
    console.print("\n")
    console.print(summary)


def show_execution_results(stats: dict):
    """
    Display execution results.
    
    Args:
        stats: Dictionary with execution statistics
    """
    table = Table(title=_("✅ Execution Results"), box=box.ROUNDED)
    table.add_column(_("Action"), style="cyan")
    table.add_column(_("Count"), justify="right", style="green")
    
    if stats.get('renamed', 0) > 0:
        table.add_row(_("Renamed"), str(stats['renamed']))
    if stats.get('moved', 0) > 0:
        table.add_row(_("Moved"), str(stats['moved']))
    if stats.get('deleted', 0) > 0:
        table.add_row(_("Deleted"), str(stats['deleted']))
    if stats.get('cleaned', 0) > 0:
        table.add_row(_("Cleaned folders"), str(stats['cleaned']))
    if stats.get('failed', 0) > 0:
        table.add_row("[red]" + _("Failed") + "[/red]", "[red]" + str(stats['failed']) + "[/red]")
    if stats.get('skipped', 0) > 0:
        table.add_row("[yellow]" + _("Skipped") + "[/yellow]", "[yellow]" + str(stats['skipped']) + "[/yellow]")
    
    console.print("\n")
    console.print(table)


def show_error(message: str):
    """
    Display error message.
    
    Args:
        message: Error message
    """
    console.print(f"\n[bold red]❌ {message}[/bold red]\n")


def show_warning(message: str):
    """
    Display warning message.
    
    Args:
        message: Warning message
    """
    console.print(f"\n[bold yellow]⚠️  {message}[/bold yellow]\n")


def show_success(message: str):
    """
    Display success message.
    
    Args:
        message: Success message
    """
    console.print(f"\n[bold green]✅ {message}[/bold green]\n")


def show_info(message: str):
    """
    Display info message.
    
    Args:
        message: Info message
    """
    console.print(f"\n[bold cyan]ℹ️  {message}[/bold cyan]\n")
