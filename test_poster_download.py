#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# test_poster_download.py - Test script for poster downloading
#

"""
Simple test to verify poster downloading functionality.
"""

import sys
from pathlib import Path

# Add usr/share to path so we can import jellyfix as a package
usr_share_dir = Path(__file__).parent / 'usr' / 'share'
sys.path.insert(0, str(usr_share_dir))

from jellyfix.core.metadata import MetadataFetcher
from jellyfix.core.image_manager import ImageManager

def main():
    """Test poster downloading"""

    print("=" * 60)
    print("Testing Poster Download System")
    print("=" * 60)

    # Initialize
    fetcher = MetadataFetcher()
    img_manager = ImageManager()

    # Test 1: Search for a movie
    print("\n[Test 1] Searching for movie: The Matrix")
    metadata = fetcher.search_movie("The Matrix", year=1999)

    if metadata:
        print(f"✓ Found: {metadata.title} ({metadata.year})")
        print(f"  TMDB ID: {metadata.tmdb_id}")
        print(f"  Poster path: {metadata.poster_path}")
        print(f"  Poster URL: {metadata.poster_url}")
        print(f"  Backdrop path: {metadata.backdrop_path}")
        print(f"  Backdrop URL: {metadata.backdrop_url}")

        # Test 2: Download poster
        print("\n[Test 2] Downloading poster...")
        poster_path = img_manager.download_poster(metadata, size='medium')

        if poster_path:
            print(f"✓ Poster downloaded: {poster_path}")
            print(f"  File size: {poster_path.stat().st_size / 1024:.2f} KB")
        else:
            print("✗ Failed to download poster")

        # Test 3: Check cache
        print("\n[Test 3] Checking cache...")
        cached = img_manager.get_cached_images(metadata.tmdb_id)
        print(f"  Cached poster: {cached['poster']}")
        print(f"  Cached backdrop: {cached['backdrop']}")

        # Test 4: Cache stats
        print("\n[Test 4] Cache statistics")
        stats = img_manager.get_cache_stats()
        print(f"  Total files: {stats['total_files']}")
        print(f"  Total size: {stats['total_size_mb']} MB")
        print(f"  Oldest entry: {stats['oldest_entry']}")

    else:
        print("✗ Failed to find movie")

    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)

if __name__ == '__main__':
    main()
