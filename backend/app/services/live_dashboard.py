from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock

from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from backend.app.models.schemas import (
    LiveDashboardMetrics,
    LiveDashboardPoint,
    LiveDashboardSession,
    LiveDashboardSummary,
)
from backend.app.services.scanner import SUPPORTED_IMAGE_EXTENSIONS

LIVE_DASHBOARD_DIR_NAME = "直播大屏数据"

RIGHT_PANEL_WIDTH = 540
REFERENCE_WIDTH = 540
REFERENCE_HEIGHT = 1080
FULL_REFERENCE_WIDTH = 1920
FULL_REFERENCE_HEIGHT = 1080
CACHE_VERSION = "dashboard-v4"

METRIC_NAMES = (
    "like_rate",
    "comment_rate",
    "avg_watch_seconds",
    "effective_enter_rate",
    "deal_conversion_rate",
    "new_customer_conversion_rate",
    "live_recommend_total",
    "live_recommend_delta",
)

METRIC_LABELS = {
    "like_rate": "点赞率",
    "comment_rate": "评论率",
    "avg_watch_seconds": "人均观看时长",
    "effective_enter_rate": "有效进房率",
    "deal_conversion_rate": "成交转化率",
    "new_customer_conversion_rate": "新客转化率",
    "live_recommend_total": "直播推荐累计",
    "live_recommend_delta": "直播推荐增量",
}

EXCLUDED_PERCENT_VALUES = {1.0}

VALUE_LAYOUTS = (
    {
        "effective_enter_rate": (18, 478, 130, 512),
        "avg_watch_seconds": (195, 478, 330, 512),
        "comment_rate": (18, 607, 130, 641),
        "like_rate": (195, 607, 330, 641),
        "deal_conversion_rate": (195, 789, 330, 824),
        "new_customer_conversion_rate": (18, 918, 130, 953),
    },
    {
        "effective_enter_rate": (18, 382, 130, 414),
        "avg_watch_seconds": (195, 382, 330, 414),
        "comment_rate": (18, 490, 130, 524),
        "like_rate": (195, 490, 330, 524),
        "deal_conversion_rate": (195, 652, 330, 686),
        "new_customer_conversion_rate": (18, 762, 130, 795),
    },
)

LIVE_RECOMMEND_TOTAL_BOX = (158, 594, 292, 630)

_ocr_engine: RapidOCR | None = None
_ocr_lock = Lock()
_cache_lock = Lock()
_dashboard_cache: dict[str, tuple[int, int, LiveDashboardPoint]] = {}

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_CACHE_PATH = REPO_ROOT / "data" / "cache" / "dashboard-ocr-cache.json"
DashboardProgress = Callable[[int, str], None]


@dataclass(frozen=True)
class Recognition:
    text: str
    confidence: float


def process_live_dashboard_screenshots(
    root_path: str,
    progress: DashboardProgress | None = None,
    session_name: str | None = None,
) -> LiveDashboardSummary | None:
    load_dashboard_cache()
    dashboard_root = resolve_dashboard_root(root_path)
    if dashboard_root is None:
        if progress is not None:
            progress(100, "未找到大屏截图目录")
        return None

    session_dirs = resolve_dashboard_session_dirs(dashboard_root)
    if not session_dirs:
        if progress is not None:
            progress(100, "未找到大屏截图文件夹")
        return LiveDashboardSummary(
            enabled=True,
            dashboard_root=str(dashboard_root),
            message="没有找到直播大屏截图文件夹",
        )

    requested_session = session_name.strip() if session_name else None
    matching_session = (
        any(session_dir.name == requested_session for session_dir in session_dirs)
        if requested_session
        else True
    )
    if requested_session and not matching_session:
        return LiveDashboardSummary(
            enabled=True,
            dashboard_root=str(dashboard_root),
            processed_sessions=[
                build_dashboard_session_overview(session_dir)
                for session_dir in session_dirs
            ],
            message=f"未找到大屏截图场次：{requested_session}",
        )

    sessions = []
    total = max(len(session_dirs), 1)
    for index, session_dir in enumerate(session_dirs, start=1):
        if requested_session and session_dir.name != requested_session:
            sessions.append(build_dashboard_session_overview(session_dir))
            continue
        if progress is not None:
            progress(round((index - 1) / total * 90), f"识别大屏截图：{session_dir.name}")
        sessions.append(process_dashboard_session(session_dir, progress=progress))
    sessions = [session for session in sessions if session.screenshot_count > 0]
    save_dashboard_cache()
    if progress is not None:
        progress(100, "大屏 OCR 完成")

    return LiveDashboardSummary(
        enabled=True,
        dashboard_root=str(dashboard_root),
        processed_sessions=sessions,
        message=None if sessions else "没有找到可识别的直播大屏截图",
    )


