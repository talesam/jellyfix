#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# i18n.py - Internationalization support for Jellyfix
#

"""
Internationalization (i18n) utilities using gettext.

This module provides translation support for Jellyfix, allowing
the application to display messages in different languages.

Usage:
    from utils.i18n import _

    print(_("Scanning directory..."))
    print(_("Found %d files") % count)
"""

import gettext
import os
from pathlib import Path

# Determine locale directory
# Default for system install
locale_dir = '/usr/share/locale'

# Check if we're running from source directory
script_dir = Path(__file__).parent.parent.parent  # Go up to jellyfix root
source_locale = script_dir / 'locale'

if source_locale.exists() and source_locale.is_dir():
    # Running from source directory
    locale_dir = str(source_locale)
elif 'APPIMAGE' in os.environ or 'APPDIR' in os.environ:
    # Running from AppImage
    # i18n.py is in: usr/share/jellyfix/utils/i18n.py
    # We need to get to: usr/share/locale
    script_path = Path(__file__).resolve()  # usr/share/jellyfix/utils/i18n.py
    utils_dir = script_path.parent           # usr/share/jellyfix/utils
    jellyfix_dir = utils_dir.parent          # usr/share/jellyfix
    share_dir = jellyfix_dir.parent          # usr/share
    appimage_locale = share_dir / 'locale'   # usr/share/locale

    if appimage_locale.is_dir():
        locale_dir = str(appimage_locale)

# Configure gettext
try:
    gettext.bindtextdomain("jellyfix", locale_dir)
    gettext.textdomain("jellyfix")

    # Try to get translations
    translation = gettext.translation("jellyfix", locale_dir, fallback=True)
    _ = translation.gettext

except Exception:
    # Fallback: no translation (return string as-is)
    def _(message):
        return message


def get_locale_dir():
    """
    Get the current locale directory path.

    Returns:
        str: Path to the locale directory
    """
    return locale_dir


def set_language(lang_code):
    """
    Set the application language.

    Args:
        lang_code: Language code (e.g., 'pt_BR', 'en_US')

    Returns:
        bool: True if language was set successfully, False otherwise
    """
    global _

    try:
        translation = gettext.translation(
            "jellyfix",
            locale_dir,
            languages=[lang_code],
            fallback=True
        )
        _ = translation.gettext
        return True

    except Exception:
        return False
