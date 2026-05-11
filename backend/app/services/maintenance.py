from __future__ import annotations

from pathlib import Path
from time import time

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT / "data"
CACHE_ROOT = DATA_ROOT / "cache"
RUNTIME_FILE_MAX_AGE_SECONDS = 24 * 60 * 60
EXPORT_MAX_AGE_SECONDS = 24 * 60 * 60
MAX_JSON_CACHE_BYTES = 256 * 1024 * 1024


def cleanup_runtime_cache() -> None:
    cleanup_old_files(CACHE_ROOT / "exports", "*.xlsx", EXPORT_MAX_AGE_SECONDS)
    cleanup_old_files(DATA_ROOT, "ocr_*.png", RUNTIME_FILE_MAX_AGE_SECONDS)
    cleanup_old_files(DATA_ROOT, "tmp_*.png", RUNTIME_FILE_MAX_AGE_SECONDS)
    trim_json_cache(CACHE_ROOT / "image-metadata-cache.json")
    trim_json_cache(CACHE_ROOT / "dashboard-ocr-cache.json")
    trim_json_cache(CACHE_ROOT / "product-image-index-cache.json")


def cleanup_old_files(root: Path, pattern: str, max_age_seconds: int) -> None:
    if not root.exists():
        return

    expire_before = time() - max_age_seconds
    for path in root.glob(pattern):
        try:
            if path.is_file() and path.stat().st_mtime < expire_before:
                path.unlink()
        except OSError:
            continue


def trim_json_cache(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > MAX_JSON_CACHE_BYTES:
            path.unlink()
    except OSError:
        return
