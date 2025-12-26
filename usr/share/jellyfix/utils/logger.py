"""Sistema de logging com Rich"""

from rich.console import Console
from rich.theme import Theme
from rich.markup import escape
from pathlib import Path
from datetime import datetime
from typing import Optional

# Tema customizado
custom_theme = Theme({
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "action": "bold magenta",
    "debug": "dim",
    "title": "bold blue",
})

# Console global
console = Console(theme=custom_theme)


class Logger:
    """Logger com suporte a cores e arquivo"""

    def __init__(self, log_file: Optional[Path] = None, verbose: bool = False, quiet: bool = False):
        self.log_file = log_file
        self.verbose = verbose
        self.quiet = quiet
        self.console = console

    def _write_to_file(self, message: str, level: str):
        """Escreve mensagem no arquivo de log"""
        if self.log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{level}] {message}\n")

    def info(self, message: str):
        """Mensagem informativa"""
        if not self.quiet:
            self.console.print(f"[info]ℹ {escape(message)}[/info]")
        self._write_to_file(message, "INFO")

    def success(self, message: str):
        """Mensagem de sucesso"""
        if not self.quiet:
            self.console.print(f"[success]✓ {escape(message)}[/success]")
        self._write_to_file(message, "SUCCESS")

    def warning(self, message: str):
        """Mensagem de aviso"""
        if not self.quiet:
            self.console.print(f"[warning]⚠ {escape(message)}[/warning]")
        self._write_to_file(message, "WARNING")

    def error(self, message: str):
        """Mensagem de erro"""
        self.console.print(f"[error]✗ {escape(message)}[/error]")
        self._write_to_file(message, "ERROR")

    def action(self, message: str):
        """Ação sendo executada"""
        if not self.quiet:
            self.console.print(f"[action]→ {escape(message)}[/action]")
        self._write_to_file(message, "ACTION")

    def debug(self, message: str):
        """Mensagem de debug (apenas se verbose)"""
        if self.verbose:
            self.console.print(f"[debug]🐛 {escape(message)}[/debug]")
        self._write_to_file(message, "DEBUG")

    def title(self, message: str):
        """Título de seção"""
        if not self.quiet:
            self.console.print(f"\n[title]{'=' * 60}[/title]")
            self.console.print(f"[title]{message.center(60)}[/title]")
            self.console.print(f"[title]{'=' * 60}[/title]\n")
        self._write_to_file(message, "TITLE")


# Logger global
_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Retorna o logger global"""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger


def set_logger(logger: Logger):
    """Define o logger global"""
    global _logger
    _logger = logger
