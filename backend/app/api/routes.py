from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from backend.app.models.schemas import (
    DashboardRunRequest,
    LiveDataRunRequest,
    MatchRequest,
    MatchResponse,
    OverviewResponse,
    RecentReportResponse,
    ScanRequest,
    ScanResponse,
    TaskCreateResponse,
    TaskStatusResponse,
    TopProductsResponse,
    TranscriptTask,
)
from backend.app.services.data_tables import (
    DEFAULT_BAD_PRODUCT_RULE,
    build_conversion_drop_rankings,
    build_good_rankings,
    current_table_process_signature,
    process_live_data_tables,
    resolve_database_dirs,
)
from backend.app.services.exporter import export_groups_to_excel
from backend.app.services.live_dashboard import (
    process_live_dashboard_screenshots,
    scan_live_dashboard_sessions,
)
from backend.app.services.matcher import match_product_groups
from backend.app.services.reports import recent_groups, session_stats, top_products
from backend.app.services.scanner import SUPPORTED_IMAGE_EXTENSIONS, scan_root_folder
from backend.app.services.store import analysis_store
from backend.app.services.task_queue import TaskProgress, task_queue
from backend.app.services.transcripts import guess_media_type, transcript_service

api_router = APIRouter()


def dump_model(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


@api_router.post("/transcripts/upload", response_model=TranscriptTask)
def upload_transcript_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> TranscriptTask:
    try:
        task = transcript_service.create_task(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存音视频文件失败：{exc}") from exc

    background_tasks.add_task(transcript_service.process_task, task.id)
    return task


@api_router.get("/transcripts", response_model=list[TranscriptTask])
def list_transcript_tasks() -> list[TranscriptTask]:
    return transcript_service.list_tasks()


@api_router.get("/transcripts/media/{task_id}")
def get_transcript_media(task_id: str) -> FileResponse:
    try:
        media_path = transcript_service.media_file(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="转写任务不存在") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="音视频文件不存在") from exc

    return FileResponse(
        path=media_path,
        filename=media_path.name,
        media_type=guess_media_type(media_path),
    )


@api_router.get("/transcripts/{task_id}", response_model=TranscriptTask)
def get_transcript_task(task_id: str) -> TranscriptTask:
    try:
        return transcript_service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="转写任务不存在") from exc


@api_router.post("/transcripts/{task_id}/retry", response_model=TranscriptTask)
def retry_transcript_task(
    task_id: str,
    background_tasks: BackgroundTasks,
) -> TranscriptTask:
    try:
        task = transcript_service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="转写任务不存在") from exc

    if task.status == "processing":
        raise HTTPException(status_code=409, detail="任务正在转写中")
    task.status = "queued"
    task.message = "任务已重新排队"
    task.error = None
    transcript_service.save_task(task)
    background_tasks.add_task(transcript_service.process_task, task.id)
    return task


@api_router.get("/transcripts/{task_id}/export")
def export_transcript_task(
    task_id: str,
    format: str = Query(default="txt", pattern="^(txt|md|srt)$"),
) -> Response:
    try:
        content, media_type, filename = transcript_service.export(task_id, format)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="转写任务不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def refresh_bad_image_scan(
    scan: ScanResponse,
    progress: TaskProgress | None = None,
) -> ScanResponse:
    database_dirs = resolve_database_dirs(scan.root_path)
    scan_path = str(database_dirs.bad_images) if database_dirs is not None else scan.root_path
    refreshed = scan_root_folder(scan_path, progress=progress)
    refreshed.root_path = scan.root_path
    refreshed.table_process = scan.table_process
    refreshed.live_dashboard = scan.live_dashboard
    analysis_store.set_scan(refreshed)
    return refreshed


