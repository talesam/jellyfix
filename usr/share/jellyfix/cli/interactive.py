#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cli/interactive.py - Interactive CLI mode with full menus
#

"""
Interactive CLI mode using questionary for menus.

This mode provides a user-friendly menu-driven interface
for scanning and organizing Jellyfin libraries.
"""

from pathlib import Path
from typing import Optional
import re
import questionary
from questionary import Style

from ..core.scanner import LibraryScanner
from ..core.renamer import Renamer
from ..utils.logger import get_logger
from ..utils.config_manager import ConfigManager
from ..utils.config import get_config, APP_VERSION
from ..utils.i18n import _
from .display import (
    console, show_banner, show_scan_results,
    show_operation_preview, show_execution_results,
    show_error, show_warning, show_success, show_info
)


# Custom style for menus
custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#4caf50 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#4caf50'),
    ('separator', 'fg:#cc5454'),
    ('instruction', ''),
    ('text', ''),
    ('checkbox', 'fg:#4caf50'),
    ('checkbox-selected', 'fg:#4caf50 bold'),
])


class InteractiveCLI:
    """Interactive CLI handler with menu-driven interface"""

    def __init__(self, config):
        """
        Initialize interactive CLI.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = get_logger()
        self.config_manager = ConfigManager()

    def run(self):
        """Run interactive mode"""
        show_banner()

        while True:
            choice = self._main_menu()

            if not choice:
                break

            if choice == "scan":
                self._scan_library()
                console.clear()
                show_banner()
            elif choice == "process":
                self._process_files()
                console.clear()
                show_banner()
            elif choice == "settings":
                self._settings_menu()
                console.clear()
                show_banner()
            elif choice == "fix_mirabel":
                self._fix_mirabel_files()
                console.clear()
                show_banner()
            elif choice == "help":
                self._show_help()
                console.clear()
                show_banner()
            elif choice == "exit":
                break

    def _main_menu(self) -> Optional[str]:
        """
        Display main menu and get user choice.

        Returns:
            Menu choice or None if cancelled
        """
        choice = questionary.select(
            _("What would you like to do?"),
            choices=[
                questionary.Choice(_("📂 Scan library"), value="scan"),
                questionary.Choice(_("🔧 Settings"), value="settings"),
                questionary.Choice(_("🚀 Process files"), value="process"),
                questionary.Choice(_("🩹 Fix Mirabel files"), value="fix_mirabel"),
                questionary.Choice(_("ℹ️  Help"), value="help"),
                questionary.Choice(_("❌ Exit"), value="exit")
            ],
            style=custom_style,
            instruction=_("(Use arrow keys to navigate)")
        ).ask()

        return choice

    def _scan_library(self):
        """Scan library and display results"""
        # Select directory
        workdir = self._select_directory()
        if not workdir:
            return

        console.clear()
        show_info(_("Scanning: %s") % workdir)

        # Scan
        scanner = LibraryScanner()
        result = scanner.scan(workdir)

        # Display results
        show_scan_results(result)

        # Wait for user
        questionary.press_any_key_to_continue().ask()

    def _process_files(self):
        """Process files: scan, plan, preview, execute"""
        # Select directory
        workdir = self._select_directory()
        if not workdir:
            return

        console.clear()
        show_info(_("Scanning: %s") % workdir)

        # Scan
        scanner = LibraryScanner()
        result = scanner.scan(workdir)

        self.logger.info(
            _("Found: %d videos, %d subtitles") %
            (len(result.video_files), len(result.subtitle_files))
        )

        # Plan operations
        self.logger.info(_("Planning operations..."))
        renamer = Renamer()
        renamer.plan_operations(workdir, result)

        if len(renamer.operations) == 0:
            show_warning(_("No operations needed"))
            questionary.press_any_key_to_continue().ask()
            return

        # Show preview
        show_operation_preview(renamer, limit=50)

        # Confirm
        confirm = questionary.confirm(
            _("Execute these operations?"),
            default=False,
            style=custom_style
        ).ask()

        if not confirm:
            show_info(_("Operation cancelled"))
            return

        # Execute
        self.logger.info(_("Executing operations..."))
        stats = renamer.execute_operations(dry_run=False)

        # Show results
        show_execution_results(stats)

        questionary.press_any_key_to_continue().ask()

    def _select_directory(self, default: Optional[Path] = None) -> Optional[Path]:
        """
        Interactive directory selector.

        Args:
            default: Default starting directory

        Returns:
            Selected directory or None if cancelled
        """
        if default is None:
            default = Path.cwd()

        current_dir = default.resolve()

        while True:
            console.clear()
            console.print("\n[bold cyan]" + _("📂 Directory Browser") + "[/bold cyan]\n")
            console.print(f"[dim]" + _("Current:") + f"[/dim] [yellow]{current_dir}[/yellow]\n")

            # List directories
            try:
                choices = []

                # Add option to select current
                choices.append(questionary.Choice(
                    _("✓ Select this directory"),
                    value="__select__"
                ))

                # Add parent option
                if current_dir.parent != current_dir:
                    choices.append(questionary.Choice(
                        _("⬆️  .. (go back)"),
                        value="__parent__"
                    ))

                # Add subdirectories
                dirs = sorted([d for d in current_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
                for d in dirs:
                    choices.append(questionary.Choice(f"📁 {d.name}", value=str(d)))

                # Add manual path entry
                choices.append(questionary.Choice(
                    _("⌨️  Type path manually"),
                    value="__manual__"
                ))

                # Add cancel option
                choices.append(questionary.Choice(
                    _("❌ Cancel"),
                    value="__cancel__"
                ))

                # Ask
                choice = questionary.select(
                    _("Select directory:"),
                    choices=choices,
                    style=custom_style
                ).ask()

                if not choice or choice == "__cancel__":
                    return None
                elif choice == "__select__":
                    return current_dir
                elif choice == "__parent__":
                    current_dir = current_dir.parent
                elif choice == "__manual__":
                    console.print("\n[cyan]" + _("Enter full directory path:") + "[/cyan]")
                    path_str = questionary.text(
                        _("Path:"),
                        default=str(current_dir),
                        style=custom_style
                    ).ask()

                    if path_str:
                        new_path = Path(path_str).expanduser().resolve()
                        if new_path.exists() and new_path.is_dir():
                            return new_path
                        else:
                            show_error(_("Directory not found!"))
                            questionary.press_any_key_to_continue().ask()
                    continue
                else:
                    current_dir = Path(choice)

            except PermissionError:
                show_error(_("Permission denied"))
                questionary.press_any_key_to_continue().ask()
                current_dir = current_dir.parent

    def _settings_menu(self):
        """Complete settings configuration menu"""
        while True:
            console.clear()
            show_banner()
            console.print("\n[bold blue]⚙️  " + _("Settings") + "[/bold blue]\n")

            # Build dynamic choices with current values
            kept_langs_str = ", ".join(self.config.kept_languages) if self.config.kept_languages else _("none")

            choice = questionary.select(
                _("What would you like to configure?"),
                choices=[
                    f"{'✓' if self.config.rename_por2 else '✗'} " + _("Rename language variants (lang2→lang, lang3→lang)"),
                    f"{'✓' if self.config.remove_language_variants else '✗'} " + _("Remove duplicate variants (lang2, lang3)"),
                    f"{'✓' if self.config.rename_no_lang else '✗'} " + _("Add language code to subtitles"),
                    f"{'✓' if self.config.remove_foreign_subs else '✗'} " + _("Remove foreign subtitles"),
                    f"🌍 " + _("Kept languages:") + f" {kept_langs_str}",
                    f"{'✓' if self.config.organize_folders else '✗'} " + _("Organize in folders (Season XX)"),
                    f"{'✓' if self.config.fetch_metadata else '✗'} " + _("Fetch metadata (TMDB/TVDB)"),
                    f"{'✓' if self.config.ask_on_multiple_results else '✗'} " + _("Ask when multiple TMDB results"),
                    f"{'✓' if self.config.add_quality_tag else '✗'} " + _("Add quality tags (1080p, 720p, etc)"),
                    f"{'✓' if self.config.use_ffprobe else '✗'} " + _("Use ffprobe for quality detection"),
                    f"{'✓' if self.config.rename_nfo else '✗'} " + _("Rename NFO files to match video"),
                    f"{'✓' if self.config.remove_non_media else '✗'} " + _("Remove non-media files (keep only videos/subtitles)"),
                    f"📊 " + _("Min Portuguese words:") + f" {self.config.min_pt_words}",
                    "🔑 " + _("Configure APIs (TMDB/TVDB)"),
                    "← " + _("Back")
                ],
                style=custom_style,
                instruction=_("(Use ↑↓ and ENTER to select)")
            ).ask()

            if not choice or _("Back") in choice:
                break

            # Handle each setting
            if _("Rename language variants") in choice:
                self.config.rename_por2 = not self.config.rename_por2
                self.config_manager.set('rename_por2', self.config.rename_por2)
                show_success(_("Setting saved"))

            elif _("Remove duplicate variants") in choice:
                self.config.remove_language_variants = not self.config.remove_language_variants
                self.config_manager.set('remove_language_variants', self.config.remove_language_variants)
                show_success(_("Setting saved"))

            elif _("Add language code") in choice:
                self.config.rename_no_lang = not self.config.rename_no_lang
                self.config_manager.set('rename_no_lang', self.config.rename_no_lang)
                show_success(_("Setting saved"))

            elif _("Remove foreign") in choice:
                self.config.remove_foreign_subs = not self.config.remove_foreign_subs
                self.config_manager.set('remove_foreign_subs', self.config.remove_foreign_subs)
                show_success(_("Setting saved"))

            elif _("Kept languages") in choice:
                self._language_selection_menu()

            elif _("Organize in folders") in choice:
                self.config.organize_folders = not self.config.organize_folders
                self.config_manager.set('organize_folders', self.config.organize_folders)
                show_success(_("Setting saved"))

            elif _("Fetch metadata") in choice:
                self.config.fetch_metadata = not self.config.fetch_metadata
                self.config_manager.set('fetch_metadata', self.config.fetch_metadata)
                show_success(_("Setting saved"))

            elif _("Ask when multiple TMDB results") in choice:
                self.config.ask_on_multiple_results = not self.config.ask_on_multiple_results
                self.config_manager.set('ask_on_multiple_results', self.config.ask_on_multiple_results)
                show_success(_("Setting saved"))

            elif _("Add quality tags") in choice:
                self.config.add_quality_tag = not self.config.add_quality_tag
                self.config_manager.set('add_quality_tag', self.config.add_quality_tag)
                show_success(_("Setting saved"))

            elif _("Use ffprobe for quality detection") in choice:
                self.config.use_ffprobe = not self.config.use_ffprobe
                self.config_manager.set('use_ffprobe', self.config.use_ffprobe)
                show_success(_("Setting saved"))

            elif _("Rename NFO files to match video") in choice:
                self.config.rename_nfo = not self.config.rename_nfo
                self.config_manager.set('rename_nfo', self.config.rename_nfo)
                show_success(_("Setting saved"))

            elif _("Remove non-media files") in choice:
                self.config.remove_non_media = not self.config.remove_non_media
                self.config_manager.set('remove_non_media', self.config.remove_non_media)
                show_success(_("Setting saved"))

            elif _("Min Portuguese words") in choice:
                new_value = questionary.text(
                    _("Minimum number of Portuguese words:"),
                    default=str(self.config.min_pt_words),
                    style=custom_style
                ).ask()
                try:
                    value = int(new_value)
                    self.config.min_pt_words = value
                    self.config_manager.set('min_pt_words', value)
                    show_success(_("Setting saved to ~/.jellyfix/config.json"))
                except ValueError:
                    show_error(_("Invalid value!"))
                questionary.press_any_key_to_continue().ask()

            elif _("Configure APIs (TMDB/TVDB)") in choice:
                self._api_settings_menu()

    def _language_selection_menu(self):
        """Language selection menu with checkbox"""
        console.clear()
        show_banner()
        console.print("\n[bold blue]🌍 " + _("Language Selection") + "[/bold blue]\n")
        console.print("[dim]" + _("Select languages to KEEP (will NOT be removed)") + "[/dim]")
        console.print("[dim]" + _("Use SPACE to check/uncheck, ENTER to confirm") + "[/dim]\n")

        # Create choices sorted alphabetically by language name
        choices = []
        for code, name in sorted(self.config.all_languages.items(), key=lambda x: x[1]):
            display_name = f"{name} ({code})"
            choices.append(questionary.Choice(
                title=display_name,
                value=code,
                checked=(code in self.config.kept_languages)
            ))

        selected = questionary.checkbox(
            _("Select languages to KEEP:"),
            choices=choices,
            style=custom_style,
            instruction=_("(SPACE = check/uncheck, ENTER = confirm)")
        ).ask()

        if selected is not None:
            self.config.kept_languages = selected
            console.print(f"\n[green]✓ " + _("Kept languages:") + f" {', '.join(selected)}[/green]")

            # Save to config file
            self.config_manager.set('kept_languages', selected)
            show_success(_("Saved to ~/.jellyfix/config.json"))

        questionary.press_any_key_to_continue().ask()

    def _api_settings_menu(self):
        """API configuration menu"""
        while True:
            console.clear()
            show_banner()
            console.print("\n[bold magenta]🔑 " + _("API Configuration") + "[/bold magenta]\n")

            # Show current status
            tmdb_key = self.config_manager.get_tmdb_api_key()
            tmdb_status = "[green]✓ " + _("Configured") + "[/green]" if tmdb_key else "[red]✗ " + _("Not configured") + "[/red]"

            console.print(f"[bold]TMDB API Key:[/bold] {tmdb_status}")
            console.print(f"[bold]" + _("Config file:") + f"[/bold] [cyan]{self.config_manager.get_config_path()}[/cyan]\n")

            choice = questionary.select(
                _("What would you like to do?"),
                choices=[
                    "🔑 " + _("Configure TMDB API Key"),
                    "📋 " + _("View current key (TMDB)"),
                    "✓ " + _("Test TMDB connection"),
                    "🗑️  " + _("Remove TMDB key"),
                    "ℹ️  " + _("How to get TMDB key"),
                    "← " + _("Back")
                ],
                style=custom_style,
                instruction=_("(Use ↑↓ and ENTER to select)")
            ).ask()

            if not choice or _("Back") in choice:
                break

            elif _("Configure TMDB API Key") in choice:
                console.print("\n[cyan]" + _("Enter your TMDB API key:") + "[/cyan]")
                api_key = questionary.text(
                    "TMDB API Key:",
                    style=custom_style
                ).ask()

                if api_key and api_key.strip():
                    self.config_manager.set_tmdb_api_key(api_key.strip())
                    self.config.tmdb_api_key = api_key.strip()
                    console.print(f"\n[green]✓ " + _("TMDB key saved to:") + "[/green]")
                    console.print(f"  [cyan]{self.config_manager.get_config_path()}[/cyan]")
                else:
                    show_warning(_("Operation cancelled"))

                questionary.press_any_key_to_continue().ask()

            elif _("View current key (TMDB)") in choice:
                key = self.config_manager.get_tmdb_api_key()
                if key:
                    # Show only first and last 4 characters
                    masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
                    console.print(f"\n[cyan]TMDB Key:[/cyan] {masked_key}")
                    console.print(f"\n[dim]" + _("File:") + f"[/dim] [cyan]{self.config_manager.get_config_path()}[/cyan]")
                else:
                    show_warning(_("No key configured"))

                questionary.press_any_key_to_continue().ask()

            elif _("Remove TMDB key") in choice:
                confirm = questionary.confirm(
                    _("Are you sure you want to remove the TMDB key?"),
                    default=False,
                    style=custom_style
                ).ask()

                if confirm:
                    self.config_manager.set_tmdb_api_key("")
                    self.config.tmdb_api_key = ""
                    show_success(_("TMDB key removed"))
                else:
                    show_warning(_("Operation cancelled"))

                questionary.press_any_key_to_continue().ask()

            elif _("Test TMDB connection") in choice:
                self._test_tmdb_connection()

            elif _("How to get TMDB key") in choice:
                self._show_tmdb_help()

    def _test_tmdb_connection(self):
        """Test TMDB API connection"""
        console.clear()
        show_banner()
        console.print("\n[bold cyan]🔍 " + _("Testing TMDB connection...") + "[/bold cyan]\n")

        api_key = self.config_manager.get_tmdb_api_key()

        if not api_key:
            show_error(_("No API key configured!"))
            console.print("\n[yellow]" + _("Configure a key first using 'Configure TMDB API Key'") + "[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return

        # Validate key format
        if len(api_key) != 32:
            show_error(_("Invalid key! Has %d characters, should have 32.") % len(api_key))
            console.print("\n[yellow]⚠️  " + _("You may have copied the Token instead of the API Key!") + "[/yellow]")
            console.print("[dim]" + _("See 'How to get TMDB key' for details") + "[/dim]")
            questionary.press_any_key_to_continue().ask()
            return

        try:
            import requests

            # Test with a simple search
            console.print("[cyan]" + _("Making test request...") + "[/cyan]")
            url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query=Matrix"

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                total_results = data.get('total_results', 0)

                show_success(_("Connection successful!"))
                console.print(f"[green]• " + _("Valid and working API key") + "[/green]")
                console.print(f"[green]• " + _("Test search returned %d results") % total_results + "[/green]")

                if total_results > 0:
                    first_movie = data['results'][0]
                    console.print(f"\n[dim]" + _("Example:") + f" {first_movie.get('title')} ({first_movie.get('release_date', 'N/A')[:4]})[/dim]")

            elif response.status_code == 401:
                show_error(_("Invalid API key!"))
                console.print("[yellow]" + _("The key was rejected by TMDB.") + "[/yellow]")
                console.print("\n[bold]" + _("Possible causes:") + "[/bold]")
                console.print("1. " + _("You copied the Reading Token instead of the API Key"))
                console.print("2. " + _("The key is incorrect or has been revoked"))
                console.print("3. " + _("You copied only part of the key"))
                console.print("\n[cyan]" + _("See 'How to get TMDB key' for detailed instructions") + "[/cyan]")

            else:
                show_error(_("Request error: HTTP %d") % response.status_code)

        except requests.exceptions.Timeout:
            show_error(_("Timeout: Server did not respond in time"))
            console.print("[yellow]" + _("Check your internet connection") + "[/yellow]")

        except requests.exceptions.ConnectionError:
            show_error(_("Connection error"))
            console.print("[yellow]" + _("Check your internet connection") + "[/yellow]")

        except Exception as e:
            show_error(_("Unexpected error: %s") % e)

        questionary.press_any_key_to_continue().ask()

    def _show_tmdb_help(self):
        """Show TMDB API key help"""
        console.clear()
        show_banner()
        help_text = f"""[bold cyan]📖 {_("How to Get TMDB API Key")}[/bold cyan]

