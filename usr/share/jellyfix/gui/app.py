#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/app.py - Main GTK4 application
#

"""
Main GTK4 application class for Jellyfix.

This module provides the application entry point and manages
the application lifecycle.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, Gdk
from pathlib import Path
from ..utils.config import __version__
from ..utils.logger import get_logger
from ..utils.i18n import _
from .windows.main_window import JellyfixMainWindow
from .windows.preferences_window import PreferencesWindow


class JellyfixApplication(Adw.Application):
    """Main Jellyfix GTK4 application"""
    
    def __init__(self):
        """Initialize application"""
        super().__init__(
            application_id='org.talesam.jellyfix',
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        
        self.logger = get_logger()
        self.window = None
    
    def do_activate(self):
        """Activate application (create main window)"""
        # Create window if not exists
        if not self.window:
            self.window = JellyfixMainWindow(application=self)
        
        # Present window
        self.window.present()
    
    def do_startup(self):
        """Startup application (setup actions, etc)"""
        Adw.Application.do_startup(self)

        # Load CSS
        self._load_css()

        # Setup application actions
        self._setup_actions()

    def _load_css(self):
        """Load custom CSS styles"""
        try:
            # Get CSS file path
            gui_dir = Path(__file__).parent
            css_file = gui_dir / 'style.css'

            if not css_file.exists():
                self.logger.warning(f"CSS file not found: {css_file}")
                return

            # Load CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(str(css_file))

            # Apply to display
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            self.logger.debug("CSS loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load CSS: {e}")
    
    def _setup_actions(self):
        """Setup application-level actions"""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *args: self.quit())
        self.add_action(quit_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Preferences action
        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self._on_preferences)
        self.add_action(preferences_action)

        # Configure API action
        configure_api_action = Gio.SimpleAction.new("configure_api", None)
        configure_api_action.connect("activate", self._on_configure_api)
        self.add_action(configure_api_action)

        # Help action
        help_action = Gio.SimpleAction.new("help", None)
        help_action.connect("activate", self._on_help)
        self.add_action(help_action)

        # Keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
        self.set_accels_for_action("app.help", ["F1"])
    
    def _on_about(self, action, param):
        """Show about dialog"""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name=_("Jellyfix"),
            application_icon="jellyfix",
            developer_name="talesam",
            version=__version__,
            website="https://github.com/talesam/jellyfix",
            issue_url="https://github.com/talesam/jellyfix/issues",
            copyright="© 2024 talesam",
            license_type=Gtk.License.MIT_X11,
            developers=["talesam"],
            translator_credits=_("translator-credits")
        )
        about.present()
    
    def _on_preferences(self, action, param):
        """Show preferences window"""
        preferences = PreferencesWindow(self.window)
        preferences.present()

    def _on_configure_api(self, action, param):
        """Show API configuration dialog"""
        from .windows.api_config_dialog import APIConfigDialog
        dialog = APIConfigDialog(self.window)
        dialog.present()

    def _on_help(self, action, param):
        """Show help window"""
        from .windows.help_window import HelpWindow
        help_window = HelpWindow(self.window)
        help_window.present()


def run_gui():
    """
    Run the GUI application.
    
    Returns:
        Exit code
    """
    app = JellyfixApplication()
    return app.run(None)
