"""Sistema de configuração do jellyfix"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

# Versão do aplicativo
APP_VERSION = "2.0.1"


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

    # Idiomas de legendas MANTIDOS (NÃO serão removidos)
    # Por padrão: português e inglês
    kept_languages: list = field(default_factory=lambda: ["por", "eng"])

    # Lista completa de idiomas conhecidos (para interface de seleção)
    all_languages: dict = field(default_factory=lambda: {
        "ara": "Árabe",
        "baq": "Basco",
        "bul": "Búlgaro",
        "cat": "Catalão",
        "chi": "Chinês",
        "cze": "Tcheco",
        "dan": "Dinamarquês",
        "dut": "Holandês",
        "eng": "Inglês",
        "fil": "Filipino",
        "fin": "Finlandês",
        "fre": "Francês",
        "ger": "Alemão",
        "glg": "Galego",
        "gre": "Grego",
        "heb": "Hebraico",
        "hin": "Hindi",
        "hrv": "Croata",
        "hun": "Húngaro",
        "ind": "Indonésio",
        "ita": "Italiano",
        "jpn": "Japonês",
        "kor": "Coreano",
        "lav": "Letão",
        "lit": "Lituano",
        "may": "Malaio",
        "nob": "Norueguês (Bokmål)",
        "nor": "Norueguês",
        "pol": "Polonês",
        "por": "Português",
        "rum": "Romeno",
        "rus": "Russo",
        "slo": "Eslovaco",
        "slv": "Esloveno",
        "spa": "Espanhol",
        "swe": "Sueco",
        "tam": "Tâmil",
        "tel": "Telugu",
        "tha": "Tailandês",
        "tur": "Turco",
        "ukr": "Ucraniano",
        "vie": "Vietnamita"
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
                    'remove_language_variants', 'organize_folders', 'fetch_metadata']:
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
