"""Busca de metadados via TMDB e TVDB"""

from pathlib import Path
from typing import Optional, Dict, List
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

    def search_movie(self, title: str, year: Optional[int] = None, interactive: bool = False) -> Optional[Metadata]:
        """
        Busca metadados de um filme.

        Args:
            title: Título do filme
            year: Ano (opcional, melhora a busca)
            interactive: Se True, permite escolher entre múltiplos resultados

        Returns:
            Metadata ou None se não encontrado
        """
        tmdb = self._init_tmdb()
        if not tmdb:
            return None

        try:
            # Limpa o título
            clean_title = self._clean_search_title(title)

            # Busca no TMDB (sem parâmetro year, filtrar depois)
            results = tmdb['movie'].search(clean_title)

            # Verifica se há resultados reais (total_results > 0)
            if not results or results.total_results == 0:
                self.logger.debug(f"Nenhum resultado para: {clean_title}")
                return None

            # Se ano foi fornecido, filtra resultados
            if year:
                filtered_results = []
                # Itera diretamente (sem slice, pois AsObj não suporta)
                count = 0
                for result in results:
                    if count >= 10:  # Verifica os 10 primeiros apenas
                        break
                    count += 1
                    if hasattr(result, 'release_date') and result.release_date:
                        match = re.search(r'^(\d{4})', result.release_date)
                        if match and int(match.group(1)) == year:
                            filtered_results.append(result)
                # Se encontrou filmes do ano, usa eles; senão usa todos os resultados
                if filtered_results:
                    results = filtered_results

            # Se modo interativo e múltiplos resultados, pede escolha
            if interactive and len(results) > 1 and self.config.interactive:
                movie = self._choose_movie_interactive(results, clean_title)
                if not movie:
                    return None
            else:
                # Pega o primeiro resultado (itera pois AsObj não suporta indexação)
                movie = None
                for result in results:
                    movie = result
                    break
                if not movie:
                    return None

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

    def search_tvshow(self, title: str, year: Optional[int] = None, interactive: bool = False) -> Optional[Metadata]:
        """
        Busca metadados de uma série.

        Args:
            title: Título da série
            year: Ano (opcional)
            interactive: Se True, permite escolher entre múltiplos resultados

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

            # Verifica se há resultados reais (total_results > 0)
            if not results or results.total_results == 0:
                self.logger.debug(f"Nenhum resultado para série: {clean_title}")
                return None

            # Se modo interativo e múltiplos resultados, pede escolha
            if interactive and len(results) > 1 and self.config.interactive:
                show = self._choose_tvshow_interactive(results, clean_title)
                if not show:
                    return None
            else:
                # Pega o primeiro resultado (ou busca por ano se fornecido)
                show = None
                if year:
                    # Itera diretamente (sem slice, pois AsObj não suporta)
                    count = 0
                    for result in results:
                        if count >= 5:  # Verifica os 5 primeiros apenas
                            break
                        count += 1
                        if hasattr(result, 'first_air_date') and result.first_air_date:
                            match = re.search(r'^(\d{4})', result.first_air_date)
                            if match and int(match.group(1)) == year:
                                show = result
                                break

                if not show:
                    # Pega o primeiro resultado iterando
                    for result in results:
                        show = result
                        break

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

    def _choose_movie_interactive(self, results: List, search_title: str):
        """
        Permite escolher interativamente entre múltiplos resultados de filme.

        Args:
            results: Lista de resultados do TMDB
            search_title: Título da busca

        Returns:
            Resultado escolhido ou None
        """
        try:
            import questionary
            from rich.console import Console
            from rich.table import Table

            console = Console()
            console.print(f"\n[yellow]⚠️  Múltiplos resultados encontrados para:[/yellow] [cyan]{search_title}[/cyan]\n")

            # Prepara opções para seleção
            choices = []
            # Itera diretamente (sem slice, pois AsObj não suporta)
            for i, movie in enumerate(results):
                if i >= 10:  # Máximo 10 resultados
                    break
                year = ""
                if hasattr(movie, 'release_date') and movie.release_date:
                    match = re.search(r'^(\d{4})', movie.release_date)
                    if match:
                        year = f" ({match.group(1)})"

                # Link do TMDB
                tmdb_link = f"https://www.themoviedb.org/movie/{movie.id}"

                # Descrição resumida
                overview = ""
                if hasattr(movie, 'overview') and movie.overview:
                    overview = movie.overview[:80] + "..." if len(movie.overview) > 80 else movie.overview

                label = f"{movie.title}{year}"
                if overview:
                    label += f" - {overview}"

                choices.append(questionary.Choice(
                    title=label,
                    value=(movie, tmdb_link)
                ))

            # Adiciona opção para pular
            choices.append(questionary.Choice(
                title="❌ Nenhum destes / Pular",
                value=None
            ))

            # Pergunta ao usuário
            from ..ui.menu import custom_style
            result = questionary.select(
                "Escolha o resultado correto:",
                choices=choices,
                style=custom_style,
                instruction="(Use ↑↓ para navegar, ENTER para confirmar)"
            ).ask()

            if result:
                selected_movie, tmdb_link = result
                console.print(f"\n[green]✓ Selecionado:[/green] {selected_movie.title}")
                console.print(f"[dim]🔗 Link: {tmdb_link}[/dim]\n")
                return selected_movie

            return None

        except ImportError:
            # Se questionary não disponível, usa o primeiro resultado
            self.logger.warning("Modo interativo não disponível. Usando primeiro resultado.")
            return results[0]
        except Exception as e:
            self.logger.error(f"Erro na escolha interativa: {e}")
            return results[0]

    def _choose_tvshow_interactive(self, results: List, search_title: str):
        """
        Permite escolher interativamente entre múltiplos resultados de série.

        Args:
            results: Lista de resultados do TMDB
            search_title: Título da busca

        Returns:
            Resultado escolhido ou None
        """
        try:
            import questionary
            from rich.console import Console

            console = Console()
            console.print(f"\n[yellow]⚠️  Múltiplos resultados encontrados para:[/yellow] [cyan]{search_title}[/cyan]\n")

            # Prepara opções para seleção
            choices = []
            # Itera diretamente (sem slice, pois AsObj não suporta)
            for i, show in enumerate(results):
                if i >= 10:  # Máximo 10 resultados
                    break
                year = ""
                if hasattr(show, 'first_air_date') and show.first_air_date:
                    match = re.search(r'^(\d{4})', show.first_air_date)
                    if match:
                        year = f" ({match.group(1)})"

                # Link do TMDB
                tmdb_link = f"https://www.themoviedb.org/tv/{show.id}"

                # Descrição resumida
                overview = ""
                if hasattr(show, 'overview') and show.overview:
                    overview = show.overview[:80] + "..." if len(show.overview) > 80 else show.overview

                label = f"{show.name}{year}"
                if overview:
                    label += f" - {overview}"

                choices.append(questionary.Choice(
                    title=label,
                    value=(show, tmdb_link)
                ))

            # Adiciona opção para pular
            choices.append(questionary.Choice(
                title="❌ Nenhum destes / Pular",
                value=None
            ))

            # Pergunta ao usuário
            from ..ui.menu import custom_style
            result = questionary.select(
                "Escolha o resultado correto:",
                choices=choices,
                style=custom_style,
                instruction="(Use ↑↓ para navegar, ENTER para confirmar)"
            ).ask()

            if result:
                selected_show, tmdb_link = result
                console.print(f"\n[green]✓ Selecionado:[/green] {selected_show.name}")
                console.print(f"[dim]🔗 Link: {tmdb_link}[/dim]\n")
                return selected_show

            return None

        except ImportError:
            # Se questionary não disponível, usa o primeiro resultado
            self.logger.warning("Modo interativo não disponível. Usando primeiro resultado.")
            return results[0]
        except Exception as e:
            self.logger.error(f"Erro na escolha interativa: {e}")
            return results[0]
