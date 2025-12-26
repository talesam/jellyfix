"""Funções auxiliares e utilitários"""

import re
from pathlib import Path
from typing import Optional

# Palavras comuns em português para detecção
PORTUGUESE_WORDS = [
    "que", "não", "para", "com", "uma", "mais", "muito", "está", "você",
    "seu", "sua", "ele", "ela", "são", "mas", "por", "até", "também",
    "bem", "foi", "ser", "vai", "pode", "ainda", "onde", "quando",
    "como", "porque", "sem", "sobre", "todo", "tinha", "foram", "fazer"
]

# Caracteres proibidos no Jellyfin
FORBIDDEN_CHARS = r'[<>:"/\\|?*]'

# Extensões de vídeo suportadas
VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv'
}

# Extensões de legenda
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.sub', '.vtt'}

# Extensões de imagem
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.ico', '.svg'
}


def calculate_subtitle_quality(file_path: Path) -> float:
    """
    Calcula a "qualidade" de um arquivo de legenda baseado em:
    - Tamanho do arquivo
    - Número de blocos de legenda
    - Número de linhas de texto

    Returns:
        Pontuação de qualidade (maior = melhor)
        0 = arquivo vazio ou inválido
    """
    try:
        # Verifica tamanho do arquivo
        file_size = file_path.stat().st_size

        # Arquivo vazio ou muito pequeno (< 100 bytes) = pontuação 0
        if file_size < 100:
            return 0.0

        # Lê o conteúdo
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.strip().split('\n')

        # Conta blocos de legenda (linhas que são apenas números)
        subtitle_blocks = 0
        text_lines = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Bloco de legenda (número sequencial)
            if line.isdigit():
                subtitle_blocks += 1
            # Linha de texto (não é timestamp)
            elif '-->' not in line and not line.isdigit():
                text_lines += 1

        # Calcula pontuação
        # Base: tamanho em KB
        size_score = file_size / 1024

        # Bônus: número de blocos de legenda (mais blocos = mais completo)
        blocks_score = subtitle_blocks * 10

        # Bônus: número de linhas de texto
        text_score = text_lines * 2

        # Penalidade para arquivos muito pequenos (< 1KB)
        if file_size < 1024:
            size_score *= 0.1  # Penaliza muito

        total_score = size_score + blocks_score + text_score

        return total_score

    except Exception:
        return 0.0


def is_portuguese_subtitle(file_path: Path, min_words: int = 5) -> bool:
    """
    Detecta se um arquivo SRT é uma legenda em português.

    Args:
        file_path: Caminho para o arquivo SRT
        min_words: Número mínimo de palavras portuguesas para considerar português

    Returns:
        True se for detectado como português
    """
    if not file_path.exists() or file_path.suffix.lower() != '.srt':
        return False

    try:
        # Lê as primeiras 100 linhas
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline() for _ in range(100)]

        content = ' '.join(lines).lower()

        # Conta quantas palavras portuguesas aparecem
        word_count = sum(1 for word in PORTUGUESE_WORDS if word in content)

        return word_count >= min_words

    except Exception:
        return False


def clean_filename(name: str) -> str:
    """
    Remove caracteres proibidos do nome do arquivo.

    Args:
        name: Nome do arquivo

    Returns:
        Nome limpo
    """
    # Substitui caracteres proibidos
    cleaned = re.sub(FORBIDDEN_CHARS, '', name)

    # Remove espaços extras
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def normalize_spaces(name: str) -> str:
    """
    Normaliza espaços: substitui pontos por espaços, remove múltiplos espaços.

    Args:
        name: Nome do arquivo

    Returns:
        Nome normalizado
    """
    # Substitui pontos por espaços (exceto na extensão)
    name = name.replace('.', ' ')

    # Remove espaços múltiplos
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def extract_year(name: str) -> Optional[int]:
    """
    Extrai o ano de um nome de arquivo.

    Args:
        name: Nome do arquivo

    Returns:
        Ano extraído ou None
    """
    # Procura padrão (YYYY) ou YYYY
    match = re.search(r'[\(\[]?(19\d{2}|20\d{2})[\)\]]?', name)
    if match:
        return int(match.group(1))
    return None


