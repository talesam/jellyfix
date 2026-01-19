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
                lang_str = str(sub.language.alpha3)
                if lang_str not in result:
                    result[lang_str] = []
                
                # Subliminal returns the subtitles object, we need to construct the path
                # It usually saves as video_name.lang.srt
                # Let's try to find the file that was created
                
                # Construct expected filename pattern
                # This is a bit tricky because subliminal might handle naming differently
                # But generally it's video_stem.lang.srt
                expected_path = video_path.with_suffix(f".{sub.language.alpha3}.srt")
                if expected_path.exists():
                    result[lang_str].append(expected_path)
                else:
                    # Try 2-letter code if 3-letter didn't exist (though we asked for 3)
                    expected_path_2 = video_path.with_suffix(f".{sub.language.alpha2}.srt")
                    if expected_path_2.exists():
                        result[lang_str].append(expected_path_2)

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
