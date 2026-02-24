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

# Pre-compiled regex patterns (avoid recompilation on every call)
_RE_FORBIDDEN = re.compile(FORBIDDEN_CHARS)
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_BRACKET_RELEASE = re.compile(r"\[(?!19|20)\w+[\w\s\.\-]*\]")
_RE_PAREN_NON_YEAR = re.compile(r"\((?!19\d{2}|20\d{2})[^\)]*\)")
_RE_YEAR_LOOSE = re.compile(r"\s+(19\d{2}|20\d{2})(?!\))\s*")
_RE_AUDIO_CHANNELS = re.compile(r"\b([257])\s+([01])\b")
_RE_REPEATED_SUFFIX = re.compile(r"(-\w+)\1+")
_RE_CONVERTED = re.compile(r"-converted", re.IGNORECASE)
_RE_RELEASE_GROUP_HYPHEN = re.compile(r"-[A-Z0-9]{2,}\b", re.IGNORECASE)
_RE_TRAILING_UPPERCASE = re.compile(r"\s+\b[A-Z]{2,6}\b\s*$")
_RE_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,\.!?;:])")
_RE_TRAILING_JUNK = re.compile(r"[\s\-\.]+$")
_RE_LEADING_JUNK = re.compile(r"^[\s\-\.]+")
_RE_YEAR = re.compile(r"[\(\[]?(19\d{2}|20\d{2})[\)\]]?")
_RE_SXXEXX = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})(?:-?[Ee](\d{1,2}))?")
_RE_NxNN = re.compile(r"\b(\d{1,2})x(\d{1,2})\b")

_RE_QUALITY_PATTERNS = [
    re.compile(r"\b(1080p|720p|480p|2160p|4K|HD|UHD|FHD)\b", re.IGNORECASE),
    re.compile(r"\b(BluRay|BRRip|BDRip|WEB-?DL|WEBRip|HDTV|DVDRip|DVD-?Rip|CAMRip|TS|TC)\b", re.IGNORECASE),
    re.compile(r"\b(x264|x265|H\.?264|H\.?265|HEVC|XviD|DivX|AVC)\b", re.IGNORECASE),
    re.compile(r"\b(Amazon|Netflix|Hulu|HBO|HMAX|Disney|Apple|Paramount|Peacock|Showtime|Starz)\b", re.IGNORECASE),
    re.compile(r"\b(Dual\.?Audio|DUAL)\b", re.IGNORECASE),
    re.compile(r"\b(Audio)\b", re.IGNORECASE),
    re.compile(r"\b(AAC|AC3|E-?AC-?3|DTS|DD\+?|MP3|FLAC|Dolby|Atmos|TrueHD)\b", re.IGNORECASE),
    re.compile(r"\b(5\.1|7\.1|2\.0)\b", re.IGNORECASE),
    re.compile(r"\b(EXTENDED|UNRATED|REMASTERED|DIRECTORS?\.?CUT|DC|IMAX)\b", re.IGNORECASE),
    re.compile(r"\b(converted|rip|web|hdtv|bluray)\b", re.IGNORECASE),
]

_RE_RESOLUTION_TAGS = [
    (re.compile(r"(?:^|[\s\._\-\[\(])(2160p|4K)(?:[\s\._\-\]\)]|$)", re.IGNORECASE), "2160p"),
    (re.compile(r"(?:^|[\s\._\-\[\(])(1080p)(?:[\s\._\-\]\)]|$)", re.IGNORECASE), "1080p"),
    (re.compile(r"(?:^|[\s\._\-\[\(])(720p)(?:[\s\._\-\]\)]|$)", re.IGNORECASE), "720p"),
    (re.compile(r"(?:^|[\s\._\-\[\(])(480p)(?:[\s\._\-\]\)]|$)", re.IGNORECASE), "480p"),
    (re.compile(r"(?:^|[\s\._\-\[\(])(8K)(?:[\s\._\-\]\)]|$)", re.IGNORECASE), "8K"),
]

_RELEASE_GROUPS = [
    "BRHD",
    "YTS",
    "YIFY",
    "RARBG",
    "ETRG",
    "PSA",
    "AMIABLE",
    "SPARKS",
    "FLEET",
    "ION10",
    "CMRG",
    "EVO",
    "NTb",
    "AMRAP",
    "FGT",
    "STUTTERSHIT",
    "VYNDROS",
    "MkvCage",
    "GalaxyRG",
    "DEFLATE",
    "NOGRP",
    "W4F",
    "ETHEL",
    "TOMMY",
    "AFG",
    "GECKOS",
]
_RE_RELEASE_GROUPS = [re.compile(rf"\b{g}\b", re.IGNORECASE) for g in _RELEASE_GROUPS]

