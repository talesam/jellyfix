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
from typing import List
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
    banner.append("    Intelligent Jellyfin Library Organizer", style="cyan")
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


def show_operation_preview(renamer: Renamer, limit: int = 50):
    """
    Display preview of planned operations grouped by video with subtitles.

    Args:
        renamer: Renamer object with planned operations
        limit: Maximum number of groups to display
    """
    from ..utils.helpers import VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS

    operations = renamer.operations
    total = len(operations)

    if total == 0:
        console.clear()
        console.print("\n✓ " + _("No operations needed. Everything is already organized!") + "\n", style="bold green")
        return

    console.clear()
    console.print("\n")
    console.print(Panel.fit(
        "📋 " + _("Operation Preview ({} files)").format(total),
        style="bold yellow",
        border_style="yellow"
    ))

    # ANSI color codes
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    # Separate operations by type
    video_ops = []
    subtitle_ops = []
    other_ops = []

    for op in operations:
        src_ext = op.source.suffix.lower()
        if src_ext in VIDEO_EXTENSIONS:
            video_ops.append(op)
        elif src_ext in SUBTITLE_EXTENSIONS:
            subtitle_ops.append(op)
        else:
            other_ops.append(op)

    # Build grouped structure: video -> [subtitles]
    groups = []

    for video_op in video_ops:
        video_stem = video_op.source.stem
        video_parent = video_op.source.parent

        # Find all subtitles that belong to this video
        related_subs = []
        for sub_op in subtitle_ops[:]:  # Iterate over a copy
            sub_stem_base = sub_op.source.stem.split('.')[0]  # Get base name before .lang.srt
            # Check if subtitle matches video (same base name or starts with video name)
            if (sub_op.source.parent == video_parent and
                (sub_stem_base == video_stem or
                 sub_op.source.stem.startswith(video_stem + '.') or
                 video_stem.startswith(sub_stem_base))):
                related_subs.append(sub_op)
                subtitle_ops.remove(sub_op)

        groups.append({
            'video': video_op,
            'subtitles': related_subs
        })

    # Add orphan subtitles as standalone groups
    for sub_op in subtitle_ops:
        groups.append({
            'video': None,
            'subtitles': [sub_op]
        })

    # Add other operations (NFO, images, etc.)
    for other_op in other_ops:
        groups.append({
            'video': None,
            'subtitles': [],
            'other': other_op
        })

    # Display grouped operations
    print()
    displayed = 0

    for i, group in enumerate(groups[:limit], 1):
        video_op = group.get('video')
        subtitles = group.get('subtitles', [])
        other_op = group.get('other')

        if video_op:
            # Video operation
            op_type_icon = _get_operation_icon(video_op.operation_type)
            print(f"{BOLD}{CYAN}{i}.{RESET} 🎬 {op_type_icon}")
            print(f"   {DIM}From:{RESET} {YELLOW}{op_op_path(video_op.source)}{RESET}")
            print(f"   {DIM}To:{RESET}   {GREEN}{op_op_path(video_op.destination)}{RESET}")
            displayed += 1

            # Related subtitles (indented)
            for sub_op in subtitles:
                sub_icon = _get_operation_icon(sub_op.operation_type)
                if sub_op.operation_type == 'delete':
                    print(f"      📄 {RED}DELETE:{RESET} {sub_op.source.name}")
                else:
                    print(f"      📄 {sub_icon}")
                    print(f"         {DIM}From:{RESET} {YELLOW}{sub_op.source.name}{RESET}")
                    print(f"         {DIM}To:{RESET}   {GREEN}{sub_op.destination.name}{RESET}")
                displayed += 1

        elif other_op:
            # Other file operation (NFO, images, etc.)
            op_type_icon = _get_operation_icon(other_op.operation_type)
            if other_op.operation_type == 'delete':
                print(f"{BOLD}{CYAN}{i}.{RESET} 📁 {RED}DELETE:{RESET} {other_op.source.name}")
            else:
                print(f"{BOLD}{CYAN}{i}.{RESET} 📁 {op_type_icon}")
                print(f"   {DIM}From:{RESET} {YELLOW}{op_op_path(other_op.source)}{RESET}")
                print(f"   {DIM}To:{RESET}   {GREEN}{op_op_path(other_op.destination)}{RESET}")
            displayed += 1

        elif subtitles:
            # Orphan subtitles (no video parent)
            for sub_op in subtitles:
                sub_icon = _get_operation_icon(sub_op.operation_type)
                if sub_op.operation_type == 'delete':
                    print(f"{BOLD}{CYAN}{i}.{RESET} 📄 {RED}DELETE:{RESET} {sub_op.source.name}")
                else:
                    print(f"{BOLD}{CYAN}{i}.{RESET} 📄 {sub_icon}")
                    print(f"   {DIM}From:{RESET} {YELLOW}{op_op_path(sub_op.source)}{RESET}")
                    print(f"   {DIM}To:{RESET}   {GREEN}{op_op_path(sub_op.destination)}{RESET}")
                displayed += 1

        print()

    # Show truncation notice
    if len(groups) > limit:
        console.print("\n[dim]... " + _("and {} more groups").format(len(groups) - limit) + "[/dim]\n")

    # Group by operation type for summary
    renames = [op for op in operations if op.operation_type == 'rename']
    moves = [op for op in operations if op.operation_type == 'move']
    move_renames = [op for op in operations if op.operation_type == 'move_rename']
    deletes = [op for op in operations if op.operation_type == 'delete']

    # Summary table
    console.print("\n")
    summary = Table.grid(padding=(0, 2))

    if len(move_renames) > 0:
        summary.add_row(
            "[cyan]📦✏️  " + _("Move + Rename:") + "[/cyan]",
            f"[bold]{len(move_renames)}[/bold]"
        )
    if len(moves) > 0:
        summary.add_row(
            "[cyan]📦 " + _("Move:") + "[/cyan]",
            f"[bold]{len(moves)}[/bold]"
        )
    if len(renames) > 0:
        summary.add_row(
            "[cyan]✏️  " + _("Rename:") + "[/cyan]",
            f"[bold]{len(renames)}[/bold]"
        )
    if len(deletes) > 0:
        summary.add_row(
            "[cyan]🗑️  " + _("Remove:") + "[/cyan]",
            f"[bold red]{len(deletes)}[/bold red]"
        )

    console.print(Panel(summary, title=_("Summary"), border_style="cyan"))


def _get_operation_icon(op_type: str) -> str:
    """Get colored operation icon based on type."""
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RED = '\033[91m'
    RESET = '\033[0m'

    icons = {
        'move_rename': f'{MAGENTA}MOVE+RENAME{RESET}',
        'move': f'{MAGENTA}MOVE{RESET}',
        'rename': f'{CYAN}RENAME{RESET}',
        'delete': f'{RED}DELETE{RESET}'
    }
    return icons.get(op_type, op_type)


def op_op_path(path: Path) -> str:
    """Format path for display, shortening if needed."""
    path_str = str(path)
    # Shorten very long paths
    if len(path_str) > 100:
        return f"...{path_str[-97:]}"
    return path_str


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
