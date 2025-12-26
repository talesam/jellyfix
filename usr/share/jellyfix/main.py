#!/usr/bin/env python3
"""
jellyfix - Organizador inteligente de bibliotecas Jellyfin

Renomeia e organiza filmes, séries e legendas automaticamente seguindo
as convenções de nomenclatura do Jellyfin.
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Adiciona o diretório atual ao path para imports relativos
sys.path.insert(0, str(Path(__file__).parent.parent))

from jellyfix.utils.config import Config, set_config, APP_VERSION
from jellyfix.utils.logger import Logger, set_logger
from jellyfix.ui.menu import InteractiveMenu
from jellyfix.core.scanner import scan_library
from jellyfix.core.renamer import Renamer


def show_help():
    """Mostra ajuda com cores usando Rich"""
    console = Console()

    console.print(Panel.fit(
        f"[bold cyan]jellyfix v{APP_VERSION}[/bold cyan]\n"
        "[dim]Organizador inteligente de bibliotecas Jellyfin[/dim]",
        border_style="cyan"
    ))

    console.print("\n[bold yellow]USO:[/bold yellow]")
    console.print("  jellyfix [opções]")

    console.print("\n[bold yellow]OPÇÕES:[/bold yellow]")
    console.print("  [cyan]-h, --help[/cyan]              Mostra esta ajuda")
    console.print("  [cyan]-v, --version[/cyan]          Mostra a versão")
    console.print("  [cyan]-w, --workdir[/cyan] DIR      Diretório de trabalho (padrão: atual)")
    console.print("  [cyan]--dry-run[/cyan]              Apenas simula, sem modificar arquivos [padrão]")
    console.print("  [cyan]--execute[/cyan]              Executa as operações de verdade")
    console.print("  [cyan]-y, --yes[/cyan]              Confirma todas as operações automaticamente")
    console.print("  [cyan]--verbose[/cyan]              Modo verboso (mais detalhes)")
    console.print("  [cyan]-q, --quiet[/cyan]            Modo silencioso (apenas erros)")
    console.print("  [cyan]--log[/cyan] ARQUIVO          Salva log em arquivo")
    console.print("  [cyan]--min-pt-words[/cyan] N       Mínimo de palavras PT para detectar (padrão: 5)")
    console.print("  [cyan]--no-rename-por2[/cyan]       Não renomear .por2.srt → .por.srt")
    console.print("  [cyan]--no-add-lang[/cyan]          Não adicionar código de idioma")
    console.print("  [cyan]--no-remove-foreign[/cyan]    Não remover legendas estrangeiras")
    console.print("  [cyan]--no-metadata[/cyan]          Não buscar metadados via TMDB")
    console.print("  [cyan]--non-interactive[/cyan]      Modo não-interativo (sem menu)")

    console.print("\n[bold yellow]EXEMPLOS:[/bold yellow]")
    console.print("  [dim]# Modo interativo (padrão)[/dim]")
    console.print("  jellyfix")
    console.print("\n  [dim]# Processar diretório específico[/dim]")
    console.print("  jellyfix --workdir /media/filmes")
    console.print("\n  [dim]# Executar sem confirmação[/dim]")
    console.print("  jellyfix --yes --execute")
    console.print("\n  [dim]# Modo verboso com log[/dim]")
    console.print("  jellyfix --verbose --log /var/log/jellyfix.log")

    console.print("\n[bold yellow]CONFIGURAÇÃO DE API:[/bold yellow]")
    console.print("  [dim]Para buscar metadados via TMDB:[/dim]")
    console.print("  export TMDB_API_KEY=sua_chave_aqui")

    console.print("\n[bold yellow]MAIS INFORMAÇÕES:[/bold yellow]")
    console.print("  https://github.com/talesam/jellyfix\n")


def parse_args():
    """Parse argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description='jellyfix - Organizador inteligente de bibliotecas Jellyfin',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False  # Desabilita --help padrão para usar o customizado
    )

    parser.add_argument(
        '-h', '--help',
        action='store_true',
        help='Mostra esta ajuda'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'jellyfix {APP_VERSION}'
    )

    parser.add_argument(
        '-w', '--workdir',
        type=str,
        default=None,
        help='Diretório de trabalho (padrão: diretório atual)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Apenas mostra o que seria feito, sem modificar arquivos (padrão)'
    )

    parser.add_argument(
        '--execute',
        action='store_true',
        help='Executa as operações de verdade (desativa dry-run)'
    )

    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Confirma todas as operações automaticamente'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Modo verboso (mostra mais detalhes)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Modo silencioso (apenas erros)'
    )

    parser.add_argument(
        '--log',
        type=str,
        default=None,
        help='Arquivo de log'
    )

    parser.add_argument(
        '--min-pt-words',
        type=int,
        default=5,
        help='Mínimo de palavras portuguesas para detectar legenda (padrão: 5)'
    )

    parser.add_argument(
        '--no-rename-por2',
        action='store_true',
        help='Não renomear .por2.srt para .por.srt'
    )

    parser.add_argument(
        '--no-add-lang',
        action='store_true',
        help='Não adicionar código de idioma a legendas'
    )

    parser.add_argument(
        '--no-remove-foreign',
        action='store_true',
        help='Não remover legendas estrangeiras'
    )

    parser.add_argument(
        '--no-metadata',
        action='store_true',
        help='Não buscar metadados via TMDB/TVDB'
    )

    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Modo não-interativo (sem menu)'
    )

    args = parser.parse_args()

    # Se --help foi usado, mostra ajuda customizada e sai
    if args.help:
        show_help()
        sys.exit(0)

    return args


