"""Busca de legenda por título (Level 2): título original do TMDB + fallback.

Cenário reportado: série em pasta com o título TRADUZIDO e
``[tmdbid-65988]``. A CLI enviava "Wynonna Earp A Maldição dos Renascidos" ao
OpenSubtitles, que indexa por "Wynonna Earp", e nada era encontrado.
Tudo aqui roda sem rede: TMDB e subliminal são mocks.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from babelfish import Language

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usr" / "share"))

import jellyfix.core.subtitle_manager as subtitle_manager  # noqa: E402
from jellyfix.core.metadata import Metadata  # noqa: E402
from jellyfix.core.subtitle_manager import SubtitleManager  # noqa: E402

TRANSLATED = "Wynonna Earp A Maldição dos Renascidos"
ORIGINAL = "Wynonna Earp"


class DummyConfig:
    kept_languages = ["por", "eng"]
    subtitle_providers = ["opensubtitlescom"]
    subtitle_extra_providers = []
    subtitle_max_pages = 1
    subtitle_timeout = 15
    opensubtitles_username = ""
    opensubtitles_password = ""
    opensubtitles_apikey = ""
    opensubtitles_accounts = []
    min_pt_words = 5


class FakeSub:
    def __init__(self, language="por", season=3, episode=1, score=0, ok=True, year=None):
        self.language = Language(language)
        self.provider_name = "opensubtitlescom"
        self.series_season = season
        self.series_episode = episode
        self.series_title = ORIGINAL
        self.year = year
        self.score = score
        self.ok = ok
        self.release = f"Wynonna.Earp.S{season:02d}E{episode:02d}.WEB-DL"


class FakePool:
    """AsyncProviderPool falso: devolve legendas por série consultada."""

    def __init__(self, catalog, queries):
        self.catalog = catalog
        self.queries = queries

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def list_subtitles(self, video, languages):
        series = getattr(video, "series", None)
        self.queries.append(series)
        return list(self.catalog.get(series, []))


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr("jellyfix.core.subtitle_manager.get_config", lambda: DummyConfig())
    manager = SubtitleManager()
    fetcher = Mock()
    fetcher.get_tvshow_by_id.return_value = Metadata(
        title=TRANSLATED, year=2016, media_type="tvshow", tmdb_id=65988, original_title=ORIGINAL
    )
    manager._metadata_fetcher = fetcher
    monkeypatch.setattr(subtitle_manager, "compute_score", lambda sub, video: sub.score)
    return manager


@pytest.fixture
def episode(tmp_path):
    season = tmp_path / f"{TRANSLATED} (2016) [tmdbid-65988]" / "Season 03"
    season.mkdir(parents=True)
    video = season / f"{TRANSLATED} - S03E01.mp4"
    video.write_bytes(b"re-encoded video: hash never matches")
    return video


def _install(monkeypatch, manager, catalog):
    queries, saved = [], []
    monkeypatch.setattr(subtitle_manager, "AsyncProviderPool", FakePool(catalog, queries))

    def fake_save(video, video_path, subs):
        saved.extend(subs)
        return {manager._subtitle_language_code(s): [video_path] for s in subs if s.ok}

    monkeypatch.setattr(manager, "_save_subtitles", fake_save)
    return queries, saved


def test_resolve_prefers_tmdb_original_title_from_pinned_folder(manager, episode):
    titles = manager.resolve_search_titles(episode, TRANSLATED, is_episode=True)

    assert titles == [ORIGINAL, TRANSLATED]
    manager._metadata_fetcher.get_tvshow_by_id.assert_called_once_with(65988)


def test_resolve_movie_uses_movie_lookup(manager, tmp_path):
    manager._metadata_fetcher.get_movie_by_id.return_value = Metadata(
        title="Cidade de Deus", year=2002, media_type="movie", tmdb_id=598, original_title="Cidade de Deus"
    )
    video = tmp_path / "Cidade de Deus (2002) [tmdbid-598]" / "Cidade de Deus (2002).mkv"

    assert manager.resolve_search_titles(video, "Cidade de Deus", is_episode=False) == ["Cidade de Deus"]
    manager._metadata_fetcher.get_movie_by_id.assert_called_once_with(598)


def test_resolve_without_tmdbid_keeps_filename_title(manager, tmp_path):
    video = tmp_path / "Wynonna.Earp.S03E01.mkv"

    assert manager.resolve_search_titles(video, ORIGINAL, is_episode=True) == [ORIGINAL]
    manager._metadata_fetcher.get_tvshow_by_id.assert_not_called()


def test_resolve_survives_tmdb_failure(manager, episode):
    manager._metadata_fetcher.get_tvshow_by_id.side_effect = RuntimeError("no API key")

    assert manager.resolve_search_titles(episode, TRANSLATED, is_episode=True) == [TRANSLATED]


def test_batch_level2_queries_original_title(monkeypatch, manager, episode):
    """O caminho da CLI: metadata_map com ``titles`` do resolvedor."""
    monkeypatch.setattr(subtitle_manager, "scan_video", lambda path: path.name)
    monkeypatch.setattr(subtitle_manager, "download_best_subtitles", lambda *a, **k: {})
    queries, _ = _install(monkeypatch, manager, {ORIGINAL: [FakeSub("por"), FakeSub("eng")]})
    titles = manager.resolve_search_titles(episode, TRANSLATED, is_episode=True)

    result = manager.download_subtitles_batch(
        [episode],
        metadata_map={episode: {
            "title": TRANSLATED, "titles": titles, "year": 2016,
            "is_episode": True, "season": 3, "episode": 1,
        }},
    )

    assert queries == [ORIGINAL]
    assert set(result[episode]) == {"por", "eng"}


def test_translated_title_is_fallback_only_for_missing_languages(monkeypatch, manager, episode):
    monkeypatch.setattr(manager, "_search_by_hash", lambda *a, **k: {})
    queries, _ = _install(monkeypatch, manager, {
        ORIGINAL: [FakeSub("eng")],
        TRANSLATED: [FakeSub("por")],
    })

    result = manager.download_subtitles(
        episode, languages=["por", "eng"], search_titles=[ORIGINAL, TRANSLATED],
        is_episode=True, season=3, episode=1,
    )

    assert set(result) == {"por", "eng"}
    assert queries == [ORIGINAL, TRANSLATED]


def test_legacy_tmdb_title_argument_still_works(monkeypatch, manager, episode):
    monkeypatch.setattr(manager, "_search_by_hash", lambda *a, **k: {})
    queries, _ = _install(monkeypatch, manager, {ORIGINAL: [FakeSub("por")]})

    result = manager.download_subtitles(
        episode, languages=["por"], tmdb_title=ORIGINAL, is_episode=True, season=3, episode=1,
    )

    assert set(result) == {"por"}
    assert queries == [ORIGINAL]


def test_other_episode_subtitle_is_rejected(monkeypatch, manager, episode):
    wrong = FakeSub("por", episode=2, score=999)
    right = FakeSub("por", episode=1, score=10)
    _, saved = _install(monkeypatch, manager, {ORIGINAL: [wrong, right]})

    result = manager._search_by_title(
        episode, ORIGINAL, 2016, {Language("por")}, is_episode=True, season=3, episode=1,
    )

    assert set(result) == {"por"}
    assert saved == [right]


def test_best_scored_subtitle_is_downloaded_first(monkeypatch, manager, episode):
    low = FakeSub("por", score=1)
    high = FakeSub("por", score=50)
    _, saved = _install(monkeypatch, manager, {ORIGINAL: [low, high]})

    manager._search_by_title(
        episode, ORIGINAL, 2016, {Language("por")}, is_episode=True, season=3, episode=1,
    )

    assert saved == [high]


def test_failed_download_tries_next_candidate(monkeypatch, manager, episode):
    broken = FakeSub("por", score=50, ok=False)
    fallback = FakeSub("por", score=10)
    _, saved = _install(monkeypatch, manager, {ORIGINAL: [broken, fallback]})

    result = manager._search_by_title(
        episode, ORIGINAL, 2016, {Language("por")}, is_episode=True, season=3, episode=1,
    )

    assert set(result) == {"por"}
    assert saved == [broken, fallback]


def test_episode_air_year_does_not_reject_newer_seasons(monkeypatch, manager, episode):
    """S04 de uma série de 2016 foi ao ar em 2020: o ano não pode descartar."""
    sub = FakeSub("por", season=4, episode=1, year=2020)
    _install(monkeypatch, manager, {ORIGINAL: [sub]})

    result = manager._search_by_title(
        episode, ORIGINAL, 2016, {Language("por")}, is_episode=True, season=4, episode=1,
    )

    assert set(result) == {"por"}


def test_movie_year_mismatch_still_rejected(monkeypatch, manager, tmp_path):
    video = tmp_path / "Movie (2016).mkv"
    video.write_bytes(b"video")
    sub = FakeSub("por", year=2001)
    sub.series_title = ""
    sub.movie_name = "Movie"
    queries, _ = _install(monkeypatch, manager, {})
    monkeypatch.setattr(
        subtitle_manager, "AsyncProviderPool",
        FakePool({None: [sub]}, queries),  # Movie não tem .series → None
    )

    assert manager._search_by_title(video, "Movie", 2016, {Language("por")}) == {}
