"""Scanner de arquivos e análise de bibliotecas"""

from pathlib import Path
from typing import List
from dataclasses import dataclass, field
from ..utils.helpers import (
    is_video_file, is_subtitle_file, is_image_file,
    has_language_code, is_portuguese_subtitle
)
from ..utils.config import get_config
from .detector import detect_media_type


@dataclass
class ScanResult:
    """Resultado do scan de uma biblioteca"""

    # Arquivos encontrados
    video_files: List[Path] = field(default_factory=list)
    subtitle_files: List[Path] = field(default_factory=list)
    image_files: List[Path] = field(default_factory=list)
    other_files: List[Path] = field(default_factory=list)

    # Legendas por categoria
    variant_subtitles: List[Path] = field(default_factory=list)  # .lang2.srt, .lang3.srt, etc.
    no_lang_subtitles: List[Path] = field(default_factory=list)  # .srt sem código
    foreign_subtitles: List[Path] = field(default_factory=list)  # Idiomas estrangeiros
    kept_subtitles: List[Path] = field(default_factory=list)  # Idiomas mantidos (.por, .eng, etc.)

    # Arquivos indesejados
    unwanted_images: List[Path] = field(default_factory=list)
    nfo_files: List[Path] = field(default_factory=list)
    non_media_files: List[Path] = field(default_factory=list)  # Arquivos que não são .srt ou .mp4

    # Estatísticas
    total_movies: int = 0
    total_episodes: int = 0

    @property
    def total_files(self) -> int:
        """Total calculado dinamicamente após arquivos serem adicionados"""
        return (
            len(self.video_files) +
            len(self.subtitle_files) +
            len(self.image_files) +
            len(self.other_files)
        )


class LibraryScanner:
    """Scanner de bibliotecas de mídia"""

    def __init__(self):
        self.config = get_config()

    def scan(self, directory: Path) -> ScanResult:
        """
        Escaneia um diretório e categoriza os arquivos.

        Args:
            directory: Diretório a escanear

        Returns:
            ScanResult com os arquivos categorizados
        """
        result = ScanResult()

        if not directory.exists() or not directory.is_dir():
            return result

        # Escaneia recursivamente
        all_files = list(directory.rglob('*'))

        for file_path in all_files:
            if not file_path.is_file():
                continue

            # Ignora arquivos ocultos e pastas de sistema
            if file_path.name.startswith('.'):
                continue

            # Categoriza por tipo
            if is_video_file(file_path):
                result.video_files.append(file_path)

                # Detecta tipo de mídia
                media_info = detect_media_type(file_path)
                if media_info.is_movie():
                    result.total_movies += 1
                elif media_info.is_tvshow():
                    result.total_episodes += 1

            elif is_subtitle_file(file_path):
                # Ignora legendas vazias ou muito pequenas (< 20 bytes)
                # Uma legenda SRT válida tem no mínimo: número + timestamp + texto
                if file_path.stat().st_size < 20:
                    continue

                result.subtitle_files.append(file_path)
                self._categorize_subtitle(file_path, result)

            elif is_image_file(file_path):
                result.image_files.append(file_path)
                self._categorize_image(file_path, result)
                # Marca imagens como non-media se configurado
                if self.config.remove_non_media:
                    result.non_media_files.append(file_path)

            elif file_path.suffix.lower() == '.nfo':
                result.nfo_files.append(file_path)
                # Marca NFO como non-media se configurado
                if self.config.remove_non_media:
                    result.non_media_files.append(file_path)

            else:
                result.other_files.append(file_path)
                # Marca arquivos que não são vídeos ou legendas para possível remoção
                if self.config.remove_non_media:
                    result.non_media_files.append(file_path)

        return result

    def _categorize_subtitle(self, file_path: Path, result: ScanResult):
        """Categoriza um arquivo de legenda"""
        import re
        filename = file_path.name.lower()

        # Detecta variações (.lang2.srt, .lang3.srt, etc.) para QUALQUER idioma
        # Padrão: .LANG + NUMERO + [.forced|.sdh|.default] + .extensão
        variant_match = re.search(r'\.([a-z]{2,3})(\d)(?:\.(forced|sdh|default))?\.(srt|ass|ssa|sub|vtt)$', filename)
        if variant_match:
            result.variant_subtitles.append(file_path)
            return

        # Verifica se já tem código de idioma
        lang_code = has_language_code(filename)

        if lang_code:
            # lang_code já vem normalizado para 3 letras pela função has_language_code
            # Verifica se é idioma mantido
            is_kept = lang_code in self.config.kept_languages

            if is_kept:
                result.kept_subtitles.append(file_path)
            # Verifica se é idioma estrangeiro (NÃO está na lista de mantidos)
            # E NÃO é .forced (nunca remover)
            elif '.forced.' not in filename:
                result.foreign_subtitles.append(file_path)
        else:
            # Sem código de idioma
            # Tenta detectar se é português
            if file_path.suffix.lower() == '.srt':
                if is_portuguese_subtitle(file_path, self.config.min_pt_words):
                    result.no_lang_subtitles.append(file_path)
                else:
                    # Não é português, pode ser estrangeira
                    result.foreign_subtitles.append(file_path)

    def _categorize_image(self, file_path: Path, result: ScanResult):
        """Categoriza um arquivo de imagem"""
        filename = file_path.name.lower()

        # Imagens reconhecidas pelo Jellyfin
        jellyfin_images = {
            'poster', 'fanart', 'backdrop', 'logo', 'banner',
            'thumb', 'clearart', 'clearlogo', 'landscape', 'disc'
        }

        # Verifica se é imagem reconhecida
        stem = file_path.stem.lower()
        if not any(img in stem for img in jellyfin_images):
            # Imagem não reconhecida
            result.unwanted_images.append(file_path)


def scan_library(directory: Path) -> ScanResult:
    """
    Escaneia uma biblioteca de mídia.

    Args:
        directory: Diretório da biblioteca

    Returns:
        Resultado do scan
    """
    scanner = LibraryScanner()
    return scanner.scan(directory)
