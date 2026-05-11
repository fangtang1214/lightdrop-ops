import { Empty } from "antd";

export function EmptyAnalysisState({ description }: { description: string }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />;
}
