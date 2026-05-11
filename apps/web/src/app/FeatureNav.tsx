import { Menu } from "antd";
import { Boxes, FileText, Monitor, Server } from "lucide-react";
import type { AppView } from "../shared/constants";

const items = [
  { key: "products", icon: <Boxes size={16} />, label: "产品分析" },
  { key: "dashboardReview", icon: <Monitor size={16} />, label: "大屏复盘" },
  { key: "transcripts", icon: <FileText size={16} />, label: "视频转文字" },
  { key: "serviceStatus", icon: <Server size={16} />, label: "服务状态" },
];

export function FeatureNav({ activeView, onChange }: { activeView: AppView; onChange: (view: AppView) => void }) {
  return (
    <Menu
      className="feature-nav"
      mode="inline"
      selectedKeys={[activeView]}
      items={items}
      onClick={({ key }) => onChange(key as AppView)}
    />
  );
}