_RE_LANG_CODE = re.compile(r"\.([a-z]{2,3}(?:[-_][A-Z]{2})?)(?:\d)?(?:\.(forced|sdh|default))?\.(srt|ass|ssa|sub|vtt)$")
_RE_LANG_SUFFIX = re.compile(r"\.[a-z]{2,3}(?:-[A-Z]{2})?$")
_RE_LANG_PART = re.compile(r"^[a-z]{2,3}(?:[-_][A-Z]{2})?$")

_RE_SE_ALT_PATTERNS = [
    re.compile(
        r"(?:Book|Volume|Vol|Part|Season|Temporada|Temp)\s*(\d{1,2})\s*[-\s]+(?:Episode|Episodio|Ep\.?|E)?\s*(\d{1,2})",
        re.IGNORECASE,
    ),
    re.compile(r"T(?:emp)?\.?\s*(\d{1,2})\s*E(?:p)?\.?\s*(\d{1,2})", re.IGNORECASE),
    re.compile(r"[\[\(\{]\s*(\d{1,2})x(\d{1,2})\s*[\]\)\}]", re.IGNORECASE),
    re.compile(r"(?:Cap\.?|Ep\.?|E)\s*(\d{1,2})", re.IGNORECASE),
    re.compile(r"[-\s](\d)(\d{2})(?:\D|$)", re.IGNORECASE),
]


# Subtitle quality scoring weights
_QUALITY_BLOCK_WEIGHT = 10
_QUALITY_LINE_WEIGHT = 2
_QUALITY_TINY_FILE_PENALTY = 0.1
_QUALITY_MIN_FILE_SIZE = 100  # bytes
_QUALITY_TINY_THRESHOLD = 1024  # bytes


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

        if file_size < _QUALITY_MIN_FILE_SIZE:
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
        blocks_score = subtitle_blocks * _QUALITY_BLOCK_WEIGHT

        # Bônus: número de linhas de texto
        text_score = text_lines * _QUALITY_LINE_WEIGHT

        if file_size < _QUALITY_TINY_THRESHOLD:
            size_score *= _QUALITY_TINY_FILE_PENALTY

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
    cleaned = _RE_FORBIDDEN.sub("", name)

    # Remove espaços extras
    cleaned = _RE_MULTI_SPACE.sub(" ", cleaned).strip()

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
    name = _RE_BRACKET_RELEASE.sub("", name)

    # Remove parênteses que NÃO são ano (1900-2099)
    # Remove: (BluRay), (DUAL), etc, mas preserva (1999), (2024)
    name = _RE_PAREN_NON_YEAR.sub("", name)

    # Remove ano solto (sem parênteses) quando está no meio/final do nome
    # Ex: "Matrix 1999 1080p" -> "Matrix 1080p"
    # Preserva apenas se estiver entre parênteses: (1999)
    name = _RE_YEAR_LOOSE.sub(" ", name)

    # Remove informações de qualidade e release comuns (padrões específicos)
    for pattern in _RE_QUALITY_PATTERNS:
        name = pattern.sub("", name)

    # Remove APENAS padrões de canais de áudio (5.1, 7.1, 2.0 -> "5 1", "7 1", "2 0")
    # NÃO remove dígitos isolados para preservar títulos como "Super 8", "District 9"
    name = _RE_AUDIO_CHANNELS.sub(" ", name)

    # Remove sufixos repetidos como "-converted-converted" (antes de remover grupos)
    name = _RE_REPEATED_SUFFIX.sub(r"\1", name)  # Remove repetições
    name = _RE_CONVERTED.sub("", name)

    # Remove grupo de release precedido por hífen (em qualquer posição)
    # Ex: -3LT0N, -YTS, -RARBG, -converted
    name = _RE_RELEASE_GROUP_HYPHEN.sub("", name)

    # Remove grupos de release comuns que aparecem soltos (sem hífen)
    # Ex: BRHD, YTS, YIFY, RARBG, ETRG, etc.
    for pattern in _RE_RELEASE_GROUPS:
        name = pattern.sub("", name)

    # Remove palavras em MAIÚSCULAS de 2-6 letras isoladas no final (geralmente grupos de release)
    # Mas preserva palavras conhecidas como "HD", "4K", "DC" (que já foram removidas antes)
    name = _RE_TRAILING_UPPERCASE.sub(" ", name)

    # Remove espaços múltiplos
    name = _RE_MULTI_SPACE.sub(" ", name).strip()

    # Remove espaços antes de pontuação
    name = _RE_SPACE_BEFORE_PUNCT.sub(r"\1", name)

    # Limpeza final: remove hífens, espaços e pontos isolados no final
    name = _RE_TRAILING_JUNK.sub("", name)
    name = _RE_LEADING_JUNK.sub("", name)  # Remove também do início se houver

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
    for pattern, tag in _RE_RESOLUTION_TAGS:
        match = pattern.search(name)
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
    match = _RE_YEAR.search(name)
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
    match = _RE_SXXEXX.search(name)
    if match:
        season = int(match.group(1))
        ep_start = int(match.group(2))
        ep_end = int(match.group(3)) if match.group(3) else ep_start
        return (season, ep_start, ep_end)

    # Padrão 1x01 (com word boundaries para não pegar anos como "2018" → "20x18")
    match = _RE_NxNN.search(name)
    if match:
        # Verifica se não é um ano (ex: "2018" não deve virar "20x18")
        # Anos válidos: 1900-2099
        match.group(0)  # Ex: "20x18"
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
    for pattern in _RE_SE_ALT_PATTERNS:
        match = pattern.search(name)
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