def ensure_table_process(
    *,
    bad_product_rule: str = DEFAULT_BAD_PRODUCT_RULE,
    include_good_rankings: bool = False,
    include_conversion_drop_rankings: bool = False,
    progress: TaskProgress | None = None,
) -> ScanResponse:
    scan = analysis_store.require_scan()
    table_process = scan.table_process
    rebuilt_tables = False
    current_signature = current_table_process_signature(scan.root_path)
    table_process_stale = (
        current_signature is not None
        and table_process is not None
        and table_process.source_signature != current_signature
    )
    bad_product_rule_changed = (
        table_process is not None
        and table_process.bad_product_rule != bad_product_rule
    )

    if (
        table_process is None
        or table_process_stale
        or bad_product_rule_changed
        or not table_process.processed_sessions
    ):
        if progress is not None:
            progress(10, "处理直播详细数据")
        table_process = process_live_data_tables(
            scan.root_path,
            bad_product_rule=bad_product_rule,
            include_good_rankings=include_good_rankings,
            include_conversion_drop_rankings=include_conversion_drop_rankings,
        )
        scan.table_process = table_process
        rebuilt_tables = True

    if table_process is not None and table_process.processed_sessions:
        if include_good_rankings and not table_process.good_rankings:
            if progress is not None:
                progress(45, "生成优品分析")
            table_process.good_rankings = build_good_rankings(
                table_process.processed_sessions
            )
        if (
            include_conversion_drop_rankings
            and not table_process.conversion_drop_rankings
        ):
            if progress is not None:
                progress(55, "生成转化落差分析")
            table_process.conversion_drop_rankings = build_conversion_drop_rankings(
                table_process.processed_sessions
            )

    analysis_store.set_table_process(table_process)
    if rebuilt_tables and table_process is not None and table_process.processed_sessions:
        if progress is not None:
            progress(70, "刷新差品图片索引")
        return refresh_bad_image_scan(scan, progress=progress)
    if progress is not None:
        progress(100, "分析完成")
    return analysis_store.require_scan()


@api_router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str) -> TaskStatusResponse:
    task = task_queue.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@api_router.post("/folders/scan", response_model=ScanResponse)
def scan_folder(payload: ScanRequest) -> ScanResponse:
    try:
        database_dirs = resolve_database_dirs(payload.root_path)
        scan_path = (
            str(database_dirs.bad_images)
            if database_dirs is not None
            else payload.root_path
        )
        scan = scan_root_folder(scan_path, analyze_images=False)
        scan.root_path = payload.root_path
        scan.live_dashboard = scan_live_dashboard_sessions(payload.root_path)
        analysis_store.set_scan(scan)
        return scan
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}") from exc



@api_router.post("/live-data/run", response_model=TaskCreateResponse)
def run_live_data(payload: LiveDataRunRequest | None = None) -> TaskCreateResponse:
    def work(progress: TaskProgress) -> tuple[str, dict]:
        scan = ensure_table_process(
            bad_product_rule=payload.bad_product_rule if payload else DEFAULT_BAD_PRODUCT_RULE,
            progress=progress,
        )
        return "scan", dump_model(scan)

    task = task_queue.submit("liveData", work)
    return TaskCreateResponse(task_id=task.id)


@api_router.post("/good-products/run", response_model=TaskCreateResponse)
def run_good_products() -> TaskCreateResponse:
    def work(progress: TaskProgress) -> tuple[str, dict]:
        scan = ensure_table_process(include_good_rankings=True, progress=progress)
        return "scan", dump_model(scan)

    task = task_queue.submit("goodProducts", work)
    return TaskCreateResponse(task_id=task.id)


@api_router.post("/conversion-drop/run", response_model=TaskCreateResponse)
def run_conversion_drop() -> TaskCreateResponse:
    def work(progress: TaskProgress) -> tuple[str, dict]:
        scan = ensure_table_process(include_conversion_drop_rankings=True, progress=progress)
        return "scan", dump_model(scan)

    task = task_queue.submit("conversionDrop", work)
    return TaskCreateResponse(task_id=task.id)


@api_router.post("/dashboard/run", response_model=TaskCreateResponse)
def run_live_dashboard(payload: DashboardRunRequest | None = None) -> TaskCreateResponse:
    def work(progress: TaskProgress) -> tuple[str, dict]:
        scan = analysis_store.require_scan()
        previous_live_dashboard = scan.live_dashboard
        scan.live_dashboard = process_live_dashboard_screenshots(
            scan.root_path,
            progress=progress,
            session_name=payload.session_name if payload else None,
        )
        if payload and payload.session_name and scan.live_dashboard is not None:
            previous_sessions = {
                session.session_name: session
                for session in (previous_live_dashboard.processed_sessions if previous_live_dashboard else [])
                if session.points
            }
            scan.live_dashboard.processed_sessions = [
                previous_sessions.get(session.session_name, session)
                if session.session_name != payload.session_name and not session.points
                else session
                for session in scan.live_dashboard.processed_sessions
            ]
        analysis_store.set_live_dashboard(scan.live_dashboard)
        progress(100, "大屏复盘完成")
        return "scan", dump_model(scan)

    task = task_queue.submit("dashboardReview", work)
    return TaskCreateResponse(task_id=task.id)


