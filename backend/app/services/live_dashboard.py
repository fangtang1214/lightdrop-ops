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
CACHE_VERSION = "dashboard-v11"
ARCHIVE_DIR_NAME = "存档"
ARCHIVE_SCHEMA_VERSION = "dashboard-session-v7"

METRIC_NAMES = (
    "live_recommend_delta",
    "live_recommend_total",
    "deal_amount_total",
    "deal_amount_delta",
    "deal_order_total",
    "deal_order_delta",
    "deal_user_total",
    "deal_user_delta",
    "online_user_count",
    "online_user_delta",
    "effective_enter_rate",
    "avg_watch_seconds",
    "comment_rate",
    "like_rate",
    "thousand_watch_deal_amount",
    "deal_conversion_rate",
    "new_customer_conversion_rate",
)

METRIC_LABELS = {
    "live_recommend_delta": "直播推荐增量",
    "live_recommend_total": "直播推荐总量",
    "deal_amount_total": "成交金额总量",
    "deal_amount_delta": "成交金额增量",
    "deal_order_total": "成交订单数总量",
    "deal_order_delta": "成交订单数增量",
    "deal_user_total": "成交人数总量",
    "deal_user_delta": "成交人数增量",
    "online_user_count": "实时在线人数",
    "online_user_delta": "实时在线人数增量",
    "effective_enter_rate": "直播有效进房率",
    "avg_watch_seconds": "人均观看时长",
    "comment_rate": "评论率",
    "like_rate": "点赞率",
    "thousand_watch_deal_amount": "千次观看成交金额",
    "deal_conversion_rate": "成交转化率",
    "new_customer_conversion_rate": "新客转化率",
}

PERCENT_METRICS = {
    "effective_enter_rate",
    "comment_rate",
    "like_rate",
    "deal_conversion_rate",
    "new_customer_conversion_rate",
}

AMOUNT_METRICS = {
    "deal_amount_total",
    "deal_amount_delta",
    "thousand_watch_deal_amount",
}

COUNT_METRICS = {
    "live_recommend_total",
    "live_recommend_delta",
    "deal_order_total",
    "deal_order_delta",
    "deal_user_total",
    "deal_user_delta",
    "online_user_count",
    "online_user_delta",
}

DELTA_METRICS = {
    "live_recommend_delta",
    "deal_amount_delta",
    "deal_order_delta",
    "deal_user_delta",
    "online_user_delta",
}

DELTA_SOURCE_METRICS = {
    "live_recommend_delta": "live_recommend_total",
    "deal_amount_delta": "deal_amount_total",
    "deal_order_delta": "deal_order_total",
    "deal_user_delta": "deal_user_total",
    "online_user_delta": "online_user_count",
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


@dataclass(frozen=True)
class OcrTextEntry:
    text: str
    confidence: float
    box: tuple[float, float, float, float]

    @property
    def cx(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def cy(self) -> float:
        return (self.box[1] + self.box[3]) / 2


@dataclass(frozen=True)
class AnchorSpec:
    metric_name: str
    aliases: tuple[str, ...]
    region: str
    value_width: int = 170
    value_height: int = 45


@dataclass(frozen=True)
class CalibratedValueBox:
    box: tuple[int, int, int, int]


ANCHOR_SPECS = (
    AnchorSpec("live_recommend_total", ("直播推荐",), "left", value_width=115),
    AnchorSpec("deal_amount_total", ("累计成交金额", "成交金额"), "left", value_width=190, value_height=52),
    AnchorSpec("deal_order_total", ("成交订单数",), "left", value_width=120),
    AnchorSpec("deal_user_total", ("成交人数",), "left", value_width=120),
    AnchorSpec("online_user_count", ("实时在线人数",), "left", value_width=120),
    AnchorSpec("effective_enter_rate", ("直播有效进房率", "有效进房率"), "right"),
    AnchorSpec("avg_watch_seconds", ("人均观看时长",), "right"),
    AnchorSpec("comment_rate", ("评论率",), "right"),
    AnchorSpec("like_rate", ("点赞率",), "right"),
    AnchorSpec("thousand_watch_deal_amount", ("千次观看成交金额",), "right", value_width=190),
    AnchorSpec("deal_conversion_rate", ("成交转化率",), "right"),
    AnchorSpec("new_customer_conversion_rate", ("新客转化率",), "right"),
)


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
                build_dashboard_session_overview(session_dir, dashboard_root)
                for session_dir in session_dirs
            ],
            message=f"未找到大屏截图场次：{requested_session}",
        )

    sessions = []
    total = max(len(session_dirs), 1)
    for index, session_dir in enumerate(session_dirs, start=1):
        if requested_session and session_dir.name != requested_session:
            sessions.append(build_dashboard_session_overview(session_dir, dashboard_root))
            continue
        if progress is not None:
            progress(round((index - 1) / total * 90), f"识别大屏截图：{session_dir.name}")
        session = process_dashboard_session(session_dir, progress=progress)
        save_dashboard_session_archive(dashboard_root, session)
        sessions.append(session)
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
        build_dashboard_session_overview(session_dir, dashboard_root)
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
        [
            path
            for path in dashboard_root.iterdir()
            if path.is_dir() and path.name != ARCHIVE_DIR_NAME
        ],
        key=lambda item: item.name.lower(),
    )


