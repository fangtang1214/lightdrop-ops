import { Button, Card, Checkbox, Col, Image, Row, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Layers } from "lucide-react";
import type { MouseEvent } from "react";
import { useMemo, useState } from "react";
import type { LiveDashboardPoint, LiveDashboardSession } from "../../api";
import { api } from "../../api";
import { AnalysisAction } from "../../shared/components/AnalysisAction";
import { EmptyAnalysisState } from "../../shared/components/EmptyAnalysisState";
import { formatDashboardMetric, formatDateTime } from "../../shared/formatters";

const { Text } = Typography;

type DashboardMetricKey = keyof LiveDashboardPoint["metrics"];

const dashboardMetricConfigs: Array<{
  key: DashboardMetricKey;
  label: string;
  color: string;
  kind: "percent" | "duration" | "count" | "amount";
}> = [
  { key: "live_recommend_delta", label: "直播推荐增量", color: "#d88912", kind: "count" },
  { key: "live_recommend_total", label: "直播推荐总量", color: "#8a6333", kind: "count" },
  { key: "deal_amount_total", label: "成交金额总量", color: "#2f7d63", kind: "amount" },
  { key: "deal_amount_delta", label: "成交金额增量", color: "#6f9f3a", kind: "amount" },
  { key: "deal_order_total", label: "成交订单数总量", color: "#335c81", kind: "count" },
  { key: "deal_order_delta", label: "成交订单数增量", color: "#5a86ad", kind: "count" },
  { key: "deal_user_total", label: "成交人数总量", color: "#7f4f24", kind: "count" },
  { key: "deal_user_delta", label: "成交人数增量", color: "#b16a2c", kind: "count" },
  { key: "online_user_count", label: "实时在线人数", color: "#4b6f44", kind: "count" },
  { key: "online_user_delta", label: "实时在线人数增量", color: "#85a35c", kind: "count" },
  { key: "effective_enter_rate", label: "直播有效进房率", color: "#7a4bb2", kind: "percent" },
  { key: "avg_watch_seconds", label: "人均观看时长", color: "#315cbe", kind: "duration" },
  { key: "comment_rate", label: "评论率", color: "#9a4d1f", kind: "percent" },
  { key: "like_rate", label: "点赞率", color: "#21735b", kind: "percent" },
  { key: "thousand_watch_deal_amount", label: "千次观看成交金额", color: "#a05a8b", kind: "amount" },
  { key: "deal_conversion_rate", label: "成交转化率", color: "#c45a73", kind: "percent" },
  { key: "new_customer_conversion_rate", label: "新客转化率", color: "#6a7d19", kind: "percent" },
];

