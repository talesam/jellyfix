"""Menu interativo com Rich e Questionary"""

from pathlib import Path
from typing import Optional
import questionary
from questionary import Style
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape
from rich import box

from ..core.scanner import scan_library, ScanResult
from ..core.renamer import Renamer
from ..core.metadata import MetadataFetcher
from ..utils.config import Config, get_config
from ..utils.logger import get_logger, console
from ..utils.config_manager import ConfigManager


# Estilo customizado para o menu
custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#4caf50 bold'),  # Verde
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#4caf50'),  # Verde
    ('separator', 'fg:#cc5454'),
    ('instruction', ''),
    ('text', ''),
    ('checkbox', 'fg:#4caf50'),  # Verde para checkbox
    ('checkbox-selected', 'fg:#4caf50 bold'),  # Verde bold quando selecionado
])


class InteractiveMenu:
    """Menu interativo do jellyfix"""

    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.console = console

    def show_banner(self):
        """Mostra banner do jellyfix"""
        self.console.clear()  # Limpa a tela
        banner = Text()
        banner.append("\n╔══════════════════════════════════════════════════════════╗\n", style="bold blue")
        banner.append("║                                                          ║\n", style="bold blue")
        banner.append("║          ", style="bold blue")
        banner.append("         🎬  JELLYFIX  🎬", style="bold magenta")
        banner.append("                       ║\n", style="bold blue")
        banner.append("║                                                          ║\n", style="bold blue")
        banner.append("║     ", style="bold blue")
        banner.append("Organizador Inteligente de Bibliotecas Jellyfin", style="cyan")
        banner.append("      ║\n", style="bold blue")
        banner.append("║                                                          ║\n", style="bold blue")
        banner.append("╚══════════════════════════════════════════════════════════╝\n", style="bold blue")
        self.console.print(banner)

    def main_menu(self) -> str:
        """Menu principal"""
        return questionary.select(
            "O que você deseja fazer?",
            choices=[
                "📂 Escanear biblioteca",
                "🔧 Configurações",
                "🚀 Processar arquivos",
                "ℹ️  Ajuda",
                "❌ Sair"
            ],
            style=custom_style,
            instruction="(Use as setas para navegar)"
        ).ask()

    def select_directory(self, default: Optional[Path] = None) -> Optional[Path]:
        """Seleciona diretório para processar de forma interativa"""
        if default is None:
            default = Path.cwd()

        current_dir = default.resolve()

        while True:
            self.console.clear()
            self.console.print("\n[bold cyan]📂 Navegador de Pastas[/bold cyan]\n")
            self.console.print(f"[dim]Pasta atual:[/dim] [yellow]{current_dir}[/yellow]\n")

            # Lista diretórios da pasta atual
            try:
                dirs = []

                # Adiciona opção de selecionar pasta atual
                dirs.append("✓ Selecionar esta pasta")

                # Adiciona opção de voltar (se não for root)
                if current_dir.parent != current_dir:
                    dirs.append("⬆️  .. (voltar)")

                # Adiciona subpastas
                subdirs = sorted([d for d in current_dir.iterdir() if d.is_dir() and not d.name.startswith('.')], key=lambda x: x.name.lower())
                for subdir in subdirs:
                    dirs.append(f"📁 {subdir.name}/")

                # Se não há subpastas
                if len(dirs) <= 2:  # Apenas "selecionar" e opcionalmente "voltar"
                    dirs.append("   (Nenhuma subpasta)")

                # Adiciona opção de digitar caminho manualmente
                dirs.append("⌨️  Digitar caminho manualmente")
                dirs.append("❌ Cancelar")

                choice = questionary.select(
                    "Escolha uma opção:",
                    choices=dirs,
                    style=custom_style,
                    instruction="(Use ↑↓ para navegar, ENTER para selecionar)"
                ).ask()

                if not choice or choice == "❌ Cancelar":
                    return None

                elif choice == "✓ Selecionar esta pasta":
                    return current_dir

                elif choice == "⬆️  .. (voltar)":
                    current_dir = current_dir.parent

                elif choice == "⌨️  Digitar caminho manualmente":
                    self.console.print("\n[cyan]Digite o caminho completo da pasta:[/cyan]")
                    path_str = questionary.text(
                        "Caminho:",
                        default=str(current_dir),
                        style=custom_style
                    ).ask()

                    if path_str:
                        new_path = Path(path_str).expanduser().resolve()
                        if new_path.exists() and new_path.is_dir():
                            return new_path
                        else:
                            self.console.print("[red]❌ Pasta não encontrada![/red]")
                            self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")
                    continue

                elif choice.startswith("📁 "):
                    # Entra na subpasta
                    folder_name = choice.replace("📁 ", "").rstrip("/")
                    current_dir = current_dir / folder_name

                elif choice == "   (Nenhuma subpasta)":
                    continue

            except PermissionError:
                self.console.print(f"[red]❌ Sem permissão para acessar: {current_dir}[/red]")
                self.console.input("\n[dim]Pressione ENTER para voltar...[/dim]")
                if current_dir.parent != current_dir:
                    current_dir = current_dir.parent
                else:
                    return None

    def show_scan_results(self, result: ScanResult):
        """Mostra resultados do scan"""
        self.console.clear()  # Limpa a tela
        self.console.print("\n")
        self.console.print(Panel.fit(
            "📊 Resultados do Scan",
            style="bold green",
            border_style="green"
        ))

        # Tabela de estatísticas
        stats_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        stats_table.add_column("Categoria", style="cyan")
        stats_table.add_column("Quantidade", justify="right", style="magenta")

        stats_table.add_row("📹 Arquivos de vídeo", str(len(result.video_files)))
        stats_table.add_row("  ├─ 🎬 Filmes", str(result.total_movies))
        stats_table.add_row("  └─ 📺 Episódios", str(result.total_episodes))
        stats_table.add_row("📝 Legendas", str(len(result.subtitle_files)))
        stats_table.add_row("  ├─ Variações", str(len(result.variant_subtitles)))
        stats_table.add_row("  ├─ Sem idioma", str(len(result.no_lang_subtitles)))
        stats_table.add_row("  ├─ Estrangeiras", str(len(result.foreign_subtitles)))
        stats_table.add_row("  └─ Com idioma", str(len(result.kept_subtitles)))
        stats_table.add_row("🖼️  Imagens", str(len(result.image_files)))
        stats_table.add_row("📄 Arquivos NFO", str(len(result.nfo_files)))
        stats_table.add_row("❓ Outros", str(len(result.other_files)))

        self.console.print(stats_table)

        # Ações sugeridas
        if result.variant_subtitles or result.no_lang_subtitles or result.foreign_subtitles:
            self.console.print("\n")
            self.console.print(Panel(
                "[yellow]💡 Ações sugeridas:[/yellow]\n\n"
                f"• {len(result.variant_subtitles)} variações de legendas (.lang2, .lang3) podem ser processadas\n"
                f"• {len(result.no_lang_subtitles)} legendas sem código de idioma\n"
                f"• {len(result.foreign_subtitles)} legendas estrangeiras podem ser removidas",
                title="Sugestões",
                border_style="yellow"
            ))

    def show_operation_preview(self, renamer: Renamer):
        """Mostra preview das operações"""
        self.console.clear()  # Limpa a tela
        operations = renamer.operations

        if not operations:
            self.console.print("\n✓ Nenhuma operação necessária. Tudo já está organizado!\n", style="bold green")
            return

        self.console.print("\n")
        self.console.print(Panel.fit(
            f"📋 Preview de Operações ({len(operations)} arquivos)",
            style="bold yellow",
            border_style="yellow"
        ))

        # Agrupa por tipo de operação
        renames = [op for op in operations if op.operation_type == 'rename']
        moves = [op for op in operations if op.operation_type == 'move']
        move_renames = [op for op in operations if op.operation_type == 'move_rename']
        deletes = [op for op in operations if op.operation_type == 'delete']

        # Mostra tabela de operações
        table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        table.add_column("Tipo", style="cyan", width=15)
        table.add_column("Arquivo Original", style="white")
        table.add_column("→", style="bold magenta", width=3)
        table.add_column("Destino", style="green")

        # Limita a 20 operações na preview
        preview_ops = operations[:20]
        for op in preview_ops:
            if op.operation_type == 'delete':
                table.add_row(
                    "🗑️ REMOVER",
                    escape(str(op.source.name)),
                    "→",
                    "[red]REMOVER[/red]"
                )
            elif op.operation_type == 'move_rename':
                table.add_row(
                    "📦✏️ MOVER+RENOMEAR",
                    escape(str(op.source)),
                    "→",
                    escape(str(op.destination))
                )
            elif op.operation_type == 'move':
                table.add_row(
                    "📦 MOVER",
                    escape(str(op.source)),
                    "→",
                    escape(str(op.destination))
                )
            else:  # rename
                table.add_row(
                    "✏️ RENOMEAR",
                    escape(str(op.source.name)),
                    "→",
                    escape(str(op.destination.name))
                )

        self.console.print(table)

        if len(operations) > 20:
            self.console.print(f"\n[dim]... e mais {len(operations) - 20} operações[/dim]\n")

        # Resumo
        self.console.print("\n")
        summary = Table.grid(padding=(0, 2))

        if len(move_renames) > 0:
            summary.add_row(
                f"[cyan]📦✏️  Mover + Renomear:[/cyan]",
                f"[bold]{len(move_renames)}[/bold]"
            )
        if len(moves) > 0:
            summary.add_row(
                f"[cyan]📦 Mover:[/cyan]",
                f"[bold]{len(moves)}[/bold]"
            )
        if len(renames) > 0:
            summary.add_row(
                f"[cyan]✏️  Renomear:[/cyan]",
                f"[bold]{len(renames)}[/bold]"
            )
        if len(deletes) > 0:
            summary.add_row(
                f"[cyan]🗑️  Remover:[/cyan]",
                f"[bold red]{len(deletes)}[/bold red]"
            )

        self.console.print(Panel(summary, title="Resumo", border_style="cyan"))

    def confirm_operations(self) -> bool:
        """Confirma execução das operações"""
        return questionary.confirm(
            "Deseja executar estas operações?",
            default=False,
            style=custom_style
        ).ask()

    def settings_menu(self, config: Config) -> Config:
        """Menu de configurações"""
        while True:
            self.console.clear()  # Limpa a tela
            self.console.print("\n")
            self.console.print(Panel.fit(
                "⚙️  Configurações",
                style="bold blue",
                border_style="blue"
            ))

            kept_langs_str = ", ".join(config.kept_languages) if config.kept_languages else "nenhum"
            choice = questionary.select(
                "O que deseja configurar?",
                choices=[
                    f"{'✓' if config.rename_por2 else '✗'} Renomear variações (lang2→lang, lang3→lang)",
                    f"{'✓' if config.remove_language_variants else '✗'} Remover variações duplicadas (lang2, lang3)",
                    f"{'✓' if config.rename_no_lang else '✗'} Adicionar código de idioma a legendas",
                    f"{'✓' if config.remove_foreign_subs else '✗'} Remover legendas estrangeiras",
                    f"🌍 Idiomas mantidos: {kept_langs_str}",
                    f"{'✓' if config.organize_folders else '✗'} Organizar em pastas (Season XX)",
                    f"{'✓' if config.fetch_metadata else '✗'} Buscar metadados (TMDB/TVDB)",
                    f"Min. palavras portuguesas: {config.min_pt_words}",
                    "🔑 Configurar APIs (TMDB/TVDB)",
                    "← Voltar"
                ],
                style=custom_style,
                instruction="(Use as setas ↑↓ e ENTER para selecionar)"
            ).ask()

            if choice == "← Voltar":
                break
            elif "Renomear variações" in choice:
                config.rename_por2 = not config.rename_por2
                config_mgr = ConfigManager()
                config_mgr.set('rename_por2', config.rename_por2)
            elif "Remover variações duplicadas" in choice:
                config.remove_language_variants = not config.remove_language_variants
                config_mgr = ConfigManager()
                config_mgr.set('remove_language_variants', config.remove_language_variants)
            elif "código de idioma" in choice:
                config.rename_no_lang = not config.rename_no_lang
                config_mgr = ConfigManager()
                config_mgr.set('rename_no_lang', config.rename_no_lang)
            elif "estrangeiras" in choice:
                config.remove_foreign_subs = not config.remove_foreign_subs
                config_mgr = ConfigManager()
                config_mgr.set('remove_foreign_subs', config.remove_foreign_subs)
            elif "Idiomas mantidos" in choice:
                self._language_selection_menu(config)
            elif "Organizar em pastas" in choice:
                config.organize_folders = not config.organize_folders
                config_mgr = ConfigManager()
                config_mgr.set('organize_folders', config.organize_folders)
            elif "Buscar metadados" in choice:
                config.fetch_metadata = not config.fetch_metadata
                config_mgr = ConfigManager()
                config_mgr.set('fetch_metadata', config.fetch_metadata)
            elif "palavras portuguesas" in choice:
                new_value = questionary.text(
                    "Número mínimo de palavras portuguesas:",
                    default=str(config.min_pt_words),
                    style=custom_style
                ).ask()
                try:
                    value = int(new_value)
                    config.min_pt_words = value
                    # Salva no arquivo de configuração
                    config_mgr = ConfigManager()
                    config_mgr.set_min_pt_words(value)
                    self.console.print("[green]✓ Salvo em ~/.jellyfix/config.json[/green]")
                except ValueError:
                    self.console.print("[red]Valor inválido![/red]")
                self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")
            elif "Configurar APIs" in choice:
                self._api_settings_menu(config)

        return config

    def _language_selection_menu(self, config: Config):
        """Menu de seleção de idiomas mantidos"""
        self.console.clear()
        self.console.print("\n")
        self.console.print(Panel.fit(
            "🌍 Seleção de Idiomas Mantidos\n\n"
            "[dim]Selecione os idiomas que DESEJA MANTER (não serão removidos)\n"
            "Use ESPAÇO para marcar/desmarcar, ENTER para confirmar[/dim]",
            style="bold blue",
            border_style="blue"
        ))

        # Cria lista de escolhas ordenada alfabeticamente pelo nome do idioma
        choices = []
        for code, name in sorted(config.all_languages.items(), key=lambda x: x[1]):
            display_name = f"{name} ({code})"
            choices.append(questionary.Choice(
                title=display_name,
                value=code,
                checked=(code in config.kept_languages)
            ))

        selected = questionary.checkbox(
            "Selecione os idiomas que DESEJA MANTER:",
            choices=choices,
            style=custom_style,
            instruction="(ESPAÇO = marcar/desmarcar, ENTER = confirmar)"
        ).ask()

        if selected is not None:
            config.kept_languages = selected
            self.console.print(f"\n[green]✓ Idiomas mantidos: {', '.join(selected)}[/green]")

            # Salva no arquivo de configuração
            from ..utils.config_manager import ConfigManager
            config_mgr = ConfigManager()
            config_mgr.set('kept_languages', selected)
            self.console.print("[green]✓ Salvo em ~/.jellyfix/config.json[/green]")

        self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

    def _test_tmdb_connection(self, config: Config):
        """Testa a conexão com TMDB"""
        self.console.clear()
        self.console.print("\n[bold cyan]🔍 Testando conexão com TMDB...[/bold cyan]\n")

        config_mgr = ConfigManager()
        api_key = config_mgr.get_tmdb_api_key()

        if not api_key:
            self.console.print("[red]✗ Nenhuma chave API configurada![/red]")
            self.console.print("\n[yellow]Configure uma chave primeiro usando 'Configurar TMDB API Key'[/yellow]")
            self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")
            return

        # Valida formato da chave
        if len(api_key) != 32:
            self.console.print(f"[red]✗ Chave inválida! Tem {len(api_key)} caracteres, deveria ter 32.[/red]")
            self.console.print("\n[yellow]⚠️  Você pode ter copiado o Token ao invés da Chave![/yellow]")
            self.console.print("[dim]Veja 'Como obter chave TMDB' para mais detalhes[/dim]")
            self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")
            return

        try:
            import requests

            # Testa com uma busca simples
            self.console.print("[cyan]Fazendo requisição de teste...[/cyan]")
            url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query=Matrix"

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                total_results = data.get('total_results', 0)

                self.console.print("\n[bold green]✓ Conexão bem-sucedida![/bold green]\n")
                self.console.print(f"[green]• API Key válida e funcionando[/green]")
                self.console.print(f"[green]• Teste de busca retornou {total_results} resultados[/green]")

                if total_results > 0:
                    first_movie = data['results'][0]
                    self.console.print(f"\n[dim]Exemplo: {first_movie.get('title')} ({first_movie.get('release_date', 'N/A')[:4]})[/dim]")

            elif response.status_code == 401:
                self.console.print("\n[bold red]✗ Chave API inválida![/bold red]\n")
                self.console.print("[yellow]A chave foi rejeitada pelo TMDB.[/yellow]")
                self.console.print("\n[bold]Possíveis causas:[/bold]")
                self.console.print("1. Você copiou o [bold]Token de Leitura[/bold] ao invés da [bold]Chave da API[/bold]")
                self.console.print("2. A chave está incorreta ou foi revogada")
                self.console.print("3. Copiou apenas parte da chave")
                self.console.print("\n[cyan]Veja 'Como obter chave TMDB' para instruções detalhadas[/cyan]")

            else:
                self.console.print(f"\n[red]✗ Erro na requisição: HTTP {response.status_code}[/red]")

        except requests.exceptions.Timeout:
            self.console.print("\n[red]✗ Timeout: Servidor não respondeu a tempo[/red]")
            self.console.print("[yellow]Verifique sua conexão com a internet[/yellow]")

        except requests.exceptions.ConnectionError:
            self.console.print("\n[red]✗ Erro de conexão[/red]")
            self.console.print("[yellow]Verifique sua conexão com a internet[/yellow]")

        except Exception as e:
            self.console.print(f"\n[red]✗ Erro inesperado: {e}[/red]")

        self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

    def _api_settings_menu(self, config: Config):
        """Menu de configuração de APIs"""
        config_mgr = ConfigManager()

        while True:
            self.console.clear()
            self.console.print("\n")
            self.console.print(Panel.fit(
                "🔑 Configuração de APIs",
                style="bold magenta",
                border_style="magenta"
            ))

            # Mostra status atual
            tmdb_key = config_mgr.get_tmdb_api_key()
            tmdb_status = "[green]✓ Configurada[/green]" if tmdb_key else "[red]✗ Não configurada[/red]"

            self.console.print(f"\n[bold]TMDB API Key:[/bold] {tmdb_status}")
            self.console.print(f"[bold]Arquivo de config:[/bold] [cyan]{config_mgr.get_config_path()}[/cyan]\n")

            choice = questionary.select(
                "O que deseja fazer?",
                choices=[
                    "🔑 Configurar TMDB API Key",
                    "📋 Ver chave atual (TMDB)",
                    "✓ Testar conexão com TMDB",
                    "🗑️  Remover chave TMDB",
                    "ℹ️  Como obter chave TMDB",
                    "← Voltar"
                ],
                style=custom_style,
                instruction="(Use as setas ↑↓ e ENTER para selecionar)"
            ).ask()

            if choice == "← Voltar":
                break

            elif "Configurar TMDB" in choice:
                self.console.print("\n[cyan]Digite sua chave da API TMDB:[/cyan]")
                api_key = questionary.text(
                    "TMDB API Key:",
                    style=custom_style
                ).ask()

                if api_key and api_key.strip():
                    config_mgr.set_tmdb_api_key(api_key.strip())
                    config.tmdb_api_key = api_key.strip()
                    self.console.print(f"\n[green]✓ Chave TMDB salva em:[/green]")
                    self.console.print(f"  [cyan]{config_mgr.get_config_path()}[/cyan]")
                else:
                    self.console.print("\n[yellow]Operação cancelada.[/yellow]")

                self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

            elif "Ver chave atual" in choice:
                key = config_mgr.get_tmdb_api_key()
                if key:
                    # Mostra apenas os primeiros e últimos 4 caracteres
                    masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
                    self.console.print(f"\n[cyan]Chave TMDB:[/cyan] {masked_key}")
                    self.console.print(f"\n[dim]Arquivo:[/dim] [cyan]{config_mgr.get_config_path()}[/cyan]")
                else:
                    self.console.print("\n[yellow]Nenhuma chave configurada.[/yellow]")

                self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

            elif "Remover chave" in choice:
                confirm = questionary.confirm(
                    "Tem certeza que deseja remover a chave TMDB?",
                    default=False,
                    style=custom_style
                ).ask()

                if confirm:
                    config_mgr.set_tmdb_api_key("")
                    config.tmdb_api_key = ""
                    self.console.print("\n[green]✓ Chave TMDB removida.[/green]")
                else:
                    self.console.print("\n[yellow]Operação cancelada.[/yellow]")

                self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

            elif "Testar conexão" in choice:
                self._test_tmdb_connection(config)

            elif "Como obter" in choice:
                self.console.clear()
                self.console.print(Panel(
                    "[bold cyan]📖 Como obter chave da API TMDB[/bold cyan]\n\n"
                    "[bold]1. Acesse:[/bold]\n"
                    "   [link=https://www.themoviedb.org/settings/api]https://www.themoviedb.org/settings/api[/link]\n\n"
                    "[bold]2. Faça login ou crie uma conta GRATUITA[/bold]\n"
                    "   • Vá em: https://www.themoviedb.org/signup\n"
                    "   • Preencha seus dados\n"
                    "   • Confirme o email\n\n"
                    "[bold]3. Solicite uma chave de API:[/bold]\n"
                    "   • Acesse: https://www.themoviedb.org/settings/api\n"
                    "   • Clique em 'Request an API Key'\n"
                    "   • Escolha 'Developer' (uso pessoal)\n"
                    "   • Preencha:\n"
                    "     - Application Name: Jellyfix\n"
                    "     - Application URL: http://localhost\n"
                    "     - Application Summary: Personal media organizer\n"
                    "   • Aceite os termos de uso\n\n"
                    "[bold red]⚠️  IMPORTANTE - Qual chave copiar:[/bold red]\n"
                    "   Você verá DUAS chaves na página:\n"
                    "   [dim]• Token de Leitura da API (grande, começa com eyJ...)[/dim]\n"
                    "   [bold green]• Chave da API (v3 auth) ← COPIE ESTA![/bold green]\n"
                    "   \n"
                    "   A chave correta tem 32 caracteres (ex: 611bc23b57add08a67b2e64ecb850be8)\n\n"
                    "[bold]4. Configure no jellyfix:[/bold]\n"
                    "   • Volte ao menu e escolha 'Configurar TMDB API Key'\n"
                    "   • Cole a [bold]Chave da API[/bold] (32 caracteres)\n"
                    "   • Use 'Testar conexão' para verificar\n\n"
                    "[green]✓ A chave é gratuita e não expira![/green]\n"
                    "[green]✓ Permite até 40 requisições por 10 segundos[/green]\n"
                    "[green]✓ Suficiente para organizar milhares de arquivos![/green]",
                    title="Como Obter Chave TMDB",
                    border_style="cyan",
                    expand=False
                ))
                self.console.input("\n[dim]Pressione ENTER para continuar...[/dim]")

    def show_help(self):
        """Mostra ajuda"""
        self.console.clear()  # Limpa a tela
        help_text = """
[bold cyan]📖 Ajuda - jellyfix[/bold cyan]

[bold]O que o jellyfix faz:[/bold]

• [green]Renomeia arquivos[/green] para o padrão Jellyfin
  - Filmes: [dim]Nome do Filme (YYYY).mkv[/dim]
  - Séries: [dim]Nome da Série S01E01.mkv[/dim]

• [green]Organiza legendas[/green] (TODAS as línguas)
  - Renomeia variações: por2→por, eng2→eng, spa3→spa
  - Adiciona código de idioma (.por.srt)
  - Remove legendas estrangeiras (mantém por e eng por padrão)
  - Opção para remover duplicatas (eng2, eng3 quando eng existe)
  - [yellow]NUNCA[/yellow] remove .forced.srt

• [green]Estrutura de pastas[/green]
  - Cria pastas Season 01, Season 02, etc
  - Move episódios para as pastas corretas

• [green]Busca metadados[/green]
  - Busca ano e IDs via TMDB/TVDB
  - Adiciona IDs às pastas [tmdbid-12345]

[bold yellow]Modo Dry-Run:[/bold yellow]
Por padrão, o jellyfix mostra o que será feito SEM alterar arquivos.
Você pode revisar as mudanças antes de aplicar.

[bold cyan]Dica:[/bold cyan] Configure sua chave TMDB:
[dim]export TMDB_API_KEY=sua_chave_aqui[/dim]
        """
        self.console.print(Panel(help_text, border_style="cyan", expand=False))

    def show_error(self, message: str):
        """Mostra mensagem de erro"""
        self.console.print(f"\n[bold red]❌ Erro:[/bold red] {message}\n")

    def show_success(self, message: str):
        """Mostra mensagem de sucesso"""
        self.console.print(f"\n[bold green]✓ {message}[/bold green]\n")
