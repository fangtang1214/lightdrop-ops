import { Card, Image, Select, Space, Table, Tabs, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { GoodProductRankRecord, LiveProductRankRecord, TableProcessSession } from "../../api";
import { api } from "../../api";
import { AnalysisAction } from "../../shared/components/AnalysisAction";
import { EmptyAnalysisState } from "../../shared/components/EmptyAnalysisState";
import { formatPercent } from "../../shared/formatters";

const { Text } = Typography;

type GoodProductTableRecord = LiveProductRankRecord | GoodProductRankRecord;

export function GoodProductAnalysis({
  sessions,
  goodRankings,
  selectedSessionName,
  onSelectSession,
  onAnalyze,
  loading,
  disabled,
}: {
  sessions: TableProcessSession[];
  goodRankings: Array<{
    range_size: number;
    session_names: string[];
    products: GoodProductRankRecord[];
  }>;
  selectedSessionName: string | null;
  onSelectSession: (sessionName: string) => void;
  onAnalyze: () => void;
  loading: boolean;
  disabled: boolean;
}) {
  const selectedSession =
    sessions.find((session) => session.session_name === selectedSessionName) ?? sessions[sessions.length - 1];

  const columns: ColumnsType<GoodProductTableRecord> = [
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
      width: 320,
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
      title: "综合评分",
      dataIndex: "net_conversion_score",
      width: 120,
      render: (value: number) => value.toFixed(6),
      sorter: (a, b) => a.net_conversion_score - b.net_conversion_score,
    },
    {
      title: "来源",
      width: 130,
      render: (_, record) =>
        "source_session_count" in record ? (
          <Tooltip title={record.source_sessions.join("、")}>
            <Tag color="green">{record.source_session_count} 场</Tag>
          </Tooltip>
        ) : (
          <Tag>单场</Tag>
        ),
    },
    {
      title: "最新场次",
      width: 160,
      ellipsis: true,
      render: (_, record) =>
        "latest_session_name" in record ? record.latest_session_name : selectedSession?.session_name,
    },
    {
      title: "来源ID",
      width: 120,
      render: (_, record) =>
        "source_product_ids" in record ? (
          <Tooltip title={record.source_product_ids.join("、")}>
            <Text>{record.source_product_ids.length} 个</Text>
          </Tooltip>
        ) : (
          <Text>1 个</Text>
        ),
    },
  ];

  function renderGoodTable(products: GoodProductTableRecord[], emptyText: string) {
    if (!products.length) {
      return <EmptyAnalysisState description={emptyText} />;
    }

    return (
      <Table
        size="small"
        rowKey={(record) => `${record.rank}-${record.product_id}`}
        columns={columns}
        dataSource={products}
        scroll={{ x: 1780 }}
        pagination={{ pageSize: 20, showSizeChanger: true }}
      />
    );
  }

  return (
    <Card
      className="section-card"
      title="优品分析"
      extra={
        <Space>
          <Select
            className="session-select"
            placeholder="选择单场"
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
      <Tabs
        items={[
          {
            key: "single",
            label: "单场转化排行",
            children: renderGoodTable(
              selectedSession?.ranked_products ?? [],
              "扫描后可查看单场转化排行",
            ),
          },
          ...[4, 10].map((range) => {
            const ranking = goodRankings.find((item) => item.range_size === range);
            return {
              key: String(range),
              label: `${range}场合并排行`,
              children: (
                <Space direction="vertical" size={12} className="full-width">
                  {ranking?.session_names.length ? (
                    <Text type="secondary">
                      合并场次：{ranking.session_names.join("、")}
                    </Text>
                  ) : null}
                  {renderGoodTable(
                    ranking?.products ?? [],
                    sessions.length >= range
                      ? "暂无可合并的优品数据"
                      : `当前只有 ${sessions.length} 场，满 ${range} 场后生成合并排行`,
                  )}
                </Space>
              ),
            };
          }),
        ]}
      />
    </Card>
  );
}
