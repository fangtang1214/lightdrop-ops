export function formatFileSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export function formatTranscriptTime(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatDuration(seconds: number) {
  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const rest = totalSeconds % 60;
  return minutes > 0 ? `${minutes}分${rest}秒` : `${rest}秒`;
}

export function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function formatDashboardMetric(value: number | null | undefined, kind: "percent" | "duration" | "count") {
  if (value === null || value === undefined) return "-";
  if (kind === "duration") return formatDuration(value);
  if (kind === "count") return Math.round(value).toLocaleString();
  return formatPercent(value);
}
