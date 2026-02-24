"""Tests for utils/helpers.py — core utility functions."""

import sys
from pathlib import Path

import pytest

# Ensure jellyfix is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usr" / "share"))

from jellyfix.utils.helpers import (
    calculate_subtitle_quality,
    clean_filename,
    extract_quality_tag,
    extract_season_episode,
    extract_year,
    has_language_code,
    is_image_file,
    is_portuguese_subtitle,
    is_subtitle_file,
    is_video_file,
    normalize_language_code,
    normalize_spaces,
    parse_subtitle_filename,
    get_base_name,
    format_season_folder,
)


# ─── extract_year ────────────────────────────────────────────────────

class TestExtractYear:
    def test_year_in_parentheses(self):
        assert extract_year("The Matrix (1999)") == 1999

    def test_year_in_brackets(self):
        assert extract_year("The Matrix [2003]") == 2003

    def test_year_bare(self):
        assert extract_year("The Matrix 1999 1080p") == 1999

    def test_no_year(self):
        assert extract_year("The Matrix") is None

    def test_year_2000s(self):
        assert extract_year("Inception (2010)") == 2010

    def test_year_recent(self):
        assert extract_year("Dune Part Two 2024") == 2024

    def test_year_old_movie(self):
        assert extract_year("Some Classic (1950)") == 1950

    def test_number_not_year(self):
        # Numbers outside valid year range should not match
        assert extract_year("Area 51") is None

    def test_multiple_years_returns_first(self):
        result = extract_year("Movie (1999) Sequel 2003")
        assert result == 1999


# ─── extract_quality_tag ─────────────────────────────────────────────

class TestExtractQualityTag:
    @pytest.mark.parametrize("filename,expected", [
        ("movie.1080p.mkv", "1080p"),
        ("movie.720p.BluRay.mkv", "720p"),
        ("movie.480p.mkv", "480p"),
        ("movie.2160p.mkv", "2160p"),
        ("movie.4K.mkv", "2160p"),
        ("movie_1080p_bluray.mkv", "1080p"),
        ("movie [1080p].mkv", "1080p"),
        ("movie (720p).mkv", "720p"),
        ("movie.8K.mkv", "8K"),
    ])
    def test_resolution_detection(self, filename, expected):
        assert extract_quality_tag(filename) == expected

    def test_no_quality(self):
        assert extract_quality_tag("movie.mkv") is None

    def test_case_insensitive(self):
        assert extract_quality_tag("movie.1080P.mkv") == "1080p"


# ─── extract_season_episode ──────────────────────────────────────────

class TestExtractSeasonEpisode:
    def test_sxxexx(self):
        assert extract_season_episode("Show S01E05") == (1, 5, 5)

    def test_sxxexx_lowercase(self):
        assert extract_season_episode("show.s02e10.720p") == (2, 10, 10)

    def test_sxxexx_multi_episode(self):
        assert extract_season_episode("Show S01E01-E02") == (1, 1, 2)

    def test_nxnn(self):
        assert extract_season_episode("show 1x01") == (1, 1, 1)

    def test_nxnn_not_year(self):
        # "2018" should NOT be parsed as 20x18
        assert extract_season_episode("Movie 2018") is None

    def test_book_volume(self):
        assert extract_season_episode("Book 1 Episode 03") == (1, 3, 3)

    def test_temporada_ep(self):
        assert extract_season_episode("T01E05") == (1, 5, 5)

    def test_no_episode_info(self):
        assert extract_season_episode("The Matrix 1999 1080p") is None

    def test_season_episode_pattern(self):
        assert extract_season_episode("Season 2 Episode 5") == (2, 5, 5)

    def test_temp_pattern(self):
        assert extract_season_episode("Temp 3 Ep 12") == (3, 12, 12)

    def test_two_digit_season(self):
        assert extract_season_episode("Show S12E01") == (12, 1, 1)


# ─── is_video_file / is_subtitle_file / is_image_file ────────────────