def scan_live_dashboard_sessions(root_path: str) -> LiveDashboardSummary | None:
    dashboard_root = resolve_dashboard_root(root_path)
    if dashboard_root is None:
        return None

    session_dirs = resolve_dashboard_session_dirs(dashboard_root)
    sessions = [
        build_dashboard_session_overview(session_dir)
        for session_dir in session_dirs
    ]
    sessions = [session for session in sessions if session.screenshot_count > 0]
    return LiveDashboardSummary(
        enabled=True,
        dashboard_root=str(dashboard_root),
        processed_sessions=sessions,
        message=None if sessions else "没有找到直播大屏截图文件",
    )


def resolve_dashboard_root(root_path: str) -> Path | None:
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return None

    if root.name == LIVE_DASHBOARD_DIR_NAME:
        return root

    dashboard_root = root / LIVE_DASHBOARD_DIR_NAME
    if dashboard_root.is_dir():
        return dashboard_root

    if has_screenshot_images(root):
        return root

    return None


def resolve_dashboard_session_dirs(dashboard_root: Path) -> list[Path]:
    if has_screenshot_images(dashboard_root):
        return [dashboard_root]

    return sorted(
        [path for path in dashboard_root.iterdir() if path.is_dir()],
        key=lambda item: item.name.lower(),
    )


def process_dashboard_session(
    session_dir: Path,
    progress: DashboardProgress | None = None,
) -> LiveDashboardSession:
    screenshots = list_screenshot_images(session_dir)
    points_by_index: dict[int, LiveDashboardPoint] = {}
    completed = 0
    workers = max(1, min(4, os.cpu_count() or 1, len(screenshots) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(analyze_dashboard_screenshot, path, index): index
            for index, path in enumerate(screenshots, start=1)
        }
        for future in as_completed(futures):
            index = futures[future]
            points_by_index[index] = future.result()
            completed += 1
            if progress is not None and screenshots:
                progress(
                    min(95, round(completed / len(screenshots) * 90)),
                    f"识别大屏截图：{session_dir.name} {completed}/{len(screenshots)}",
                )

    points = apply_live_recommend_deltas(
        [points_by_index[index] for index in sorted(points_by_index)]
    )
    averages = average_metrics([point.metrics for point in points])

    return LiveDashboardSession(
        session_name=session_dir.name,
        folder_path=str(session_dir),
        screenshot_count=len(points),
        start_time=points[0].captured_at if points else None,
        end_time=points[-1].captured_at if points else None,
        averages=averages,
        points=points,
    )


def build_dashboard_session_overview(session_dir: Path) -> LiveDashboardSession:
    screenshots = list_screenshot_images(session_dir)
    start_time = parse_capture_time(screenshots[0].name) if screenshots else None
    end_time = parse_capture_time(screenshots[-1].name) if screenshots else None
    return LiveDashboardSession(
        session_name=session_dir.name,
        folder_path=str(session_dir),
        screenshot_count=len(screenshots),
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        averages=LiveDashboardMetrics(),
        points=[],
    )


def list_screenshot_images(session_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in session_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ],
        key=lambda item: item.name.lower(),
    )


