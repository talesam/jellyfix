"""Sistema de renomeação de arquivos para padrão Jellyfin"""

from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import re
import shutil

from ..utils.helpers import (
    clean_filename, normalize_spaces, extract_year,
    extract_season_episode, format_season_folder,
    is_video_file, is_subtitle_file, parse_subtitle_filename,
    calculate_subtitle_quality
)
from ..utils.config import get_config
from ..utils.logger import get_logger
from .detector import detect_media_type, MediaType
from .metadata import MetadataFetcher


@dataclass
class RenameOperation:
    """Representa uma operação de renomeação"""
    source: Path
    destination: Path
    operation_type: str  # 'rename', 'move', 'delete'
    reason: str

    @property
    def will_overwrite(self) -> bool:
        """Verifica se vai sobrescrever um arquivo existente"""
        return self.destination.exists() and self.source != self.destination


class Renamer:
    """Gerenciador de renomeação de arquivos"""

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.operations: List[RenameOperation] = []
        self.metadata_fetcher = MetadataFetcher() if self.config.fetch_metadata else None

    def plan_operations(self, directory: Path) -> List[RenameOperation]:
        """
        Planeja todas as operações de renomeação.

        Args:
            directory: Diretório a processar

        Returns:
            Lista de operações planejadas
        """
        self.operations = []

        # Coleta todos os arquivos de legendas para processamento inteligente
        subtitle_files = []
        video_files = []

        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue

            if file_path.name.startswith('.'):
                continue

            # Processa vídeos
            if is_video_file(file_path):
                video_files.append(file_path)

            # Processa legendas
            elif is_subtitle_file(file_path):
                subtitle_files.append(file_path)

        # Processa vídeos
        for file_path in video_files:
            self._plan_video_rename(file_path)

        # Processa legendas de forma inteligente (2 fases)
        self._plan_subtitle_variants(subtitle_files, directory)

        return self.operations

    def _plan_video_rename(self, file_path: Path):
        """Planeja renomeação de um arquivo de vídeo"""
        media_info = detect_media_type(file_path)

        if media_info.is_movie():
            self._plan_movie_rename(file_path, media_info)
        elif media_info.is_tvshow():
            self._plan_tvshow_rename(file_path, media_info)

    def _plan_movie_rename(self, file_path: Path, media_info):
        """Planeja renomeação de um filme"""
        # Extrai informações
        title = clean_filename(normalize_spaces(media_info.title or file_path.stem))
        year = extract_year(file_path.stem)

        if not title:
            return

        # Busca metadados se configurado
        folder_suffix = ""
        if self.metadata_fetcher and self.config.fetch_metadata:
            self.logger.info(f"🔍 Buscando: {title}")
            metadata = self.metadata_fetcher.search_movie(title, year, interactive=self.config.interactive)

            if metadata:
                # Usa título e ano dos metadados
                title = clean_filename(metadata.title)
                year = metadata.year or year

                # Adiciona ID do provedor
                if metadata.tmdb_id:
                    folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"
                elif metadata.imdb_id:
                    folder_suffix = f" [imdbid-{metadata.imdb_id}]"

                self.logger.info(f"✓ Encontrado: {title} ({year}) [ID: {metadata.tmdb_id}]")
            else:
                self.logger.warning(f"✗ Não encontrado: {title}")

        # Formato: "Nome do Filme (YYYY).ext"
        if year:
            new_name = f"{title} ({year}){file_path.suffix}"
        else:
            new_name = f"{title}{file_path.suffix}"

        # Verifica se está na pasta correta
        parent_folder = file_path.parent.name
        expected_folder = f"{title} ({year}){folder_suffix}" if year else f"{title}{folder_suffix}"

        # Define destino
        if parent_folder != expected_folder:
            # Precisa mover para pasta correta
            new_folder = file_path.parent.parent / expected_folder
            new_path = new_folder / new_name
        else:
            # Apenas renomeia
            new_path = file_path.parent / new_name

        if new_path != file_path:
            # Detecta o tipo de operação com mais precisão
            pasta_mudou = new_path.parent != file_path.parent
            nome_mudou = new_path.name != file_path.name

            if pasta_mudou and nome_mudou:
                op_type = 'move_rename'
            elif pasta_mudou:
                op_type = 'move'
            else:
                op_type = 'rename'

            self.operations.append(RenameOperation(
                source=file_path,
                destination=new_path,
                operation_type=op_type,
                reason=f"Padronizar nome de filme: {file_path.name} → {new_name}"
            ))

    def _plan_tvshow_rename(self, file_path: Path, media_info):
        """Planeja renomeação de um episódio de série"""
        if media_info.season is None or media_info.episode_start is None:
            return

        title = clean_filename(normalize_spaces(media_info.title or file_path.stem))

        if not title:
            return

        # Busca metadados se configurado
        folder_suffix = ""
        year = None
        if self.metadata_fetcher and self.config.fetch_metadata:
            self.logger.info(f"🔍 Buscando série: {title}")
            metadata = self.metadata_fetcher.search_tvshow(title, interactive=self.config.interactive)

            if metadata:
                # Usa título dos metadados
                title = clean_filename(metadata.title)
                year = metadata.year

                # Adiciona ID do provedor
                if metadata.tmdb_id:
                    folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"
                elif metadata.tvdb_id:
                    folder_suffix = f" [tvdbid-{metadata.tvdb_id}]"
                elif metadata.imdb_id:
                    folder_suffix = f" [imdbid-{metadata.imdb_id}]"
                self.logger.info(f"✓ Encontrado: {title} ({year}) [ID: {metadata.tmdb_id}]")
            else:
                self.logger.warning(f"✗ Não encontrado: {title}")

        # Formato: "Nome da Série S01E01.ext" ou "Nome da Série S01E01-E02.ext"
        if media_info.episode_end and media_info.episode_end != media_info.episode_start:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}-E{media_info.episode_end:02d}"
        else:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}"

        new_name = f"{title} {episode_part}{file_path.suffix}"

        # Verifica estrutura de pastas
        # Esperado: SeriesFolder/Season XX/episode.mkv
        season_folder_name = format_season_folder(media_info.season)

        # Encontra a pasta da série
        if file_path.parent.name.lower().startswith('season'):
            # Já está em uma pasta de temporada
            series_folder = file_path.parent.parent
        else:
            # Não está em pasta de temporada
            series_folder = file_path.parent

        # Define o nome esperado da pasta da série (com ano e ID se encontrado metadados)
        if year:
            expected_series_folder = f"{title} ({year}){folder_suffix}"
        else:
            expected_series_folder = f"{title}{folder_suffix}"


        # Verifica se a pasta da série precisa ser renomeada
        if series_folder.name != expected_series_folder:
            # A pasta da série precisa ser renomeada
            new_series_folder = series_folder.parent / expected_series_folder
        else:
            new_series_folder = series_folder

        # Define o caminho completo do arquivo
        new_folder = new_series_folder / season_folder_name
        new_path = new_folder / new_name

        if new_path != file_path:
            # Detecta o tipo de operação com mais precisão
            pasta_mudou = new_path.parent != file_path.parent
            nome_mudou = new_path.name != file_path.name

            if pasta_mudou and nome_mudou:
                op_type = 'move_rename'
            elif pasta_mudou:
                op_type = 'move'
            else:
                op_type = 'rename'

            # Se mudou a pasta da série, inclui isso na razão
            if new_series_folder != series_folder:
                reason = f"Organizar com metadados: {series_folder.name} → {expected_series_folder}"
            else:
                reason = f"Padronizar episódio: {file_path.name} → {new_name}"

            self.operations.append(RenameOperation(
                source=file_path,
                destination=new_path,
                operation_type=op_type,
                reason=reason
            ))

    def _plan_subtitle_variants(self, subtitle_files: List[Path], directory: Path):
        """
        Processa legendas de forma inteligente em 2 fases.

        Fase 1: Renomeia variações (lang2, lang3) para lang.srt quando lang.srt não existe
        Fase 2: Remove outras variações duplicadas (se configurado)
        """
        # Organiza legendas por diretório e base name
        from collections import defaultdict

        # Agrupa: {(dir, base_name, lang_code): [lista de paths com variações]}
        grouped = defaultdict(list)

        for file_path in subtitle_files:
            filename = file_path.name.lower()

            # Pula .forced (nunca mexe)
            if '.forced.' in filename:
                # Processa outras operações em .forced
                self._plan_subtitle_other_operations(file_path)
                continue

            # Detecta variações: .lang2.srt, .lang3.srt
            variant_match = re.search(r'\.([a-z]{3})(\d)\.srt$', filename)
            if variant_match:
                lang_code = variant_match.group(1)
                variant_num = int(variant_match.group(2))
                base_name = file_path.name[:-(len(variant_match.group(0)))]

                key = (file_path.parent, base_name, lang_code)
                grouped[key].append((variant_num, file_path))
            else:
                # Não é variação, processa normalmente
                self._plan_subtitle_other_operations(file_path)

        # Processa cada grupo de variações
        for (parent_dir, base_name, lang_code), variants in grouped.items():
            # Calcula qualidade de cada variação
            scored_variants = []
            for num, path in variants:
                quality = calculate_subtitle_quality(path)
                file_size = path.stat().st_size
                scored_variants.append((quality, num, path, file_size))

                # Log de debug (apenas em modo verbose)
                self.logger.debug(
                    f"Legenda .{lang_code}{num}.srt: "
                    f"qualidade={quality:.1f}, tamanho={file_size} bytes"
                )

            # Ordena por qualidade (MELHOR primeiro, depois menor número como desempate)
            scored_variants.sort(key=lambda x: (-x[0], x[1]))

            # Verifica se existe .lang.srt (sem número)
            target_name = f"{base_name}.{lang_code}.srt"
            target_path = parent_dir / target_name

            if not target_path.exists():
                # NÃO existe .lang.srt → renomeia a MELHOR variação
                best_quality, best_num, best_path, best_size = scored_variants[0]

                # Verifica se a melhor tem qualidade > 0 (não é vazia/inválida)
                if best_quality > 0:
                    self.operations.append(RenameOperation(
                        source=best_path,
                        destination=target_path,
                        operation_type='rename',
                        reason=f"Renomear .{lang_code}{best_num}.srt para .{lang_code}.srt (melhor: {best_size} bytes, qualidade {best_quality:.0f})"
                    ))

                    # Marca as outras para remoção (se configurado)
                    if self.config.remove_language_variants and len(scored_variants) > 1:
                        for quality, num, path, size in scored_variants[1:]:
                            self.operations.append(RenameOperation(
                                source=path,
                                destination=path,
                                operation_type='delete',
                                reason=f"Remover variação .{lang_code}{num}.srt ({size} bytes, inferior)"
                            ))
                else:
                    # Todas as variações têm qualidade 0 (vazias/inválidas)
                    self.logger.warning(
                        f"Todas as variações .{lang_code}X.srt estão vazias ou inválidas - não renomeando"
                    )
            else:
                # JÁ existe .lang.srt → remove TODAS as variações (se configurado)
                if self.config.remove_language_variants:
                    for quality, num, path, size in scored_variants:
                        self.operations.append(RenameOperation(
                            source=path,
                            destination=path,
                            operation_type='delete',
                            reason=f"Remover variação .{lang_code}{num}.srt (já existe .{lang_code}.srt)"
                        ))

    def _plan_subtitle_other_operations(self, file_path: Path):
        """Outras operações de legendas (idiomas estrangeiros, sem idioma, etc.)"""
        filename = file_path.name.lower()

        # Remove legendas estrangeiras (que NÃO estão na lista de idiomas mantidos)
        if self.config.remove_foreign_subs:
            # Verifica se tem código de idioma que NÃO está na lista de mantidos
            for lang_code in self.config.all_languages.keys():
                # Pula idiomas que devem ser mantidos
                if lang_code in self.config.kept_languages:
                    continue

                # Verifica padrões: .LANG.srt, .LANG2.srt, .LANG3.srt
                pattern = rf'\.{lang_code}\d?\.srt$'
                if re.search(pattern, filename):
                    self.operations.append(RenameOperation(
                        source=file_path,
                        destination=file_path,  # Será deletado
                        operation_type='delete',
                        reason=f"Remover legenda em idioma estrangeiro ({lang_code})"
                    ))
                    return

        # 3. Adiciona código de idioma a legendas sem código
        if self.config.rename_no_lang:
            from ..utils.helpers import has_language_code, is_portuguese_subtitle

            if not has_language_code(file_path.name):
                # Verifica se é português
                if is_portuguese_subtitle(file_path, self.config.min_pt_words):
                    # Adiciona .por antes da extensão
                    new_name = f"{file_path.stem}.por{file_path.suffix}"
                    new_path = file_path.parent / new_name
                    self.operations.append(RenameOperation(
                        source=file_path,
                        destination=new_path,
                        operation_type='rename',
                        reason="Adicionar código de idioma português (.por)"
                    ))

    def execute_operations(self, dry_run: bool = True) -> Dict[str, int]:
        """
        Executa as operações planejadas.

        Args:
            dry_run: Se True, apenas simula as operações

        Returns:
            Dicionário com estatísticas
        """
        stats = {
            'renamed': 0,
            'moved': 0,
            'deleted': 0,
            'failed': 0,
            'skipped': 0,
            'cleaned': 0  # Pastas vazias removidas
        }

        # Rastreia pastas de origem para limpeza posterior
        source_folders = set()

        for operation in self.operations:
            try:
                # Verifica se vai sobrescrever
                if operation.will_overwrite:
                    self.logger.warning(
                        f"Pulando (destino existe): {operation.source.name} → {operation.destination.name}"
                    )
                    stats['skipped'] += 1
                    continue

                if dry_run:
                    # Modo dry-run: apenas loga
                    self.logger.debug(
                        f"[DRY-RUN] {operation.operation_type.upper()}: "
                        f"{operation.source} → {operation.destination}"
                    )
                else:
                    # Executa a operação
                    if operation.operation_type == 'delete':
                        operation.source.unlink()
                        self.logger.action(f"Removido: {operation.source.name}")
                        stats['deleted'] += 1

                    elif operation.operation_type in ('move', 'move_rename'):
                        # Rastreia pasta de origem para limpeza posterior
                        source_folders.add(operation.source.parent)

                        # Cria pasta de destino se não existir
                        operation.destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(operation.source), str(operation.destination))

                        if operation.operation_type == 'move_rename':
                            self.logger.action(
                                f"Movido e renomeado: {operation.source} → {operation.destination}"
                            )
                            stats['moved'] += 1
                            stats['renamed'] += 1
                        else:
                            self.logger.action(
                                f"Movido: {operation.source} → {operation.destination}"
                            )
                            stats['moved'] += 1

                    elif operation.operation_type == 'rename':
                        operation.source.rename(operation.destination)
                        self.logger.action(
                            f"Renomeado: {operation.source.name} → {operation.destination.name}"
                        )
                        stats['renamed'] += 1

            except Exception as e:
                self.logger.error(f"Erro ao processar {operation.source}: {e}")
                stats['failed'] += 1

        # Remove pastas vazias após mover arquivos
        if not dry_run and source_folders:
            for folder in sorted(source_folders, key=lambda p: len(str(p)), reverse=True):
                try:
                    if folder.exists() and folder.is_dir():
                        # Verifica se a pasta está vazia (incluindo subpastas)
                        if not any(folder.iterdir()):
                            folder.rmdir()
                            self.logger.action(f"Removida pasta vazia: {folder}")
                            stats['cleaned'] += 1
                        else:
                            # Verifica subpastas vazias também
                            for subfolder in folder.rglob('*'):
                                if subfolder.is_dir() and not any(subfolder.iterdir()):
                                    subfolder.rmdir()
                                    self.logger.action(f"Removida pasta vazia: {subfolder}")
                                    stats['cleaned'] += 1

                            # Tenta remover a pasta principal novamente
                            if not any(folder.iterdir()):
                                folder.rmdir()
                                self.logger.action(f"Removida pasta vazia: {folder}")
                                stats['cleaned'] += 1
                except Exception as e:
                    self.logger.debug(f"Não foi possível remover pasta {folder}: {e}")

        return stats
