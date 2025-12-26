# JellyFix

**Organizador inteligente de bibliotecas Jellyfin** - Renomeia e organiza filmes, séries e legendas automaticamente seguindo as convenções do Jellyfin.

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

## Características

- 🎬 **Renomeação inteligente** - Filmes e séries no padrão Jellyfin
- 📝 **Gestão avançada de legendas**
  - Escolhe a melhor variação (.por2, .eng3) por qualidade
  - Remove idiomas estrangeiros (configurável)
  - Adiciona códigos de idioma automaticamente
  - Protege arquivos .forced
- 🌍 **Suporte multilíngue** - Configure quais idiomas manter
- 📊 **Metadados TMDB** - Busca títulos, anos e IDs automaticamente
- 🗂️ **Organização automática** - Estrutura de pastas Season XX
- 🎨 **Interface TUI** - Menu interativo elegante com Rich
- 💾 **Configuração persistente** - Preferências salvas em `~/.jellyfix/config.json`

## Instalação

### Arch Linux

```bash
cd pkgbuild/
makepkg -si
```

### Outras Distribuições

```bash
# 1. Instale dependências
pip install rich questionary requests

# 2. Instale JellyFix
sudo cp -r usr/share/jellyfix /usr/share/
sudo cp usr/bin/jellyfix /usr/bin/
sudo chmod +x /usr/bin/jellyfix
```

## Uso

### Modo Interativo

```bash
jellyfix
```

Menu com todas as opções disponíveis.

### Modo CLI

```bash
# Dry-run (padrão - mostra o que seria feito)
jellyfix --workdir /media/filmes

# Executar de verdade
jellyfix --workdir /media/filmes --execute --yes

# Com log
jellyfix --verbose --log /var/log/jellyfix.log
```

## Exemplos

### Filmes

**Antes:**
```
/Filmes/Matrix.1999.1080p.BluRay.mkv
```

**Depois:**
```
/Filmes/Matrix (1999) [tmdbid-603]/
├── Matrix (1999).mkv
├── Matrix (1999).por.srt
└── Matrix (1999).eng.srt
```

### Séries

**Antes:**
```
/Series/breaking.bad.s01e01.720p.mkv
```

**Depois:**
```
/Series/Breaking Bad (2008) [tmdbid-1396]/
└── Season 01/
    ├── Breaking Bad S01E01.mkv
    └── Breaking Bad S01E01.por.srt
```

## Sistema de Qualidade de Legendas

JellyFix escolhe a **melhor** legenda entre variações baseado em:

- Tamanho do arquivo
- Número de blocos de diálogo
- Número de linhas de texto
- Rejeita arquivos < 100 bytes

**Exemplo:** Se `por3.srt` (102KB) tem mais conteúdo que `por2.srt` (65KB), o **por3** será escolhido e renomeado para `por.srt`.

## Configuração

### API TMDB (Opcional)

```bash
# 1. Obtenha chave gratuita: https://www.themoviedb.org/settings/api
# 2. Configure
export TMDB_API_KEY="sua_chave_aqui"
```

### Idiomas Mantidos

Por padrão mantém **português** e **inglês**. Configure outros no menu interativo:

```
🌍 Idiomas mantidos: por, eng
```

## Opções CLI

```
jellyfix [opções]

Diretório:
  -w, --workdir DIR       Diretório de trabalho

Execução:
  --dry-run               Apenas simula (padrão)
  --execute               Executa de verdade
  -y, --yes               Confirma automaticamente

Saída:
  --verbose               Modo verboso
  -q, --quiet             Modo silencioso
  --log ARQUIVO           Salva log

Operações:
  --no-rename-por2        Desativa renomeação de variações
  --no-add-lang           Não adiciona código de idioma
  --no-remove-foreign     Não remove legendas estrangeiras
  --no-metadata           Não busca metadados

Detecção:
  --min-pt-words N        Palavras PT para detectar (padrão: 5)

Outros:
  -h, --help              Mostra ajuda
  -v, --version           Mostra versão
  --non-interactive       Modo CLI sem menu
```

## Estrutura do Projeto

```
jellyfix/
├── usr/
│   ├── bin/jellyfix              # CLI principal
│   └── share/jellyfix/           # Módulos Python
│       ├── core/                 # Lógica principal
│       │   ├── detector.py       # Detecção filme/série
│       │   ├── scanner.py        # Scanner de arquivos
│       │   ├── renamer.py        # Renomeação
│       │   └── metadata.py       # TMDB API
│       ├── utils/                # Utilitários
│       │   ├── config.py         # Configurações
│       │   ├── helpers.py        # Funções auxiliares
│       │   └── logger.py         # Logging
│       └── ui/
│           └── menu.py           # Interface TUI
├── pkgbuild/PKGBUILD             # Pacote Arch Linux
├── README.md
├── jellyfin-naming-guide.md      # Guia completo
└── LICENSE
```

## Dependências

- Python 3.8+
- python-rich
- python-requests
- python-questionary

## Documentação Adicional

- [Guia de Nomenclatura Jellyfin](jellyfin-naming-guide.md)
- [Documentação Oficial Jellyfin](https://jellyfin.org/docs/general/server/media/movies/)

## Licença

MIT License - Copyright (c) 2024 Tales A. Mendonça

## Links

- **Repositório**: https://github.com/talesam/jellyfix
- **Issues**: https://github.com/talesam/jellyfix/issues
- **TMDB API**: https://www.themoviedb.org/settings/api

---

**⭐ Se este projeto foi útil, deixe uma estrela!**
