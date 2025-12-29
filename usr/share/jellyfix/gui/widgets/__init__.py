#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/widgets/__init__.py - Widgets package
#

"""Custom widgets for Jellyfix GUI"""

from .dashboard import DashboardView
from .preview_panel import PreviewPanel
from .operations_list import OperationsListView

__all__ = ['DashboardView', 'PreviewPanel', 'OperationsListView']
