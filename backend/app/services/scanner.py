from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Callable

from PIL import Image

from backend.app.models.schemas import ImageRecord, ScanResponse, SessionRecord
from backend.app.utils.image_hash import compute_dhash_from_image

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp"}
REPO_ROOT = Path(__file__).resolve().parents[3]
METADATA_CACHE_PATH = REPO_ROOT / "data" / "cache" / "image-metadata-cache.json"

_metadata_cache: dict[str, tuple[int, int, int, int, str, str]] = {}
_metadata_cache_lock = Lock()
ScanProgress = Callable[[int, str], None]


def scan_root_folder(
    root_path: str,
    *,
    analyze_images: bool = True,
    progress: ScanProgress | None = None,
) -> ScanResponse:
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("目录不存在或不是有效文件夹")

    sessions: list[SessionRecord] = []
    images: list[ImageRecord] = []
    skipped_files: list[str] = []

    session_dirs = list_session_dirs(root)

    if not analyze_images:
        if progress:
            progress(100, "目录扫描完成")
        return ScanResponse(
            root_path=str(root),
            sessions=[
                SessionRecord(
                    id=session_index,
                    name=session_dir.name,
                    folder_path=str(session_dir),
                    session_index=session_index,
                    image_count=0,
                )
                for session_index, session_dir in enumerate(session_dirs, start=1)
            ],
            images=[],
            skipped_files=[],
        )

    load_metadata_cache()
    total_sessions = max(len(session_dirs), 1)
    with ThreadPoolExecutor(max_workers=get_scan_worker_count()) as executor:
        for session_index, session_dir in enumerate(session_dirs, start=1):
            if progress:
                progress(
                    int((session_index - 1) / total_sessions * 95),
                    f"扫描图片：{session_dir.name}",
                )
            session_images: list[ImageRecord] = []
            image_paths = sorted(
                [
                    path
                    for path in session_dir.rglob("*")
                    if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
                ],
                key=lambda item: str(item.relative_to(session_dir)).lower(),
            )

            jobs = (
                (image_path, session_index, session_dir.name, analyze_images)
                for image_path in image_paths
            )
            for image_record, error in executor.map(process_image_job, jobs):
                if error:
                    skipped_files.append(error)
                    continue
                if image_record is not None:
                    session_images.append(image_record)

            sessions.append(
                SessionRecord(
                    id=session_index,
                    name=session_dir.name,
                    folder_path=str(session_dir),
                    session_index=session_index,
                    image_count=len(session_images),
                )
            )
            images.extend(session_images)

    save_metadata_cache()
    if progress:
        progress(100, "图片扫描完成")

    return ScanResponse(
        root_path=str(root),
        sessions=sessions,
        images=images,
        skipped_files=skipped_files,
    )


def list_session_dirs(root: Path) -> list[Path]:
    session_dirs: list[Path] = []
    with os.scandir(root) as entries:
        for entry in entries:
            try:
                if entry.is_dir():
                    session_dirs.append(Path(entry.path))
            except OSError:
                continue
    return sorted(session_dirs, key=lambda item: item.name.lower())


def get_scan_worker_count() -> int:
    configured = os.getenv("LIGHTDROP_SCAN_WORKERS")
    if configured:
        try:
            return max(1, min(int(configured), 64))
        except ValueError:
            pass

    cpu_count = os.cpu_count() or 4
    return max(4, min(cpu_count + 4, 16))


def process_image_job(
    job: tuple[Path, int, str, bool],
) -> tuple[ImageRecord | None, str | None]:
    image_path, session_index, session_name, analyze_images = job
    try:
        if analyze_images:
            width, height, file_size, image_hash, image_id = read_image_metadata(image_path)
        else:
            stat = image_path.stat()
            file_size = stat.st_size
            image_id = build_image_id_from_stat(image_path, file_size, stat.st_mtime_ns)
            width = None
            height = None
            image_hash = None
    except Exception as exc:  # noqa: BLE001 - scanner should continue on one bad image
        return None, f"{image_path}: {exc}"

    return (
        ImageRecord(
            image_id=image_id,
            file_name=image_path.name,
            file_path=str(image_path),
            session_id=session_index,
            session_name=session_name,
            session_index=session_index,
            width=width,
            height=height,
            file_size=file_size,
            image_hash=image_hash,
        ),
        None,
    )


def read_image_metadata(path: Path) -> tuple[int, int, int, str, str]:
    stat = path.stat()
    file_size = stat.st_size
    modified_ns = stat.st_mtime_ns
    cache_key = str(path.resolve())

    with _metadata_cache_lock:
        cached = _metadata_cache.get(cache_key)
        if cached and cached[0] == file_size and cached[1] == modified_ns:
            _, _, width, height, image_hash, image_id = cached
            return width, height, file_size, image_hash, image_id

    with Image.open(path) as image:
        width, height = image.size
        image_hash = compute_dhash_from_image(image)

    image_id = build_image_id_from_stat(path, file_size, modified_ns)

    with _metadata_cache_lock:
        _metadata_cache[cache_key] = (
            file_size,
            modified_ns,
            width,
            height,
            image_hash,
            image_id,
        )

    return width, height, file_size, image_hash, image_id


def load_metadata_cache() -> None:
    if _metadata_cache or not METADATA_CACHE_PATH.exists():
        return
    try:
        payload = json.loads(METADATA_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

    with _metadata_cache_lock:
        for key, value in payload.items():
            if isinstance(value, list) and len(value) == 6:
                try:
                    _metadata_cache[key] = (
                        int(value[0]),
                        int(value[1]),
                        int(value[2]),
                        int(value[3]),
                        str(value[4]),
                        str(value[5]),
                    )
                except (TypeError, ValueError):
                    continue


def save_metadata_cache() -> None:
    METADATA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _metadata_cache_lock:
        payload = {key: list(value) for key, value in _metadata_cache.items()}
    METADATA_CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def build_image_id(path: Path, file_size: int) -> str:
    stat = path.stat()
    return build_image_id_from_stat(path, file_size, stat.st_mtime_ns)


def build_image_id_from_stat(path: Path, file_size: int, modified_ns: int) -> str:
    source = f"{path.resolve()}:{file_size}:{modified_ns}"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
