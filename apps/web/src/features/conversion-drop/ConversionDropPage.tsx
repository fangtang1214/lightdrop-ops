import { Card, Empty, Image, Select, Space, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ConversionDropRankRecord, TableProcessSession } from "../../api";
import { api } from "../../api";
import { AnalysisAction } from "../../shared/components/AnalysisAction";
import { EmptyAnalysisState } from "../../shared/components/EmptyAnalysisState";
import { formatPercent } from "../../shared/formatters";

export function ConversionDropAnalysis({
  sessions,
  dropRankings,
  selectedSessionName,
  onSelectSession,
  onAnalyze,
  loading,
  disabled,
}: {
  sessions: TableProcessSession[];
  dropRankings: Array<{
    session_name: string;
    products: ConversionDropRankRecord[];
  }>;
  selectedSessionName: string | null;
  onSelectSession: (sessionName: string) => void;
  onAnalyze: () => void;
  loading: boolean;
  disabled: boolean;
}) {
  const selectedSession =
    sessions.find((session) => session.session_name === selectedSessionName) ?? sessions[sessions.length - 1];
  const selectedRanking = dropRankings.find(
    (ranking) => ranking.session_name === selectedSession?.session_name,
  );
  const products = selectedRanking?.products ?? [];

  const columns: ColumnsType<ConversionDropRankRecord> = [
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
      width: 300,
      ellipsis: true,
    },
    {
      title: "落差比例",
      dataIndex: "drop_ratio",
      width: 110,
      render: formatPercent,
      sorter: (a, b) => a.drop_ratio - b.drop_ratio,
      defaultSortOrder: "descend",
    },
    {
      title: "历史最佳场次",
      dataIndex: "history_session_name",
      width: 170,
      ellipsis: true,
    },
    {
      title: "历史转化率",
      dataIndex: "history_click_conversion_rate",
      width: 130,
      render: formatPercent,
      sorter: (a, b) => a.history_click_conversion_rate - b.history_click_conversion_rate,
    },
    {
      title: "本场转化率",
      dataIndex: "current_click_conversion_rate",
      width: 130,
      render: formatPercent,
      sorter: (a, b) => a.current_click_conversion_rate - b.current_click_conversion_rate,
    },
    {
      title: "历史曝光点击",
      dataIndex: "history_exposure_click_rate",
      width: 130,
      render: formatPercent,
      sorter: (a, b) => a.history_exposure_click_rate - b.history_exposure_click_rate,
    },
    {
      title: "本场曝光点击",
      dataIndex: "current_exposure_click_rate",
      width: 130,
      render: formatPercent,
      sorter: (a, b) => a.current_exposure_click_rate - b.current_exposure_click_rate,
    },
    {
      title: "综合评分落差",
      dataIndex: "net_conversion_drop",
      width: 130,
      render: (value: number) => value.toFixed(6),
      sorter: (a, b) => a.net_conversion_drop - b.net_conversion_drop,
    },
    {
      title: "历史综合评分",
      dataIndex: "history_net_conversion_score",
      width: 130,
      render: (value: number) => value.toFixed(6),
      sorter: (a, b) => a.history_net_conversion_score - b.history_net_conversion_score,
    },
    {
      title: "本场综合评分",
      dataIndex: "current_net_conversion_score",
      width: 130,
      render: (value: number) => value.toFixed(6),
      sorter: (a, b) => a.current_net_conversion_score - b.current_net_conversion_score,
    },
    {
      title: "历史商品ID",
      dataIndex: "history_product_id",
      width: 150,
    },
    {
      title: "历史排名",
      dataIndex: "history_rank",
      width: 90,
      sorter: (a, b) => a.history_rank - b.history_rank,
    },
    {
      title: "本场排名",
      dataIndex: "current_rank",
      width: 90,
      sorter: (a, b) => a.current_rank - b.current_rank,
    },
    {
      title: "成交人数",
      width: 120,
      render: (_, record) => `${record.history_deal_people} -> ${record.current_deal_people}`,
    },
    {
      title: "曝光人数",
      width: 120,
      render: (_, record) => `${record.history_exposure_people} -> ${record.current_exposure_people}`,
    },
    {
      title: "同款ID",
      width: 110,
      fixed: "right",
      render: (_, record) => (
        <Tooltip title={record.source_product_ids.join("、")}>
          <Tag color="gold">{record.source_product_ids.length} 个</Tag>
        </Tooltip>
      ),
    },
  ];

  return (
    <Card
      className="section-card"
      title="转化落差品排行"
      extra={
        <Space>
          <Select
            className="session-select"
            placeholder="选择对比场次"
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
            <Tag>本场：{selectedSession.session_name}</Tag>
            <Tag>历史范围：之前 {Math.max(sessions.indexOf(selectedSession), 0)} 场</Tag>
            <Tag color="gold">落差款 {products.length} 个</Tag>
          </Space>
          {products.length ? (
            <Table
              size="small"
              rowKey={(record) => `${record.rank}-${record.product_id}-${record.history_product_id}`}
              columns={columns}
              dataSource={products}
              scroll={{ x: 2250 }}
              pagination={{ pageSize: 20, showSizeChanger: true }}
            />
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                sessions.indexOf(selectedSession) > 0
                  ? "没有找到历史表现更好的同款"
                  : "第一场没有历史场次可对比"
              }
            />
          )}
        </Space>
      ) : (
        <EmptyAnalysisState description="扫描后可查看转化落差排行" />
      )}
    </Card>
  );
}
