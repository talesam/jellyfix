"""Detector de tipo de mídia (filme vs série)"""

from pathlib import Path
from enum import Enum
from typing import Optional
from ..utils.helpers import extract_season_episode, is_video_file


class MediaType(Enum):
    """Tipo de mídia"""
    MOVIE = "movie"
    TVSHOW = "tvshow"
    UNKNOWN = "unknown"


class MediaInfo:
    """Informações sobre um arquivo de mídia"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.media_type = MediaType.UNKNOWN
        self.season: Optional[int] = None
        self.episode_start: Optional[int] = None
        self.episode_end: Optional[int] = None
        self.year: Optional[int] = None
        self.title: Optional[str] = None

        self._detect()

    def _detect(self):
        """Detecta o tipo de mídia e extrai informações"""
        if not is_video_file(self.file_path):
            return

        filename = self.file_path.stem

        # Tenta extrair informações de série
        se_info = extract_season_episode(filename)

        if se_info:
            # É uma série
            self.media_type = MediaType.TVSHOW
            self.season, self.episode_start, self.episode_end = se_info

            # Extrai o título (tudo antes do padrão de season/episode)
            import re

            # Tenta padrão S01E01
            match = re.search(r'^(.+?)\s*[Ss]\d{1,2}[Ee]\d{1,2}', filename)
            if match:
                self.title = match.group(1).strip()
            else:
                # Tenta padrão 1x01
                match = re.search(r'^(.+?)\s*\d{1,2}x\d{1,2}', filename)
                if match:
                    self.title = match.group(1).strip()
                else:
                    # Tenta padrão Book/Volume/Part/Season
                    match = re.search(r'^(.+?)\s*(?:Book|Volume|Vol|Part|Season|Temporada|Cap\.?|Ep\.?)\s*\d{1,2}', filename, re.IGNORECASE)
                    if match:
                        self.title = match.group(1).strip()
                    else:
                        # Fallback: usa o nome do arquivo sem extensão
                        self.title = filename
        else:
            # Verifica se a estrutura de pastas indica série
            parent_folder = self.file_path.parent.name.lower()

            if parent_folder.startswith('season') or parent_folder.startswith('temporada'):
                self.media_type = MediaType.TVSHOW
                # Tenta extrair número da temporada da pasta
                import re
                match = re.search(r'(\d+)', parent_folder)
                if match:
                    self.season = int(match.group(1))
            else:
                # Provavelmente é um filme
                self.media_type = MediaType.MOVIE
                self.title = filename

    def is_movie(self) -> bool:
        """Verifica se é um filme"""
        return self.media_type == MediaType.MOVIE

    def is_tvshow(self) -> bool:
        """Verifica se é uma série"""
        return self.media_type == MediaType.TVSHOW

    def __repr__(self):
        if self.is_tvshow():
            return f"MediaInfo({self.title} S{self.season:02d}E{self.episode_start:02d}, type={self.media_type.value})"
        else:
            return f"MediaInfo({self.title}, type={self.media_type.value})"


def detect_media_type(file_path: Path) -> MediaInfo:
    """
    Detecta o tipo de mídia de um arquivo.

    Args:
        file_path: Caminho do arquivo

    Returns:
        MediaInfo com informações detectadas
    """
    return MediaInfo(file_path)


def is_movie_folder(folder_path: Path) -> bool:
    """
    Verifica se uma pasta contém filmes.

    Args:
        folder_path: Caminho da pasta

    Returns:
        True se for pasta de filmes
    """
    # Verifica se tem subpastas "Season" ou arquivos com S01E01
    has_season_folders = any(
        d.name.lower().startswith(('season', 'temporada'))
        for d in folder_path.iterdir()
        if d.is_dir()
    )

    if has_season_folders:
        return False

    # Verifica arquivos de vídeo
    video_files = [f for f in folder_path.glob('*') if is_video_file(f)]

    if not video_files:
        return True  # Pasta vazia, assume filme

    # Verifica se algum arquivo tem padrão de série
    for video in video_files[:5]:  # Checa apenas primeiros 5 arquivos
        if extract_season_episode(video.stem):
            return False

    return True


def is_tvshow_folder(folder_path: Path) -> bool:
    """
    Verifica se uma pasta contém séries.

    Args:
        folder_path: Caminho da pasta

    Returns:
        True se for pasta de séries
    """
    return not is_movie_folder(folder_path)