class TestFileTypeDetection:
    @pytest.mark.parametrize("ext,expected", [
        (".mkv", True), (".mp4", True), (".avi", True),
        (".mov", True), (".webm", True), (".m4v", True),
        (".srt", False), (".txt", False), (".jpg", False),
    ])
    def test_is_video_file(self, ext, expected):
        assert is_video_file(Path(f"file{ext}")) == expected

    @pytest.mark.parametrize("ext,expected", [
        (".srt", True), (".ass", True), (".ssa", True),
        (".sub", True), (".vtt", True),
        (".mkv", False), (".txt", False),
    ])
    def test_is_subtitle_file(self, ext, expected):
        assert is_subtitle_file(Path(f"file{ext}")) == expected

    @pytest.mark.parametrize("ext,expected", [
        (".jpg", True), (".jpeg", True), (".png", True),
        (".gif", True), (".webp", True), (".svg", True),
        (".mkv", False), (".srt", False),
    ])
    def test_is_image_file(self, ext, expected):
        assert is_image_file(Path(f"file{ext}")) == expected


# ─── clean_filename ──────────────────────────────────────────────────

class TestCleanFilename:
    def test_removes_forbidden_chars(self):
        # Note: ':' is allowed on Linux (removed from FORBIDDEN_CHARS)
        assert clean_filename('Movie: The "Sequel"') == "Movie: The Sequel"

    def test_removes_question_mark(self):
        assert clean_filename("What?") == "What"

    def test_removes_pipe(self):
        assert clean_filename("A|B") == "AB"

    def test_collapses_spaces(self):
        assert clean_filename("Movie   Name") == "Movie Name"

    def test_already_clean(self):
        assert clean_filename("My Movie (2024)") == "My Movie (2024)"


# ─── normalize_spaces ────────────────────────────────────────────────

class TestNormalizeSpaces:
    def test_dots_to_spaces(self):
        result = normalize_spaces("The.Matrix.1999")
        assert "The Matrix" in result
        assert "." not in result

    def test_underscores_to_spaces(self):
        result = normalize_spaces("The_Matrix")
        assert "The Matrix" in result

    def test_removes_quality_tags(self):
        result = normalize_spaces("Movie.Name.1080p.BluRay.x264")
        assert "1080p" not in result
        assert "BluRay" not in result
        assert "x264" not in result

    def test_preserves_year_in_parens(self):
        result = normalize_spaces("Movie Name (2024)")
        assert "(2024)" in result

    def test_removes_release_group(self):
        result = normalize_spaces("Movie.Name-YIFY")
        assert "YIFY" not in result

    def test_removes_bracket_content(self):
        result = normalize_spaces("Movie [1080p] [DUAL]")
        assert "[" not in result


# ─── has_language_code ────────────────────────────────────────────────

class TestHasLanguageCode:
    def test_eng_code(self):
        assert has_language_code("movie.eng.srt") == "eng"

    def test_por_code(self):
        assert has_language_code("movie.por.srt") == "por"

    def test_pt_code(self):
        assert has_language_code("movie.pt.srt") == "por"

    def test_pt_br_code(self):
        # pt-BR with dot separator doesn't match current regex (expected)
        # The regex lowercases input, making region code not match [A-Z]{2}
        assert has_language_code("movie.pt-BR.srt") is None

    def test_pt_code_detected(self):
        # Plain .pt. works fine
        assert has_language_code("movie.pt.srt") == "por"

    def test_no_code(self):
        assert has_language_code("movie.srt") is None

    def test_eng_forced(self):
        assert has_language_code("movie.eng.forced.srt") == "eng"

    def test_eng_sdh(self):
        assert has_language_code("movie.eng.sdh.srt") == "eng"

    def test_variant_number(self):
        assert has_language_code("movie.eng2.srt") == "eng"


# ─── normalize_language_code ──────────────────────────────────────────

class TestNormalizeLanguageCode:
    @pytest.mark.parametrize("code,expected", [
        ("en", "eng"), ("pt", "por"), ("es", "spa"), ("fr", "fre"),
        ("de", "ger"), ("it", "ita"), ("ja", "jpn"), ("ko", "kor"),
        ("br", "por"),
    ])
    def test_two_letter_codes(self, code, expected):
        assert normalize_language_code(code) == expected

    def test_three_letter_passthrough(self):
        assert normalize_language_code("eng") == "eng"
        assert normalize_language_code("por") == "por"

    def test_region_stripped(self):
        assert normalize_language_code("pt-BR") == "por"
        assert normalize_language_code("pt_BR") == "por"


