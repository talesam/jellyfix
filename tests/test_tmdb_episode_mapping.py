"""Conversão de numeração absoluta de release para a numeração do TMDB."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "usr" / "share"))

from jellyfix.core.renamer import map_to_tmdb_episode

# Black Clover (tmdbid-73223): especiais, temporada 1 com 170, temporada 2 com 26
BLACK_CLOVER = {0: 2, 1: 170, 2: 26}


@pytest.mark.parametrize("episode,expected", [
    # Release divide em "S03" mas mantém o número absoluto
    ((3, 103, 103), (1, 103, 103)),
    ((3, 154, 154), (1, 154, 154)),
    # Episódio absoluto que cai na temporada 2 do TMDB
    ((3, 180, 180), (2, 10, 10)),
])
def test_impossible_pair_is_mapped_as_absolute(episode, expected):
    assert map_to_tmdb_episode(*episode, BLACK_CLOVER) == expected


@pytest.mark.parametrize("episode", [
    (1, 100, 100),   # existe no TMDB: não mexe
    (2, 10, 10),
    (0, 1, 1),       # especiais
    (3, 5, 5),       # temporada inexistente, mas número baixo: ambíguo
    (3, 200, 200),   # além do total da série
])
def test_valid_or_ambiguous_pair_is_kept(episode):
    assert map_to_tmdb_episode(*episode, BLACK_CLOVER) is None


def test_without_tmdb_data_nothing_changes():
    assert map_to_tmdb_episode(3, 104, 104, {}) is None


def test_multi_episode_across_seasons_is_kept():
    assert map_to_tmdb_episode(3, 170, 171, BLACK_CLOVER) is None