def extract_season_episode(name: str) -> Optional[tuple]:
    """
    Extrai informações de temporada e episódio do nome.

    Formatos suportados:
    - S01E01
    - s01e01
    - 1x01
    - S01E01-E02 (múltiplos episódios)

    Args:
        name: Nome do arquivo

    Returns:
        Tupla (season, episode_start, episode_end) ou None
    """
    # Padrão S01E01 ou s01e01
    match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})(?:-?[Ee](\d{1,2}))?', name)
    if match:
        season = int(match.group(1))
        ep_start = int(match.group(2))
        ep_end = int(match.group(3)) if match.group(3) else ep_start
        return (season, ep_start, ep_end)

    # Padrão 1x01
    match = re.search(r'(\d{1,2})x(\d{1,2})', name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return (season, episode, episode)

    return None


def is_video_file(file_path: Path) -> bool:
    """Verifica se é um arquivo de vídeo"""
    return file_path.suffix.lower() in VIDEO_EXTENSIONS


def is_subtitle_file(file_path: Path) -> bool:
    """Verifica se é um arquivo de legenda"""
    return file_path.suffix.lower() in SUBTITLE_EXTENSIONS


def is_image_file(file_path: Path) -> bool:
    """Verifica se é um arquivo de imagem"""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def has_language_code(filename: str) -> Optional[str]:
    """
    Verifica se o nome do arquivo já tem código de idioma.

    Args:
        filename: Nome do arquivo

    Returns:
        Código de idioma encontrado ou None
    """
    # Procura por padrões como .pt, .pt-BR, .eng, .eng2, .eng.forced, etc.
    # IMPORTANTE: Apenas ANTES da extensão do arquivo para evitar falsos positivos
    # Exemplos aceitos:
    #   "file.eng.srt" -> "eng"
    #   "file.eng2.srt" -> "eng"
    #   "file.eng.forced.srt" -> "eng"
    #   "file.por.srt" -> "por"
    #   "The.Great.Flood.srt" -> None (não pega "gre" de Great)

    # Padrão: .LANG[NUMERO][.forced|.sdh|.default].EXTENSAO
    match = re.search(r'\.([a-z]{2,3}(?:-[A-Z]{2})?)(?:\d)?(?:\.(forced|sdh|default))?\.(srt|ass|ssa|sub|vtt)$', filename.lower())
    if match:
        return match.group(1)
    return None


def get_base_name(file_path: Path) -> str:
    """
    Obtém o nome base do arquivo sem extensões de idioma e arquivo.

    Exemplo:
        "Filme.pt-BR.srt" -> "Filme"
        "Serie S01E01.mkv" -> "Serie S01E01"

    Args:
        file_path: Caminho do arquivo

    Returns:
        Nome base
    """
    name = file_path.stem

    # Remove código de idioma se presente
    name = re.sub(r'\.[a-z]{2,3}(?:-[A-Z]{2})?$', '', name)

    return name


def format_season_folder(season: int) -> str:
    """
    Formata nome da pasta de temporada.

    Args:
        season: Número da temporada

    Returns:
        Nome formatado (ex: "Season 01")
    """
    return f"Season {season:02d}"


def parse_subtitle_filename(file_path: Path) -> dict:
    """
    Analisa nome de arquivo de legenda e extrai informações.

    Args:
        file_path: Caminho do arquivo de legenda

    Returns:
        Dicionário com: base_name, language, flags (default, forced, sdh)
    """
    name = file_path.stem
    parts = name.split('.')

    info = {
        'base_name': parts[0],
        'language': None,
        'default': False,
        'forced': False,
        'sdh': False,
    }

    # Processa as partes do nome
    for part in parts[1:]:
        part_lower = part.lower()

        # Verifica flags
        if part_lower == 'default':
            info['default'] = True
        elif part_lower == 'forced':
            info['forced'] = True
        elif part_lower == 'sdh':
            info['sdh'] = True
        # Verifica código de idioma (2-3 letras, opcionalmente com região)
        elif re.match(r'^[a-z]{2,3}(?:-[A-Z]{2})?$', part):
            info['language'] = part

    return info
