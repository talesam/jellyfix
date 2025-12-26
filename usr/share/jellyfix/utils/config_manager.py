"""Gerenciador de configuração persistente em JSON"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigManager:
    """Gerencia configurações persistentes em arquivo JSON"""

    def __init__(self):
        self.config_dir = Path.home() / '.jellyfix'
        self.config_file = self.config_dir / 'config.json'
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Garante que o diretório de configuração existe"""
        self.config_dir.mkdir(exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """
        Carrega configurações do arquivo JSON.

        Returns:
            Dicionário com configurações ou dict vazio se arquivo não existir
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, config: Dict[str, Any]):
        """
        Salva configurações no arquivo JSON.

        Args:
            config: Dicionário com configurações
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Erro ao salvar configuração: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de configuração.

        Args:
            key: Chave da configuração
            default: Valor padrão se não existir

        Returns:
            Valor da configuração ou default
        """
        config = self.load()
        return config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Define valor de configuração.

        Args:
            key: Chave da configuração
            value: Valor a definir
        """
        config = self.load()
        config[key] = value
        self.save(config)

    def get_tmdb_api_key(self) -> Optional[str]:
        """Obtém chave da API TMDB"""
        return self.get('tmdb_api_key')

    def set_tmdb_api_key(self, key: str):
        """Define chave da API TMDB"""
        self.set('tmdb_api_key', key)

    def get_tvdb_api_key(self) -> Optional[str]:
        """Obtém chave da API TVDB"""
        return self.get('tvdb_api_key')

    def set_tvdb_api_key(self, key: str):
        """Define chave da API TVDB"""
        self.set('tvdb_api_key', key)

    def get_min_pt_words(self) -> int:
        """Obtém número mínimo de palavras portuguesas"""
        return self.get('min_pt_words', 5)

    def set_min_pt_words(self, value: int):
        """Define número mínimo de palavras portuguesas"""
        self.set('min_pt_words', value)

    def export_config(self) -> str:
        """
        Exporta configuração atual como JSON formatado.

        Returns:
            String JSON formatada
        """
        config = self.load()
        return json.dumps(config, indent=4, ensure_ascii=False)

    def import_config(self, json_str: str):
        """
        Importa configuração de string JSON.

        Args:
            json_str: String JSON com configurações
        """
        try:
            config = json.loads(json_str)
            self.save(config)
        except json.JSONDecodeError as e:
            raise Exception(f"JSON inválido: {e}")

    def reset(self):
        """Remove arquivo de configuração (reset para padrões)"""
        if self.config_file.exists():
            self.config_file.unlink()

    def get_config_path(self) -> str:
        """Retorna caminho do arquivo de configuração"""
        return str(self.config_file)