export function LiveDashboardReview({
  sessions,
  selectedSession,
  onSelectSession,
  onAnalyze,
  onAnalyzeAll,
  loading,
  disabled,
}: {
  sessions: LiveDashboardSession[];
  selectedSession: LiveDashboardSession | null;
  onSelectSession: (sessionName: string) => void;
  onAnalyze: () => void;
  onAnalyzeAll: () => void;
  loading: boolean;
  disabled: boolean;
}) {
  const [selectedMetricKeys, setSelectedMetricKeys] = useState<DashboardMetricKey[]>([
    "live_recommend_delta",
  ]);
  const selectedMetrics = useMemo(
    () =>
      dashboardMetricConfigs.filter((metric) =>
        selectedMetricKeys.includes(metric.key),
      ),
    [selectedMetricKeys],
  );
  const hasAnalysis = Boolean(selectedSession?.points.length);

  const columns: ColumnsType<LiveDashboardPoint> = [
    {
      title: "分钟",
      dataIndex: "minute_offset",
      width: 78,
      fixed: "left",
      render: (value: number) => `+${value}`,
    },
    {
      title: "截图",
      dataIndex: "file_path",
      width: 88,
      fixed: "left",
      render: (value: string, record) => (
        <Image
          src={api.imageUrl(value)}
          alt={record.file_name}
          width={56}
          height={56}
          className="table-product-image"
          preview={{ src: api.imageUrl(value) }}
        />
      ),
    },
    {
      title: "时间",
      dataIndex: "time_label",
      width: 90,
      fixed: "left",
    },
    ...dashboardMetricConfigs.map((metric) => ({
      title: metric.label,
      width: metric.kind === "duration" || metric.kind === "amount" ? 140 : 120,
      render: (_: unknown, record: LiveDashboardPoint) =>
        formatDashboardMetric(record.metrics[metric.key], metric.kind),
      sorter: (a: LiveDashboardPoint, b: LiveDashboardPoint) =>
        (a.metrics[metric.key] ?? -1) - (b.metrics[metric.key] ?? -1),
    })),
    {
      title: "识别状态",
      width: 170,
      render: (_: unknown, record) =>
        record.missing_metrics.length ? (
          <Tooltip title={record.missing_metrics.join("、")}>
            <Tag color="gold">缺 {record.missing_metrics.length} 项</Tag>
          </Tooltip>
        ) : (
          <Tag color="green">完整</Tag>
        ),
    },
  ];

  return (
    <Card
      className="section-card"
      title="大屏复盘"
      extra={
        <Space>
          <Select
            className="session-select"
            placeholder="选择大屏截图场次"
            value={selectedSession?.session_name}
            onChange={onSelectSession}
            options={sessions.map((session) => ({
              label: `${session.session_name} (${session.screenshot_count} 张)`,
              value: session.session_name,
            }))}
          />
          <Button icon={<Layers size={16} />} loading={loading} disabled={disabled} onClick={onAnalyzeAll}>
            一键分析所有场次
          </Button>
          <AnalysisAction loading={loading} disabled={disabled} onAnalyze={onAnalyze} />
        </Space>
      }
    >
      {selectedSession ? (
        <Space direction="vertical" size={16} className="full-width">
          <Space wrap>
            <Tag>截图 {selectedSession.screenshot_count} 张</Tag>
            <Tag>间隔 1 分钟</Tag>
            {selectedSession.start_time ? <Tag>{formatDateTime(selectedSession.start_time)}</Tag> : null}
            {selectedSession.end_time ? <Tag>{formatDateTime(selectedSession.end_time)}</Tag> : null}
          </Space>
          {hasAnalysis ? (
            <>
              <Row gutter={[12, 12]}>
                {dashboardMetricConfigs.map((metric) => (
                  <Col xs={12} md={8} xl={4} key={metric.key}>
                    <div className="dashboard-average">
                      <Text type="secondary">{metric.label}均值</Text>
                      <Text strong>
                        {formatDashboardMetric(selectedSession.averages[metric.key], metric.kind)}
                      </Text>
                    </div>
                  </Col>
                ))}
              </Row>
              <Space direction="vertical" size={8} className="chart-toolbar">
                <Text type="secondary">曲线指标</Text>
                <Checkbox.Group
                  value={selectedMetricKeys}
                  onChange={(values) =>
                    setSelectedMetricKeys(
                      (values.length ? values : ["live_recommend_delta"]) as DashboardMetricKey[],
                    )
                  }
                  options={dashboardMetricConfigs.map((metric) => ({
                    label: metric.label,
                    value: metric.key,
                  }))}
                />
              </Space>
              <DashboardMetricChart points={selectedSession.points} metrics={selectedMetrics} />
              <Table
                size="small"
                rowKey="file_path"
                columns={columns}
                dataSource={selectedSession.points}
                scroll={{ x: 2260 }}
                pagination={{ pageSize: 20, showSizeChanger: true }}
              />
            </>
          ) : (
            <EmptyAnalysisState description="已发现该场次截图，点击开始分析后生成 OCR 数据与曲线" />
          )}
        </Space>
      ) : (
        <EmptyAnalysisState description="扫描后可查看直播大屏截图复盘" />
      )}
    </Card>
  );
}

