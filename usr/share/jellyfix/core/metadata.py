"""Busca de metadados via TMDB e TVDB"""

from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
import re

from ..utils.config import get_config
from ..utils.logger import get_logger


@dataclass
class Metadata:
    """Movie or TV show metadata"""
    title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    tvdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    original_title: Optional[str] = None
    overview: Optional[str] = None
    # Image paths
    poster_path: Optional[str] = None      # Relative path (e.g., '/abc123.jpg')
    backdrop_path: Optional[str] = None    # Relative path (e.g., '/xyz789.jpg')
    poster_url: Optional[str] = None       # Full CDN URL
    backdrop_url: Optional[str] = None     # Full CDN URL


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

    def _search_movie_with_fallback(self, movie_api, title: str, year: Optional[int] = None):
        """
        Busca filme com fallback incremental.
        Se não encontrar, remove palavras do final até achar.

        Args:
            movie_api: API do TMDB Movie
            title: Título limpo
            year: Ano (opcional)

        Returns:
            Resultados da busca ou None
        """
        words = title.split()
        min_words = 1  # Mínimo de palavras para tentar

        # Tenta com título completo primeiro
        for i in range(len(words), min_words - 1, -1):
            current_title = ' '.join(words[:i])

            if i < len(words):
                self.logger.debug(f"Tentando busca alternativa: '{current_title}'")

            try:
                results = movie_api.search(current_title)

                # Se encontrou resultados, retorna
                if results and hasattr(results, 'total_results') and results.total_results > 0:
                    if i < len(words):
                        self.logger.info(f"✓ Encontrado usando: '{current_title}' (removidas {len(words) - i} palavras)")
                    return results

            except Exception as e:
                self.logger.debug(f"Erro ao buscar '{current_title}': {e}")
                continue

        # Não encontrou nada
        return None

    def _search_tvshow_with_fallback(self, tv_api, title: str):
        """
        Busca série com fallback incremental.
        Se não encontrar, remove palavras do final até achar.

        Args:
            tv_api: API do TMDB TV
            title: Título limpo

        Returns:
            Resultados da busca ou None
        """
        words = title.split()
        min_words = 1  # Mínimo de palavras para tentar

        # Tenta com título completo primeiro
        for i in range(len(words), min_words - 1, -1):
            current_title = ' '.join(words[:i])

            if i < len(words):
                self.logger.debug(f"Tentando busca alternativa: '{current_title}'")

            try:
                results = tv_api.search(current_title)

                # Se encontrou resultados, retorna
                if results and hasattr(results, 'total_results') and results.total_results > 0:
                    if i < len(words):
                        self.logger.info(f"✓ Encontrado usando: '{current_title}' (removidas {len(words) - i} palavras)")
                    return results

            except Exception as e:
                self.logger.debug(f"Erro ao buscar '{current_title}': {e}")
                continue

        # Não encontrou nada
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

            # Busca incremental: tenta com título completo, depois vai removendo palavras do final
            results = self._search_movie_with_fallback(tmdb['movie'], clean_title, year)

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
            if interactive and len(results) > 1 and self.config.ask_on_multiple_results:
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

            # Build image URLs
            poster_path = getattr(movie, 'poster_path', None)
            backdrop_path = getattr(movie, 'backdrop_path', None)

            base_url = "https://image.tmdb.org/t/p"
            poster_url = f"{base_url}/w500{poster_path}" if poster_path else None
            backdrop_url = f"{base_url}/w1280{backdrop_path}" if backdrop_path else None

            return Metadata(
                title=movie.title,
                year=movie_year,
                tmdb_id=movie.id,
                imdb_id=getattr(movie, 'imdb_id', None),
                original_title=getattr(movie, 'original_title', None),
                overview=getattr(movie, 'overview', None),
                poster_path=poster_path,
                backdrop_path=backdrop_path,
                poster_url=poster_url,
                backdrop_url=backdrop_url
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

            # Busca incremental: tenta com título completo, depois vai removendo palavras do final
            results = self._search_tvshow_with_fallback(tmdb['tv'], clean_title)

            # Verifica se há resultados reais (total_results > 0)
            if not results or results.total_results == 0:
                self.logger.debug(f"Nenhum resultado para série: {clean_title}")
                return None

            # Se modo interativo e múltiplos resultados, pede escolha
            if interactive and len(results) > 1 and self.config.ask_on_multiple_results:
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

            # Build image URLs
            poster_path = getattr(show, 'poster_path', None)
            backdrop_path = getattr(show, 'backdrop_path', None)

            base_url = "https://image.tmdb.org/t/p"
            poster_url = f"{base_url}/w500{poster_path}" if poster_path else None
            backdrop_url = f"{base_url}/w1280{backdrop_path}" if backdrop_path else None

            return Metadata(
                title=show.name,
                year=show_year,
                tmdb_id=show.id,
                original_title=getattr(show, 'original_name', None),
                overview=getattr(show, 'overview', None),
                poster_path=poster_path,
                backdrop_path=backdrop_path,
                poster_url=poster_url,
                backdrop_url=backdrop_url
            )

        except Exception as e:
            self.logger.error(f"Erro ao buscar série '{title}': {e}")
            return None

    def _clean_search_title(self, title: str) -> str:
        """
        Limpa o título para busca usando heurísticas estruturais.

        Estratégia:
        1. Detecta o ano e pega apenas até ele (geralmente após o ano é lixo)
        2. Remove informações técnicas óbvias
        3. Remove grupos de release

        Args:
            title: Título original

        Returns:
            Título limpo
        """
        original = title

        # Remove informações entre colchetes e parênteses (exceto ano)
        title = re.sub(r'\[[^\]]*\]', '', title)
        title = re.sub(r'\([^\)]*(?:1080|720|480|BluRay|WEB|HDTV|DVDRip)[^\)]*\)', '', title)

        # Substitui separadores por espaços
        title = title.replace('.', ' ').replace('_', ' ').replace('-', ' ')

        # HEURÍSTICA 1: Se tem ano (1900-2099), pega apenas até o ano
        # Ex: "Movie Name 2020 1080p BluRay" -> "Movie Name 2020"
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
        if year_match:
            # Pega tudo até o final do ano
            title = title[:year_match.end()].strip()
        else:
            # HEURÍSTICA 2: Se não tem ano, detecta onde começa a parte técnica
            # Procura pela primeira ocorrência de padrões técnicos
            technical_start = None

            # Padrões que indicam início de metadados técnicos
            technical_patterns = [
                r'\b(1080p|720p|480p|2160p|4K|8K)\b',  # Resoluções
                r'\b(BluRay|BRRip|WEB-?DL|WEBRip|HDTV|DVDRip|BDRip)\b',  # Formatos
                r'\b(x264|x265|H\.?264|H\.?265|HEVC|XviD)\b',  # Codecs
                r'\b(AAC|AC3|DTS|DD|MP3|FLAC)\b',  # Áudio
                r'\b(DUAL|Dual\.?Audio)\b',  # Dual audio
            ]

            for pattern in technical_patterns:
                match = re.search(pattern, title, re.IGNORECASE)
                if match:
                    if technical_start is None or match.start() < technical_start:
                        technical_start = match.start()

            if technical_start is not None and technical_start > 0:
                title = title[:technical_start].strip()

        # Remove espaços múltiplos
        title = re.sub(r'\s+', ' ', title).strip()

        # Se ficou muito curto (< 2 palavras), usa o original limpo
        if len(title.split()) < 2:
            title = original.replace('.', ' ').replace('_', ' ')
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
            from ..cli.interactive import custom_style
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
            for result in results:
                return result
        except Exception as e:
            self.logger.error(f"Erro na escolha interativa: {e}")
            # Retorna primeiro resultado (itera pois AsObj não suporta indexação)
            for result in results:
                return result
            return None

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
            from ..cli.interactive import custom_style
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
            for result in results:
                return result
        except Exception as e:
            self.logger.error(f"Erro na escolha interativa: {e}")
            # Retorna primeiro resultado (itera pois AsObj não suporta indexação)
            for result in results:
                return result
            return None
