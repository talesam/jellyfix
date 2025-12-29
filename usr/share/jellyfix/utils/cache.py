#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cache.py - Cache management with automatic expiration
#

"""
File caching system with automatic expiration.

This module provides a cache manager that stores files locally
with automatic expiration after a configurable number of days.

Usage:
    from utils.cache import CacheManager

    cache = CacheManager()

    # Save content
    path = cache.save("poster_12345", image_bytes, ext='jpg')

    # Retrieve content
    cached_path = cache.get("poster_12345")

    # Clear cache
    cache.clear_all()
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
import hashlib
from datetime import datetime, timedelta


class CacheManager:
    """Manages file caching with automatic expiration"""

    def __init__(self, cache_dir: Optional[Path] = None, expiration_days: int = 30):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache storage (default: ~/.jellyfix/cache)
            expiration_days: Days until cached files expire (default: 30)
        """
        self.cache_dir = cache_dir or Path.home() / '.jellyfix' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.cache_dir / 'index.json'
        self.expiration_days = expiration_days
        self.index: Dict[str, Dict[str, Any]] = {}

        self._load_index()
        self._cleanup_expired()

    def _load_index(self):
        """Load cache index from JSON file"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
            except (json.JSONDecodeError, IOError):
                # Corrupted index, start fresh
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        """Save cache index to JSON file"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except IOError:
            pass  # Fail silently if we can't save index

    def _cleanup_expired(self):
        """Remove expired cache entries"""
        expired_keys = []
        now = datetime.now()

        for key, entry in self.index.items():
            try:
                cached_time = datetime.fromisoformat(entry['timestamp'])
                if now - cached_time > timedelta(days=self.expiration_days):
                    expired_keys.append(key)
            except (KeyError, ValueError):
                # Invalid entry, mark for removal
                expired_keys.append(key)

        # Remove expired entries
        for key in expired_keys:
            self._remove_entry(key)

        if expired_keys:
            self._save_index()

    def _remove_entry(self, key: str):
        """
        Remove a cache entry and its file.

        Args:
            key: Cache key to remove
        """
        if key in self.index:
            file_path = Path(self.index[key]['path'])
            file_path.unlink(missing_ok=True)
            del self.index[key]

    def _generate_filename(self, key: str, ext: str = 'dat') -> str:
        """
        Generate a unique filename for a cache key.

        Args:
            key: Cache key
            ext: File extension (without dot)

        Returns:
            Filename (e.g., 'abc123def456.jpg')
        """
        hash_digest = hashlib.md5(key.encode()).hexdigest()
        return f"{hash_digest}.{ext}"

    def get(self, key: str) -> Optional[str]:
        """
        Get cached file path if exists and not expired.

        Args:
            key: Cache key

        Returns:
            Path to cached file, or None if not found/expired
        """
        if key not in self.index:
            return None

        entry = self.index[key]
        file_path = Path(entry['path'])

        # Check if file exists
        if not file_path.exists():
            del self.index[key]
            self._save_index()
            return None

        # Check expiration
        try:
            cached_time = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - cached_time > timedelta(days=self.expiration_days):
                self._remove_entry(key)
                self._save_index()
                return None
        except (KeyError, ValueError):
            # Invalid timestamp, remove entry
            self._remove_entry(key)
            self._save_index()
            return None

        return str(file_path)

    def save(self, key: str, content: bytes, ext: str = 'dat') -> Path:
        """
        Save content to cache and return path.

        Args:
            key: Cache key (unique identifier)
            content: Binary content to cache
            ext: File extension (default: 'dat')

        Returns:
            Path to cached file
        """
        filename = self._generate_filename(key, ext)
        file_path = self.cache_dir / filename

        # Write content to file
        file_path.write_bytes(content)

        # Update index
        self.index[key] = {
            'path': str(file_path),
            'timestamp': datetime.now().isoformat(),
            'size': len(content),
            'ext': ext
        }
        self._save_index()

        return file_path

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and is valid, False otherwise
        """
        return self.get(key) is not None

    def clear_all(self):
        """Clear entire cache (remove all files and index)"""
        # Remove all cached files
        for entry in self.index.values():
            file_path = Path(entry['path'])
            file_path.unlink(missing_ok=True)

        # Clear index
        self.index = {}
        self._save_index()

    def clear_expired(self):
        """Clear only expired entries"""
        self._cleanup_expired()

    def get_cache_size(self) -> int:
        """
        Get total size of cache in bytes.

        Returns:
            Total cache size in bytes
        """
        total_size = 0
        for entry in self.index.values():
            total_size += entry.get('size', 0)
        return total_size

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (total_files, total_size, oldest_entry)
        """
        if not self.index:
            return {
                'total_files': 0,
                'total_size': 0,
                'oldest_entry': None
            }

        total_size = self.get_cache_size()

        # Find oldest entry
        oldest_time = None
        for entry in self.index.values():
            try:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if oldest_time is None or entry_time < oldest_time:
                    oldest_time = entry_time
            except (KeyError, ValueError):
                pass

        return {
            'total_files': len(self.index),
            'total_size': total_size,
            'oldest_entry': oldest_time.isoformat() if oldest_time else None
        }