@api_router.post("/match/run", response_model=TaskCreateResponse)
def run_match(payload: MatchRequest) -> TaskCreateResponse:
    def work(progress: TaskProgress) -> tuple[str, dict]:
        progress(5, "准备图片数据")
        scan = analysis_store.require_scan()
        if resolve_database_dirs(scan.root_path) is not None:
            scan = ensure_table_process(
                bad_product_rule=payload.bad_product_rule,
                progress=progress,
            )
        elif not scan.images or any(image.image_hash is None for image in scan.images):
            scan = refresh_bad_image_scan(scan, progress=progress)

        progress(75, "匹配相似商品")
        groups = match_product_groups(
            scan.images,
            scan.sessions,
            threshold=payload.hash_distance_threshold,
        )
        analysis_store.set_groups(groups)

        response = MatchResponse(
            status="success",
            total_images=len(scan.images),
            product_groups=len(groups),
            duplicate_groups=len([group for group in groups if group.appear_count >= 2]),
            groups=groups,
        )
        progress(100, "匹配完成")
        return "match", dump_model(response)

    task = task_queue.submit("match", work)
    return TaskCreateResponse(task_id=task.id)


@api_router.get("/reports/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    try:
        scan = analysis_store.require_scan()
        groups = analysis_store.require_groups()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    recent_duplicate_counts: dict[str, int] = {}
    for n in (4, 6, 10):
        _, products = recent_groups(groups, scan.sessions, n=n, min_count=2)
        recent_duplicate_counts[str(n)] = len(products)

    top_product = top_products(groups, limit=1)

    return OverviewResponse(
        total_sessions=len(scan.sessions),
        total_images=len(scan.images),
        product_groups=len(groups),
        duplicate_groups=len([group for group in groups if group.appear_count >= 2]),
        recent_duplicate_counts=recent_duplicate_counts,
        top_product=top_product[0] if top_product else None,
        session_stats=session_stats(groups, scan.sessions),
    )


@api_router.get("/reports/recent", response_model=RecentReportResponse)
def get_recent_report(
    n: int = Query(default=4, ge=1, le=100),
    min_count: int = Query(default=2, ge=1, le=100),
) -> RecentReportResponse:
    try:
        scan = analysis_store.require_scan()
        groups = analysis_store.require_groups()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    sessions, products = recent_groups(groups, scan.sessions, n=n, min_count=min_count)
    return RecentReportResponse(
        range=n,
        min_count=min_count,
        sessions=sessions,
        products=products,
    )


@api_router.get("/reports/top-products", response_model=TopProductsResponse)
def get_top_products(limit: int = Query(default=20, ge=1, le=200)) -> TopProductsResponse:
    try:
        groups = analysis_store.require_groups()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TopProductsResponse(products=top_products(groups, limit=limit))


@api_router.get("/exports/excel")
def export_excel() -> FileResponse:
    try:
        groups = analysis_store.require_groups()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    output_path = export_groups_to_excel(groups)
    return FileResponse(
        path=output_path,
        filename="lightdrop-products-report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@api_router.get("/images/preview")
def preview_image(path: str) -> FileResponse:
    image_path = Path(path).expanduser().resolve()
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    if image_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    if not is_allowed_preview_path(image_path):
        raise HTTPException(status_code=403, detail="图片不在当前扫描目录内")
    return FileResponse(path=image_path)


def is_allowed_preview_path(image_path: Path) -> bool:
    try:
        scan = analysis_store.require_scan()
    except RuntimeError:
        return False

    allowed_roots = {Path(scan.root_path).expanduser().resolve()}

    database_dirs = resolve_database_dirs(scan.root_path)
    if database_dirs is not None:
        allowed_roots.update(
            {
                database_dirs.root,
                database_dirs.data_tables,
                database_dirs.all_images,
                database_dirs.bad_images,
            }
        )

    if scan.live_dashboard is not None and scan.live_dashboard.dashboard_root:
        allowed_roots.add(Path(scan.live_dashboard.dashboard_root).expanduser().resolve())

    for session in scan.sessions:
        allowed_roots.add(Path(session.folder_path).expanduser().resolve())
    if scan.live_dashboard is not None:
        for session in scan.live_dashboard.processed_sessions:
            allowed_roots.add(Path(session.folder_path).expanduser().resolve())

    return any(is_relative_to(image_path, root) for root in allowed_roots)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
