#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# core/subtitle_manager.py - Automatic subtitle downloading
#

"""
Subtitle downloading manager using Subliminal.

Handles searching and downloading subtitles from various providers
(OpenSubtitles, Podnapisi, etc.) using the Subliminal library.

Implements a 3-level search strategy:
  1. Search by video hash (exact match)
  2. Search by TMDB title/metadata (fallback)
  3. Manual search with user query (last resort)
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Any, Tuple
from dataclasses import dataclass
import re

from ..utils.logger import get_logger
from ..utils.i18n import _
from ..utils.config import get_config

try:
    from subliminal import download_best_subtitles, scan_video  # noqa: F401
    from subliminal import list_subtitles, AsyncProviderPool  # noqa: F401
    from subliminal.video import Video, Movie  # noqa: F401
    from babelfish import Language
    HAS_SUBLIMINAL = True
except ImportError:
    HAS_SUBLIMINAL = False


# Language display names mapping (ISO 639-2 to human readable)
LANGUAGE_NAMES = {
    'por': 'Português',
    'eng': 'English',
    'spa': 'Español',
    'fre': 'Français',
    'ger': 'Deutsch',
    'ita': 'Italiano',
    'jpn': '日本語',
    'kor': '한국어',
    'chi': '中文',
    'rus': 'Русский',
    'ara': 'العربية',
    'hin': 'हिन्दी',
    'tur': 'Türkçe',
    'pol': 'Polski',
    'dut': 'Nederlands',
    'swe': 'Svenska',
    'nor': 'Norsk',
    'dan': 'Dansk',
    'fin': 'Suomi',
    'gre': 'Ελληνικά',
    'heb': 'עברית',
    'tha': 'ไทย',
    'vie': 'Tiếng Việt',
    'ind': 'Bahasa Indonesia',
    'may': 'Bahasa Melayu',
    'rum': 'Română',
    'hun': 'Magyar',
    'cze': 'Čeština',
    'ukr': 'Українська',
}


@dataclass
class SubtitleResult:
    """Represents a subtitle search result for manual selection"""
    id: str
    language: str  # ISO 639-2 code (e.g., 'por', 'eng')
    provider: str
    release_name: str
    score: int
    subtitle_obj: Any  # The actual Subtitle object
    
    # Enhanced fields for better UX
    language_name: str = ""  # Human readable (e.g., "Português (Brasil)")
    language_country: str = ""  # Country variant (e.g., "BR", "PT")
    is_forced: bool = False  # Forced subtitles for foreign parts
    is_hearing_impaired: bool = False  # SDH/HI subtitles
    file_size: int = 0  # Size in bytes (0 = unknown)
    download_count: int = 0  # Popularity indicator


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
                           providers: Optional[List[str]] = None,
                           tmdb_title: Optional[str] = None,
                           tmdb_year: Optional[int] = None,
                           tmdb_id: Optional[int] = None,
                           is_episode: bool = False,
                           season: Optional[int] = None,
                           episode: Optional[int] = None,
                           min_score: int = 0) -> Dict[str, List[Path]]:
        """
        Download subtitles for a video file using multi-level search.

        Level 1: Search by video hash (exact match)
        Level 2: Search by TMDB title/metadata (if Level 1 fails)

        Args:
            video_path: Path to video file
            languages: List of languages to download (e.g., ['por', 'eng'])
                       If None, uses configured defaults.
            providers: List of providers to use (e.g., ['opensubtitles', 'podnapisi'])
                       If None, uses default providers.
            tmdb_title: Title from TMDB for fallback search
            tmdb_year: Year from TMDB for fallback search
            tmdb_id: TMDB ID for additional matching
            is_episode: Whether this is a TV episode
            season: Season number for episodes
            episode: Episode number for episodes
            min_score: Minimum score to accept subtitles (0 = accept all)

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
            if self.config.kept_languages:
                languages = self.config.kept_languages
            else:
                languages = ['por', 'eng']

        # Convert to set of Language objects
        # Special handling for Portuguese: search both 'por' (Portugal) and 'pob' (Brazil)
        langs = set()
        for lang in languages:
            if lang == "por":
                # Add both Portuguese Portugal and Portuguese Brazil
                langs.add(Language('por'))
                try:
                    # pob = Portuguese (Brazil) in OpenSubtitles
                    langs.add(Language('por', 'BR'))
                except Exception:
                    pass  # Some versions may not support country codes
            else:
                langs.add(Language(lang))
        
        self.logger.info(_("Searching subtitles for: %s (Languages: %s)") % 
                         (video_path.name, ", ".join(languages)))

        all_results = {}
        missing_langs = set(languages)  # Track languages we still need

        # Level 1: Search by hash
        result = self._search_by_hash(video_path, langs, providers, min_score)
        
        if result:
            all_results.update(result)
            # Remove found languages from missing
            missing_langs -= set(result.keys())
            self.logger.info(_("Level 1 (hash) found: %s") % ", ".join(result.keys()))
        
        # If we still have missing languages and have TMDB info, try Level 2
        if missing_langs and tmdb_title:
            self.logger.info(_("Missing languages: %s - trying TMDB title search") % 
                           ", ".join(missing_langs))
            
            # Convert missing languages to Language objects
            missing_lang_objs = {Language(lang) for lang in missing_langs}
            
            result2 = self._search_by_title(
                video_path=video_path,
                title=tmdb_title,
                year=tmdb_year,
                langs=missing_lang_objs,
                providers=providers,
                is_episode=is_episode,
                season=season,
                episode=episode,
                min_score=min_score
            )
            
            if result2:
                all_results.update(result2)
                missing_langs -= set(result2.keys())
                self.logger.info(_("Level 2 (TMDB) found: %s") % ", ".join(result2.keys()))
        
        if missing_langs:
            self.logger.info(_("Still missing: %s (try manual search)") % ", ".join(missing_langs))
        
        if not all_results:
            self.logger.info(_("No subtitles found for: %s") % video_path.name)
        
        return all_results

    def _search_by_hash(self, video_path: Path, langs: Set, 
                        providers: Optional[List[str]] = None,
                        min_score: int = 0) -> Dict[str, List[Path]]:
        """
        Level 1: Search subtitles by video file hash.
        
        This provides the most accurate match since the hash uniquely identifies the video.
        """
        try:
            # Scan video for information (hash, size, etc.)
            video = scan_video(video_path)
            
            # Download best subtitles
            subtitles = download_best_subtitles([video], langs, providers=providers,
                                                 min_score=min_score)
            
            if not subtitles or not subtitles[video]:
                return {}

            downloaded_subs = subtitles[video]
            self.logger.info(_("Found %d subtitles by hash for: %s") % 
                           (len(downloaded_subs), video_path.name))

            return self._save_subtitles(video, video_path, downloaded_subs)

        except Exception as e:
            self.logger.debug(f"Hash search failed: {e}")
            return {}

    def _search_by_title(self, video_path: Path, title: str, year: Optional[int],
                         langs: Set, providers: Optional[List[str]] = None,
                         is_episode: bool = False,
                         season: Optional[int] = None,
                         episode: Optional[int] = None,
                         min_score: int = 0) -> Dict[str, List[Path]]:
        """
        Level 2: Search subtitles by title (from TMDB metadata).
        
        Uses list_subtitles to get all candidates, then validates each one
        to ensure it matches the correct movie/show before downloading.
        """
        try:
            # Create video object from title
            if is_episode and season is not None and episode is not None:
                # Format: "Show Name S01E01.mkv"
                search_name = f"{title} S{season:02d}E{episode:02d}.mkv"
            else:
                # Format: "Movie Name (Year).mkv"
                if year:
                    search_name = f"{title} ({year}).mkv"
                else:
                    search_name = f"{title}.mkv"

            self.logger.info(f"Level 2 searching: '{search_name}' for {[lg.alpha3 for lg in langs]}")
            video = Video.fromname(search_name)
            
            # Use list_subtitles to get all candidates (more control than download_best_subtitles)
            with AsyncProviderPool(providers=providers) as pool:
                all_subtitles = pool.list_subtitles(video, langs)
            
            # Flatten results and validate each subtitle
            # Note: list_subtitles returns a list of subtitles, not a dict
            validated_subs = []
            title_lower = title.lower().strip()
            title_clean = ''.join(c for c in title_lower if c.isalnum() or c.isspace())
            
            self.logger.debug(f"Level 2: Received {len(all_subtitles)} subtitles from providers")
            
            for sub in all_subtitles:
                # Get provider name from subtitle object
                provider = getattr(sub, 'provider_name', 'unknown')
                
                # Get subtitle release info for validation
                release_info = (
                    getattr(sub, 'release_info', '') or 
                    getattr(sub, 'releases', [''])[0] if hasattr(sub, 'releases') else ''
                )
                movie_name = getattr(sub, 'movie_name', '') or getattr(sub, 'series', '') or ''
                sub_year = getattr(sub, 'year', None)
                
                # Simplified validation - be very permissive
                # Only reject if we have definitive proof it's wrong
                is_valid = True
                rejection_reason = None
                
                # Check year mismatch (only if both years are available)
                if year and sub_year and abs(year - sub_year) > 2:
                    is_valid = False
                    rejection_reason = f"year mismatch ({sub_year} vs {year})"
                
                # Check if it's clearly a different movie (if movie_name is present)
                if is_valid and movie_name:
                    movie_name_clean = ''.join(c for c in movie_name.lower() if c.isalnum() or c.isspace())
                    # Only reject if names are completely different
                    title_words = set(title_clean.split())
                    movie_words = set(movie_name_clean.split())
                    common_words = title_words & movie_words
                    # Reject only if NO words in common
                    if len(common_words) == 0 and len(title_words) > 0 and len(movie_words) > 0:
                        is_valid = False
                        rejection_reason = f"different movie: '{movie_name}'"
                
                if is_valid:
                    self.logger.debug(f"  [ACCEPT] {sub.language} from {provider}: {movie_name or release_info[:50]}")
                    validated_subs.append(sub)
                else:
                    self.logger.debug(f"  [REJECT] {sub.language} from {provider}: {rejection_reason}")
            
            if not validated_subs:
                self.logger.info(f"Level 2: No validated subtitles for '{title}' ({year})")
                return {}
            
            # Group by language and pick best for each
            best_by_lang = {}
            for sub in validated_subs:
                lang = str(sub.language.alpha3)
                # Prioritize pt-BR over pt-PT
                if lang == 'por':
                    self._get_portuguese_variant(sub)
                else:
                    pass
                
                if lang not in best_by_lang:
                    best_by_lang[lang] = sub
            
            downloaded_subs = list(best_by_lang.values())
            self.logger.info(_("Found %d validated subtitles by title for: %s") % 
                           (len(downloaded_subs), video_path.name))

            return self._save_subtitles(video, video_path, downloaded_subs)

        except Exception as e:
            self.logger.error(f"Title search failed: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _validate_subtitle_match(self, title: str, year: Optional[int],
                                  sub_movie_name: str, sub_year: Optional[int],
                                  release_info: str, is_episode: bool = False,
                                  season: Optional[int] = None,
                                  episode: Optional[int] = None) -> bool:
        """
        Validate if a subtitle matches the target movie/show.
        
        Returns True if the subtitle is likely for the correct content.
        Uses relaxed matching - accepts when we can't definitively reject.
        """
        title_lower = title.lower().strip()
        # Remove special characters for matching
        title_clean = ''.join(c for c in title_lower if c.isalnum() or c.isspace())
        
        # If we have a movie name from the subtitle, check it
        if sub_movie_name:
            sub_name_lower = sub_movie_name.lower().strip()
            sub_name_clean = ''.join(c for c in sub_name_lower if c.isalnum() or c.isspace())
            
            # Direct match or partial match
            if title_clean in sub_name_clean or sub_name_clean in title_clean:
                # Year must match if both are available (within 1 year tolerance)
                if year and sub_year and abs(year - sub_year) > 1:
                    return False
                return True
            
            # Use similarity ratio for fuzzy matching (lowered threshold)
            similarity = self._title_similarity(title_clean, sub_name_clean)
            if similarity >= 0.5:  # Lowered from 0.8 to be more permissive
                if year and sub_year and abs(year - sub_year) > 1:
                    return False
                return True
        
        # Fallback: Check release info for title words
        if release_info:
            release_lower = release_info.lower()
            release_clean = ''.join(c for c in release_lower if c.isalnum() or c.isspace())
            
            # Check if significant title words appear in release info
            title_words = [w for w in title_clean.split() if len(w) > 2]
            if title_words:
                words_found = sum(1 for w in title_words if w in release_clean)
                match_ratio = words_found / len(title_words) if title_words else 0
                
                # Accept if at least 40% of words match (relaxed from 60%)
                if match_ratio >= 0.4:
                    # For movies, prefer year match but don't require it
                    if year and str(year) in release_info:
                        return True
                    elif year and (str(year - 1) in release_info or str(year + 1) in release_info):
                        return True
                    elif not year:
                        return True
                    # Year in title but not in release - still accept if good word match
                    elif match_ratio >= 0.6:
                        return True
        
        # For episodes, require season/episode match
        if is_episode and season is not None and episode is not None:
            season_ep_pattern = f"s{season:02d}e{episode:02d}"
            if release_info and season_ep_pattern in release_info.lower():
                return True
            return False
        
        # If we have no info to validate, ACCEPT by default (changed from reject)
        # This allows subtitles through when providers don't give us metadata
        # The user can still see and choose from the results
        if not sub_movie_name and not release_info:
            return True
        
        return False
    
    def _title_similarity(self, a: str, b: str) -> float:
        """Calculate simple similarity ratio between two strings."""
        if not a or not b:
            return 0.0
        
        # Use set intersection of words
        words_a = set(a.split())
        words_b = set(b.split())
        
        if not words_a or not words_b:
            return 0.0
        
        intersection = words_a & words_b
        union = words_a | words_b
        
        return len(intersection) / len(union) if union else 0.0
    
    def _get_portuguese_variant(self, sub) -> str:
        """
        Detect if Portuguese subtitle is pt-BR or pt-PT.
        Returns 'por-br' or 'por-pt' for prioritization.
        """
        release_info = (
            getattr(sub, 'release_info', '') or 
            getattr(sub, 'releases', [''])[0] if hasattr(sub, 'releases') else ''
        ).lower()
        
        # Check for Brazilian Portuguese indicators
        br_indicators = ['brazil', 'brasileiro', 'br', 'pt-br', 'ptbr', 'bra']
        pt_indicators = ['portugal', 'português', 'pt-pt', 'ptpt', 'por']
        
        for indicator in br_indicators:
            if indicator in release_info:
                return 'por-br'
        
        for indicator in pt_indicators:
            if indicator in release_info:
                return 'por-pt'
        
        # Default to generic Portuguese
        return 'por'
    
    def _get_language_display_info(self, sub) -> Tuple[str, str]:
        """
        Get human-readable language name and country code from subtitle.
        
        Args:
            sub: Subtitle object
            
        Returns:
            Tuple of (language_name, country_code)
            e.g., ("Português (Brasil)", "BR") or ("English", "")
        """
        lang_code = str(sub.language.alpha3)
        base_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
        
        # Get release info for country detection
        release_info = (
            getattr(sub, 'release_info', '') or ''
        ).lower()
        if not release_info and hasattr(sub, 'releases') and sub.releases:
            release_info = (sub.releases[0] or '').lower()
        
        country = ""
        
        # Detect Portuguese variant
        if lang_code == 'por':
            br_indicators = ['brazil', 'brasileiro', 'br ', 'pt-br', 'ptbr', 'bra ', '(br)', '[br]']
            pt_indicators = ['portugal', 'pt-pt', 'ptpt', '(pt)', '[pt]']
            
            for indicator in br_indicators:
                if indicator in release_info:
                    country = "BR"
                    base_name = "Português (Brasil)"
                    break
            else:
                for indicator in pt_indicators:
                    if indicator in release_info:
                        country = "PT"
                        base_name = "Português (Portugal)"
                        break
        
        # Detect Spanish variant
        elif lang_code == 'spa':
            lat_indicators = ['latino', 'lat ', 'latinoamerica', 'latam', 'spanish-lat', 'mexico', 'mx']
            esp_indicators = ['spain', 'españa', 'castellano', 'spanish-es', '(es)', '[es]']
            
            for indicator in lat_indicators:
                if indicator in release_info:
                    country = "LAT"
                    base_name = "Español (Latino)"
                    break
            else:
                for indicator in esp_indicators:
                    if indicator in release_info:
                        country = "ES"
                        base_name = "Español (España)"
                        break
        
        # Detect English variant
        elif lang_code == 'eng':
            us_indicators = ['english-us', 'en-us', '(us)', '[us]', 'american']
            uk_indicators = ['english-uk', 'en-gb', '(uk)', '[uk]', 'british']
            
            for indicator in us_indicators:
                if indicator in release_info:
                    country = "US"
                    base_name = "English (US)"
                    break
            else:
                for indicator in uk_indicators:
                    if indicator in release_info:
                        country = "UK"
                        base_name = "English (UK)"
                        break
        
        return base_name, country

    def search_subtitles_manual(self, query: str, 
                                languages: Optional[List[str]] = None,
                                is_episode: bool = False,
                                season: Optional[int] = None,
                                episode: Optional[int] = None,
                                year: Optional[int] = None,
                                providers: Optional[List[str]] = None) -> List[SubtitleResult]:
        """
        Level 3: Manual search - returns list of subtitles for user selection.
        
        Args:
            query: Search term (movie/show title)
            languages: Languages to search for
            is_episode: Whether searching for TV episode
            season: Season number for episodes
            episode: Episode number for episodes
            year: Year for movies
            providers: Providers to use
            
        Returns:
            List of SubtitleResult for user to choose from
        """
        if not self.is_available():
            return []

        # Default languages if not provided
        if not languages:
            if self.config.kept_languages:
                languages = self.config.kept_languages
            else:
                languages = ['por', 'eng']

        # Convert to set of Language objects
        # Special handling for Portuguese: search both 'por' (Portugal) and 'pob' (Brazil)
        langs = set()
        for lang in languages:
            if lang == "por":
                langs.add(Language('por'))
                try:
                    langs.add(Language('por', 'BR'))  # pob = Portuguese Brazil
                except Exception:
                    pass
            else:
                langs.add(Language(lang))
        
        try:
            # Create video from query
            if is_episode and season is not None and episode is not None:
                search_name = f"{query} S{season:02d}E{episode:02d}.mkv"
            else:
                if year:
                    search_name = f"{query} ({year}).mkv"
                else:
                    search_name = f"{query}.mkv"
            
            self.logger.info(_("Manual search: %s") % search_name)
            video = Video.fromname(search_name)
            
            # List all subtitles (not just best)
            with AsyncProviderPool(providers=providers) as pool:
                all_subtitles = pool.list_subtitles(video, langs)
            
            # Create results from list
            # Note: list_subtitles returns a list of Subtitle objects, not a dict
            results = []
            for sub in all_subtitles:
                # Get provider name from subtitle object
                provider = getattr(sub, 'provider_name', 'unknown')
                
                # Get release name (clean it up)
                release = getattr(sub, 'release_info', '') or ''
                if not release and hasattr(sub, 'releases') and sub.releases:
                    release = sub.releases[0] if sub.releases else ''
                if not release:
                    # Try movie_name as fallback
                    release = getattr(sub, 'movie_name', '') or getattr(sub, 'series', '') or ''
                if not release:
                    release = _("Unknown release")
                
                # Get language info
                lang_code = str(sub.language.alpha3)
                lang_name, lang_country = self._get_language_display_info(sub)
                
                # Detect forced/hearing impaired from release info
                release_lower = release.lower() if release else ''
                is_forced = any(x in release_lower for x in ['forced', 'forçada', 'forçado'])
                is_hi = any(x in release_lower for x in ['sdh', 'hi ', 'hearing', 'cc', 'closed caption'])
                
                # Get file size if available
                file_size = getattr(sub, 'size', 0) or 0
                
                # Get download count if available (popularity)
                download_count = getattr(sub, 'download_count', 0) or 0
                
                results.append(SubtitleResult(
                    id=str(getattr(sub, 'id', hash(sub))),
                    language=lang_code,
                    provider=str(provider),
                    release_name=str(release)[:150],  # Truncate long names
                    score=0,
                    subtitle_obj=sub,
                    language_name=lang_name,
                    language_country=lang_country,
                    is_forced=is_forced,
                    is_hearing_impaired=is_hi,
                    file_size=file_size,
                    download_count=download_count
                ))
            
            # Sort by language, then by download count (popularity), then provider
            results.sort(key=lambda x: (x.language, -x.download_count, x.provider, x.release_name))
            
            self.logger.info(_("Found %d subtitles in manual search") % len(results))
            return results
            
        except Exception as e:
            self.logger.error(f"Manual search failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def download_selected_subtitle(self, subtitle_result: SubtitleResult, 
                                   video_path: Path) -> Optional[Path]:
        """
        Download a specific subtitle selected by user.
        
        Args:
            subtitle_result: The SubtitleResult chosen by user
            video_path: Path to save subtitle next to
            
        Returns:
            Path to downloaded subtitle or None
        """
        if not self.is_available():
            return None
            
        try:
            sub = subtitle_result.subtitle_obj
            
            # Download subtitle content
            from subliminal import download_subtitles
            download_subtitles([sub])
            
            if not sub.content:
                self.logger.error("Failed to download subtitle content")
                return None
            
            # Save to file
            lang = subtitle_result.language
            subtitle_path = video_path.with_suffix(f".{lang}.srt")
            
            # Handle encoding
            encoding = getattr(sub, 'encoding', None) or 'utf-8'
            try:
                content = sub.content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # Fallback to chardet
                import chardet
                detected = chardet.detect(sub.content)
                content = sub.content.decode(detected.get('encoding', 'utf-8'), errors='replace')
            
            subtitle_path.write_text(content, encoding='utf-8')
            self.logger.info(_("Downloaded subtitle: %s") % subtitle_path.name)
            
            return subtitle_path
            
        except Exception as e:
            self.logger.error(f"Failed to download selected subtitle: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_subtitles(self, video, video_path: Path, 
                        downloaded_subs: List) -> Dict[str, List[Path]]:
        """Save downloaded subtitles and normalize language codes to 3-letter format.
        
        Note: We download content manually and save to video_path location to ensure
        the subtitle is saved next to the actual video file, not where subliminal
        thinks the video is (which may be wrong for Level 2 virtual videos).
        """
        from subliminal import download_subtitles as subliminal_download
        
        result = {}
        
        for sub in downloaded_subs:
            try:
                # Download subtitle content if not already downloaded
                if not sub.content:
                    subliminal_download([sub])
                
                if not sub.content:
                    self.logger.warning(f"Failed to download subtitle content for {sub}")
                    continue
                
                # Always aim for 3-letter code (por, eng)
                lang_alpha3 = str(sub.language.alpha3)
                str(sub.language.alpha2)
                
                if lang_alpha3 not in result:
                    result[lang_alpha3] = []
                
                # Save directly to video_path location with 3-letter code
                subtitle_path = video_path.with_suffix(f".{lang_alpha3}.srt")
                
                # Handle encoding
                encoding = getattr(sub, 'encoding', None) or 'utf-8'
                try:
                    content = sub.content.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    # Fallback to chardet
                    try:
                        import chardet
                        detected = chardet.detect(sub.content)
                        content = sub.content.decode(detected.get('encoding', 'utf-8'), errors='replace')
                    except Exception:
                        content = sub.content.decode('utf-8', errors='replace')
                
                # Write to file
                subtitle_path.write_text(content, encoding='utf-8')
                self.logger.info(f"Saved subtitle: {subtitle_path.name}")
                
                result[lang_alpha3].append(subtitle_path)
                
            except Exception as e:
                self.logger.error(f"Failed to save subtitle: {e}")
                import traceback
                traceback.print_exc()

        return result

    def list_providers(self) -> List[str]:
        """List available subtitle providers"""
        if not self.is_available():
            return []
        
        try:
            from subliminal.extensions import provider_manager
            return [p.name for p in provider_manager]
        except ImportError:
            return []

    @staticmethod
    def extract_tmdb_info_from_path(path: Path) -> Tuple[Optional[int], Optional[str], Optional[int]]:
        """
        Extract TMDB ID, title and year from a file path.
        
        Looks for patterns like:
        - [tmdbid-12345]
        - Movie Name (2020)
        
        Returns:
            Tuple of (tmdb_id, title, year)
        """
        path_str = str(path)
        
        # Extract TMDB ID
        tmdb_match = re.search(r'\[tmdbid-(\d+)\]', path_str)
        tmdb_id = int(tmdb_match.group(1)) if tmdb_match else None
        
        # Extract title and year from filename or folder
        # Pattern: "Title (Year)" or "Title (Year) [tmdbid-XXX]"
        name = path.stem if path.is_file() else path.name
        
        # Remove quality tags and other noise
        name = re.sub(r'\s*-\s*(2160p|1080p|720p|480p|4K|BluRay|WEB-DL|HDRip).*', '', name)
        name = re.sub(r'\s*\[tmdbid-\d+\].*', '', name)
        
        # Extract year
        year_match = re.search(r'\((\d{4})\)', name)
        year = int(year_match.group(1)) if year_match else None
        
        # Extract title (before the year)
        if year_match:
            title = name[:year_match.start()].strip()
        else:
            title = name.strip()
        
        return tmdb_id, title, year
