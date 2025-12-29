#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cli/__init__.py - CLI interface package
#

"""
Command-line interface (CLI) for Jellyfix.

This package provides both interactive and non-interactive CLI modes.
"""

from .app import run_cli

__all__ = ['run_cli']
