#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# core/subtitle_manager.py - Automatic subtitle downloading
#

"""
Subtitle downloading manager using Subliminal.

Handles searching and downloading subtitles from various providers
(OpenSubtitles, Podnapisi, etc.) using the Subliminal library.
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Any
import logging

from ..utils.logger import get_logger
from ..utils.i18n import _
from ..utils.config import get_config

try:
    from subliminal import download_best_subtitles, region, save_subtitles, scan_video
    from subliminal.video import Video
    from babelfish import Language
    HAS_SUBLIMINAL = True
except ImportError:
    HAS_SUBLIMINAL = False


class SubtitleManager:
    """Manages subtitle searching and downloading"""

    def __init__(self):
        """Initialize subtitle manager"""
        self.logger = get_logger()
        self.config = get_config()
        
        if not HAS_SUBLIMINAL:
            self.logger.warning("Subliminal library not found. Subtitle downloading disabled.")

    def is_available(self) -> bool:
        """Check if subtitle downloading is available (libraries installed)"""
        return HAS_SUBLIMINAL

    def download_subtitles(self, video_path: Path, languages: Optional[List[str]] = None, 
                           providers: Optional[List[str]] = None) -> Dict[str, List[Path]]:
        """
        Download subtitles for a video file.

        Args:
            video_path: Path to video file
            languages: List of languages to download (e.g., ['por', 'eng'])
                       If None, uses configured defaults.
            providers: List of providers to use (e.g., ['opensubtitles', 'podnapisi'])
                       If None, uses default providers.

        Returns:
            Dictionary mapping language code to list of downloaded subtitle paths
        """
        if not self.is_available():
            self.logger.error("Cannot download subtitles: 'subliminal' library missing.")
            return {}

        if not video_path.exists():
            self.logger.error(f"Video file not found: {video_path}")
            return {}

        # Default languages if not provided
        if not languages:
            # Prefer configured kept languages, default to por, eng if empty
            if self.config.kept_languages:
                languages = self.config.kept_languages
            else:
                languages = ['por', 'eng']

        # Convert to set of Language objects
        langs = {Language(l) for l in languages}
        
        self.logger.info(_("Searching subtitles for: %s (Languages: %s)") % 
                         (video_path.name, ", ".join(languages)))

        try:
            # Scan video for information (hash, size, etc.)
            video = scan_video(video_path)
            
            # Download best subtitles
            subtitles = download_best_subtitles([video], langs, providers=providers)
            
            if not subtitles or not subtitles[video]:
                self.logger.info(_("No subtitles found for: %s") % video_path.name)
                return {}

            downloaded_subs = subtitles[video]
            self.logger.info(_("Found %d subtitles for: %s") % (len(downloaded_subs), video_path.name))

            # Save subtitles
            # We want to save them next to the video
            # Subliminal's save_subtitles does exactly that
            saved_subtitles = save_subtitles(video, downloaded_subs)
            
            result = {}
            for sub in saved_subtitles:
                # Always aim for 3-letter code (por, eng)
                lang_alpha3 = str(sub.language.alpha3)
                lang_alpha2 = str(sub.language.alpha2)
                
                if lang_alpha3 not in result:
                    result[lang_alpha3] = []
                
                # Expected paths
                path_alpha3 = video_path.with_suffix(f".{lang_alpha3}.srt")
                path_alpha2 = video_path.with_suffix(f".{lang_alpha2}.srt")
                
                final_path = None
                
                if path_alpha3.exists():
                    # Already perfect
                    final_path = path_alpha3
                elif path_alpha2.exists():
                    # Rename 2-letter to 3-letter
                    try:
                        path_alpha2.rename(path_alpha3)
                        self.logger.info(f"Renamed subtitle: {path_alpha2.name} -> {path_alpha3.name}")
                        final_path = path_alpha3
                    except Exception as e:
                        self.logger.error(f"Failed to rename subtitle {path_alpha2.name}: {e}")
                        final_path = path_alpha2
                
                if final_path:
                    result[lang_alpha3].append(final_path)

            return result

        except Exception as e:
            self.logger.error(_("Error downloading subtitles: %s") % e)
            return {}

    def list_providers(self) -> List[str]:
        """List available subtitle providers"""
        if not self.is_available():
            return []
        
        # This is a bit hacky to get providers list from subliminal
        # usually they are registered entry points
        try:
            from subliminal.extensions import provider_manager
            return [p.name for p in provider_manager]
        except ImportError:
            return []
