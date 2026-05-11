import { Card, Image, Space, Tag, Tooltip, Typography } from "antd";
import type { ProductGroup } from "../../api";
import { api } from "../../api";
import { EmptyAnalysisState } from "../../shared/components/EmptyAnalysisState";

const { Text } = Typography;

export function ProductGrid({
  range,
  products,
  emptyText,
}: {
  range: number;
  products: ProductGroup[];
  emptyText: string;
}) {
  if (!products.length) {
    return <EmptyAnalysisState description={emptyText} />;
  }

  return (
    <div className="product-grid">
      {products.map((product) => (
        <ProductCard key={product.product_group_id} product={product} range={range} />
      ))}
    </div>
  );
}

function ProductCard({ product, range }: { product: ProductGroup; range: number }) {
  const hasDifferentTotal = product.total_appear_count > product.appear_count;
  const rangeLabel = range < 4 ? `当前${range}场` : `近${range}场`;
  const appearedSessionText = product.appeared_sessions.join("、");

  return (
    <Card className="product-card" bodyStyle={{ padding: 0 }}>
      <Image
        src={api.imageUrl(product.representative_image)}
        alt={product.product_group_id}
        className="product-image"
        fallback=""
      />
      <Tooltip
        title={appearedSessionText}
        placement="topLeft"
        overlayClassName="appeared-sessions-tooltip"
        mouseEnterDelay={0.15}
      >
        <div className="product-body">
          <Space direction="vertical" size={8} className="full-width">
            <Space align="center" className="product-title">
              <Text strong>{product.product_group_id}</Text>
              <Tag color="green">
                {rangeLabel} {product.appear_count} 次
              </Tag>
            </Space>
            {hasDifferentTotal ? (
              <Text type="secondary">全部 {product.total_appear_count} 次</Text>
            ) : null}
            <Text type="secondary" ellipsis>
              {appearedSessionText}
            </Text>
            <Text type="secondary">{product.images.length} 张相似图片</Text>
          </Space>
        </div>
      </Tooltip>
    </Card>
  );
}

export function ProductList({ products }: { products: ProductGroup[] }) {
  if (!products.length) {
    return <EmptyAnalysisState description="等待匹配结果" />;
  }

  return (
    <Space direction="vertical" size={10} className="full-width">
      {products.map((product, index) => (
        <div className="rank-row" key={product.product_group_id}>
          <div className={`rank-badge${index < 3 ? ` rank-badge-${index + 1}` : ""}`}>
            {index + 1}
          </div>
          <img src={api.imageUrl(product.representative_image)} alt="" />
          <div className="rank-copy">
            <Text strong>{product.product_group_id}</Text>
            <Text type="secondary" ellipsis>
              {product.appeared_sessions.join("、")}
            </Text>
          </div>
          <Tag>{product.total_appear_count} 次</Tag>
        </div>
      ))}
    </Space>
  );
}
