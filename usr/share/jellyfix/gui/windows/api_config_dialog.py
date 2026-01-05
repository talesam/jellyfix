#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/api_config_dialog.py - API Configuration dialog
#

"""
API Configuration dialog for TMDB key management.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

from ...utils.logger import get_logger
from ...utils.i18n import _
from ...utils.config_manager import ConfigManager


class APIConfigDialog(Adw.Window):
    """API Configuration dialog"""

    def __init__(self, parent):
        """
        Initialize API configuration dialog.

        Args:
            parent: Parent window
        """
        super().__init__(transient_for=parent, modal=True)

        self.logger = get_logger()
        self.config_manager = ConfigManager()

        # Window properties
        self.set_title(_("API Configuration"))
        self.set_default_size(660, 680)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build dialog UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Preferences page
        self.prefs_page = Adw.PreferencesPage()

        # TMDB Configuration group
        tmdb_group = Adw.PreferencesGroup(
            title=_("TMDB Configuration"),
            description=_("Configure The Movie Database API key")
        )

        # Current status row
        tmdb_key = self.config_manager.get_tmdb_api_key()
        status_text = _("✓ Configured") if tmdb_key else _("✗ Not configured")
        self.status_row = Adw.ActionRow(
            title=_("TMDB API Key"),
            subtitle=status_text
        )
        tmdb_group.add(self.status_row)

        # Config file path row
        config_path = str(self.config_manager.get_config_path())
        config_row = Adw.ActionRow(
            title=_("Config file"),
            subtitle=config_path
        )
        tmdb_group.add(config_row)

        self.prefs_page.add(tmdb_group)

        # Actions group
        actions_group = Adw.PreferencesGroup(
            title=_("Actions")
        )

        # Configure key button
        configure_row = Adw.ActionRow(
            title=_("Configure TMDB API Key"),
            subtitle=_("Enter your TMDB API key")
        )
        configure_button = Gtk.Button(
            label=_("Configure"),
            valign=Gtk.Align.CENTER
        )
        configure_button.add_css_class("suggested-action")
        configure_button.connect("clicked", self._on_configure_clicked)
        configure_row.add_suffix(configure_button)
        actions_group.add(configure_row)

        # View key button
        view_row = Adw.ActionRow(
            title=_("View Current Key"),
            subtitle=_("Show masked API key")
        )
        view_button = Gtk.Button(
            label=_("View"),
            valign=Gtk.Align.CENTER
        )
        view_button.connect("clicked", self._on_view_clicked)
        view_row.add_suffix(view_button)
        actions_group.add(view_row)

        # Test connection button
        test_row = Adw.ActionRow(
            title=_("Test TMDB Connection"),
            subtitle=_("Verify API key is working")
        )
        test_button = Gtk.Button(
            label=_("Test"),
            valign=Gtk.Align.CENTER
        )
        test_button.connect("clicked", self._on_test_clicked)
        test_row.add_suffix(test_button)
        actions_group.add(test_row)

        # Remove key button
        remove_row = Adw.ActionRow(
            title=_("Remove TMDB Key"),
            subtitle=_("Delete stored API key")
        )
        remove_button = Gtk.Button(
            label=_("Remove"),
            valign=Gtk.Align.CENTER
        )
        remove_button.add_css_class("destructive-action")
        remove_button.connect("clicked", self._on_remove_clicked)
        remove_row.add_suffix(remove_button)
        actions_group.add(remove_row)

        self.prefs_page.add(actions_group)

        # Help group
        help_group = Adw.PreferencesGroup(
            title=_("Help")
        )

        # How to get key button
        help_row = Adw.ActionRow(
            title=_("How to Get TMDB API Key"),
            subtitle=_("Step-by-step tutorial")
        )
        help_button = Gtk.Button(
            label=_("Tutorial"),
            valign=Gtk.Align.CENTER
        )
        help_button.connect("clicked", self._on_help_clicked)
        help_row.add_suffix(help_button)
        help_group.add(help_row)

        self.prefs_page.add(help_group)

        # Add to scrolled window
        scrolled.set_child(self.prefs_page)
        main_box.append(scrolled)

        # Set content
        self.set_content(main_box)

    def _on_configure_clicked(self, button):
        """Handle configure button click"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Configure TMDB API Key"),
            body=_("Enter your TMDB API key below")
        )

        # Add entry row
        entry = Gtk.Entry()
        entry.set_placeholder_text(_("Paste API key here"))
        entry.set_visibility(True)

        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save"))
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "save":
                api_key = entry.get_text().strip()
                if api_key:
                    self.config_manager.set_tmdb_api_key(api_key)
                    self.logger.success(f"TMDB key saved")

                    # IMPORTANT: Update the config singleton in memory
                    from ...utils.config import get_config
                    config = get_config()
                    config.tmdb_api_key = api_key

                    # Update status
                    self.status_row.set_subtitle(_("✓ Configured"))

                    # Show toast
                    toast = Adw.Toast(title=_("API key saved successfully"))
                    if hasattr(self.get_transient_for(), 'toast_overlay'):
                        self.get_transient_for().toast_overlay.add_toast(toast)

        dialog.connect("response", on_response)
        dialog.present()

    def _on_view_clicked(self, button):
        """Handle view button click"""
        key = self.config_manager.get_tmdb_api_key()

        if key:
            # Mask key
            masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"

            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Current TMDB API Key"),
                body=f"{_('Masked key')}: {masked_key}\n\n{_('Full key stored in')}: {self.config_manager.get_config_path()}"
            )
        else:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("No API Key"),
                body=_("No TMDB API key configured yet")
            )

        dialog.add_response("ok", _("OK"))
        dialog.present()

    def _on_test_clicked(self, button):
        """Handle test button click"""
        from ...core.metadata import MetadataFetcher

        key = self.config_manager.get_tmdb_api_key()
        if not key:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("No API Key"),
                body=_("Please configure TMDB API key first")
            )
            dialog.add_response("ok", _("OK"))
            dialog.present()
            return

        # Test connection
        try:
            fetcher = MetadataFetcher()
            result = fetcher.search_movie("The Matrix", 1999)

            if result:
                dialog = Adw.MessageDialog(
                    transient_for=self,
                    heading=_("✓ Connection Successful"),
                    body=_("TMDB API key is working correctly!\n\nTest search returned: {}").format(result.title)
                )
            else:
                dialog = Adw.MessageDialog(
                    transient_for=self,
                    heading=_("⚠ Connection Failed"),
                    body=_("Could not fetch data from TMDB. Please check your API key.")
                )
        except Exception as e:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("✗ Connection Error"),
                body=_("Error testing connection: {}").format(str(e))
            )

        dialog.add_response("ok", _("OK"))
        dialog.present()

    def _on_remove_clicked(self, button):
        """Handle remove button click"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Remove API Key?"),
            body=_("This will delete your stored TMDB API key. You will need to configure it again.")
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog, response):
            if response == "remove":
                self.config_manager.remove_tmdb_api_key()

                # IMPORTANT: Update the config singleton in memory
                from ...utils.config import get_config
                config = get_config()
                config.tmdb_api_key = ""

                self.status_row.set_subtitle(_("✗ Not configured"))
                self.logger.info("TMDB key removed")

                # Show toast
                toast = Adw.Toast(title=_("API key removed"))
                if hasattr(self.get_transient_for(), 'toast_overlay'):
                    self.get_transient_for().toast_overlay.add_toast(toast)

        dialog.connect("response", on_response)
        dialog.present()

    def _on_help_clicked(self, button):
        """Handle help button click"""
        help_text = _("""How to Get TMDB API Key:

1. Go to https://www.themoviedb.org/signup
2. Create a free account
3. Go to Settings → API
4. Request an API key (choose "Developer" option)
5. Fill in the required information
6. Copy the API Key (v3 auth)
7. Paste it in Jellyfix

The API key is free and allows you to:
• Fetch movie and TV show metadata
• Download posters and backdrops
• Get accurate titles and release dates
• Organize your library with TMDB IDs""")

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("How to Get TMDB API Key"),
            body=help_text
        )
        dialog.add_response("ok", _("OK"))
        dialog.present()