def process_dashboard_session(
    session_dir: Path,
    progress: DashboardProgress | None = None,
) -> LiveDashboardSession:
    screenshots = list_screenshot_images(session_dir)
    calibrated_boxes = calibrate_dashboard_value_boxes(screenshots[0]) if screenshots else {}
    points_by_index: dict[int, LiveDashboardPoint] = {}
    completed = 0
    workers = max(1, min(4, os.cpu_count() or 1, len(screenshots) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(analyze_dashboard_screenshot, path, index, calibrated_boxes): index
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

    points = apply_delta_metrics(
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


def build_dashboard_session_overview(
    session_dir: Path,
    dashboard_root: Path | None = None,
) -> LiveDashboardSession:
    screenshots = list_screenshot_images(session_dir)
    start_time = parse_capture_time(screenshots[0].name) if screenshots else None
    end_time = parse_capture_time(screenshots[-1].name) if screenshots else None
    overview = LiveDashboardSession(
        session_name=session_dir.name,
        folder_path=str(session_dir),
        screenshot_count=len(screenshots),
        start_time=start_time.isoformat() if start_time else None,
        end_time=end_time.isoformat() if end_time else None,
        averages=LiveDashboardMetrics(),
        points=[],
    )
    if dashboard_root is None:
        return overview

    archived = load_dashboard_session_archive(dashboard_root, session_dir.name)
    if archived is not None and archive_matches_session(archived, overview):
        return archived
    return overview


def archive_matches_session(
    archived: LiveDashboardSession,
    overview: LiveDashboardSession,
) -> bool:
    return (
        archived.session_name == overview.session_name
        and archived.screenshot_count == overview.screenshot_count
        and archived.start_time == overview.start_time
        and archived.end_time == overview.end_time
        and bool(archived.points)
    )


def load_dashboard_session_archive(
    dashboard_root: Path,
    session_name: str,
) -> LiveDashboardSession | None:
    archive_file = dashboard_archive_path(dashboard_root, session_name)
    if not archive_file.exists():
        return None

    try:
        payload = json.loads(archive_file.read_text(encoding="utf-8"))
        if payload.get("version") != ARCHIVE_SCHEMA_VERSION:
            return None
        session_payload = payload.get("session", payload)
        session = LiveDashboardSession.model_validate(session_payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None

    if session.session_name != session_name:
        return None
    return session


def save_dashboard_session_archive(
    dashboard_root: Path,
    session: LiveDashboardSession,
) -> None:
    archive_file = dashboard_archive_path(dashboard_root, session.session_name)
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": ARCHIVE_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "session": session.model_dump(mode="json"),
    }
    archive_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dashboard_archive_path(dashboard_root: Path, session_name: str) -> Path:
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", session_name).strip(" .")
    if not safe_name:
        safe_name = "dashboard-session"
    return dashboard_root / ARCHIVE_DIR_NAME / f"{safe_name}.json"


def list_screenshot_images(session_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in session_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ],
        key=lambda item: item.name.lower(),
    )


def analyze_dashboard_screenshot(
    image_path: Path,
    index: int,
    calibrated_boxes: dict[str, CalibratedValueBox] | None = None,
) -> LiveDashboardPoint:
    stat = image_path.stat()
    cache_key = build_cache_key(image_path)
    cached = _dashboard_cache.get(cache_key)
    if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime_ns:
        cached_point = cached[2]
        return cached_point.model_copy(update={"index": index, "minute_offset": index - 1})

    full_image = open_rgb_image(image_path)
    if calibrated_boxes:
        raw_values, confidence = read_calibrated_metric_values(full_image, calibrated_boxes)
    else:
        raw_values, confidence = read_anchor_metric_values(full_image)
    fill_legacy_metric_values(full_image, raw_values)
    metric_values = {
        name: parse_metric_value(name, raw_values.get(name, ""))
        for name in METRIC_NAMES
    }
    for delta_name in DELTA_METRICS:
        metric_values[delta_name] = None
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


def apply_delta_metrics(
    points: list[LiveDashboardPoint],
) -> list[LiveDashboardPoint]:
    previous_values: dict[str, float | None] = {
        source_name: None for source_name in DELTA_SOURCE_METRICS.values()
    }
    updated_points: list[LiveDashboardPoint] = []
    for point in points:
        metric_updates: dict[str, float | None] = {}
        for delta_name, source_name in DELTA_SOURCE_METRICS.items():
            value = getattr(point.metrics, source_name)
            previous_value = previous_values[source_name]
            value = repair_cumulative_metric_value(source_name, value, previous_value)
            metric_updates[source_name] = value

            delta: float | None = None
            if value is not None:
                if previous_value is not None:
                    if source_name == "online_user_count":
                        delta = value - previous_value
                    elif value >= previous_value:
                        delta = value - previous_value
                if source_name == "online_user_count" or previous_value is None or value >= previous_value:
                    previous_values[source_name] = value
            metric_updates[delta_name] = delta

        metrics = point.metrics.model_copy(
            update=metric_updates
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


def repair_cumulative_metric_value(
    name: str,
    value: float | None,
    previous_value: float | None,
) -> float | None:
    if value is None or previous_value is None or value >= previous_value:
        return value
    if name == "online_user_count":
        return value
    if name == "deal_amount_total":
        return repair_scaled_amount_total(value, previous_value)
    return repair_live_recommend_total(value, previous_value)


def repair_scaled_amount_total(
    value: float,
    previous_value: float,
) -> float | None:
    if value >= previous_value / 10:
        return None
    candidates = [
        round(value * multiplier, 2)
        for multiplier in (10, 100, 1000, 10000)
        if value * multiplier >= previous_value
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: candidate - previous_value)


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


def calibrate_dashboard_value_boxes(
    image_path: Path,
) -> dict[str, CalibratedValueBox]:
    image = open_rgb_image(image_path)
    width, height = image.size
    region_defs = {
        "left": ((0, 0), image.crop((0, 0, width // 2, height))),
        "right": ((max(width - RIGHT_PANEL_WIDTH, 0), 0), crop_right_panel(image)),
    }
    entries_by_region = {
        name: detect_text_entries(region)
        for name, (_, region) in region_defs.items()
    }
    boxes: dict[str, CalibratedValueBox] = {}
    for spec in ANCHOR_SPECS:
        origin, region = region_defs[spec.region]
        anchor = find_anchor_entry(entries_by_region[spec.region], spec.aliases)
        if anchor is None:
            continue
        boxes[spec.metric_name] = CalibratedValueBox(
            box=anchor_value_box(anchor, spec, origin, region.size)
        )
    return boxes


def anchor_value_box(
    anchor: OcrTextEntry,
    spec: AnchorSpec,
    origin: tuple[int, int],
    region_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x1, _, _, y2 = anchor.box
    region_width, region_height = region_size
    left = max(0, round(x1 - 6))
    top = min(region_height, round(y2 + 2))
    right = min(region_width, round(x1 + spec.value_width))
    bottom = min(region_height, round(y2 + spec.value_height))
    return (
        origin[0] + left,
        origin[1] + top,
        origin[0] + right,
        origin[1] + bottom,
    )


def read_calibrated_metric_values(
    image: Image.Image,
    calibrated_boxes: dict[str, CalibratedValueBox],
) -> tuple[dict[str, str], float | None]:
    raw_values: dict[str, str] = {}
    confidences: list[float] = []
    for spec in ANCHOR_SPECS:
        value_box = calibrated_boxes.get(spec.metric_name)
        if value_box is None:
            continue
        recognition = recognize_value_crop(image, value_box.box)
        raw_values[spec.metric_name] = recognition.text
        if parse_metric_value(spec.metric_name, recognition.text) is not None:
            confidences.append(recognition.confidence)

    confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    return raw_values, confidence


def read_anchor_metric_values(
    image: Image.Image,
) -> tuple[dict[str, str], float | None]:
    width, height = image.size
    regions = {
        "left": image.crop((0, 0, width // 2, height)),
        "right": crop_right_panel(image),
    }
    entries_by_region = {
        name: detect_text_entries(region)
        for name, region in regions.items()
    }
    raw_values: dict[str, str] = {}
    confidences: list[float] = []
    for spec in ANCHOR_SPECS:
        region = regions[spec.region]
        entries = entries_by_region[spec.region]
        recognition = read_metric_by_anchor(region, entries, spec)
        if recognition is None:
            continue
        raw_values[spec.metric_name] = recognition.text
        if parse_metric_value(spec.metric_name, recognition.text) is not None:
            confidences.append(recognition.confidence)

    confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    return raw_values, confidence


def detect_text_entries(image: Image.Image) -> list[OcrTextEntry]:
    engine = get_ocr_engine()
    with _ocr_lock:
        result, _ = engine(image, use_det=True, use_cls=False, use_rec=True)
    entries: list[OcrTextEntry] = []
    for item in result or []:
        if len(item) < 3:
            continue
        polygon, text, confidence = item
        entries.append(
            OcrTextEntry(
                text=str(text).strip(),
                confidence=float(confidence or 0),
                box=polygon_bounds(polygon),
            )
        )
    return entries


def polygon_bounds(polygon: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def read_metric_by_anchor(
    region: Image.Image,
    entries: list[OcrTextEntry],
    spec: AnchorSpec,
) -> Recognition | None:
    anchor = find_anchor_entry(entries, spec.aliases)
    if anchor is None:
        return None

    fallback = find_detected_value_below_anchor(entries, anchor, spec)
    if fallback is not None:
        return fallback

    x1, _, _, y2 = anchor.box
    box = (
        max(0, round(x1 - 6)),
        min(region.height, round(y2 + 2)),
        min(region.width, round(x1 + spec.value_width)),
        min(region.height, round(y2 + spec.value_height)),
    )
    recognition = recognize_value_crop(region, box)
    if parse_metric_value(spec.metric_name, recognition.text) is not None:
        return recognition
    return recognition


def find_anchor_entry(
    entries: list[OcrTextEntry],
    aliases: tuple[str, ...],
) -> OcrTextEntry | None:
    for alias in aliases:
        normalized_alias = normalize_anchor_text(alias)
        matches = [
            entry
            for entry in entries
            if normalized_alias in normalize_anchor_text(entry.text)
        ]
        if matches:
            return max(matches, key=lambda entry: (entry.confidence, -entry.cy))
    return None


def find_detected_value_below_anchor(
    entries: list[OcrTextEntry],
    anchor: OcrTextEntry,
    spec: AnchorSpec,
) -> Recognition | None:
    x1, _, _, y2 = anchor.box
    x_left = x1 - 12
    x_right = x1 + spec.value_width
    candidates = []
    for entry in entries:
        if entry.cy <= y2 or entry.cy - y2 > 72:
            continue
        if entry.cx < x_left or entry.cx > x_right:
            continue
        if parse_metric_value(spec.metric_name, entry.text) is None:
            continue
        candidates.append(entry)
    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda entry: (entry.cy - y2, abs(entry.cx - x1), -entry.confidence),
    )
    return Recognition(text=best.text, confidence=best.confidence)


def normalize_anchor_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_ocr_text(text))


def fill_legacy_metric_values(
    image: Image.Image,
    raw_values: dict[str, str],
) -> None:
    if "live_recommend_total" not in raw_values:
        raw_values["live_recommend_total"] = read_live_recommend_total(image).text

    right_panel = crop_right_panel(image)
    layout_results = [read_layout_values(right_panel, layout) for layout in VALUE_LAYOUTS]
    legacy_values, _ = select_best_layout(layout_results)
    for name, value in legacy_values.items():
        if name not in raw_values or parse_metric_value(name, raw_values[name]) is None:
            raw_values[name] = value


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

    if name in COUNT_METRICS:
        match = re.search(r"\d+", cleaned.replace(",", ""))
        return float(match.group(0)) if match else None

    if name == "thousand_watch_deal_amount":
        return parse_cent_amount_value(cleaned)

    if name in AMOUNT_METRICS:
        return parse_amount_value(cleaned)

    if name == "avg_watch_seconds":
        numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", cleaned)]
        if not numbers:
            return None
        if len(numbers) >= 2:
            value = numbers[0] * 60 + numbers[1]
        else:
            value = numbers[0]
        return value

    percent_text = cleaned.replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", percent_text)
    if not match:
        return None
    value = round(float(match.group(0)) / 100, 6)
    if value in EXCLUDED_PERCENT_VALUES:
        return None
    return value


def parse_amount_value(text: str) -> float | None:
    normalized = (
        text.replace("，", ",")
        .replace("。", ".")
        .replace("．", ".")
        .replace(" ", "")
    )
    value_text = re.sub(r"[^\d.,]", "", normalized)
    if not value_text:
        return None

    if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{2}", value_text):
        value = float(value_text.replace(",", ""))
    elif re.fullmatch(r"\d+[.,]\d{2}", value_text):
        value = float(value_text.replace(",", "."))
    elif re.fullmatch(r"\d+[.,]\d{3}", value_text):
        value = float(value_text.replace(",", "").replace(".", ""))
    else:
        digits = re.sub(r"\D", "", value_text)
        if not digits:
            return None
        value = float(digits)

    if "万" in normalized:
        value *= 10000
    return round(value, 2)


def parse_cent_amount_value(text: str) -> float | None:
    normalized = (
        text.replace("，", ",")
        .replace("。", ".")
        .replace("．", ".")
        .replace(" ", "")
    )
    value_text = re.sub(r"[^\d.,]", "", normalized)
    if not value_text:
        return None

    if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{2}", value_text):
        value = float(value_text.replace(",", ""))
    elif re.fullmatch(r"\d+[.,]\d{2}", value_text):
        value = float(value_text.replace(",", "."))
    else:
        digits = re.sub(r"\D", "", value_text)
        if not digits:
            return None
        if len(digits) >= 5:
            digits = digits[:-1]
        value = float(digits) / 100

    if "万" in normalized:
        value *= 10000
    return round(value, 2)


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