def normalize_language_code(lang_code: str) -> str:
    """
    Normaliza códigos de idioma de 2 ou 3 caracteres para o padrão de 3 letras.

    Args:
        lang_code: Código de idioma (pode ser en, eng, pt, pt-BR, pt_BR, br, etc.)

    Returns:
        Código normalizado de 3 letras (eng, por, spa, etc.)
    """
    # Remove qualquer região/país do código (pt-BR -> pt, pt_BR -> pt)
    base_code = lang_code.split('-')[0].split('_')[0].lower()

    # Mapa de códigos de 2 letras para 3 letras (ISO 639-1 -> ISO 639-2)
    code_map = {
        'en': 'eng',  # English
        'pt': 'por',  # Portuguese
        'br': 'por',  # Brazilian (não é código ISO, mas comum em legendas)
        'es': 'spa',  # Spanish
        'fr': 'fre',  # French
        'de': 'ger',  # German
        'it': 'ita',  # Italian
        'ja': 'jpn',  # Japanese
        'ko': 'kor',  # Korean
        'zh': 'chi',  # Chinese
        'ru': 'rus',  # Russian
        'ar': 'ara',  # Arabic
        'hi': 'hin',  # Hindi
        'nl': 'dut',  # Dutch
        'sv': 'swe',  # Swedish
        'no': 'nor',  # Norwegian
        'da': 'dan',  # Danish
        'fi': 'fin',  # Finnish
        'pl': 'pol',  # Polish
        'tr': 'tur',  # Turkish
        'he': 'heb',  # Hebrew
        'el': 'gre',  # Greek
        'cs': 'cze',  # Czech
        'hu': 'hun',  # Hungarian
        'ro': 'rum',  # Romanian
        'uk': 'ukr',  # Ukrainian
        'th': 'tha',  # Thai
        'vi': 'vie',  # Vietnamese
        'id': 'ind',  # Indonesian
        'ms': 'may',  # Malay
        'tl': 'fil',  # Filipino
    }

    # Se já está no formato de 3 letras, retorna normalizado
    if len(base_code) == 3:
        return base_code

    # Se é 2 letras, converte usando o mapa
    if len(base_code) == 2:
        return code_map.get(base_code, base_code)

    # Se não se encaixa em nenhum padrão, retorna como está
    return base_code


def has_language_code(filename: str) -> Optional[str]:
    """
    Verifica se o nome do arquivo já tem código de idioma.

    Args:
        filename: Nome do arquivo

    Returns:
        Código de idioma encontrado (normalizado para 3 letras) ou None
    """
    # Procura por padrões como .pt, .pt-BR, .pt_BR, .eng, .en, .eng2, .eng.forced, etc.
    # IMPORTANTE: Apenas ANTES da extensão do arquivo para evitar falsos positivos
    # Exemplos aceitos:
    #   "file.eng.srt" -> "eng"
    #   "file.en.srt" -> "eng"
    #   "file.eng2.srt" -> "eng"
    #   "file.eng.forced.srt" -> "eng"
    #   "file.por.srt" -> "por"
    #   "file.pt.srt" -> "por"
    #   "file.pt-BR.srt" -> "por"
    #   "file.pt_BR.srt" -> "por"
    #   "The.Great.Flood.srt" -> None (não pega "gre" de Great)

    # Padrão: .LANG[NUMERO][.forced|.sdh|.default].EXTENSAO
    # Aceita 2-3 letras, com região opcional (-XX ou _XX)
    match = _RE_LANG_CODE.search(filename.lower())
    if match:
        lang_code = match.group(1)
        # Normaliza o código para 3 letras
        return normalize_language_code(lang_code)
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
    name = _RE_LANG_SUFFIX.sub("", name)

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
        # Verifica código de idioma (2-3 letras, opcionalmente com região como pt-BR ou pt_BR)
        elif _RE_LANG_PART.match(part_lower):
            # Normaliza o código de idioma para 3 letras
            info['language'] = normalize_language_code(part_lower)

    return info
