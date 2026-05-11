import { Alert, Button, Card, Col, Row, Space, Tag, Typography, message } from "antd";
import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const { Text } = Typography;

function statusTag(ready: boolean, starting: boolean) {
  if (ready) {
    return <Tag color="green">已启动</Tag>;
  }
  if (starting) {
    return <Tag color="blue">启动中</Tag>;
  }
  return <Tag color="gold">未就绪</Tag>;
}

function ServiceCard({
  title,
  ready,
  starting,
  localUrl,
  lanUrl,
}: {
  title: string;
  ready: boolean;
  starting: boolean;
  localUrl: string;
  lanUrl: string | null;
}) {
  return (
    <Card className="section-card service-card" title={title} extra={statusTag(ready, starting)}>
      <Space direction="vertical" size={8} className="full-width">
        <div className="service-url-row">
          <Text type="secondary">本机</Text>
          <Text copyable>{localUrl}</Text>
        </div>
        <div className="service-url-row">
          <Text type="secondary">局域网</Text>
          {lanUrl ? <Text copyable>{lanUrl}</Text> : <Text type="secondary">未检测到可用网卡</Text>}
        </div>
      </Space>
    </Card>
  );
}

export function ServiceStatusPage() {
  const bridge = window.lightdrop;
  const [status, setStatus] = useState<LightDropServiceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [openingLocal, setOpeningLocal] = useState(false);
  const [openingLan, setOpeningLan] = useState(false);

  const backendStarting = Boolean(status?.servicesStarting || status?.startedBackend);
  const webStarting = Boolean(status?.servicesStarting || status?.startedWeb);
  const canOpenLocal = Boolean(status?.backendReady && status?.webReady);
  const canOpenLan = Boolean(canOpenLocal && status?.lanWebUrl);

  const currentPageUrl = useMemo(() => {
    if (typeof window === "undefined") return "";
    return window.location.href;
  }, []);

  async function refreshStatus(silent = false) {
    if (!bridge) return;
    if (!silent) setLoading(true);
    try {
      setStatus(await bridge.getServiceStatus());
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : "读取服务状态失败");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function openLocalInBrowser() {
    if (!bridge) return;
    setOpeningLocal(true);
    try {
      setStatus(await bridge.openWebFrontendInBrowser());
    } finally {
      setOpeningLocal(false);
    }
  }

  async function openLanInBrowser() {
    if (!bridge) return;
    setOpeningLan(true);
    try {
      setStatus(await bridge.openLanWebFrontendInBrowser());
    } finally {
      setOpeningLan(false);
    }
  }

  useEffect(() => {
    if (!bridge) return;

    void refreshStatus(true);
    const unsubscribe = bridge.onServicesChanged(() => {
      void refreshStatus(true);
    });
    const timer = window.setInterval(() => {
      void refreshStatus(true);
    }, 2000);

    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, [bridge]);

  if (!bridge) {
    return (
      <Alert
        type="info"
        showIcon
        message="服务状态只在桌面启动程序中显示"
        description={`当前页面地址：${currentPageUrl}`}
      />
    );
  }

  return (
    <Space direction="vertical" size={16} className="full-width service-status-page">
      <Card
        className="section-card"
        title="服务状态"
        extra={
          <Space wrap>
            <Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void refreshStatus()}>
              刷新
            </Button>
            <Button
              icon={<ExternalLink size={16} />}
              disabled={!canOpenLocal}
              loading={openingLocal}
              onClick={openLocalInBrowser}
            >
              浏览器打开
            </Button>
            <Button
              icon={<ExternalLink size={16} />}
              disabled={!canOpenLan}
              loading={openingLan}
              onClick={openLanInBrowser}
            >
              打开局域网地址
            </Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={12}>
            <ServiceCard
              title="后端服务"
              ready={Boolean(status?.backendReady)}
              starting={backendStarting}
              localUrl={status?.backendUrl ?? "http://127.0.0.1:8000"}
              lanUrl={status?.lanBackendUrl ?? null}
            />
          </Col>
          <Col xs={24} xl={12}>
            <ServiceCard
              title="Web 前端"
              ready={Boolean(status?.webReady)}
              starting={webStarting}
              localUrl={status?.webUrl ?? "http://127.0.0.1:5173"}
              lanUrl={status?.lanWebUrl ?? null}
            />
          </Col>
        </Row>
      </Card>

      <Alert
        type="info"
        showIcon
        message="关闭这个主窗口时，本窗口启动的前端和后端服务会一起结束。"
      />
    </Space>
  );
}
