const defaultApiBase =
  window.location.protocol === "http:" || window.location.protocol === "https:"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://127.0.0.1:8000";

const API_BASE = import.meta.env.VITE_API_BASE ?? defaultApiBase;
const defaultTimeoutMs = 15000;

import type {
  BadProductRule,
  OverviewResponse,
  RecentReportResponse,
  ScanResponse,
  TaskCreateResponse,
  TaskStatusResponse,
  TopProductsResponse,
  TranscriptTask,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
  }, 300000);

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function fetchWithTimeout(
  url: string,
  init?: RequestInit,
  timeoutMs = defaultTimeoutMs,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("后端服务响应超时，请确认主窗口中的服务状态为已启动");
    }
    throw new Error("无法连接后端服务，请确认主窗口中的服务状态为已启动");
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  scanFolder(rootPath: string) {
    return request<ScanResponse>("/api/folders/scan", {
      method: "POST",
      body: JSON.stringify({ root_path: rootPath }),
    });
  },
  runMatch(hashDistanceThreshold: number, badProductRule: BadProductRule) {
    return request<TaskCreateResponse>("/api/match/run", {
      method: "POST",
      body: JSON.stringify({
        hash_distance_threshold: hashDistanceThreshold,
        bad_product_rule: badProductRule,
      }),
    });
  },
  runLiveData(badProductRule: BadProductRule) {
    return request<TaskCreateResponse>("/api/live-data/run", {
      method: "POST",
      body: JSON.stringify({ bad_product_rule: badProductRule }),
    });
  },
  runGoodProducts() {
    return request<TaskCreateResponse>("/api/good-products/run", {
      method: "POST",
    });
  },
  runConversionDrop() {
    return request<TaskCreateResponse>("/api/conversion-drop/run", {
      method: "POST",
    });
  },
  runDashboardReview(sessionName?: string) {
    return request<TaskCreateResponse>("/api/dashboard/run", {
      method: "POST",
      body: JSON.stringify({ session_name: sessionName ?? null }),
    });
  },
  getTask(taskId: string) {
    return request<TaskStatusResponse>(`/api/tasks/${taskId}`);
  },
  getOverview() {
    return request<OverviewResponse>("/api/reports/overview");
  },
  getRecent(n: number, minCount: number) {
    return request<RecentReportResponse>(`/api/reports/recent?n=${n}&min_count=${minCount}`);
  },
  getTopProducts(limit = 20) {
    return request<TopProductsResponse>(`/api/reports/top-products?limit=${limit}`);
  },
  imageUrl(path: string) {
    return `${API_BASE}/api/images/preview?path=${encodeURIComponent(path)}`;
  },
  listTranscripts() {
    return request<TranscriptTask[]>("/api/transcripts");
  },
  uploadTranscript(file: File) {
    return uploadRequest<TranscriptTask>("/api/transcripts/upload", file);
  },
  getTranscriptTask(taskId: string) {
    return request<TranscriptTask>(`/api/transcripts/${taskId}`);
  },
  retryTranscript(taskId: string) {
    return request<TranscriptTask>(`/api/transcripts/${taskId}/retry`, {
      method: "POST",
    });
  },
  transcriptExportUrl(taskId: string, format: "txt" | "md" | "srt") {
    return `${API_BASE}/api/transcripts/${taskId}/export?format=${format}`;
  },
};
