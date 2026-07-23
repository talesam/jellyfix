"""Tests for core/subtitle_manager.py language handling."""

import sys
from pathlib import Path

from babelfish import Language

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usr" / "share"))

from jellyfix.core.subtitle_manager import SubtitleManager, _patch_opensubtitlescom_languages


class DummyConfig:
    kept_languages = ["por", "eng"]
    subtitle_providers = ["opensubtitlescom"]
    subtitle_extra_providers = []
    subtitle_max_pages = 1
    subtitle_timeout = 15
    opensubtitles_username = ""
    opensubtitles_password = ""
    opensubtitles_apikey = ""


class DummySubtitle:
    def __init__(self, language, release_info=""):
        self.language = language
        self.release_info = release_info


def test_build_languages_uses_portugal_variant(monkeypatch):
    monkeypatch.setattr("jellyfix.core.subtitle_manager.get_config", lambda: DummyConfig())
    manager = SubtitleManager()

    langs = manager._build_languages(["por-pt"])

    assert Language("por", "PT") in langs
    assert Language("por", "BR") not in langs


def test_opensubtitlescom_provider_allows_portugal_portuguese(monkeypatch):
    import jellyfix.core.subtitle_manager as subtitle_manager
    from subliminal.providers.opensubtitlescom import OpenSubtitlesComProvider

    monkeypatch.setattr(subtitle_manager, "_OSCOM_LANGUAGES_PATCHED", False)
    OpenSubtitlesComProvider.languages.discard(Language("por", "PT"))

    _patch_opensubtitlescom_languages()

    assert Language("por", "PT") in OpenSubtitlesComProvider.languages


def test_build_languages_keeps_existing_portuguese_brazil_behavior(monkeypatch):
    monkeypatch.setattr("jellyfix.core.subtitle_manager.get_config", lambda: DummyConfig())
    manager = SubtitleManager()

    langs = manager._build_languages(["por"])

    assert Language("por") in langs
    assert Language("por", "BR") in langs
    assert Language("por", "PT") not in langs


def test_subtitle_language_code_preserves_portugal_variant(monkeypatch):
    monkeypatch.setattr("jellyfix.core.subtitle_manager.get_config", lambda: DummyConfig())
    manager = SubtitleManager()
    sub = DummySubtitle(Language("por", "PT"))

    assert manager._subtitle_language_code(sub) == "por-pt"


def test_generic_portuguese_release_stays_generic(monkeypatch):
    monkeypatch.setattr("jellyfix.core.subtitle_manager.get_config", lambda: DummyConfig())
    manager = SubtitleManager()
    sub = DummySubtitle(Language("por"), release_info="Portuguese subtitles")

    assert manager._subtitle_language_code(sub) == "por"


def test_extract_tmdb_info_cleans_raw_release_filename():
    path = Path("/tmp/a/Barba.Ensopada.De.Sangue.2025.1080p.AMZNWEB.mp4")

    assert SubtitleManager.extract_tmdb_info_from_path(path) == (
        None,
        "Barba Ensopada De Sangue",
        2025,
    )
