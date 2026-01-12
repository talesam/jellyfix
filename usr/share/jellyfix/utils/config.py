"""Configuration system for Jellyfix"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

# Application version
APP_VERSION = "2.5.1"


@dataclass
class Config:
    """Configurações do jellyfix"""

    # Diretórios
    work_dir: Path = field(default_factory=Path.cwd)
    backup_dir: Optional[Path] = None
    log_file: Optional[Path] = None

    # Operações
    rename_por2: bool = True  # Mantido por compatibilidade, mas agora renomeia TODAS as variações
    rename_no_lang: bool = True
    remove_foreign_subs: bool = True
    remove_language_variants: bool = False  # Remove eng2, por3, etc. quando já existe eng, por
    remove_unwanted: bool = True
    organize_folders: bool = True
    fetch_metadata: bool = True
    add_quality_tag: bool = True  # Adiciona tag de qualidade (1080p, 720p, etc)
    use_ffprobe: bool = False  # Usa ffprobe para detectar resolução (mais lento mas preciso)
    ask_on_multiple_results: bool = False  # Pergunta ao usuário quando há múltiplos resultados TMDB
    rename_nfo: bool = True  # Renomeia arquivos NFO para corresponder ao vídeo
    remove_non_media: bool = False  # Remove arquivos que não sejam .srt ou .mp4

    # Detecção de português
    min_pt_words: int = 5

    # Modos de execução
    dry_run: bool = True
    interactive: bool = True
    verbose: bool = False
    quiet: bool = False
    auto_confirm: bool = False

    # APIs
    tmdb_api_key: str = ""
    tvdb_api_key: str = ""

    # Subtitle languages to KEEP (will NOT be removed)
    # Default: Portuguese and English
    kept_languages: list = field(default_factory=lambda: ["por", "eng"])

    # Complete list of known languages (for selection interface)
    all_languages: dict = field(default_factory=lambda: {
        "ara": "Arabic",
        "baq": "Basque",
        "bul": "Bulgarian",
        "cat": "Catalan",
        "chi": "Chinese",
        "cze": "Czech",
        "dan": "Danish",
        "dut": "Dutch",
        "eng": "English",
        "fil": "Filipino",
        "fin": "Finnish",
        "fre": "French",
        "ger": "German",
        "glg": "Galician",
        "gre": "Greek",
        "heb": "Hebrew",
        "hin": "Hindi",
        "hrv": "Croatian",
        "hun": "Hungarian",
        "ind": "Indonesian",
        "ita": "Italian",
        "jpn": "Japanese",
        "kor": "Korean",
        "lav": "Latvian",
        "lit": "Lithuanian",
        "may": "Malay",
        "nob": "Norwegian (Bokmål)",
        "nor": "Norwegian",
        "pol": "Polish",
        "por": "Portuguese",
        "rum": "Romanian",
        "rus": "Russian",
        "slo": "Slovak",
        "slv": "Slovenian",
        "spa": "Spanish",
        "swe": "Swedish",
        "tam": "Tamil",
        "tel": "Telugu",
        "tha": "Thai",
        "tur": "Turkish",
        "ukr": "Ukrainian",
        "vie": "Vietnamese"
    })

    def __post_init__(self):
        """Converte strings para Path objects"""
        if isinstance(self.work_dir, str):
            self.work_dir = Path(self.work_dir)
        if self.backup_dir and isinstance(self.backup_dir, str):
            self.backup_dir = Path(self.backup_dir)
        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

        # Carrega configurações do arquivo persistente
        from .config_manager import ConfigManager
        config_mgr = ConfigManager()

        # API keys com prioridade:
        # 1. Valor já fornecido
        # 2. Arquivo de configuração JSON
        # 3. Variável de ambiente
        if not self.tmdb_api_key:
            self.tmdb_api_key = config_mgr.get_tmdb_api_key() or os.getenv("TMDB_API_KEY", "")

        if not self.tvdb_api_key:
            self.tvdb_api_key = config_mgr.get_tvdb_api_key() or os.getenv("TVDB_API_KEY", "")

        # Carrega configurações do arquivo persistente
        saved_languages = config_mgr.get('kept_languages')
        if saved_languages:
            self.kept_languages = saved_languages

        # Carrega opções booleanas
        for key in ['rename_por2', 'rename_no_lang', 'remove_foreign_subs',
                    'remove_language_variants', 'organize_folders', 'fetch_metadata',
                    'ask_on_multiple_results', 'rename_nfo', 'remove_non_media']:
            saved_value = config_mgr.get(key)
            if saved_value is not None:
                setattr(self, key, saved_value)

        # Carrega min_pt_words
        saved_min_pt = config_mgr.get('min_pt_words')
        if saved_min_pt is not None:
            self.min_pt_words = saved_min_pt


# Configuração global (singleton pattern)
_config: Optional[Config] = None


def get_config() -> Config:
    """Retorna a configuração global"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """Define a configuração global"""
    global _config
    _config = config