def interactive_mode(config: Config):
    """Modo interativo com menu"""
    menu = InteractiveMenu()

    while True:
        menu.show_banner()  # Limpa tela e mostra banner
        choice = menu.main_menu()

        if choice == "❌ Sair":
            menu.console.clear()
            menu.console.print("\n[bold blue]Até logo! 👋[/bold blue]\n")
            break

        elif choice == "ℹ️  Ajuda":
            menu.show_help()
            menu.console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")

        elif choice == "🔧 Configurações":
            config = menu.settings_menu(config)
            set_config(config)

        elif choice == "📂 Escanear biblioteca":
            # Seleciona diretório
            directory = menu.select_directory(config.work_dir)
            if not directory:
                continue

            # Escaneia
            menu.console.print("\n[cyan]🔍 Escaneando biblioteca...[/cyan]")
            result = scan_library(directory)
            menu.show_scan_results(result)
            menu.console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")

        elif choice == "🚀 Processar arquivos":
            # Seleciona diretório
            directory = menu.select_directory(config.work_dir)
            if not directory:
                continue

            # Escaneia
            menu.console.print("\n[cyan]🔍 Analisando arquivos...[/cyan]")

            # Mostra se vai buscar metadados
            if config.fetch_metadata and config.tmdb_api_key:
                menu.console.print("[dim]   • Buscando metadados via TMDB...[/dim]")

            # Planeja operações
            renamer = Renamer()

            with menu.console.status("[cyan]Processando...[/cyan]", spinner="dots"):
                renamer.plan_operations(directory)

            # Mostra preview
            menu.show_operation_preview(renamer)

            if not renamer.operations:
                menu.console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")
                continue

            # Confirma
            if not config.auto_confirm:
                if not menu.confirm_operations():
                    menu.console.print("\n[yellow]Operação cancelada.[/yellow]\n")
                    menu.console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")
                    continue

            # Pergunta se quer executar de verdade ou dry-run
            dry_run = True
            if not config.auto_confirm:
                execute = menu.console.input(
                    "\n[bold yellow]Executar de verdade? (s/N):[/bold yellow] "
                ).lower() == 's'
                dry_run = not execute

            # Executa
            menu.console.print("\n[cyan]⚙️  Processando...[/cyan]\n")
            stats = renamer.execute_operations(dry_run=dry_run)

            # Mostra resultados
            if dry_run:
                menu.console.print(
                    f"\n[bold yellow]🔍 Dry-run completado![/bold yellow]\n"
                    f"Operações planejadas: {len(renamer.operations)}\n"
                    f"Use --execute para aplicar as mudanças.\n"
                )
            else:
                # Monta mensagem de conclusão
                parts = []
                if stats['renamed'] > 0:
                    parts.append(f"{stats['renamed']} renomeado(s)")
                if stats['moved'] > 0:
                    parts.append(f"{stats['moved']} movido(s)")
                if stats['deleted'] > 0:
                    parts.append(f"{stats['deleted']} removido(s)")
                if stats.get('cleaned', 0) > 0:
                    parts.append(f"{stats['cleaned']} pasta(s) limpa(s)")
                if stats['failed'] > 0:
                    parts.append(f"{stats['failed']} falha(s)")
                if stats['skipped'] > 0:
                    parts.append(f"{stats['skipped']} pulado(s)")

                message = "Concluído! " + ", ".join(parts) if parts else "Nenhuma operação executada"
                menu.show_success(message)

            menu.console.input("\n[dim]Pressione ENTER para voltar ao menu...[/dim]")


