#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/__init__.py - GUI package for Jellyfix
#

"""
Graphical User Interface (GUI) for Jellyfix using GTK4 and libadwaita.

This package provides a modern, GNOME-style interface for managing
Jellyfin libraries.
"""

from .app import JellyfixApplication

__all__ = ['JellyfixApplication']