def analyze_dashboard_screenshot(image_path: Path, index: int) -> LiveDashboardPoint:
    stat = image_path.stat()
    cache_key = build_cache_key(image_path)
    cached = _dashboard_cache.get(cache_key)
    if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
        cached_point = cached[2]
        return cached_point.model_copy(update={"index": index, "minute_offset": index - 1})

    full_image = open_rgb_image(image_path)
    live_recommend_total = read_live_recommend_total(full_image)
    right_panel = crop_right_panel(full_image)
    layout_results = [read_layout_values(right_panel, layout) for layout in VALUE_LAYOUTS]
    raw_values, confidence = select_best_layout(layout_results)
    raw_values["live_recommend_total"] = live_recommend_total.text
    metric_values = {
        name: parse_metric_value(name, raw_values.get(name, ""))
        for name in METRIC_NAMES
    }
    metric_values["live_recommend_delta"] = None
    missing_metrics = [
        METRIC_LABELS[name]
        for name, value in metric_values.items()
        if value is None
    ]
    captured_at = parse_capture_time(image_path.name)

    point = LiveDashboardPoint(
        index=index,
        minute_offset=index - 1,
        file_name=image_path.name,
        file_path=str(image_path),
        captured_at=captured_at.isoformat() if captured_at else None,
        time_label=captured_at.strftime("%H:%M") if captured_at else f"+{index - 1} 分钟",
        metrics=LiveDashboardMetrics(**metric_values),
        confidence=confidence,
        raw_values=raw_values,
        missing_metrics=missing_metrics,
    )
    with _cache_lock:
        _dashboard_cache[cache_key] = (stat.st_size, stat.st_mtime_ns, point)
    return point


def apply_live_recommend_deltas(
    points: list[LiveDashboardPoint],
) -> list[LiveDashboardPoint]:
    previous_total: float | None = None
    updated_points: list[LiveDashboardPoint] = []
    for point in points:
        total = repair_live_recommend_total(
            point.metrics.live_recommend_total,
            previous_total,
        )
        delta: float | None = None
        if total is not None:
            if previous_total is not None and total >= previous_total:
                delta = total - previous_total
            previous_total = total

        metrics = point.metrics.model_copy(
            update={
                "live_recommend_total": total,
                "live_recommend_delta": delta,
            }
        )
        missing_metrics = [
            label
            for name, label in METRIC_LABELS.items()
            if getattr(metrics, name) is None
        ]
        updated_points.append(
            point.model_copy(
                update={
                    "metrics": metrics,
                    "missing_metrics": missing_metrics,
                }
            )
        )
    return updated_points


def repair_live_recommend_total(
    total: float | None,
    previous_total: float | None,
) -> float | None:
    if total is None or previous_total is None or total >= previous_total:
        return total

    digits = str(int(total))
    candidates = []
    for index in range(len(digits) + 1):
        candidate = int(f"{digits[:index]}0{digits[index:]}")
        if candidate >= previous_total:
            candidates.append(candidate)

    if not candidates:
        return None
    return float(min(candidates, key=lambda candidate: candidate - previous_total))


