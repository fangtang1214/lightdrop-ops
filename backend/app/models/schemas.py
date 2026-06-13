from pydantic import BaseModel, Field
from typing import Any, Literal

BadProductRule = Literal["bottom_20", "zero_conversion"]


class ScanRequest(BaseModel):
    root_path: str = Field(..., min_length=1)


class DashboardRunRequest(BaseModel):
    session_name: str | None = None


class MatchRequest(BaseModel):
    hash_distance_threshold: int = Field(default=8, ge=0, le=64)
    bad_product_rule: BadProductRule = "bottom_20"


class LiveDataRunRequest(BaseModel):
    bad_product_rule: BadProductRule = "bottom_20"


class SessionRecord(BaseModel):
    id: int
    name: str
    folder_path: str
    session_index: int
    image_count: int


class ImageRecord(BaseModel):
    image_id: str
    file_name: str
    file_path: str
    session_id: int
    session_name: str
    session_index: int
    width: int | None = None
    height: int | None = None
    file_size: int
    image_hash: str | None = None


class ProductGroupRecord(BaseModel):
    id: int
    product_group_id: str
    representative_image: str
    images: list[ImageRecord]
    appeared_sessions: list[str]
    appeared_session_ids: list[int]
    appear_count: int
    total_appear_count: int


class BadProductRecord(BaseModel):
    product_id: str
    title: str
    rank_from_bottom: int
    exposure_click_rate: float
    click_conversion_rate: float
    refund_rate: float
    net_conversion_score: float
    exposure_people: int
    click_people: int
    deal_people: int
    deal_orders: int
    refund_orders: int
    matched_images: list[str]
    copied_images: list[str]


class LiveProductRankRecord(BaseModel):
    product_id: str
    title: str
    representative_image: str | None = None
    matched_images: list[str] = Field(default_factory=list)
    rank: int
    rank_from_bottom: int
    is_bad_product: bool
    exposure_click_rate: float
    click_conversion_rate: float
    refund_rate: float
    net_conversion_score: float
    exposure_people: int
    click_people: int
    deal_people: int
    deal_orders: int
    refund_orders: int


class GoodProductRankRecord(BaseModel):
    product_id: str
    title: str
    representative_image: str | None = None
    matched_images: list[str] = Field(default_factory=list)
    rank: int
    exposure_click_rate: float
    click_conversion_rate: float
    refund_rate: float
    net_conversion_score: float
    exposure_people: int
    click_people: int
    deal_people: int
    deal_orders: int
    refund_orders: int
    source_session_count: int
    source_sessions: list[str]
    source_product_ids: list[str]
    latest_session_name: str


class GoodProductRanking(BaseModel):
    range_size: int
    session_names: list[str]
    products: list[GoodProductRankRecord]


class ConversionDropRankRecord(BaseModel):
    product_id: str
    title: str
    representative_image: str | None = None
    matched_images: list[str] = Field(default_factory=list)
    rank: int
    current_session_name: str
    history_session_name: str
    history_product_id: str
    history_title: str
    current_rank: int
    history_rank: int
    current_net_conversion_score: float
    history_net_conversion_score: float
    net_conversion_drop: float
    drop_ratio: float
    current_click_conversion_rate: float
    history_click_conversion_rate: float
    click_conversion_rate_drop: float
    current_exposure_click_rate: float
    history_exposure_click_rate: float
    current_exposure_people: int
    history_exposure_people: int
    current_click_people: int
    history_click_people: int
    current_deal_people: int
    history_deal_people: int
    source_product_ids: list[str]


class ConversionDropRanking(BaseModel):
    session_name: str
    products: list[ConversionDropRankRecord]


class TableProcessSession(BaseModel):
    table_file: str
    session_name: str
    total_products: int
    selected_bad_products: int
    matched_products: int
    copied_images: int
    unmatched_product_ids: list[str]
    products: list[BadProductRecord]
    ranked_products: list[LiveProductRankRecord]


class TableProcessSummary(BaseModel):
    enabled: bool
    data_tables_dir: str | None = None
    all_images_dir: str | None = None
    bad_images_dir: str | None = None
    bad_product_rule: BadProductRule = "bottom_20"
    processed_sessions: list[TableProcessSession] = Field(default_factory=list)
    good_rankings: list[GoodProductRanking] = Field(default_factory=list)
    conversion_drop_rankings: list[ConversionDropRanking] = Field(default_factory=list)
    source_signature: str | None = None
    message: str | None = None


class LiveDashboardMetrics(BaseModel):
    live_recommend_delta: float | None = None
    live_recommend_total: float | None = None
    deal_amount_total: float | None = None
    deal_amount_delta: float | None = None
    deal_order_total: float | None = None
    deal_order_delta: float | None = None
    deal_user_total: float | None = None
    deal_user_delta: float | None = None
    online_user_count: float | None = None
    online_user_delta: float | None = None
    effective_enter_rate: float | None = None
    avg_watch_seconds: float | None = None
    comment_rate: float | None = None
    like_rate: float | None = None
    thousand_watch_deal_amount: float | None = None
    deal_conversion_rate: float | None = None
    new_customer_conversion_rate: float | None = None


class LiveDashboardPoint(BaseModel):
    index: int
    minute_offset: int
    file_name: str
    file_path: str
    captured_at: str | None = None
    time_label: str
    metrics: LiveDashboardMetrics
    confidence: float | None = None
    raw_values: dict[str, str] = Field(default_factory=dict)
    missing_metrics: list[str] = Field(default_factory=list)


class LiveDashboardSession(BaseModel):
    session_name: str
    folder_path: str
    screenshot_count: int
    start_time: str | None = None
    end_time: str | None = None
    averages: LiveDashboardMetrics
    points: list[LiveDashboardPoint]


class LiveDashboardSummary(BaseModel):
    enabled: bool
    dashboard_root: str | None = None
    processed_sessions: list[LiveDashboardSession] = Field(default_factory=list)
    message: str | None = None


class ScanResponse(BaseModel):
    root_path: str
    sessions: list[SessionRecord]
    images: list[ImageRecord]
    skipped_files: list[str]
    table_process: TableProcessSummary | None = None
    live_dashboard: LiveDashboardSummary | None = None


class MatchResponse(BaseModel):
    status: str
    total_images: int
    product_groups: int
    duplicate_groups: int
    groups: list[ProductGroupRecord]


class TaskCreateResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    id: str
    name: str
    status: str
    progress: int = 0
    message: str = ""
    result_kind: str | None = None
    result: Any = None
    error: str | None = None
    created_at: str
    updated_at: str


class OverviewResponse(BaseModel):
    total_sessions: int
    total_images: int
    product_groups: int
    duplicate_groups: int
    recent_duplicate_counts: dict[str, int]
    top_product: ProductGroupRecord | None
    session_stats: list[dict]


class RecentReportResponse(BaseModel):
    range: int
    min_count: int
    sessions: list[SessionRecord]
    products: list[ProductGroupRecord]


class TopProductsResponse(BaseModel):
    products: list[ProductGroupRecord]


class TranscriptSentence(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None


class TranscriptTask(BaseModel):
    id: str
    file_name: str
    file_size: int
    status: str
    provider: str = "dashscope"
    message: str | None = None
    error: str | None = None
    text: str = ""
    summary: str | None = None
    sentences: list[TranscriptSentence] = Field(default_factory=list)
    duration_ms: int | None = None
    dashscope_task_id: str | None = None
    transcription_url: str | None = None
    media_url: str | None = None
    created_at: str
    updated_at: str
