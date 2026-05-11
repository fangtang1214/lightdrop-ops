import { Card, Col, Empty, Row, Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { OverviewResponse, ProductGroup, SessionRecord } from "../../api";
import type { ReportMap } from "../../shared/constants";
import { ProductGrid, ProductList } from "./ProductCards";

const sessionColumns: ColumnsType<SessionRecord> = [
  {
    title: "场次",
    dataIndex: "session_index",
    width: 80,
    render: (value) => `第 ${value} 场`,
  },
  { title: "文件夹", dataIndex: "name" },
  { title: "图片数", dataIndex: "image_count", width: 100 },
];

const statsColumns: ColumnsType<Record<string, number | string>> = [
  { title: "场次", dataIndex: "session_name" },
  { title: "图片数", dataIndex: "image_count", width: 100 },
  { title: "商品组", dataIndex: "product_count", width: 100 },
  { title: "重复差品", dataIndex: "repeated_product_count", width: 110 },
  { title: "新增差品", dataIndex: "new_product_count", width: 110 },
  {
    title: "重复率",
    dataIndex: "duplicate_rate",
    width: 100,
    render: (value: number) => `${Math.round(value * 100)}%`,
  },
];

export function BadProductPage({
  visibleReportRanges,
  reports,
  overview,
  topProducts,
  sessions,
}: {
  visibleReportRanges: number[];
  reports: ReportMap;
  overview: OverviewResponse | null;
  topProducts: ProductGroup[];
  sessions: SessionRecord[];
}) {
  return (
    <>
      <Row gutter={[16, 16]} className="main-grid" id="reports">
        <Col xs={24} xl={15}>
          <Card title="最近场次重复差品" className="section-card">
            {visibleReportRanges.length ? (
              <Tabs
                items={visibleReportRanges.map((range) => ({
                  key: String(range),
                  label: range < 4 ? `当前 ${range} 场` : `最近 ${range} 场`,
                  children: (
                    <ProductGrid
                      range={range}
                      products={reports[range]?.products ?? []}
                      emptyText={overview ? "没有符合条件的重复差品" : "等待匹配结果"}
                    />
                  ),
                }))}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={overview ? "场次不足，至少 2 场才有重复判断价值" : "等待匹配结果"}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card title="高频差品排行榜" className="section-card">
            <ProductList products={topProducts} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={11}>
          <Card title="直播场次" className="section-card">
            <Table size="small" rowKey="id" columns={sessionColumns} dataSource={sessions} pagination={{ pageSize: 8 }} />
          </Card>
        </Col>
        <Col xs={24} xl={13}>
          <Card title="场次复盘" className="section-card">
            <Table
              size="small"
              rowKey="session_id"
              columns={statsColumns}
              dataSource={overview?.session_stats ?? []}
              pagination={{ pageSize: 8 }}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
