import { Card, Image, Select, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { BadProductRule, LiveProductRankRecord, TableProcessSession } from "../../api";
import { api } from "../../api";
import { AnalysisAction } from "../../shared/components/AnalysisAction";
import { EmptyAnalysisState } from "../../shared/components/EmptyAnalysisState";
import { getBadProductRuleLabel } from "../../shared/constants";
import { formatPercent } from "../../shared/formatters";

export function LiveDataRanking({
  sessions,
  selectedSessionName,
  onSelectSession,
  onAnalyze,
  loading,
  disabled,
  badProductRule,
}: {
  sessions: TableProcessSession[];
  selectedSessionName: string | null;
  onSelectSession: (sessionName: string) => void;
  onAnalyze: () => void;
  loading: boolean;
  disabled: boolean;
  badProductRule: BadProductRule;
}) {
  const selectedSession =
    sessions.find((session) => session.session_name === selectedSessionName) ?? sessions[0];

  const columns: ColumnsType<LiveProductRankRecord> = [
    {
      title: "排名",
      dataIndex: "rank",
      width: 76,
      fixed: "left",
    },
    {
      title: "图片",
      dataIndex: "representative_image",
      width: 88,
      fixed: "left",
      render: (value: string | null | undefined, record) =>
        value ? (
          <Image
            src={api.imageUrl(value)}
            alt={record.product_id}
            width={56}
            height={56}
            className="table-product-image"
            preview={{
              src: api.imageUrl(value),
            }}
          />
        ) : (
          <div className="image-placeholder">无图</div>
        ),
    },
    {
      title: "商品ID",
      dataIndex: "product_id",
      width: 150,
      fixed: "left",
    },
    {
      title: "商品标题",
      dataIndex: "title",
      width: 340,
      ellipsis: true,
    },
    {
      title: "转化率",
      dataIndex: "click_conversion_rate",
      width: 120,
      render: formatPercent,
      sorter: (a, b) => a.click_conversion_rate - b.click_conversion_rate,
      defaultSortOrder: "descend",
    },
    {
      title: "成交人数",
      dataIndex: "deal_people",
      width: 100,
      sorter: (a, b) => a.deal_people - b.deal_people,
    },
    {
      title: "成交订单",
      dataIndex: "deal_orders",
      width: 100,
      sorter: (a, b) => a.deal_orders - b.deal_orders,
    },
    {
      title: "点击人数",
      dataIndex: "click_people",
      width: 100,
      sorter: (a, b) => a.click_people - b.click_people,
    },
    {
      title: "曝光人数",
      dataIndex: "exposure_people",
      width: 100,
      sorter: (a, b) => a.exposure_people - b.exposure_people,
    },
    {
      title: "曝光点击率",
      dataIndex: "exposure_click_rate",
      width: 120,
      render: formatPercent,
      sorter: (a, b) => a.exposure_click_rate - b.exposure_click_rate,
    },
    {
      title: "退款率",
      dataIndex: "refund_rate",
      width: 100,
      render: formatPercent,
      sorter: (a, b) => a.refund_rate - b.refund_rate,
    },
    {
      title: "退款订单",
      dataIndex: "refund_orders",
      width: 100,
      sorter: (a, b) => a.refund_orders - b.refund_orders,
    },
    {
      title: "综合评分",
      dataIndex: "net_conversion_score",
      width: 120,
      render: (value: number) => value.toFixed(6),
      sorter: (a, b) => a.net_conversion_score - b.net_conversion_score,
    },
    {
      title: "标记",
      dataIndex: "is_bad_product",
      width: 90,
      fixed: "right",
      render: (value: boolean) => (value ? <Tag color="red">差品</Tag> : null),
      filters: [
        { text: "差品", value: true },
        { text: "非差品", value: false },
      ],
      onFilter: (value, record) => record.is_bad_product === value,
    },
  ];

  return (
    <Card
      className="section-card"
      title="直播详细数据"
      extra={
        <Space>
          <Select
            className="session-select"
            placeholder="选择直播场次"
            value={selectedSession?.session_name}
            onChange={onSelectSession}
            options={sessions.map((session) => ({
              label: session.session_name,
              value: session.session_name,
            }))}
          />
          <AnalysisAction loading={loading} disabled={disabled} onAnalyze={onAnalyze} />
        </Space>
      }
    >
      {selectedSession ? (
        <Space direction="vertical" size={14} className="full-width">
          <Space wrap>
            <Tag>共 {selectedSession.total_products} 个商品</Tag>
            <Tag color="red">
              {getBadProductRuleLabel(badProductRule)}定义差品：{selectedSession.selected_bad_products} 个
            </Tag>
            <Tag>匹配图片 {selectedSession.matched_products} 个商品</Tag>
          </Space>
          <Table
            size="small"
            rowKey="product_id"
            columns={columns}
            dataSource={selectedSession.ranked_products}
            scroll={{ x: 1780 }}
            pagination={{ pageSize: 20, showSizeChanger: true }}
          />
        </Space>
      ) : (
        <EmptyAnalysisState description="扫描后可查看每场直播的完整排名" />
      )}
    </Card>
  );
}
