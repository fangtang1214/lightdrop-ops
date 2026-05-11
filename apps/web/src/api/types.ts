export type BadProductRule = "bottom_20" | "zero_conversion";

export interface SessionRecord {
  id: number;
  name: string;
  folder_path: string;
  session_index: number;
  image_count: number;
}

export interface ImageRecord {
  image_id: string;
  file_name: string;
  file_path: string;
  session_id: number;
  session_name: string;
  session_index: number;
  width?: number;
  height?: number;
  file_size: number;
  image_hash?: string;
}

export interface ProductGroup {
  id: number;
  product_group_id: string;
  representative_image: string;
  images: ImageRecord[];
  appeared_sessions: string[];
  appeared_session_ids: number[];
  appear_count: number;
  total_appear_count: number;
}

export interface ScanResponse {
  root_path: string;
  sessions: SessionRecord[];
  images: ImageRecord[];
  skipped_files: string[];
  table_process?: TableProcessSummary | null;
  live_dashboard?: LiveDashboardSummary | null;
}

export interface TableProcessSummary {
  enabled: boolean;
  data_tables_dir?: string | null;
  all_images_dir?: string | null;
  bad_images_dir?: string | null;
  bad_product_rule: BadProductRule;
  processed_sessions: TableProcessSession[];
  good_rankings: GoodProductRanking[];
  conversion_drop_rankings: ConversionDropRanking[];
  source_signature?: string | null;
  message?: string | null;
}

export interface TableProcessSession {
  table_file: string;
  session_name: string;
  total_products: number;
  selected_bad_products: number;
  matched_products: number;
  copied_images: number;
  unmatched_product_ids: string[];
  ranked_products: LiveProductRankRecord[];
}

export interface LiveProductRankRecord {
  product_id: string;
  title: string;
  representative_image?: string | null;
  matched_images: string[];
  rank: number;
  rank_from_bottom: number;
  is_bad_product: boolean;
  exposure_click_rate: number;
  click_conversion_rate: number;
  refund_rate: number;
  net_conversion_score: number;
  exposure_people: number;
  click_people: number;
  deal_people: number;
  deal_orders: number;
  refund_orders: number;
}

export interface GoodProductRanking {
  range_size: number;
  session_names: string[];
  products: GoodProductRankRecord[];
}

export interface GoodProductRankRecord {
  product_id: string;
  title: string;
  representative_image?: string | null;
  matched_images: string[];
  rank: number;
  exposure_click_rate: number;
  click_conversion_rate: number;
  refund_rate: number;
  net_conversion_score: number;
  exposure_people: number;
  click_people: number;
  deal_people: number;
  deal_orders: number;
  refund_orders: number;
  source_session_count: number;
  source_sessions: string[];
  source_product_ids: string[];
  latest_session_name: string;
}

export interface ConversionDropRanking {
  session_name: string;
  products: ConversionDropRankRecord[];
}

export interface ConversionDropRankRecord {
  product_id: string;
  title: string;
  representative_image?: string | null;
  matched_images: string[];
  rank: number;
  current_session_name: string;
  history_session_name: string;
  history_product_id: string;
  history_title: string;
  current_rank: number;
  history_rank: number;
  current_net_conversion_score: number;
  history_net_conversion_score: number;
  net_conversion_drop: number;
  drop_ratio: number;
  current_click_conversion_rate: number;
  history_click_conversion_rate: number;
  click_conversion_rate_drop: number;
  current_exposure_click_rate: number;
  history_exposure_click_rate: number;
  current_exposure_people: number;
  history_exposure_people: number;
  current_click_people: number;
  history_click_people: number;
  current_deal_people: number;
  history_deal_people: number;
  source_product_ids: string[];
}

export interface LiveDashboardMetrics {
  like_rate?: number | null;
  comment_rate?: number | null;
  avg_watch_seconds?: number | null;
  effective_enter_rate?: number | null;
  deal_conversion_rate?: number | null;
  new_customer_conversion_rate?: number | null;
  live_recommend_total?: number | null;
  live_recommend_delta?: number | null;
}

export interface LiveDashboardPoint {
  index: number;
  minute_offset: number;
  file_name: string;
  file_path: string;
  captured_at?: string | null;
  time_label: string;
  metrics: LiveDashboardMetrics;
  confidence?: number | null;
  raw_values: Record<string, string>;
  missing_metrics: string[];
}

export interface LiveDashboardSession {
  session_name: string;
  folder_path: string;
  screenshot_count: number;
  start_time?: string | null;
  end_time?: string | null;
  averages: LiveDashboardMetrics;
  points: LiveDashboardPoint[];
}

export interface LiveDashboardSummary {
  enabled: boolean;
  dashboard_root?: string | null;
  processed_sessions: LiveDashboardSession[];
  message?: string | null;
}

export interface MatchResponse {
  status: string;
  total_images: number;
  product_groups: number;
  duplicate_groups: number;
  groups: ProductGroup[];
}

export interface TaskCreateResponse {
  task_id: string;
}

export interface TaskStatusResponse {
  id: string;
  name: string;
  status: "queued" | "running" | "completed" | "done" | "failed";
  progress: number;
  message: string;
  result_kind?: "scan" | "match" | string | null;
  result?: unknown;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OverviewResponse {
  total_sessions: number;
  total_images: number;
  product_groups: number;
  duplicate_groups: number;
  recent_duplicate_counts: Record<string, number>;
  top_product: ProductGroup | null;
  session_stats: Array<Record<string, number | string>>;
}

export interface RecentReportResponse {
  range: number;
  min_count: number;
  sessions: SessionRecord[];
  products: ProductGroup[];
}

export interface TopProductsResponse {
  products: ProductGroup[];
}

export interface TranscriptSentence {
  index: number;
  start_ms: number;
  end_ms: number;
  text: string;
  speaker?: string | null;
}

export interface TranscriptTask {
  id: string;
  file_name: string;
  file_size: number;
  status: string;
  provider: string;
  message?: string | null;
  error?: string | null;
  text: string;
  summary?: string | null;
  sentences: TranscriptSentence[];
  duration_ms?: number | null;
  dashscope_task_id?: string | null;
  transcription_url?: string | null;
  media_url?: string | null;
  created_at: string;
  updated_at: string;
}
