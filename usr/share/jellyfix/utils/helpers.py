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
FORBIDDEN_CHARS = r'[<>"/\\|?*]'  # Removido ':' para permitir em Linux

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
    # Substitui pontos, underscores e hífen duplo por espaços
    name = name.replace('.', ' ').replace('_', ' ').replace('--', ' ')

    # Remove colchetes com conteúdo de release (mas preserva ano)
    # Remove: [1080p], [BluRay], [HEVC], [DUAL], etc
    name = re.sub(r'\[(?!19|20)\w+[\w\s\.\-]*\]', '', name)

    # Remove parênteses que NÃO são ano (1900-2099)
    # Remove: (BluRay), (DUAL), etc, mas preserva (1999), (2024)
    name = re.sub(r'\((?!19\d{2}|20\d{2})[^\)]*\)', '', name)

    # Remove ano solto (sem parênteses) quando está no meio/final do nome
    # Ex: "Matrix 1999 1080p" -> "Matrix 1080p"
    # Preserva apenas se estiver entre parênteses: (1999)
    name = re.sub(r'\s+(19\d{2}|20\d{2})(?!\))\s*', ' ', name)

    # Remove informações de qualidade e release comuns (padrões específicos)
    quality_patterns = [
        # Resoluções
        r'\b(1080p|720p|480p|2160p|4K|HD|UHD|FHD)\b',
        # Formatos de vídeo (palavras específicas)
        r'\b(BluRay|BRRip|BDRip|WEB-?DL|WEBRip|HDTV|DVDRip|DVD-?Rip|CAMRip|TS|TC)\b',
        # Codecs
        r'\b(x264|x265|H\.?264|H\.?265|HEVC|XviD|DivX|AVC)\b',
        # Plataformas de streaming
        r'\b(Amazon|Netflix|Hulu|HBO|HMAX|Disney|Apple|Paramount|Peacock|Showtime|Starz)\b',
        # Áudio (deve vir antes para pegar "Dual Audio" junto)
        r'\b(Dual\.?Audio|DUAL)\b',
        r'\b(Audio)\b',  # Remove "Audio" sozinho também
        r'\b(AAC|AC3|E-?AC-?3|DTS|DD\+?|MP3|FLAC|Dolby|Atmos|TrueHD)\b',
        r'\b(5\.1|7\.1|2\.0)\b',
        # Edições especiais
        r'\b(EXTENDED|UNRATED|REMASTERED|DIRECTORS?\.?CUT|DC|IMAX)\b',
        # Sufixos técnicos comuns
        r'\b(converted|rip|web|hdtv|bluray)\b',
    ]

    for pattern in quality_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove APENAS padrões de canais de áudio (5.1, 7.1, 2.0 -> "5 1", "7 1", "2 0")
    # NÃO remove dígitos isolados para preservar títulos como "Super 8", "District 9"
    name = re.sub(r'\b([257])\s+([01])\b', ' ', name)

    # Remove sufixos repetidos como "-converted-converted" (antes de remover grupos)
    name = re.sub(r'(-\w+)\1+', r'\1', name)  # Remove repetições
    name = re.sub(r'-converted', '', name, flags=re.IGNORECASE)

    # Remove grupo de release precedido por hífen (em qualquer posição)
    # Ex: -3LT0N, -YTS, -RARBG, -converted
    name = re.sub(r'-[A-Z0-9]{2,}\b', '', name, flags=re.IGNORECASE)

    # Remove grupos de release comuns que aparecem soltos (sem hífen)
    # Ex: BRHD, YTS, YIFY, RARBG, ETRG, etc.
    release_groups = [
        'BRHD', 'YTS', 'YIFY', 'RARBG', 'ETRG', 'PSA', 'AMIABLE',
        'SPARKS', 'FLEET', 'ION10', 'CMRG', 'EVO', 'NTb', 'AMRAP',
        'FGT', 'STUTTERSHIT', 'VYNDROS', 'MkvCage', 'GalaxyRG',
        'DEFLATE', 'NOGRP', 'W4F', 'ETHEL', 'TOMMY', 'AFG', 'GECKOS'
    ]
    for group in release_groups:
        name = re.sub(rf'\b{group}\b', '', name, flags=re.IGNORECASE)

    # Remove palavras em MAIÚSCULAS de 2-6 letras isoladas no final (geralmente grupos de release)
    # Mas preserva palavras conhecidas como "HD", "4K", "DC" (que já foram removidas antes)
    name = re.sub(r'\s+\b[A-Z]{2,6}\b\s*$', ' ', name)

    # Remove espaços múltiplos
    name = re.sub(r'\s+', ' ', name).strip()

    # Remove espaços antes de pontuação
    name = re.sub(r'\s+([,\.!?;:])', r'\1', name)

    # Limpeza final: remove hífens, espaços e pontos isolados no final
    name = re.sub(r'[\s\-\.]+$', '', name)
    name = re.sub(r'^[\s\-\.]+', '', name)  # Remove também do início se houver

    return name.strip()


