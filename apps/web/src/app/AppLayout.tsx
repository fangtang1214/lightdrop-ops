import { Button, ConfigProvider, Layout, Space, Typography } from "antd";
import { RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import type { AppView } from "../shared/constants";
import { FeatureNav } from "./FeatureNav";

const { Content, Sider } = Layout;
const { Text, Title } = Typography;

export function AppLayout({
  activeView,
  selectedSessionText,
  canRefresh,
  loading,
  onViewChange,
  onRefresh,
  children,
}: {
  activeView: AppView;
  selectedSessionText: string;
  canRefresh: boolean;
  loading: boolean;
  onViewChange: (view: AppView) => void;
  onRefresh: () => void;
  children: ReactNode;
}) {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#21735b",
          borderRadius: 8,
          borderRadiusLG: 10,
          colorBgContainer: "#ffffff",
          colorBgLayout: "#f0f4f8",
          colorBorderSecondary: "#e8edf2",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)",
          boxShadowSecondary: "0 4px 16px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04)",
        },
      }}
    >
      <Layout className="app-shell">
        <Sider className="app-sider" width={212} breakpoint="lg" collapsedWidth={0}>
          <div className="sider-brand">
            <Title level={4}>轻放助手</Title>
            <Text type="secondary">直播电商运营</Text>
          </div>
          <FeatureNav activeView={activeView} onChange={onViewChange} />
        </Sider>
        <Content className="workspace">
          <header className="page-header" id="overview">
            <div>
              <Title level={2}>轻放直播电商运营助手</Title>
              <Text type="secondary">{selectedSessionText}</Text>
            </div>
            <Space>
              <Button icon={<RefreshCw size={16} />} disabled={!canRefresh} loading={loading} onClick={onRefresh}>
                刷新
              </Button>
            </Space>
          </header>
          {children}
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
