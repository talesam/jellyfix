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
    calculate_subtitle_quality, extract_quality_tag, detect_video_resolution
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

    def __init__(self, metadata_fetcher: Optional[MetadataFetcher] = None):
        self.config = get_config()
        self.logger = get_logger()
        self.operations: List[RenameOperation] = []
        # Usa o metadata_fetcher fornecido (com cache de escolhas) ou cria novo
        if metadata_fetcher:
            self.metadata_fetcher = metadata_fetcher
        else:
            self.metadata_fetcher = MetadataFetcher() if self.config.fetch_metadata else None

    def plan_operations(self, directory: Path, scan_result=None) -> List[RenameOperation]:
        """
        Planeja todas as operações de renomeação.

        Args:
            directory: Diretório a processar
            scan_result: ScanResult opcional (se fornecido, usa arquivos filtrados; caso contrário, escaneia o diretório)

        Returns:
            Lista de operações planejadas
        """
        self.operations = []
        self.planned_destinations = set()  # Rastreia destinos para evitar conflitos
        self.video_operations_map = {}  # Mapa: video_stem -> operação de vídeo
        self.work_dir = directory  # Working directory for organizing files

        # Coleta todos os arquivos de legendas para processamento inteligente
        subtitle_files = []
        video_files = []

        if scan_result:
            # Usa arquivos do ScanResult filtrado
            print(f"DEBUG: Using filtered ScanResult - videos: {len(scan_result.video_files)}, subtitles: {len(scan_result.subtitle_files)}")
            video_files = scan_result.video_files
            subtitle_files = scan_result.subtitle_files
        else:
            # Escaneia o diretório normalmente
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
                    # Ignora legendas vazias ou muito pequenas (< 20 bytes)
                    if file_path.stat().st_size < 20:
                        continue
                    subtitle_files.append(file_path)

        # Processa arquivos Mirabel se configurado (ANTES de processar vídeos)
        if self.config.fix_mirabel_files:
            subtitle_files = self._plan_mirabel_fixes(subtitle_files)

        # Processa vídeos
        for file_path in video_files:
            self._plan_video_rename(file_path)

        # Processa legendas que acompanham vídeos (move/renomeia junto)
        # Retorna lista de legendas já processadas
        processed_subtitles = self._plan_subtitle_companion(subtitle_files, video_files)

        # Processa legendas de forma inteligente (variações de idioma)
        # Exclui as que já foram processadas
        remaining_subtitles = [s for s in subtitle_files if s not in processed_subtitles]
        self._plan_subtitle_variants(remaining_subtitles, directory)

        # Remove arquivos não-mídia se configurado (ANTES de processar extras)
        if self.config.remove_non_media and scan_result and scan_result.non_media_files:
            self._plan_non_media_removal(scan_result.non_media_files)

        # Processa arquivos extras (NFO, imagens, etc) que devem acompanhar os vídeos
        self._plan_extra_files(directory, video_files, scan_result)

        return self.operations

    def replan_for_video_with_metadata(self, video_path: Path, metadata, all_operations: List[RenameOperation]) -> List[RenameOperation]:
        """
        Re-planeja operações para um vídeo específico usando novo metadata fornecido manualmente.
        Retorna lista de novas operações que devem substituir as antigas.

        Args:
            video_path: Caminho do arquivo de vídeo original
            metadata: Novo metadata selecionado manualmente (objeto Metadata)
            all_operations: Lista completa de operações atuais

        Returns:
            Lista de novas operações (vídeo + legendas + extras) que substituirão as antigas
        """
        from ..utils.helpers import normalize_spaces, is_subtitle_file
        import re

        # Inicializa variáveis de controle
        self.operations = []
        self.planned_destinations = set()
        self.video_operations_map = {}
        self.work_dir = video_path.parent

        # Detecta tipo de mídia
        media_info = detect_media_type(video_path)

        # Planeja operação do vídeo com o novo metadata
        if media_info.is_movie():
            new_video_op = self._plan_movie_rename_with_metadata(video_path, media_info, metadata)
        elif media_info.is_tvshow():
            new_video_op = self._plan_tvshow_rename_with_metadata(video_path, media_info, metadata)
        else:
            return []  # Não é filme nem série, não faz nada

        if not new_video_op:
            return []

        # Encontra todos os arquivos relacionados ao vídeo original
        video_stem_original = video_path.stem
        video_normalized = normalize_spaces(video_stem_original)
        related_files = []

        # Busca legendas, NFO, e outros arquivos relacionados no mesmo diretório
        for file_path in video_path.parent.iterdir():
            if not file_path.is_file():
                continue
            if file_path == video_path:
                continue

            # Verifica se o arquivo está relacionado ao vídeo (mesmo base name)
            file_stem = file_path.stem

            # Para legendas, remove código de idioma antes de comparar
            if is_subtitle_file(file_path):
                base_match = re.match(r'(.+?)\.([a-z]{2,3}\d?)(\.forced)?$', file_stem, re.IGNORECASE)
                if base_match:
                    file_base = base_match.group(1)
                else:
                    file_base = file_stem

                if normalize_spaces(file_base) == video_normalized or file_base == video_stem_original:
                    related_files.append(file_path)

            # Para NFO e outros, compara nome completo
            elif file_path.suffix.lower() in ['.nfo', '.jpg', '.png', '.jpeg']:
                if normalize_spaces(file_stem) == video_normalized or file_stem == video_stem_original:
                    related_files.append(file_path)

        # Separa por tipo
        subtitle_files = [f for f in related_files if is_subtitle_file(f)]
        nfo_files = [f for f in related_files if f.suffix.lower() == '.nfo']
        image_files = [f for f in related_files if f.suffix.lower() in ['.jpg', '.png', '.jpeg']]

        # Configura mapa de operações de vídeo para _plan_subtitle_companion
        self.video_operations_map[video_stem_original] = new_video_op
        self.video_operations_map[video_normalized] = new_video_op

        # Planeja legendas companheiras (remove estrangeiras, renomeia)
        processed_subs = self._plan_subtitle_companion(subtitle_files, [video_path])

        # Planeja variantes de legendas (escolhe melhor qualidade, remove duplicadas)
        remaining_subs = [s for s in subtitle_files if s not in processed_subs]
        if remaining_subs:
            self._plan_subtitle_variants(remaining_subs, video_path.parent)

        # Planeja arquivos NFO
        if nfo_files and self.config.rename_nfo:
            new_video_stem = new_video_op.destination.stem
            new_video_folder = new_video_op.destination.parent

            for nfo_path in nfo_files:
                new_nfo_name = f"{new_video_stem}.nfo"
                new_nfo_path = new_video_folder / new_nfo_name

                if new_nfo_path != nfo_path:
                    pasta_mudou = new_nfo_path.parent != nfo_path.parent
                    nome_mudou = new_nfo_path.name != nfo_path.name

                    if pasta_mudou and nome_mudou:
                        op_type = 'move_rename'
                    elif pasta_mudou:
                        op_type = 'move'
                    else:
                        op_type = 'rename'

                    self.operations.append(RenameOperation(
                        source=nfo_path,
                        destination=new_nfo_path,
                        operation_type=op_type,
                        reason=f"Acompanhar vídeo: {nfo_path.name} → {new_nfo_name}"
                    ))

        # Planeja arquivos de imagem
        if image_files:
            new_video_folder = new_video_op.destination.parent

            for img_path in image_files:
                new_img_path = new_video_folder / img_path.name

                if new_img_path != img_path and new_img_path.parent != img_path.parent:
                    self.operations.append(RenameOperation(
                        source=img_path,
                        destination=new_img_path,
                        operation_type='move',
                        reason=f"Acompanhar vídeo"
                    ))

        return self.operations

    def _plan_movie_rename_with_metadata(self, file_path: Path, media_info, metadata) -> Optional[RenameOperation]:
        """
        Planeja renomeação de filme usando metadata fornecido (não busca TMDB).
        Retorna a operação planejada ou None.
        """
        title = clean_filename(metadata.title)
        year = metadata.year

        # Build folder suffix with TMDB ID
        folder_suffix = ""
        if metadata.tmdb_id:
            folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"
        elif metadata.imdb_id:
            folder_suffix = f" [imdbid-{metadata.imdb_id}]"

        # Detect quality tag
        quality_tag = None
        if self.config.add_quality_tag:
            quality_tag = extract_quality_tag(file_path.stem)
            if not quality_tag and self.config.use_ffprobe:
                quality_tag = detect_video_resolution(file_path)

        # Build new name
        if year:
            base_name = f"{title} ({year})"
        else:
            base_name = f"{title}"

        if quality_tag:
            new_name = f"{base_name} - {quality_tag}{file_path.suffix}"
        else:
            new_name = f"{base_name}{file_path.suffix}"

        # Expected folder name
        expected_folder = f"{base_name}{folder_suffix}"

        # Determine if we need to organize into folders
        if self.config.organize_folders:
            # Check current location
            parent_folder = file_path.parent

            if parent_folder.name != expected_folder:
                # Need to create/move to proper folder
                if parent_folder == self.work_dir:
                    new_folder = self.work_dir / expected_folder
                else:
                    new_folder = self.work_dir / expected_folder
            else:
                # Already in correct folder
                new_folder = parent_folder
        else:
            # Don't organize folders, keep in current location
            new_folder = file_path.parent

        new_path = new_folder / new_name

        if new_path != file_path:
            pasta_mudou = new_path.parent != file_path.parent
            nome_mudou = new_path.name != file_path.name

            if pasta_mudou and nome_mudou:
                op_type = 'move_rename'
            elif pasta_mudou:
                op_type = 'move'
            else:
                op_type = 'rename'

            op = RenameOperation(
                source=file_path,
                destination=new_path,
                operation_type=op_type,
                reason=f"Atualização manual: {metadata.title} ({metadata.year})"
            )
            self.operations.append(op)
            return op

        return None

    def _plan_tvshow_rename_with_metadata(self, file_path: Path, media_info, metadata) -> Optional[RenameOperation]:
        """
        Planeja renomeação de série usando metadata fornecido (não busca TMDB).
        Retorna a operação planejada ou None.
        """
        title = clean_filename(metadata.title)
        year = metadata.year

        # Build folder suffix with TMDB ID
        folder_suffix = ""
        if metadata.tmdb_id:
            folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"
        elif metadata.tvdb_id:
            folder_suffix = f" [tvdbid-{metadata.tvdb_id}]"
        elif metadata.imdb_id:
            folder_suffix = f" [imdbid-{metadata.imdb_id}]"

        # Detect quality tag
        quality_tag = None
        if self.config.add_quality_tag:
            quality_tag = extract_quality_tag(file_path.stem)
            if not quality_tag and self.config.use_ffprobe:
                quality_tag = detect_video_resolution(file_path)

        # Format episode part
        if media_info.episode_end and media_info.episode_end != media_info.episode_start:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}-E{media_info.episode_end:02d}"
        else:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}"

        if quality_tag:
            new_name = f"{title} {episode_part} - {quality_tag}{file_path.suffix}"
        else:
            new_name = f"{title} {episode_part}{file_path.suffix}"

        # Determine series folder structure
        season_folder_name = format_season_folder(media_info.season)

        # Find series folder
        if file_path.parent.name.lower().startswith('season'):
            series_folder = file_path.parent.parent
        else:
            series_folder = file_path.parent

        # Expected series folder name
        if year:
            expected_series_folder = f"{title} ({year}){folder_suffix}"
        else:
            expected_series_folder = f"{title}{folder_suffix}"

        # Determine new series folder path
        if series_folder.name != expected_series_folder:
            if series_folder == self.work_dir:
                new_series_folder = self.work_dir.parent / expected_series_folder
            else:
                new_series_folder = self.work_dir / expected_series_folder
        else:
            new_series_folder = series_folder

        # Full path
        new_folder = new_series_folder / season_folder_name
        new_path = new_folder / new_name

        if new_path != file_path:
            pasta_mudou = new_path.parent != file_path.parent
            nome_mudou = new_path.name != file_path.name

            if pasta_mudou and nome_mudou:
                op_type = 'move_rename'
            elif pasta_mudou:
                op_type = 'move'
            else:
                op_type = 'rename'

            if new_series_folder != series_folder:
                reason = f"Atualização manual: {series_folder.name} → {expected_series_folder}"
            else:
                reason = f"Atualização manual: {file_path.name} → {new_name}"

            op = RenameOperation(
                source=file_path,
                destination=new_path,
                operation_type=op_type,
                reason=reason
            )
            self.operations.append(op)
            return op

        return None

    def _plan_video_rename(self, file_path: Path):
        """Planeja renomeação de um arquivo de vídeo"""
        media_info = detect_media_type(file_path)

        if media_info.is_movie():
            self._plan_movie_rename(file_path, media_info)
        elif media_info.is_tvshow():
            self._plan_tvshow_rename(file_path, media_info)

    def _plan_movie_rename(self, file_path: Path, media_info):
        """Plan movie file rename"""
        # Extract information
        title = clean_filename(normalize_spaces(media_info.title or file_path.stem))
        year = extract_year(file_path.stem)

        if not title:
            return

        # Fetch metadata if configured
        folder_suffix = ""
        if self.metadata_fetcher and self.config.fetch_metadata:
            self.logger.info(f"🔍 Searching: {title}")
            metadata = self.metadata_fetcher.search_movie(title, year, interactive=self.config.interactive)

            if metadata:
                # Use title and year from metadata
                title = clean_filename(metadata.title)
                year = metadata.year or year

                # Add provider ID
                if metadata.tmdb_id:
                    folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"
                elif metadata.imdb_id:
                    folder_suffix = f" [imdbid-{metadata.imdb_id}]"

                self.logger.info(f"✓ Found: {title} ({year}) [ID: {metadata.tmdb_id}]")
            else:
                self.logger.warning(f"✗ Not found: {title}")

        # Detect quality tag
        quality_tag = None
        if self.config.add_quality_tag:
            # First try to extract from filename
            quality_tag = extract_quality_tag(file_path.stem)

            # If not found and ffprobe is enabled, detect from video
            if not quality_tag and self.config.use_ffprobe:
                quality_tag = detect_video_resolution(file_path)

        # Jellyfin format: "Movie Name (YYYY) - 1080p.ext" or "Movie Name (YYYY).ext"
        if year:
            base_name = f"{title} ({year})"
        else:
            base_name = f"{title}"

        if quality_tag:
            new_name = f"{base_name} - {quality_tag}{file_path.suffix}"
        else:
            new_name = f"{base_name}{file_path.suffix}"

        # Check if in correct folder
        parent_folder = file_path.parent.name
        expected_folder = f"{title} ({year}){folder_suffix}" if year else f"{title}{folder_suffix}"

        # Define destination
        if parent_folder != expected_folder:
            # Always create the organized folder in the working directory
            new_folder = self.work_dir / expected_folder
            new_path = new_folder / new_name
        else:
            # Just rename
            new_path = file_path.parent / new_name

        if new_path != file_path:
            # Detect operation type precisely
            folder_changed = new_path.parent != file_path.parent
            name_changed = new_path.name != file_path.name

            if folder_changed and name_changed:
                op_type = 'move_rename'
            elif folder_changed:
                op_type = 'move'
            else:
                op_type = 'rename'

            self.operations.append(RenameOperation(
                source=file_path,
                destination=new_path,
                operation_type=op_type,
                reason=f"Standardize movie name: {file_path.name} → {new_name}"
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

        # Detecta tag de qualidade
        quality_tag = None
        if self.config.add_quality_tag:
            # Primeiro tenta extrair do nome do arquivo
            quality_tag = extract_quality_tag(file_path.stem)

            # Se não encontrou e ffprobe está habilitado, detecta do vídeo
            if not quality_tag and self.config.use_ffprobe:
                quality_tag = detect_video_resolution(file_path)

        # Formato Jellyfin: "Nome da Série S01E01 - 1080p.ext" ou "Nome da Série S01E01.ext"
        # IMPORTANTE: NÃO usar hífen antes de S01E01, apenas ESPAÇO! O Jellyfin não reconhece com hífen.
        if media_info.episode_end and media_info.episode_end != media_info.episode_start:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}-E{media_info.episode_end:02d}"
        else:
            episode_part = f"S{media_info.season:02d}E{media_info.episode_start:02d}"

        if quality_tag:
            new_name = f"{title} {episode_part} - {quality_tag}{file_path.suffix}"
        else:
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
            # Determina onde criar a nova pasta da série
            # Caso 1: work_dir É a pasta da série → criar no parent do work_dir
            # Caso 2: work_dir É uma pasta Season → criar no parent do parent do work_dir
            # Caso 3: work_dir é uma pasta que contém séries → criar no work_dir

            if series_folder == self.work_dir:
                # Caso 1: usuário selecionou a pasta da série (ex: "Criminal Minds")
                new_series_folder = self.work_dir.parent / expected_series_folder
            elif self.work_dir.name.lower().startswith('season'):
                # Caso 2: usuário selecionou uma pasta Season (ex: "Season 1")
                # A nova pasta da série deve ficar no mesmo nível da pasta da série original
                new_series_folder = series_folder.parent / expected_series_folder
            elif series_folder.parent == self.work_dir:
                # Caso 3: work_dir contém a pasta da série
                new_series_folder = self.work_dir / expected_series_folder
            else:
                # Caso padrão: criar no work_dir
                new_series_folder = self.work_dir / expected_series_folder
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

    def _plan_subtitle_companion(self, subtitle_files: List[Path], video_files: List[Path]) -> List[Path]:
        """
        Processa legendas que acompanham vídeos.
        Quando um vídeo é movido/renomeado, a legenda correspondente também é.
        Legendas de idiomas estrangeiros são marcadas para DELETE se configurado.

        Returns:
            Lista de legendas que foram processadas
        """
        from ..utils.helpers import normalize_spaces, has_language_code, is_portuguese_subtitle
        import re

        processed_subtitles = []

        # Cria mapa de vídeos por base name (normalizado para matching)
        video_operations = {}
        for op in self.operations:
            if op.source in video_files:
                # Normaliza o nome do vídeo para fazer matching
                video_stem = op.source.stem
                video_normalized = normalize_spaces(video_stem)
                video_operations[video_normalized] = op
                # Também guarda pela chave exata para matching direto
                video_operations[video_stem] = op
        
        # Armazena para uso em _plan_subtitle_variants
        self.video_operations_map = video_operations

        # Processa cada legenda
        for subtitle_path in subtitle_files:
            # Verifica se é arquivo Mirabel (já identificado em _plan_mirabel_fixes)
            mirabel_data = getattr(self, 'mirabel_info', {}).get(subtitle_path)

            if mirabel_data:
                # Usa informações do Mirabel
                subtitle_base = mirabel_data['base_name']
                lang_code = mirabel_data['target_lang']
                lang_code_base = mirabel_data['target_lang']
                forced_suffix = '.forced' if mirabel_data['forced'] else ''
            else:
                # Processamento normal para legendas não-Mirabel
                # Extrai base name da legenda (remove .LANG.srt)
                subtitle_name = subtitle_path.stem

                # Primeiro, detecta se tem .forced (case-insensitive) em qualquer posição
                forced_suffix = ''
                subtitle_name_lower = subtitle_name.lower()
                if '.forced' in subtitle_name_lower:
                    forced_suffix = '.forced'
                    # Remove .forced temporariamente para facilitar o parsing
                    # Preserva o case original para o matching
                    forced_pos = subtitle_name_lower.rfind('.forced')
                    subtitle_name_no_forced = subtitle_name[:forced_pos] + subtitle_name[forced_pos+7:]
                else:
                    subtitle_name_no_forced = subtitle_name

                # Remove código de idioma se presente
                # Padrões: .por, .eng, .pt, .en, .pt-BR, .pt_BR, .por2, etc. (agora sem .forced porque já foi removido)
                base_match = re.match(r'(.+?)\.([a-z]{2,3}(?:[-_][A-Z]{2})?\d?)$', subtitle_name_no_forced, re.IGNORECASE)
                if base_match:
                    from ..utils.helpers import normalize_language_code
                    subtitle_base = base_match.group(1)
                    lang_code_raw = base_match.group(2).lower()  # ex: "en2", "pt-br", "por"

                    # Remove dígito do código se tiver (por2 -> por, en2 -> en)
                    lang_code_no_digit = re.sub(r'\d+$', '', lang_code_raw)

                    # Normaliza o código de idioma para 3 letras (en -> eng, pt -> por, pt-BR -> por)
                    lang_code_base = normalize_language_code(lang_code_no_digit)

                    # lang_code mantém o original com dígito se tiver (usado para detectar variantes)
                    # mas normalizado (en2 -> eng2)
                    if lang_code_raw != lang_code_no_digit:  # tem dígito
                        lang_code = lang_code_base + lang_code_raw[-1]  # eng + 2 = eng2
                    else:
                        lang_code = lang_code_base
                else:
                    # Não tem código de idioma explícito
                    subtitle_base = subtitle_name_no_forced
                    lang_code = None
                    lang_code_base = None

                    # Se é .forced sem código de idioma, detecta pelo conteúdo
                    if forced_suffix and self.config.rename_no_lang:
                        if is_portuguese_subtitle(subtitle_path, self.config.min_pt_words):
                            lang_code = 'por'
                            lang_code_base = 'por'

            # Procura vídeo correspondente (primeiro tenta match exato, depois normalizado)
            matching_video_op = video_operations.get(subtitle_base)

            if not matching_video_op:
                # Tenta matching normalizado (mais flexível)
                subtitle_normalized = normalize_spaces(subtitle_base)
                matching_video_op = video_operations.get(subtitle_normalized)

            if matching_video_op:
                # Encontrou vídeo correspondente que será movido/renomeado

                # Detecta se é uma variante (tem dígito no código de idioma: por2, eng3, etc.)
                is_variant = lang_code and lang_code != lang_code_base  # por2 != por

                # VERIFICA SE É IDIOMA ESTRANGEIRO (NÃO está na lista de mantidos)
                is_foreign = False
                if lang_code_base and self.config.remove_foreign_subs:
                    # Verifica se o idioma base está na lista de mantidos
                    is_foreign = lang_code_base not in self.config.kept_languages

                if is_foreign:
                    # Legenda estrangeira - marcar como processada e DELETE
                    processed_subtitles.append(subtitle_path)
                    self.operations.append(RenameOperation(
                        source=subtitle_path,
                        destination=subtitle_path,  # Será deletado
                        operation_type='delete',
                        reason=f"Remover legenda em idioma estrangeiro ({lang_code_base})"
                    ))
                elif is_variant:
                    # Variante de idioma mantido (.por2, .eng3)
                    # NÃO processa aqui - deixa para _plan_subtitle_variants
                    # que vai escolher a melhor legenda se não existir .por.srt
                    pass  # Será tratada depois
                else:
                    # Legenda de idioma mantido (não é variante) - mover/renomear junto com vídeo
                    
                    # Se não tem código de idioma, verifica se vai receber um
                    if not lang_code:
                        # Verifica se é legenda portuguesa e deve adicionar código
                        if self.config.rename_no_lang and is_portuguese_subtitle(subtitle_path, self.config.min_pt_words):
                            # Esta legenda receberia código .por
                            # Mas NÃO processa aqui - deixa para _plan_subtitle_variants
                            # para comparar qualidade com .por2.srt, .por3.srt, etc.
                            pass  # Será tratada depois
                            continue
                    
                    processed_subtitles.append(subtitle_path)
                    
                    # Monta novo nome da legenda baseado no novo nome do vídeo
                    new_video_stem = matching_video_op.destination.stem

                    # Usa o código base (sem dígito) para o nome final
                    final_lang_code = lang_code_base if lang_code_base else lang_code

                    if final_lang_code:
                        new_subtitle_name = f"{new_video_stem}.{final_lang_code}{forced_suffix}{subtitle_path.suffix}"
                    else:
                        new_subtitle_name = f"{new_video_stem}{subtitle_path.suffix}"

                    # Destino é na mesma pasta do novo vídeo
                    new_subtitle_path = matching_video_op.destination.parent / new_subtitle_name

                    # VERIFICA CONFLITO: Se o destino já foi planejado, pula esta legenda
                    if new_subtitle_path in self.planned_destinations:
                        self.logger.warning(
                            f"Conflito de destino: {subtitle_path.name} → {new_subtitle_name} "
                            f"(destino já em uso, ignorando)"
                        )
                        continue

                    if new_subtitle_path != subtitle_path:
                        # Detecta tipo de operação
                        pasta_mudou = new_subtitle_path.parent != subtitle_path.parent
                        nome_mudou = new_subtitle_path.name != subtitle_path.name

                        if pasta_mudou and nome_mudou:
                            op_type = 'move_rename'
                        elif pasta_mudou:
                            op_type = 'move'
                        else:
                            op_type = 'rename'

                        self.operations.append(RenameOperation(
                            source=subtitle_path,
                            destination=new_subtitle_path,
                            operation_type=op_type,
                            reason=f"Acompanhar vídeo: {subtitle_path.name} → {new_subtitle_name}"
                        ))
                        
                        # Marca o destino como usado
                        self.planned_destinations.add(new_subtitle_path)

        return processed_subtitles

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

            # Detecta variações: .lang2.srt, .lang3.srt (aceita 2-3 letras)
            variant_match = re.search(r'\.([a-z]{2,3})(\d)\.srt$', filename)
            if variant_match:
                from ..utils.helpers import normalize_language_code
                lang_code_raw = variant_match.group(1)
                variant_num = int(variant_match.group(2))
                base_name = file_path.name[:-(len(variant_match.group(0)))]

                # Normaliza o código de idioma para 3 letras
                lang_code = normalize_language_code(lang_code_raw)

                key = (file_path.parent, base_name, lang_code)
                grouped[key].append((variant_num, file_path))
            else:
                # Verifica se é .srt sem código de idioma que é português
                # Estas são candidatas para se tornarem .por.srt
                from ..utils.helpers import is_portuguese_subtitle
                no_lang_match = re.match(r'^(.+)\.srt$', file_path.name, re.IGNORECASE)
                if no_lang_match and self.config.rename_no_lang:
                    # Verifica se não tem código de idioma explícito
                    base_name_check = no_lang_match.group(1)
                    has_lang = re.search(r'\.([a-z]{2,3})$', base_name_check, re.IGNORECASE)
                    if not has_lang and is_portuguese_subtitle(file_path, self.config.min_pt_words):
                        # É .srt português sem código → candidata para .por.srt
                        base_name = base_name_check
                        key = (file_path.parent, base_name, 'por')
                        # Usa 0 como número para ter prioridade sobre variantes
                        grouped[key].append((0, file_path))
                    else:
                        # Não é português ou já tem código, processa normalmente
                        self._plan_subtitle_other_operations(file_path)
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
            
            # Verifica se há operação de vídeo correspondente (para usar a pasta de destino)
            from ..utils.helpers import normalize_spaces
            video_op = self.video_operations_map.get(base_name) or \
                       self.video_operations_map.get(normalize_spaces(base_name))
            
            if video_op:
                # Usa a pasta de destino do vídeo
                new_video_stem = video_op.destination.stem
                final_target_name = f"{new_video_stem}.{lang_code}.srt"
                final_target_path = video_op.destination.parent / final_target_name
            else:
                # Mantém na pasta original
                final_target_path = target_path

            if not target_path.exists():
                # NÃO existe .lang.srt → renomeia a MELHOR variação
                best_quality, best_num, best_path, best_size = scored_variants[0]

                # Verifica se a melhor tem qualidade > 0 (não é vazia/inválida)
                if best_quality > 0:
                    # Verifica conflito de destino
                    if final_target_path in self.planned_destinations:
                        self.logger.warning(
                            f"Conflito de destino: {best_path.name} → {final_target_path.name} "
                            f"(destino já em uso, ignorando)"
                        )
                    else:
                        # Determina tipo de operação
                        pasta_mudou = final_target_path.parent != best_path.parent
                        nome_mudou = final_target_path.name != best_path.name
                        
                        if pasta_mudou and nome_mudou:
                            op_type = 'move_rename'
                        elif pasta_mudou:
                            op_type = 'move'
                        else:
                            op_type = 'rename'
                        
                        self.operations.append(RenameOperation(
                            source=best_path,
                            destination=final_target_path,
                            operation_type=op_type,
                            reason=f"Renomear .{lang_code}{best_num}.srt para .{lang_code}.srt (melhor: {best_size} bytes, qualidade {best_quality:.0f})"
                        ))
                        self.planned_destinations.add(final_target_path)

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

                # Verifica padrões: .LANG.srt, .LANG2.srt, .LANG.forced.srt
                pattern = rf'\.{lang_code}\d?(?:\.forced)?\.srt$'
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

    def _plan_extra_files(self, directory: Path, video_files: List[Path], scan_result=None):
        """
        Planeja movimentação e renomeação de arquivos extras (NFO, imagens, etc) que acompanham vídeos.

        Quando um vídeo é movido para uma nova pasta, todos os arquivos extras da pasta
        original devem ser movidos junto. Arquivos NFO são também renomeados para
        corresponder ao nome do vídeo se a opção rename_nfo estiver habilitada.

        Args:
            directory: Diretório base
            video_files: Lista de arquivos de vídeo processados
            scan_result: Resultado do scan (opcional) para filtrar arquivos permitidos
        """
        from ..utils.helpers import is_video_file, is_subtitle_file

        # Se temos um scan_result (filtrado), cria um set de arquivos permitidos
        allowed_files = None
        if scan_result:
            allowed_files = set()
            allowed_files.update(scan_result.video_files)
            allowed_files.update(scan_result.subtitle_files)
            allowed_files.update(scan_result.image_files)
            allowed_files.update(scan_result.nfo_files)
            allowed_files.update(scan_result.other_files)
            allowed_files.update(scan_result.non_media_files)
            # Inclui também as listas categorizadas para garantir
            allowed_files.update(scan_result.variant_subtitles)
            allowed_files.update(scan_result.no_lang_subtitles)
            allowed_files.update(scan_result.foreign_subtitles)
            allowed_files.update(scan_result.kept_subtitles)
            allowed_files.update(scan_result.unwanted_images)

        # Cria mapa de vídeos: pasta_original -> (nova_pasta, video_stem_antigo, video_stem_novo)
        video_folder_map = {}
        video_rename_map = {}  # old_stem -> new_stem para renomear NFO
        
        for op in self.operations:
            if op.source in video_files:
                old_folder = op.source.parent
                new_folder = op.destination.parent
                old_stem = op.source.stem
                new_stem = op.destination.stem
                
                # Mapeia pastas
                if old_folder != new_folder:
                    if old_folder not in video_folder_map:
                        video_folder_map[old_folder] = new_folder
                
                # Mapeia renomeação de stem (para NFO)
                if old_stem != new_stem:
                    video_rename_map[old_stem] = (new_stem, new_folder)
                elif old_folder != new_folder:
                    # Mesmo stem mas pasta diferente
                    video_rename_map[old_stem] = (old_stem, new_folder)

        # Para cada pasta que está sendo esvaziada, move os arquivos extras
        for old_folder, new_folder in video_folder_map.items():
            # Lista todos os arquivos na pasta antiga
            for file_path in old_folder.iterdir():
                if not file_path.is_file():
                    continue
                
                # Verifica se o arquivo é permitido (se houver filtro)
                if allowed_files is not None and file_path not in allowed_files:
                    continue

                # Ignora arquivos ocultos
                if file_path.name.startswith('.'):
                    continue

                # Ignora vídeos e legendas (já foram processados)
                if is_video_file(file_path) or is_subtitle_file(file_path):
                    continue

                # Verifica se o arquivo já tem uma operação planejada
                already_planned = any(op.source == file_path for op in self.operations)
                if already_planned:
                    continue

                # Verifica se é arquivo NFO e se deve renomear
                is_nfo = file_path.suffix.lower() == '.nfo'
                
                if is_nfo and self.config.rename_nfo:
                    # Tenta encontrar o vídeo correspondente para renomear o NFO
                    nfo_stem = file_path.stem
                    
                    if nfo_stem in video_rename_map:
                        # NFO corresponde a um vídeo renomeado
                        new_stem, target_folder = video_rename_map[nfo_stem]
                        new_name = f"{new_stem}.nfo"
                        new_path = target_folder / new_name
                        
                        # Verifica conflito
                        if new_path.exists() and new_path != file_path:
                            self.logger.warning(f"NFO já existe no destino, pulando: {file_path.name}")
                            continue
                        
                        # Determina tipo de operação
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
                            reason=f"Renomear NFO para corresponder ao vídeo: {file_path.name} → {new_name}"
                        ))
                        continue
                
                # Move o arquivo extra para a nova pasta (sem renomear)
                new_path = new_folder / file_path.name

                # Verifica se já existe um arquivo com esse nome no destino
                if new_path.exists() and new_path != file_path:
                    self.logger.warning(f"Arquivo extra já existe no destino, pulando: {file_path.name}")
                    continue

                self.operations.append(RenameOperation(
                    source=file_path,
                    destination=new_path,
                    operation_type='move',
                    reason=f"Mover arquivo extra junto com vídeo: {file_path.name}"
                ))

        # Processar tvshow.nfo de séries
        # Para séries, o tvshow.nfo fica na pasta raiz (ex: /Serie/tvshow.nfo)
        # Precisamos movê-lo quando a pasta da série é renomeada
        series_root_map = {}  # old_series_root -> new_series_root

        for old_folder, new_folder in video_folder_map.items():
            # Detecta se é uma pasta de temporada (Season XX)
            if 'season' in old_folder.name.lower():
                old_series_root = old_folder.parent
                new_series_root = new_folder.parent

                if old_series_root != new_series_root:
                    series_root_map[old_series_root] = new_series_root

        # Mover tvshow.nfo da raiz da série
        for old_series_root, new_series_root in series_root_map.items():
            tvshow_nfo = old_series_root / 'tvshow.nfo'

            if tvshow_nfo.exists() and tvshow_nfo.is_file():
                # Verifica se já tem operação planejada
                already_planned = any(op.source == tvshow_nfo for op in self.operations)
                if already_planned:
                    continue

                new_tvshow_path = new_series_root / 'tvshow.nfo'

                # Verifica conflito
                if new_tvshow_path.exists() and new_tvshow_path != tvshow_nfo:
                    self.logger.warning(f"tvshow.nfo já existe no destino, pulando")
                    continue

                self.operations.append(RenameOperation(
                    source=tvshow_nfo,
                    destination=new_tvshow_path,
                    operation_type='move',
                    reason="Mover tvshow.nfo para nova pasta da série"
                ))

    def _plan_non_media_removal(self, non_media_files: List[Path]):
        """
        Planeja remoção de arquivos que não sejam .srt ou .mp4.

        Args:
            non_media_files: Lista de arquivos não-mídia a serem removidos
        """
        for file_path in non_media_files:
            # Verifica se o arquivo ainda não tem operação planejada
            already_planned = any(op.source == file_path for op in self.operations)
            if already_planned:
                continue

            # Adiciona operação de remoção
            self.operations.append(RenameOperation(
                source=file_path,
                destination=file_path,  # Será deletado
                operation_type='delete',
                reason=f"Remover arquivo não-mídia: {file_path.suffix}"
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

    def _plan_mirabel_fixes(self, subtitle_files: List[Path]) -> List[Path]:
        """
        Identifica arquivos Mirabel e guarda informações para renomeação posterior.

        NÃO cria operações aqui - apenas prepara as informações para que
        _plan_subtitle_companion crie uma única operação direta do arquivo
        original para o destino final.

        Padrões reconhecidos:
        - .pt-BR.hi.srt → .por.srt
        - .br.hi.srt → .por.srt
        - .pt-BR.hi.forced.srt → .por.forced.srt
        - .br.hi.forced.srt → .por.forced.srt
        - .en.hi.srt → .eng.srt
        - .en.hi.forced.srt → .eng.forced.srt

        Args:
            subtitle_files: Lista de arquivos de legenda

        Returns:
            Lista de arquivos de legenda (paths originais, não modificados)
        """
        # Patterns para detectar arquivos Mirabel
        # Grupo 1: base_name, Grupo 2: código do idioma, Grupo 3: .forced (opcional)
        mirabel_patterns = [
            # Português: pt-BR, br, pt_BR, etc → por
            (re.compile(r'^(.+?)\.(pt-BR|pt-br|br|BR|pt_BR|pt_br)\.hi(\.forced)?\.srt$', re.IGNORECASE), 'por'),
            # Inglês: en, EN → eng
            (re.compile(r'^(.+?)\.(en|EN)\.hi(\.forced)?\.srt$', re.IGNORECASE), 'eng'),
        ]

        # Inicializa o mapa de informações Mirabel
        self.mirabel_info = {}  # Mapa: old_path -> {base_name, target_lang, forced}

        updated_subtitle_files = []
        mirabel_count = 0

        for file_path in subtitle_files:
            matched = False
            for pattern, target_lang in mirabel_patterns:
                match = pattern.match(file_path.name)
                if match:
                    matched = True
                    base_name = match.group(1)
                    forced = match.group(3)  # '.forced' ou None

                    # Constrói novo nome para verificar se já existe
                    if forced:
                        new_name = f"{base_name}.{target_lang}.forced.srt"
                    else:
                        new_name = f"{base_name}.{target_lang}.srt"

                    new_path = file_path.parent / new_name

                    # Verifica se destino já existe
                    if new_path.exists() and new_path != file_path:
                        # Destino existe - marca para deleção
                        self.operations.append(RenameOperation(
                            source=file_path,
                            destination=file_path,
                            operation_type='delete',
                            reason=f"Mirabel duplicado: {new_name} já existe"
                        ))
                        self.logger.debug(f"Mirabel duplicado será deletado: {file_path.name}")
                    else:
                        # Guarda informações para renomeação posterior
                        self.mirabel_info[file_path] = {
                            'base_name': base_name,
                            'target_lang': target_lang,
                            'forced': bool(forced)
                        }
                        mirabel_count += 1
                        # Mantém o path ORIGINAL na lista
                        updated_subtitle_files.append(file_path)
                        self.logger.debug(f"Mirabel identificado: {file_path.name} → {new_name}")
                    break  # Sai do loop de patterns após match

            if not matched:
                # Não é arquivo Mirabel, mantém na lista
                updated_subtitle_files.append(file_path)

        if mirabel_count > 0:
            self.logger.info(f"Encontrados {mirabel_count} arquivos Mirabel para correção")

        return updated_subtitle_files