def extract_quality_tag(name: str) -> Optional[str]:
    """
    Extrai tag de qualidade do nome do arquivo.

    Suporta formatos:
    - Resoluções: 480p, 720p, 1080p, 2160p, 4K, 8K
    - Dentro ou fora de colchetes/parênteses
    - Com ou sem separadores (_1080p_, .1080p., 1080p)

    Args:
        name: Nome do arquivo

    Returns:
        Tag de qualidade ou None
    """
    # Resoluções (aceita word boundary OU underscore/ponto)
    resolution_patterns = [
        (r'(?:^|[\s\._\-\[\(])(2160p|4K)(?:[\s\._\-\]\)]|$)', '2160p'),  # 4K
        (r'(?:^|[\s\._\-\[\(])(1080p)(?:[\s\._\-\]\)]|$)', '1080p'),
        (r'(?:^|[\s\._\-\[\(])(720p)(?:[\s\._\-\]\)]|$)', '720p'),
        (r'(?:^|[\s\._\-\[\(])(480p)(?:[\s\._\-\]\)]|$)', '480p'),
        (r'(?:^|[\s\._\-\[\(])(8K)(?:[\s\._\-\]\)]|$)', '8K'),
    ]

    for pattern, tag in resolution_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return tag

    return None


def detect_video_resolution(file_path: Path) -> Optional[str]:
    """
    Detecta resolução de vídeo usando ffprobe.

    Args:
        file_path: Caminho do arquivo de vídeo

    Returns:
        Tag de resolução (480p, 720p, 1080p, 2160p) ou None
    """
    try:
        import subprocess
        import json

        # Verifica se ffprobe está disponível
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(file_path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)

        # Procura stream de vídeo
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                height = stream.get('height')
                if height:
                    # Mapeia altura para tag de qualidade
                    if height >= 2160:
                        return '2160p'
                    elif height >= 1080:
                        return '1080p'
                    elif height >= 720:
                        return '720p'
                    elif height >= 480:
                        return '480p'
                    else:
                        return None

        return None

    except (ImportError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


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
    - S01E01, s01e01
    - 1x01
    - S01E01-E02 (múltiplos episódios)
    - Book 1 - 01, Volume 1 - 01, Part 1 - 01
    - Season 1 Episode 01, Temporada 1 Episodio 01

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

    # Padrão 1x01 (com word boundaries para não pegar anos como "2018" → "20x18")
    match = re.search(r'\b(\d{1,2})x(\d{1,2})\b', name)
    if match:
        # Verifica se não é um ano (ex: "2018" não deve virar "20x18")
        # Anos válidos: 1900-2099
        full_match = match.group(0)  # Ex: "20x18"
        # Se parece com ano, ignora
        potential_year = match.group(1) + match.group(2)  # Ex: "2018"
        if len(potential_year) == 4 and potential_year.isdigit():
            year_val = int(potential_year)
            if 1900 <= year_val <= 2099:
                # É um ano, não é SxxExx
                return None

        season = int(match.group(1))
        episode = int(match.group(2))
        return (season, episode, episode)

    # Padrões alternativos: Book 1 - 01, T01E01, [01x01], etc
    patterns = [
        # Book 1 - 01, Volume 2 - 05, Part 3 - 12, Season 1 Episode 01
        r'(?:Book|Volume|Vol|Part|Season|Temporada|Temp)\s*(\d{1,2})\s*[-\s]+(?:Episode|Episodio|Ep\.?|E)?\s*(\d{1,2})',
        # T01E01, T1E1, Temp01Ep01
        r'T(?:emp)?\.?\s*(\d{1,2})\s*E(?:p)?\.?\s*(\d{1,2})',
        # [01x01], (1x01), {1x01}
        r'[\[\(\{]\s*(\d{1,2})x(\d{1,2})\s*[\]\)\}]',
        # Cap 01, Ep 01, E01
        r'(?:Cap\.?|Ep\.?|E)\s*(\d{1,2})',
        # - 101, - 201 (temporada implícita: 1x01, 2x01)
        r'[-\s](\d)(\d{2})(?:\D|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            # Verifica se o match não está dentro de um ano
            # Ex: "Movie 2018" não deve ser S20E18 ou S2E01
            match_start = match.start()
            match_end = match.end()

            # Verifica se há um dígito antes do match (formando ano)
            if match_start > 0 and name[match_start - 1].isdigit():
                # Pode ser parte de um ano maior
                continue

            # Verifica se há dígito depois (formando ano)
            if match_end < len(name) and name[match_end].isdigit():
                # Pode ser parte de um ano maior
                continue

            season = int(match.group(1))
            episode = int(match.group(2)) if len(match.groups()) > 1 else int(match.group(1))
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