function DashboardMetricChart({
  points,
  metrics,
}: {
  points: LiveDashboardPoint[];
  metrics: Array<(typeof dashboardMetricConfigs)[number]>;
}) {
  const [hoverMinute, setHoverMinute] = useState<number | null>(null);
  const width = 920;
  const height = 300;
  const padding = { top: 18, right: 18, bottom: 34, left: 46 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const rawMetricSeries = metrics.map((metric) => ({
    ...metric,
    values: points
      .map((point) => ({
        x: point.minute_offset,
        value: point.metrics[metric.key],
      }))
      .filter((item): item is { x: number; value: number } => item.value !== null && item.value !== undefined),
  }));
  const metricSeries = rawMetricSeries.map((series) => ({
    ...series,
    maxValue: Math.max(...series.values.map((item) => item.value), 0) || 1,
  }));
  const maxX = Math.max(...points.map((point) => point.minute_offset), 1);
  const isRelativeScale = metricSeries.length > 1;
  const singleAxisKind = metricSeries[0]?.kind ?? "count";
  const singleMaxValue = metricSeries[0]?.maxValue ?? 1;
  const hoveredPoint =
    hoverMinute === null
      ? null
      : points.reduce((closest, point) => {
          if (!closest) return point;
          return Math.abs(point.minute_offset - hoverMinute) <
            Math.abs(closest.minute_offset - hoverMinute)
            ? point
            : closest;
        }, null as LiveDashboardPoint | null);

  function xScale(value: number) {
    return padding.left + (value / maxX) * chartWidth;
  }

  function yScale(value: number, maxValue = singleMaxValue) {
    const displayValue = isRelativeScale ? value / maxValue : value / singleMaxValue;
    return padding.top + chartHeight - displayValue * chartHeight;
  }

  function formatAxisTick(tick: number) {
    if (isRelativeScale) {
      return `${Math.round(tick * 100)}%`;
    }
    return formatDashboardMetric(tick * singleMaxValue, singleAxisKind);
  }

  function updateHover(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * width;
    const clampedX = Math.max(padding.left, Math.min(width - padding.right, x));
    setHoverMinute(Math.round(((clampedX - padding.left) / chartWidth) * maxX));
  }

  return (
    <div className="dashboard-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="大屏指标曲线"
        onMouseMove={updateHover}
        onMouseLeave={() => setHoverMinute(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = padding.top + chartHeight - tick * chartHeight;
          return (
            <g key={tick}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="chart-grid" />
              <text x={12} y={y + 4} className="chart-axis">
                {formatAxisTick(tick)}
              </text>
            </g>
          );
        })}
        <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} className="chart-axis-line" />
        {metricSeries.map((series) => (
          <polyline
            key={series.key}
            fill="none"
            stroke={series.color}
            strokeWidth={2.4}
            points={series.values
              .map((item) => `${xScale(item.x)},${yScale(item.value, series.maxValue)}`)
              .join(" ")}
          />
        ))}
        {hoveredPoint ? (
          <g>
            <line
              x1={xScale(hoveredPoint.minute_offset)}
              x2={xScale(hoveredPoint.minute_offset)}
              y1={padding.top}
              y2={height - padding.bottom}
              className="chart-hover-line"
            />
            {metricSeries.map((series) => {
              const value = hoveredPoint.metrics[series.key];
              if (value === null || value === undefined) return null;
              return (
                <circle
                  key={series.key}
                  cx={xScale(hoveredPoint.minute_offset)}
                  cy={yScale(value, series.maxValue)}
                  r={4}
                  fill={series.color}
                  stroke="#fff"
                  strokeWidth={1.5}
                />
              );
            })}
          </g>
        ) : null}
        {points.length ? (
          <>
            <text x={padding.left} y={height - 10} className="chart-axis">+0</text>
            <text x={width - padding.right - 34} y={height - 10} className="chart-axis">+{maxX}</text>
          </>
        ) : null}
      </svg>
      {hoveredPoint ? (
        <div className="chart-tooltip">
          <Text strong>{hoveredPoint.time_label}</Text>
          {metricSeries.map((series) => {
            const value = hoveredPoint.metrics[series.key];
            if (value === null || value === undefined) return null;
            return (
              <span key={series.key}>
                <i style={{ background: series.color }} />
                {series.label}: {formatDashboardMetric(value, series.kind)}
              </span>
            );
          })}
        </div>
      ) : null}
      <div className="dashboard-legend">
        {metricSeries.map((series) => (
          <span key={series.key}>
            <i style={{ background: series.color }} />
            {series.label}
          </span>
        ))}
      </div>
    </div>
  );
}