def load_dashboard_cache() -> None:
    if not DASHBOARD_CACHE_PATH.exists():
        return

    try:
        payload = json.loads(DASHBOARD_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    loaded: dict[str, tuple[int, int, LiveDashboardPoint]] = {}
    for key, item in payload.items():
        if not isinstance(item, list) or len(item) != 3:
            continue
        try:
            loaded[key] = (
                int(item[0]),
                int(item[1]),
                LiveDashboardPoint.model_validate(item[2]),
            )
        except (TypeError, ValueError):
            continue

    with _cache_lock:
        _dashboard_cache.update(loaded)


def save_dashboard_cache() -> None:
    DASHBOARD_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        payload = {
            key: [size, mtime, point.model_dump(mode="json")]
            for key, (size, mtime, point) in _dashboard_cache.items()
        }
    DASHBOARD_CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def open_rgb_image(image_path: Path) -> Image.Image:
    with Image.open(image_path) as image:
        return image.convert("RGB")


def crop_right_panel(image: Image.Image) -> Image.Image:
    width, height = image.size
    left = max(width - RIGHT_PANEL_WIDTH, 0)
    return image.crop((left, 0, width, height))


def read_live_recommend_total(image: Image.Image) -> Recognition:
    return recognize_value_crop(
        image,
        scale_full_box(LIVE_RECOMMEND_TOTAL_BOX, image.size),
    )


def read_layout_values(
    right_panel: Image.Image,
    layout: dict[str, tuple[int, int, int, int]],
) -> tuple[dict[str, str], dict[str, float]]:
    raw_values: dict[str, str] = {}
    confidences: dict[str, float] = {}
    for name, box in layout.items():
        recognition = recognize_value_crop(right_panel, scale_box(box, right_panel.size))
        raw_values[name] = recognition.text
        confidences[name] = recognition.confidence
    return raw_values, confidences


def recognize_value_crop(
    right_panel: Image.Image,
    box: tuple[int, int, int, int],
) -> Recognition:
    crop = right_panel.crop(box)
    crop = crop.resize((crop.width * 3, crop.height * 3))

    engine = get_ocr_engine()
    with _ocr_lock:
        result, _ = engine(crop, use_det=False, use_cls=False, use_rec=True)

    if not result:
        return Recognition(text="", confidence=0)

    best = max(result, key=lambda item: float(item[1] or 0))
    return Recognition(text=str(best[0]).strip(), confidence=float(best[1] or 0))


def get_ocr_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                _ocr_engine = RapidOCR()
    return _ocr_engine


def select_best_layout(
    layout_results: list[tuple[dict[str, str], dict[str, float]]],
) -> tuple[dict[str, str], float | None]:
    def score(result: tuple[dict[str, str], dict[str, float]]) -> tuple[int, float]:
        raw_values, confidences = result
        parsed_count = sum(
            1
            for name in METRIC_NAMES
            if parse_metric_value(name, raw_values.get(name, "")) is not None
        )
        average_confidence = sum(confidences.values()) / max(len(confidences), 1)
        return parsed_count, average_confidence

    raw_values, confidences = max(layout_results, key=score)
    valid_confidences = [
        confidences[name]
        for name in METRIC_NAMES
        if name in confidences
        if parse_metric_value(name, raw_values.get(name, "")) is not None
    ]
    confidence = (
        round(sum(valid_confidences) / len(valid_confidences), 4)
        if valid_confidences
        else None
    )
    return raw_values, confidence


def parse_metric_value(name: str, text: str) -> float | None:
    cleaned = normalize_ocr_text(text)
    if not cleaned or cleaned in {"-", "一", "—"}:
        return None

    if name in {"live_recommend_total", "live_recommend_delta"}:
        match = re.search(r"\d+", cleaned.replace(",", ""))
        return float(match.group(0)) if match else None

    if name == "avg_watch_seconds":
        numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", cleaned)]
        if not numbers:
            return None
        if len(numbers) >= 2:
            value = numbers[0] * 60 + numbers[1]
        else:
            value = numbers[0]
        return value if value > 0 else None

    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    value = round(float(match.group(0)) / 100, 6)
    if value in EXCLUDED_PERCENT_VALUES:
        return None
    return value


def normalize_ocr_text(text: str) -> str:
    return (
        text.strip()
        .replace("％", "%")
        .replace("O", "0")
        .replace("o", "0")
        .replace("０", "0")
        .replace("，", ".")
        .replace("。", ".")
    )


def average_metrics(metrics: list[LiveDashboardMetrics]) -> LiveDashboardMetrics:
    values: dict[str, float | None] = {}
    for name in METRIC_NAMES:
        numbers = [
            float(value)
            for metric in metrics
            if (value := getattr(metric, name)) is not None
        ]
        values[name] = round(sum(numbers) / len(numbers), 6) if numbers else None
    return LiveDashboardMetrics(**values)


def scale_box(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = size
    scale_x = width / REFERENCE_WIDTH
    scale_y = height / REFERENCE_HEIGHT
    return (
        round(box[0] * scale_x),
        round(box[1] * scale_y),
        round(box[2] * scale_x),
        round(box[3] * scale_y),
    )


def scale_full_box(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = size
    scale_x = width / FULL_REFERENCE_WIDTH
    scale_y = height / FULL_REFERENCE_HEIGHT
    return (
        round(box[0] * scale_x),
        round(box[1] * scale_y),
        round(box[2] * scale_x),
        round(box[3] * scale_y),
    )


def build_cache_key(image_path: Path) -> str:
    return f"{CACHE_VERSION}:{image_path.resolve()}"


def parse_capture_time(file_name: str) -> datetime | None:
    match = re.search(r"(\d{8})_(\d{6})", file_name)
    if not match:
        return None
    try:
        return datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def has_screenshot_images(path: Path) -> bool:
    return any(
        child.is_file() and child.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        for child in path.iterdir()
    )
