<p align="center">
  <img src="usr/share/icons/hicolor/scalable/apps/jellyfix.svg" alt="Jellyfix Logo" width="128" height="128">
</p>

<h1 align="center">Jellyfix</h1>

<p align="center">
  <strong>Intelligent Jellyfin Media Library Organizer</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.8%2B-blue.svg" alt="Python"></a>
  <a href="https://gtk.org/"><img src="https://img.shields.io/badge/GTK-4-orange.svg" alt="GTK4"></a>
</p>

---

## ✨ Features

- **Smart Renaming** — Movies and TV shows following Jellyfin naming conventions
- **TMDB Integration** — Automatic metadata, titles, and poster fetching
- **Subtitle Management** — Language detection, quality selection, and cleanup
- **Modern GUI** — GTK4 + libadwaita interface with drag-and-drop support
- **CLI Mode** — Full-featured command line interface with TUI menu

## 📦 Installation

### Arch Linux

```bash
cd pkgbuild/
makepkg -si
```

### Manual Installation

```bash
# Install dependencies
pip install rich questionary requests

# Install Jellyfix
sudo cp -r usr/share/jellyfix /usr/share/
sudo cp -r usr/share/icons /usr/share/
sudo cp -r usr/share/applications /usr/share/
sudo cp usr/bin/jellyfix* /usr/bin/
sudo chmod +x /usr/bin/jellyfix*
```

## 🚀 Usage

### GUI Mode

```bash
jellyfix-gui
```

### CLI Interactive Mode

```bash
jellyfix
```

### CLI Direct Mode

```bash
# Preview changes (dry-run)
jellyfix --workdir /media/movies

# Apply changes
jellyfix --workdir /media/movies --execute --yes
```

## 📁 Before & After

### Movies

```
Before: /Movies/Matrix.1999.1080p.BluRay.mkv

After:  /Movies/Matrix (1999) [tmdbid-603]/
        ├── Matrix (1999) - 1080p.mkv
        └── Matrix (1999).por.srt
```

### TV Shows

```
Before: /Series/breaking.bad.s01e01.720p.mkv

After:  /Series/Breaking Bad (2008) [tmdbid-1396]/
        └── Season 01/
            └── Breaking Bad - S01E01 - 720p.mkv
```

## ⚙️ Configuration

### TMDB API Key

Get your free API key at [themoviedb.org](https://www.themoviedb.org/settings/api) and configure via:

- GUI: Menu → Configure API
- CLI: `export TMDB_API_KEY="your_key"`
- Config file: `~/.jellyfix/config.json`

## 📋 Requirements

- Python 3.8+
- GTK4, libadwaita (GUI only)
- python-rich, python-questionary, python-requests

## 📄 License

MIT License — Copyright (c) 2024 Tales A. Mendonça

---

<p align="center">
  <a href="https://github.com/talesam/jellyfix">GitHub</a> •
  <a href="https://github.com/talesam/jellyfix/issues">Issues</a>
</p>
