"""Legendas avulsas (nome de release) associadas ao episódio pelo SxxExx.

Cenário reportado por usuário: série já organizada em
``Wynonna Earp A Maldição dos Renascidos (2016) [tmdbid-65988]/Season 03``,
vídeos já no padrão, e legendas baixadas à mão com nome de release
(``Wynonna.Earp.S03E01...ViSUM.por.srt``). O Jellyfix respondia "Nenhuma
operação necessária": o vídeo não mudava, então a legenda não tinha a quem
seguir, e o nome de release nunca é igual ao do vídeo.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from jellyfix.core.metadata import Metadata
from jellyfix.core.renamer import Renamer
from jellyfix.utils.config import Config, set_config

TITLE = "Wynonna Earp A Maldição dos Renascidos"
SERIES = f"{TITLE} (2016) [tmdbid-65988]"
RELEASES = {
    1: "Wynonna.Earp.S03E01.Blood.Red.and.Going.Down.1080p.AMZN.WEB-DL.DD+5.1.H.264-ViSUM",
    2: "Wynonna.Earp.S03E02.When.You.Call.My.Name.1080p.AMZN.WEB-DL.DD+5.1.H.264-ViSUM",
    4: "Wynonna.Earp.S03E04.No.Cure.For.Crazy.1080p.BluRay.BRip.DDP5.1.x264-ViSUM",
    5: "Wynonna.Earp.S03E05.Jolene.720p.AMZN.WEB-DL.DD+5.1.H.264-ViSUM",
}
PT_BODY = (
    "1\n00:00:01,000 --> 00:00:02,000\n"
    "que não para com uma mais muito está você ele ela\n\n"
) * 30
EN_BODY = "1\n00:00:01,000 --> 00:00:02,000\nHello there my friend\n\n" * 30


@pytest.fixture
def library(tmp_path):
    """Reproduz a pasta do vídeo: 12 episódios certos, .eng em todos, .por no E03."""
    season = tmp_path / SERIES / "Season 03"
    season.mkdir(parents=True)
    for episode in range(1, 13):
        (season / f"{TITLE} - S03E{episode:02d}.mp4").write_bytes(b"video")
        (season / f"{TITLE} - S03E{episode:02d}.eng.srt").write_text(EN_BODY)
    (season / f"{TITLE} - S03E03.por.srt").write_text(PT_BODY)
    for release in RELEASES.values():
        (season / f"{release}.por.srt").write_text(PT_BODY)
    return tmp_path, season


def _plan(work_dir: Path):
    set_config(Config(work_dir=work_dir, fetch_metadata=True, dry_run=True))
    fetcher = Mock()
    fetcher.get_tvshow_by_id.return_value = Metadata(
        title=TITLE, year=2016, media_type="tvshow", tmdb_id=65988, original_title="Wynonna Earp"
    )
    fetcher.get_movie_by_id.return_value = Metadata(
        title="Filme", year=2020, media_type="movie", tmdb_id=1
    )
    renamer = Renamer(metadata_fetcher=fetcher)
    return renamer, renamer.plan_operations(work_dir)


def _video(season: Path, episode: int, suffix: str = ".mp4") -> Path:
    return season / f"{TITLE} - S03E{episode:02d}{suffix}"


@pytest.mark.parametrize("level", ["library", "series", "season"])
def test_release_subtitles_follow_unchanged_episode(library, level):
    root, season = library
    work_dir = {"library": root, "series": season.parent, "season": season}[level]

    renamer, ops = _plan(work_dir)

    assert {(op.source.name, op.destination.name, op.operation_type) for op in ops} == {
        (f"{release}.por.srt", f"{TITLE} - S03E{episode:02d}.por.srt", "rename")
        for episode, release in RELEASES.items()
    }
    assert all(op.source != op.destination for op in ops)

    renamer.execute_operations(dry_run=False)
    _, second = _plan(work_dir)
    assert second == []  # idempotente: nenhuma operação "renomear para o mesmo nome"


def test_existing_base_subtitle_is_kept_and_release_becomes_variant(library):
    root, season = library
    (season / f"{TITLE} - S03E01.por.srt").write_text(PT_BODY)

    _, ops = _plan(root)

    by_source = {op.source.name: op for op in ops}
    op = by_source[f"{RELEASES[1]}.por.srt"]
    assert op.destination == season / f"{TITLE} - S03E01.por2.srt"
    assert not op.will_overwrite
    assert all(op.source.name != f"{TITLE} - S03E01.por.srt" for op in ops)


def test_release_goes_above_existing_variants(library):
    root, season = library
    (season / f"{TITLE} - S03E01.por.srt").write_text(PT_BODY)
    (season / f"{TITLE} - S03E01.por2.srt").write_text(PT_BODY)
    # Só a .por2 (sem .por): a fase de variantes vai promovê-la, então a avulsa
    # não pode ocupar o .por.
    (season / f"{TITLE} - S03E02.por2.srt").write_text(PT_BODY)

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert destinations[f"{RELEASES[1]}.por.srt"] == f"{TITLE} - S03E01.por3.srt"
    assert destinations[f"{RELEASES[2]}.por.srt"] == f"{TITLE} - S03E02.por3.srt"
    assert destinations[f"{TITLE} - S03E02.por2.srt"] == f"{TITLE} - S03E02.por.srt"


def test_two_releases_for_same_episode_best_quality_gets_base_name(library):
    root, season = library
    worse = season / "Wynonna.Earp.S03E01.720p.HDTV.x264-KILLERS.por.srt"
    worse.write_text(PT_BODY[: len(PT_BODY) // 10])

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert destinations[f"{RELEASES[1]}.por.srt"] == f"{TITLE} - S03E01.por.srt"
    assert destinations[worse.name] == f"{TITLE} - S03E01.por2.srt"


def test_ambiguous_episode_versions_are_not_associated(library):
    root, season = library
    _video(season, 1).rename(season / f"{TITLE} - S03E01 - 1080p.mp4")
    (season / f"{TITLE} - S03E01 - 720p.mp4").write_bytes(b"video")

    _, ops = _plan(root)

    assert all(op.source.name != f"{RELEASES[1]}.por.srt" for op in ops)
    assert any(op.source.name == f"{RELEASES[2]}.por.srt" for op in ops)


def test_multi_episode_only_matches_same_range(library):
    root, season = library
    _video(season, 1).rename(season / f"{TITLE} - S03E01-E02.mp4")
    _video(season, 2).unlink()
    (season / f"{TITLE} - S03E02.eng.srt").unlink()
    double = season / "Wynonna.Earp.S03E01E02.1080p.WEB-DL-ViSUM.por.srt"
    double.write_text(PT_BODY)

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert f"{RELEASES[1]}.por.srt" not in destinations  # S03E01 ≠ S03E01-E02
    assert f"{RELEASES[2]}.por.srt" not in destinations
    assert destinations[double.name] == f"{TITLE} - S03E01-E02.por.srt"


@pytest.mark.parametrize("flags", ["forced", "sdh", "default", "sdh.forced"])
def test_flags_are_preserved(library, flags):
    root, season = library
    subtitle = season / f"{RELEASES[1]}.por.{flags}.srt"
    (season / f"{RELEASES[1]}.por.srt").rename(subtitle)

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert destinations[subtitle.name] == f"{TITLE} - S03E01.por.{flags}.srt"


def test_foreign_release_subtitle_is_removed(library):
    root, season = library
    foreign = season / f"{RELEASES[1]}.spa.srt"
    foreign.write_text("1\n00:00:01,000 --> 00:00:02,000\nHola amigo\n")

    _, ops = _plan(root)

    delete = [op for op in ops if op.source == foreign]
    assert [op.operation_type for op in delete] == ["delete"]


def test_untagged_release_subtitle_receives_detected_language(library):
    root, season = library
    untagged = season / f"{RELEASES[1]}.srt"
    (season / f"{RELEASES[1]}.por.srt").rename(untagged)

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert destinations[untagged.name] == f"{TITLE} - S03E01.por.srt"


def test_release_subtitle_uses_destination_of_renamed_video(library):
    root, season = library
    _video(season, 6).rename(season / "Wynonna.Earp.S03E06.720p.WEB.x264.mp4")
    loose = season / "Wynonna.Earp.S03E06.Other.Release-GRP.por.srt"
    loose.write_text(PT_BODY)

    _, ops = _plan(root)

    destinations = {op.source.name: op.destination for op in ops}
    assert destinations["Wynonna.Earp.S03E06.720p.WEB.x264.mp4"] == _video(season, 6)
    assert destinations[loose.name] == season / f"{TITLE} - S03E06.por.srt"


def test_release_subtitle_does_not_steal_companion_name_of_moving_video(tmp_path):
    """A legenda que já acompanhava o vídeo tem prioridade sobre a avulsa."""
    season = tmp_path / SERIES / "Season 03"
    season.mkdir(parents=True)
    video = season / "Wynonna.Earp.S03E07.mp4"
    video.write_bytes(b"video")
    loose = season / "Wynonna.Earp.S03E07.Waiting.Room.1080p.WEB-DL-ViSUM.por.srt"
    loose.write_text(PT_BODY)
    (season / "Wynonna.Earp.S03E07.por.srt").write_text(PT_BODY)

    _, ops = _plan(tmp_path)

    destinations = {op.source.name: op.destination.name for op in ops}
    assert destinations["Wynonna.Earp.S03E07.por.srt"] == f"{TITLE} - S03E07.por.srt"
    assert destinations[loose.name] == f"{TITLE} - S03E07.por2.srt"


def test_mixed_series_folder_is_not_associated(tmp_path):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "Show A - S01E01.mkv").write_bytes(b"video")
    (folder / "Show B - S01E02.mkv").write_bytes(b"video")
    loose = folder / "Show.B.S01E01.WEB-GRP.por.srt"
    loose.write_text(PT_BODY)
    set_config(Config(work_dir=tmp_path, fetch_metadata=False, dry_run=True))

    ops = Renamer().plan_operations(tmp_path)

    assert all(op.source != loose for op in ops)


def test_movies_are_not_associated_by_episode(tmp_path):
    folder = tmp_path / "Filme (2020) [tmdbid-1]"
    folder.mkdir()
    (folder / "Filme (2020) [tmdbid-1].mkv").write_bytes(b"video")
    loose = folder / "Filme.S01E01.WEB-GRP.por.srt"
    loose.write_text(PT_BODY)

    _, ops = _plan(tmp_path)

    assert all(op.source != loose for op in ops)