def non_interactive_mode(config: Config):
    """Modo não-interativo (CLI)"""
    logger = Logger(config.log_file, config.verbose, config.quiet)
    set_logger(logger)

    logger.title("JELLYFIX - Organizador de Bibliotecas Jellyfin")

    # Escaneia
    logger.info(f"Escaneando: {config.work_dir}")
    result = scan_library(config.work_dir)

    logger.info(f"Encontrados: {len(result.video_files)} vídeos, {len(result.subtitle_files)} legendas")

    # Planeja operações
    logger.info("Planejando operações...")
    renamer = Renamer()
    renamer.plan_operations(config.work_dir)

    if not renamer.operations:
        logger.success("Nenhuma operação necessária. Tudo já está organizado!")
        return

    logger.info(f"{len(renamer.operations)} operações planejadas")

    # Executa
    dry_run = not config.auto_confirm
    if config.dry_run:
        dry_run = True

    if dry_run:
        logger.warning("Modo DRY-RUN: Nenhuma alteração será feita")

    stats = renamer.execute_operations(dry_run=dry_run)

    # Resultados
    if dry_run:
        logger.info(
            f"Dry-run concluído: {len(renamer.operations)} operações planejadas"
        )
    else:
        # Monta mensagem de conclusão
        parts = []
        if stats['renamed'] > 0:
            parts.append(f"{stats['renamed']} renomeado(s)")
        if stats['moved'] > 0:
            parts.append(f"{stats['moved']} movido(s)")
        if stats['deleted'] > 0:
            parts.append(f"{stats['deleted']} removido(s)")
        if stats.get('cleaned', 0) > 0:
            parts.append(f"{stats['cleaned']} pasta(s) limpa(s)")
        if stats['failed'] > 0:
            parts.append(f"{stats['failed']} falha(s)")
        if stats['skipped'] > 0:
            parts.append(f"{stats['skipped']} pulado(s)")

        message = "Concluído! " + ", ".join(parts) if parts else "Nenhuma operação executada"
        logger.success(message)


def main():
    """Função principal"""
    args = parse_args()

    # Cria configuração
    config = Config(
        work_dir=Path(args.workdir) if args.workdir else Path.cwd(),
        log_file=Path(args.log) if args.log else None,
        dry_run=args.dry_run and not args.execute,
        verbose=args.verbose,
        quiet=args.quiet,
        auto_confirm=args.yes,
        min_pt_words=args.min_pt_words,
        rename_por2=not args.no_rename_por2,
        rename_no_lang=not args.no_add_lang,
        remove_foreign_subs=not args.no_remove_foreign,
        fetch_metadata=not args.no_metadata,
    )

    set_config(config)

    # Modo interativo ou CLI
    if args.non_interactive or args.yes:
        non_interactive_mode(config)
    else:
        try:
            interactive_mode(config)
        except KeyboardInterrupt:
            print("\n\n👋 Interrompido pelo usuário. Até logo!\n")
            sys.exit(0)


if __name__ == '__main__':
    main()