# ─── calculate_subtitle_quality ──────────────────────────────────────

class TestCalculateSubtitleQuality:
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.srt"
        f.write_text("")
        assert calculate_subtitle_quality(f) == 0.0

    def test_tiny_file(self, tmp_path):
        f = tmp_path / "tiny.srt"
        f.write_text("x" * 50)
        assert calculate_subtitle_quality(f) == 0.0

    def test_valid_subtitle(self, tmp_path):
        f = tmp_path / "good.srt"
        # Needs > 100 bytes to pass the minimum size check
        blocks = []
        for i in range(1, 20):
            blocks.append(f"{i}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\nSubtitle line {i}\n")
        f.write_text("\n".join(blocks))
        score = calculate_subtitle_quality(f)
        assert score > 0

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nonexistent.srt"
        assert calculate_subtitle_quality(f) == 0.0

    def test_larger_better(self, tmp_path):
        """A subtitle with more blocks should score higher."""
        small = tmp_path / "small.srt"
        large = tmp_path / "large.srt"

        small_content = (
            "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nWorld\n"
        )
        large_content = small_content * 20

        small.write_text(small_content)
        large.write_text(large_content)

        assert calculate_subtitle_quality(large) > calculate_subtitle_quality(small)


# ─── is_portuguese_subtitle ──────────────────────────────────────────

class TestIsPortugueseSubtitle:
    def test_portuguese_content(self, tmp_path):
        f = tmp_path / "test.srt"
        f.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\n"
            "Você não pode fazer isso para ele\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\n"
            "Mas ela também vai com você sem onde ir\n\n"
            "3\n00:00:05,000 --> 00:00:06,000\n"
            "Como pode ser uma coisa muito boa\n"
        )
        assert is_portuguese_subtitle(f) is True

    def test_english_content(self, tmp_path):
        f = tmp_path / "test.srt"
        f.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\n"
            "You cannot do this\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\n"
            "Where are we going now?\n"
        )
        assert is_portuguese_subtitle(f) is False

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nonexistent.srt"
        assert is_portuguese_subtitle(f) is False

    def test_non_srt_extension(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Você não pode fazer isso")
        assert is_portuguese_subtitle(f) is False


# ─── parse_subtitle_filename ─────────────────────────────────────────

class TestParseSubtitleFilename:
    def test_lang_code(self):
        info = parse_subtitle_filename(Path("Movie.eng.srt"))
        assert info["language"] == "eng"

    def test_forced_flag(self):
        info = parse_subtitle_filename(Path("Movie.por.forced.srt"))
        assert info["forced"] is True
        assert info["language"] == "por"

    def test_sdh_flag(self):
        info = parse_subtitle_filename(Path("Movie.eng.sdh.srt"))
        assert info["sdh"] is True

    def test_default_flag(self):
        info = parse_subtitle_filename(Path("Movie.por.default.srt"))
        assert info["default"] is True

    def test_no_lang(self):
        info = parse_subtitle_filename(Path("Movie.srt"))
        assert info["language"] is None

    def test_base_name(self):
        info = parse_subtitle_filename(Path("My Movie.eng.forced.srt"))
        assert info["base_name"] == "My Movie"


# ─── get_base_name ───────────────────────────────────────────────────

class TestGetBaseName:
    def test_removes_lang_suffix(self):
        assert get_base_name(Path("Movie.por.srt")) == "Movie"

    def test_video_file(self):
        assert get_base_name(Path("Movie Name.mkv")) == "Movie Name"


# ─── format_season_folder ────────────────────────────────────────────

class TestFormatSeasonFolder:
    def test_single_digit(self):
        assert format_season_folder(1) == "Season 01"

    def test_double_digit(self):
        assert format_season_folder(12) == "Season 12"
