import { Card, Col, Row, Statistic } from "antd";
import type { OverviewResponse } from "../../api";
import { plannedReportRanges } from "../constants";

const metricColors = [
  "#21735b",
  "#315cbe",
  "#9a4d1f",
  "#c45a73",
  "#7a4bb2",
  "#6a7d19",
  "#d88912",
];

export function OverviewMetrics({
  overview,
  sessionCount,
}: {
  overview: OverviewResponse | null;
  sessionCount: number;
}) {
  const cards: Array<[string, number]> = [
    ["总场次", overview?.total_sessions ?? 0],
    ["总图片", overview?.total_images ?? 0],
    ["商品组", overview?.product_groups ?? 0],
    ["重复差品", overview?.duplicate_groups ?? 0],
  ];

  if (overview && sessionCount > 0 && sessionCount < 4) {
    cards.push([`当前${sessionCount}场重复`, overview.duplicate_groups]);
  } else {
    for (const range of plannedReportRanges) {
      if (sessionCount >= range) {
        cards.push([`近${range}场重复`, overview?.recent_duplicate_counts[String(range)] ?? 0]);
      }
    }
  }

  return (
    <Row gutter={[16, 16]} className="metric-row">
      {cards.map(([label, value], index) => (
        <Col xs={12} md={8} xl={4} key={label}>
          <Card
            className="metric-card"
            style={{ "--metric-color": metricColors[index % metricColors.length] } as React.CSSProperties}
          >
            <Statistic title={label} value={value} />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
