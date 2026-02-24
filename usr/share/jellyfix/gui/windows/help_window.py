#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/help_window.py - Help and tutorial window
#

"""
Help window with comprehensive tutorials and documentation.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

from ...utils.i18n import _
from ...utils.config import APP_VERSION


class HelpWindow(Adw.Window):
    """Help and documentation window"""

    def __init__(self, parent):
        """
        Initialize help window.

        Args:
            parent: Parent window
        """
        super().__init__(transient_for=parent, modal=True)

        # Window properties
        self.set_title(_("Jellyfix Help"))
        self.set_default_size(800, 600)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build help UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_start(40)
        content_box.set_margin_end(40)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup('<span size="xx-large" weight="bold">🎬 Jellyfix</span>')
        title_label.set_halign(Gtk.Align.CENTER)
        content_box.append(title_label)

        # Version
        version_label = Gtk.Label()
        version_label.set_markup(f'<span size="small">{_("Version")} {APP_VERSION}</span>')
        version_label.set_halign(Gtk.Align.CENTER)
        content_box.append(version_label)

        # Description
        desc_label = Gtk.Label()
        desc_label.set_markup(f'<b>{_("Intelligent Jellyfin Library Organizer")}</b>')
        desc_label.set_halign(Gtk.Align.CENTER)
        content_box.append(desc_label)

        # Separator
        separator = Gtk.Separator()
        content_box.append(separator)

        # What It Does section
        self._add_section(
            content_box,
            _("What Jellyfix Does"),
            _(
                "Jellyfix automatically organizes your media library following Jellyfin naming conventions:\n"
                "\n"
                "• <b>Renames files</b> to Jellyfin standard format\n"
                "• <b>Organizes episodes</b> into Season folders\n"
                "• <b>Manages subtitles</b>: renames, removes foreign languages, adds language codes\n"
                "• <b>Fetches metadata</b> from TMDB/TVDB\n"
                "• <b>Detects and adds quality tags</b> (1080p, 720p, etc)\n"
                "• <b>Adds provider IDs</b> to folder names ([tmdbid-12345])"
            ),
        )

        # Examples section
        self._add_section(
            content_box,
            _("Examples"),
            _(
                "<b>Movies:</b>\n"
                "  Before: movie.name.2023.1080p.bluray.mkv\n"
                "  After:  Movie Name (2023) [tmdbid-12345]/Movie Name (2023) - 1080p.mkv\n"
                "\n"
                "<b>TV Shows:</b>\n"
                "  Before: show.name.s01e05.720p.mkv\n"
                "  After:  Show Name (2024) [tmdbid-67890]/Season 01/Show Name S01E05 - 720p.mkv\n"
                "\n"
                "<b>Subtitles:</b>\n"
                "  • Renames: .por2.srt → .por.srt, .eng3.srt → .eng.srt\n"
                "  • Adds language codes: subtitle.srt → Movie Name.por.srt\n"
                "  • Removes foreign languages (keeps configured languages only)\n"
                "  • <b>NEVER</b> removes .forced.srt files"
            ),
        )

        # How to Use section
        self._add_section(
            content_box,
            _("How to Use"),
            _(
                "<b>1. Configure TMDB API Key (recommended)</b>\n"
                "   Menu → Configure API Keys → Follow the tutorial\n"
                "   This enables metadata fetching and poster downloads.\n"
                "\n"
                "<b>2. Scan Library</b>\n"
                '   Click "Scan Library" on Dashboard\n'
                "   Select your media folder\n"
                "   Review the scan results\n"
                "\n"
                "<b>3. Review Operations</b>\n"
                '   Switch to "Operations" tab\n'
                "   Preview what will be changed\n"
                "   Select operations to see details\n"
                "\n"
                "<b>4. Execute</b>\n"
                '   Click "Process Files"\n'
                "   Confirm the operation\n"
                "   Files will be renamed and organized\n"
                "\n"
                "<b>Tip:</b> Always review the preview before executing!"
            ),
        )

        # Settings section
        self._add_section(
            content_box,
            _("Settings"),
            _(
                "Configure Jellyfix behavior:\n"
                "\n"
                "• <b>Subtitle Handling:</b> Rename variants, add language codes, remove foreign\n"
                "• <b>Kept Languages:</b> Choose which subtitle languages to keep\n"
                "• <b>Metadata:</b> Enable/disable TMDB fetching\n"
                "• <b>Quality Tags:</b> Add resolution tags to filenames\n"
                "• <b>ffprobe:</b> Use ffprobe for accurate quality detection"
            ),
        )

        # Important Notes section
        self._add_section(
            content_box,
            _("Important Notes"),
            _(
                "⚠️ <b>Dry-run is DEFAULT</b>\n"
                "Files are NOT modified unless you explicitly execute operations.\n"
                "\n"
                "✓ <b>Always review before executing</b>\n"
                "Check the operation preview carefully.\n"
                "\n"
                "🔑 <b>Configure TMDB API</b>\n"
                "For best results, configure your TMDB API key in Settings.\n"
                "\n"
                "🌍 <b>Customize kept languages</b>\n"
                "Configure which subtitle languages to keep in Preferences."
            ),
        )

        # Links section
        links_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        links_box.set_halign(Gtk.Align.CENTER)

        links_title = Gtk.Label()
        links_title.set_markup(f'<b>{_("Links")}</b>')
        links_box.append(links_title)

        homepage_button = Gtk.LinkButton(
            uri="https://github.com/talesam/jellyfix",
            label=_("Homepage")
        )
        links_box.append(homepage_button)

        issues_button = Gtk.LinkButton(
            uri="https://github.com/talesam/jellyfix/issues",
            label=_("Report Issues")
        )
        links_box.append(issues_button)

        tmdb_button = Gtk.LinkButton(
            uri="https://www.themoviedb.org/settings/api",
            label=_("Get TMDB API Key")
        )
        links_box.append(tmdb_button)

        content_box.append(links_box)

        # Add content to scrolled window
        scrolled.set_child(content_box)
        main_box.append(scrolled)

        # Set content
        self.set_content(main_box)

    def _add_section(self, parent, title, content):
        """
        Add a help section.

        Args:
            parent: Parent widget
            title: Section title
            content: Section content (markup)
        """
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<span size="large" weight="bold">{title}</span>')
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_top(10)
        parent.append(title_label)

        # Content
        content_label = Gtk.Label()
        content_label.set_markup(content.strip())
        content_label.set_wrap(True)
        content_label.set_halign(Gtk.Align.START)
        content_label.set_xalign(0)
        parent.append(content_label)
