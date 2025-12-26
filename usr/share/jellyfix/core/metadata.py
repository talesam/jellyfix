"""Busca de metadados via TMDB e TVDB"""

from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
import re

from ..utils.config import get_config
from ..utils.logger import get_logger


@dataclass
class Metadata:
    """Metadados de um filme ou série"""
    title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    tvdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    original_title: Optional[str] = None
    overview: Optional[str] = None


class MetadataFetcher:
    """Busca metadados via TMDB e TVDB"""

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self._tmdb = None
        self._tvdb = None

    def _init_tmdb(self):
        """Inicializa cliente TMDB"""
        if self._tmdb is not None:
            return self._tmdb

        if not self.config.tmdb_api_key:
            self.logger.warning("TMDB API key não configurada. Use: export TMDB_API_KEY=sua_chave")
            return None

        try:
            from tmdbv3api import TMDb, Movie, TV

            tmdb = TMDb()
            tmdb.api_key = self.config.tmdb_api_key
            tmdb.language = 'pt-BR'

            self._tmdb = {
                'client': tmdb,
                'movie': Movie(),
                'tv': TV()
            }
            return self._tmdb

        except ImportError:
            self.logger.error("tmdbv3api não instalado. Instale com: pip install tmdbv3api")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao inicializar TMDB: {e}")
            return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Metadata]:
        """
        Busca metadados de um filme.

        Args:
            title: Título do filme
            year: Ano (opcional, melhora a busca)

        Returns:
            Metadata ou None se não encontrado
        """
        tmdb = self._init_tmdb()
        if not tmdb:
            return None

        try:
            # Limpa o título
            clean_title = self._clean_search_title(title)

            # Busca no TMDB
            if year:
                results = tmdb['movie'].search(clean_title, year=year)
            else:
                results = tmdb['movie'].search(clean_title)

            if not results:
                self.logger.debug(f"Nenhum resultado para: {clean_title}")
                return None

            # Pega o primeiro resultado
            movie = results[0]

            # Extrai ano do release_date
            movie_year = None
            if hasattr(movie, 'release_date') and movie.release_date:
                match = re.search(r'^(\d{4})', movie.release_date)
                if match:
                    movie_year = int(match.group(1))

            return Metadata(
                title=movie.title,
                year=movie_year,
                tmdb_id=movie.id,
                imdb_id=getattr(movie, 'imdb_id', None),
                original_title=getattr(movie, 'original_title', None),
                overview=getattr(movie, 'overview', None)
            )

        except Exception as e:
            self.logger.error(f"Erro ao buscar filme '{title}': {e}")
            return None

    def search_tvshow(self, title: str, year: Optional[int] = None) -> Optional[Metadata]:
        """
        Busca metadados de uma série.

        Args:
            title: Título da série
            year: Ano (opcional)

        Returns:
            Metadata ou None se não encontrado
        """
        tmdb = self._init_tmdb()
        if not tmdb:
            return None

        try:
            # Limpa o título
            clean_title = self._clean_search_title(title)

            # Busca no TMDB
            results = tmdb['tv'].search(clean_title)

            if not results:
                self.logger.debug(f"Nenhum resultado para série: {clean_title}")
                return None

            # Pega o primeiro resultado (ou busca por ano se fornecido)
            show = None
            if year:
                for result in results[:5]:  # Verifica os 5 primeiros
                    if hasattr(result, 'first_air_date') and result.first_air_date:
                        match = re.search(r'^(\d{4})', result.first_air_date)
                        if match and int(match.group(1)) == year:
                            show = result
                            break

            if not show:
                show = results[0]

            # Extrai ano
            show_year = None
            if hasattr(show, 'first_air_date') and show.first_air_date:
                match = re.search(r'^(\d{4})', show.first_air_date)
                if match:
                    show_year = int(match.group(1))

            return Metadata(
                title=show.name,
                year=show_year,
                tmdb_id=show.id,
                original_title=getattr(show, 'original_name', None),
                overview=getattr(show, 'overview', None)
            )

        except Exception as e:
            self.logger.error(f"Erro ao buscar série '{title}': {e}")
            return None

    def _clean_search_title(self, title: str) -> str:
        """
        Limpa o título para busca.

        Remove:
        - Informações de qualidade (1080p, 720p, BluRay, etc)
        - Grupos de release ([YTS], [RARBG], etc)
        - Informações extras

        Args:
            title: Título original

        Returns:
            Título limpo
        """
        # Remove informações entre colchetes e parênteses (exceto ano)
        title = re.sub(r'\[[^\]]*\]', '', title)
        title = re.sub(r'\([^\)]*(?:1080|720|480|BluRay|WEB|HDTV|DVDRip)[^\)]*\)', '', title)

        # Remove informações de qualidade comuns
        quality_patterns = [
            r'\b(1080p|720p|480p|2160p|4K)\b',
            r'\b(BluRay|BRRip|WEB-DL|WEBRip|HDTV|DVDRip|BDRip)\b',
            r'\b(x264|x265|H\.?264|H\.?265|HEVC|XviD)\b',
            r'\b(AAC|AC3|DTS|MP3|FLAC)\b',
            r'\b(5\.1|2\.0|7\.1)\b',
            r'\b(EXTENDED|UNRATED|DIRECTORS?\.CUT|REMASTERED)\b',
        ]

        for pattern in quality_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # Remove pontos e underscores
        title = title.replace('.', ' ').replace('_', ' ')

        # Remove espaços múltiplos
        title = re.sub(r'\s+', ' ', title).strip()

        return title

    def get_folder_name(self, metadata: Metadata, provider_id: bool = False) -> str:
        """
        Gera nome de pasta no padrão Jellyfin.

        Args:
            metadata: Metadados
            provider_id: Se deve incluir ID do provedor

        Returns:
            Nome da pasta formatado
        """
        if metadata.year:
            folder_name = f"{metadata.title} ({metadata.year})"
        else:
            folder_name = metadata.title

        # Adiciona ID do provedor se solicitado
        if provider_id:
            if metadata.tmdb_id:
                folder_name += f" [tmdbid-{metadata.tmdb_id}]"
            elif metadata.imdb_id:
                folder_name += f" [imdbid-{metadata.imdb_id}]"
            elif metadata.tvdb_id:
                folder_name += f" [tvdbid-{metadata.tvdb_id}]"

        return folder_name