[bold]1. {_("Access:")}[/bold]
   [link=https://www.themoviedb.org/settings/api]https://www.themoviedb.org/settings/api[/link]

[bold]2. {_("Login or create a FREE account")}[/bold]
   • https://www.themoviedb.org/signup
   • {_("Fill in your details")}
   • {_("Confirm email")}

[bold]3. {_("Request an API key:")}[/bold]
   • {_("Access")}: https://www.themoviedb.org/settings/api
   • {_("Click 'Request an API Key'")}
   • {_("Choose 'Developer' (personal use)")}
   • {_("Fill in")}:
     - Application Name: Jellyfix
     - Application URL: http://localhost
     - Application Summary: Personal media organizer
   • {_("Accept terms of use")}

[bold red]⚠️  {_("IMPORTANT - Which key to copy:")}[/bold red]
   {_("You will see TWO keys on the page:")}
   [dim]• {_("API Read Access Token (long, starts with eyJ...)")}[/dim]
   [bold green]• {_("API Key (v3 auth) ← COPY THIS ONE!")}[/bold green]

   {_("The correct key has 32 characters (ex: 611bc23b57add08a67b2e64ecb850be8)")}

[bold]4. {_("Configure in jellyfix:")}[/bold]
   • {_("Return to menu and choose 'Configure TMDB API Key'")}
   • {_("Paste the API Key (32 characters)")}
   • {_("Use 'Test connection' to verify")}

[green]✓ {_("The key is free and does not expire!")}[/green]
[green]✓ {_("Allows up to 40 requests per 10 seconds")}[/green]
[green]✓ {_("Enough to organize thousands of files!")}[/green]
"""
        from rich.panel import Panel
        console.print(Panel(help_text, title=_("How to Get TMDB Key"), border_style="cyan", expand=False))
        questionary.press_any_key_to_continue().ask()

    def _show_help(self):
        """Show complete help information"""
        console.clear()
        show_banner()
        help_text = f"""[bold cyan]📖 {_("Help - jellyfix v")} {APP_VERSION}[/bold cyan]

[bold]{_("What jellyfix does:")}[/bold]

• [green]{_("Renames files")}[/green] {_("to Jellyfin standard")}
  - {_("Movies")}: [dim]{_("Movie Name (YYYY).mkv")}[/dim]
  - {_("Series")}: [dim]{_("Series Name S01E01.mkv")}[/dim]

• [green]{_("Organizes subtitles")}[/green] {_("(ALL languages)")}
  - {_("Renames variants")}: por2→por, eng2→eng, spa3→spa
  - {_("Adds language code")} (.por.srt)
  - {_("Removes foreign subtitles")} ({_("keeps por and eng by default")})
  - {_("Option to remove duplicates")} (eng2, eng3 {_("when eng exists")})
  - [yellow]{_("NEVER")}[/yellow] {_("removes .forced.srt")}

• [green]{_("Folder structure")}[/green]
  - {_("Creates folders Season 01, Season 02, etc")}
  - {_("Moves episodes to correct folders")}

• [green]{_("Fetches metadata")}[/green]
  - {_("Searches year and IDs via TMDB/TVDB")}
  - {_("Adds IDs to folders [tmdbid-12345]")}

• [green]{_("Quality detection")}[/green]
  - {_("Adds quality tags (1080p, 720p, etc) to filenames")}
  - {_("Option to use ffprobe for accurate detection")}

[bold yellow]{_("Dry-Run Mode:")}[/bold yellow]
{_("By default, jellyfix shows what will be done WITHOUT changing files.")}
{_("You can review changes before applying.")}

[bold cyan]{_("Tip:")}[/bold cyan] {_("Configure your TMDB key")}:
[dim]Settings → Configure APIs → Configure TMDB API Key[/dim]
"""
        from rich.panel import Panel
        console.print(Panel(help_text, border_style="cyan", expand=False))
        questionary.press_any_key_to_continue().ask()

    def _fix_mirabel_files(self):
        """
        Fix Mirabel subtitle files.

        Renames subtitle files with non-standard language codes like:
        - .pt-BR.hi.srt → .por.srt
        - .br.hi.srt → .por.srt
        - .pt-BR.hi.forced.srt → .por.forced.srt
        - .br.hi.forced.srt → .por.forced.srt
        """
        from ..core.renamer import RenameOperation

        # Select directory
        workdir = self._select_directory()
        if not workdir:
            return

        console.clear()
        show_info(_("Scanning for Mirabel files: %s") % workdir)

        # Pattern to match Mirabel files: .pt-BR.hi, .br.hi, .pt-br.hi, .BR.hi, etc.
        mirabel_pattern = re.compile(
            r'^(.+?)\.(pt-BR|pt-br|br|BR|pt_BR|pt_br)\.hi(\.forced)?\.srt$',
            re.IGNORECASE
        )

        # Scan for Mirabel files
        mirabel_files = []
        for file_path in workdir.rglob('*.srt'):
            if not file_path.is_file():
                continue
            if mirabel_pattern.match(file_path.name):
                mirabel_files.append(file_path)

        if not mirabel_files:
            show_warning(_("No Mirabel files found"))
            questionary.press_any_key_to_continue().ask()
            return

        self.logger.info(_("Found %d Mirabel files") % len(mirabel_files))

        # Create rename operations
        operations = []
        for file_path in mirabel_files:
            match = mirabel_pattern.match(file_path.name)
            if match:
                base_name = match.group(1)
                forced = match.group(3)  # '.forced' or None

                # Build new filename
                if forced:
                    new_name = f"{base_name}.por.forced.srt"
                else:
                    new_name = f"{base_name}.por.srt"

                new_path = file_path.parent / new_name

                # Check if destination already exists
                if new_path.exists() and new_path != file_path:
                    # Destination exists - mark for deletion instead
                    operations.append(RenameOperation(
                        source=file_path,
                        destination=file_path,  # Not used for delete
                        operation_type='delete',
                        reason=_("Duplicate: %s already exists") % new_name
                    ))
                else:
                    operations.append(RenameOperation(
                        source=file_path,
                        destination=new_path,
                        operation_type='rename',
                        reason=_("Mirabel fix: %s → %s") % (file_path.name, new_name)
                    ))

        if not operations:
            show_warning(_("No operations needed"))
            questionary.press_any_key_to_continue().ask()
            return

        # Show preview
        console.print("\n[bold cyan]" + _("Operations to perform:") + "[/bold cyan]\n")
        for i, op in enumerate(operations[:50], 1):
            if op.operation_type == 'delete':
                console.print(f"[red]{i}. DELETE: {op.source.name}[/red]")
                console.print(f"   [dim]{op.reason}[/dim]")
            else:
                console.print(f"[green]{i}. {op.source.name}[/green]")
                console.print(f"   → [yellow]{op.destination.name}[/yellow]")

        if len(operations) > 50:
            console.print(f"\n[dim]... {_('and %d more operations') % (len(operations) - 50)}[/dim]")

        console.print(f"\n[bold]{_('Total: %d operations') % len(operations)}[/bold]\n")

        # Confirm
        confirm = questionary.confirm(
            _("Execute these operations?"),
            default=False,
            style=custom_style
        ).ask()

        if not confirm:
            show_info(_("Operation cancelled"))
            questionary.press_any_key_to_continue().ask()
            return

        # Execute operations
        self.logger.info(_("Executing operations..."))
        stats = {'renamed': 0, 'deleted': 0, 'failed': 0}

        for op in operations:
            try:
                if op.operation_type == 'delete':
                    op.source.unlink()
                    stats['deleted'] += 1
                else:
                    op.source.rename(op.destination)
                    stats['renamed'] += 1
            except Exception as e:
                self.logger.error(_("Error processing %s: %s") % (op.source.name, e))
                stats['failed'] += 1

        # Show results
        console.print("\n[bold green]" + _("Results:") + "[/bold green]")
        console.print(f"  [green]✓ {_('Renamed')}: {stats['renamed']}[/green]")
        if stats['deleted'] > 0:
            console.print(f"  [yellow]🗑 {_('Deleted')}: {stats['deleted']}[/yellow]")
        if stats['failed'] > 0:
            console.print(f"  [red]✗ {_('Failed')}: {stats['failed']}[/red]")

        show_success(_("Mirabel files fixed!"))
        questionary.press_any_key_to_continue().ask()
