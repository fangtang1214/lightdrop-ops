import { Alert, Modal, Progress, Space, Spin, Tabs, Typography, message } from "antd";
import { Suspense, lazy, useMemo, useState } from "react";
import { useAnalysisActions } from "../hooks/useAnalysisActions";
import { useReports } from "../hooks/useReports";
import { useScanWorkspace } from "../hooks/useScanWorkspace";
import { OverviewMetrics } from "../shared/components/OverviewMetrics";
import {
  getBadProductRuleLabel,
  getVisibleReportRanges,
  type AppView,
  type ProductAnalysisView,
} from "../shared/constants";
import { AppLayout } from "./AppLayout";
import { CommandBar } from "./CommandBar";

const { Text } = Typography;

const BadProductPage = lazy(() =>
  import("../features/bad-products/BadProductPage").then((module) => ({
    default: module.BadProductPage,
  })),
);
const GoodProductAnalysis = lazy(() =>
  import("../features/good-products/GoodProductPage").then((module) => ({
    default: module.GoodProductAnalysis,
  })),
);
const ConversionDropAnalysis = lazy(() =>
  import("../features/conversion-drop/ConversionDropPage").then((module) => ({
    default: module.ConversionDropAnalysis,
  })),
);
const LiveDataRanking = lazy(() =>
  import("../features/live-data/LiveDataPage").then((module) => ({
    default: module.LiveDataRanking,
  })),
);
const LiveDashboardReview = lazy(() =>
  import("../features/dashboard-review/DashboardReviewPage").then((module) => ({
    default: module.LiveDashboardReview,
  })),
);
const TranscriptWorkbench = lazy(() =>
  import("../features/transcripts/TranscriptWorkbench").then((module) => ({
    default: module.TranscriptWorkbench,
  })),
);
const ServiceStatusPage = lazy(() =>
  import("../features/service-status/ServiceStatusPage").then((module) => ({
    default: module.ServiceStatusPage,
  })),
);

export function App() {
  const [activeView, setActiveView] = useState<AppView>("products");
  const [productAnalysisView, setProductAnalysisView] = useState<ProductAnalysisView>("analysis");
  const [tableProcessModalOpen, setTableProcessModalOpen] = useState(false);
  const workspace = useScanWorkspace();
  const reportsState = useReports();

  const refreshCurrentReports = () => reportsState.refreshReports(workspace.scan?.sessions.length ?? 0, workspace.minCount);
  const actions = useAnalysisActions({
    scan: workspace.scan,
    rootPath: workspace.rootPath,
    threshold: workspace.threshold,
    badProductRule: workspace.badProductRule,
    applyScanResult: workspace.applyScanResult,
    refreshReports: refreshCurrentReports,
  });

  const visibleReportRanges = useMemo(
    () => getVisibleReportRanges(workspace.scan?.sessions.length ?? 0),
    [workspace.scan],
  );

  async function scanFolder() {
    await actions.runScan(async () => {
      const result = await workspace.scanFolder();
      workspace.applyScanResult(result);
      reportsState.clearReports();
      message.success("扫描完成");
    });
  }

  async function matchProducts() {
    const succeeded = await actions.runMatch();
    if (succeeded) {
      setTableProcessModalOpen(true);
    }
  }

  function renderProductAnalysis() {
    return (
      <Tabs
        className="product-analysis-tabs"
        activeKey={productAnalysisView}
        onChange={(key) => setProductAnalysisView(key as ProductAnalysisView)}
        items={[
          {
            key: "analysis",
            label: "差品分析",
            children: (
              <BadProductPage
                visibleReportRanges={visibleReportRanges}
                reports={reportsState.reports}
                overview={reportsState.overview}
                topProducts={reportsState.topProducts}
                sessions={workspace.scan?.sessions ?? []}
              />
            ),
          },
          {
            key: "goodProducts",
            label: "优品分析",
            children: (
              <GoodProductAnalysis
                sessions={workspace.tableSessions}
                goodRankings={workspace.scan?.table_process?.good_rankings ?? []}
                selectedSessionName={workspace.selectedRankingSession?.session_name ?? null}
                onSelectSession={workspace.setSelectedDetailSession}
                onAnalyze={actions.analyzeGoodProducts}
                loading={actions.loadingFor("goodProducts")}
                disabled={!workspace.scan || actions.loading}
              />
            ),
          },
          {
            key: "conversionDrop",
            label: "转化落差",
            children: (
              <ConversionDropAnalysis
                sessions={workspace.tableSessions}
                dropRankings={workspace.scan?.table_process?.conversion_drop_rankings ?? []}
                selectedSessionName={workspace.selectedRankingSession?.session_name ?? null}
                onSelectSession={workspace.setSelectedDetailSession}
                onAnalyze={actions.analyzeConversionDrop}
                loading={actions.loadingFor("conversionDrop")}
                disabled={!workspace.scan || actions.loading}
              />
            ),
          },
          {
            key: "liveData",
            label: "直播数据",
            children: (
              <LiveDataRanking
                sessions={workspace.tableSessions}
                selectedSessionName={workspace.selectedRankingSession?.session_name ?? null}
                onSelectSession={workspace.setSelectedDetailSession}
                onAnalyze={actions.analyzeLiveData}
                loading={actions.loadingFor("liveData")}
                disabled={!workspace.scan || actions.loading}
                badProductRule={workspace.scan?.table_process?.bad_product_rule ?? workspace.badProductRule}
              />
            ),
          },
        ]}
      />
    );
  }

  function renderActiveView() {
    if (activeView === "products") {
      return renderProductAnalysis();
    }

    if (activeView === "dashboardReview") {
      return (
        <LiveDashboardReview
          sessions={workspace.dashboardSessions}
          selectedSession={workspace.selectedDashboard}
          onSelectSession={workspace.setSelectedDashboardSession}
          onAnalyze={() => actions.analyzeDashboardReview(workspace.selectedDashboard?.session_name)}
          onAnalyzeAll={() => actions.analyzeDashboardReview()}
          loading={actions.loadingFor("dashboardReview")}
          disabled={!workspace.rootPath.trim() || actions.loading}
        />
      );
    }

    if (activeView === "serviceStatus") {
      return <ServiceStatusPage />;
    }

    return <TranscriptWorkbench />;
  }

  return (
    <AppLayout
      activeView={activeView}
      selectedSessionText={workspace.selectedSessionText}
      canRefresh={Boolean(reportsState.overview)}
      loading={actions.loading}
      onViewChange={setActiveView}
      onRefresh={() => actions.runTask("refresh", refreshCurrentReports)}
    >
      <CommandBar
        rootPath={workspace.rootPath}
        threshold={workspace.threshold}
        minCount={workspace.minCount}
        badProductRule={workspace.badProductRule}
        hasScan={Boolean(workspace.scan)}
        scanLoading={actions.loadingFor("scan")}
        matchLoading={actions.loadingFor("match")}
        busy={actions.loading}
        onRootPathChange={workspace.setRootPath}
        onThresholdChange={workspace.setThreshold}
        onMinCountChange={workspace.setMinCount}
        onBadProductRuleChange={workspace.setBadProductRule}
        onScan={scanFolder}
        onMatch={matchProducts}
      />

      {actions.taskStatus && actions.loading ? (
        <Alert
          type={actions.taskStatus.status === "failed" ? "error" : "info"}
          showIcon
          className="scan-warning"
          message={actions.taskStatus.message || "任务处理中"}
          description={<Progress percent={actions.taskStatus.progress} size="small" status="active" />}
        />
      ) : null}

      {!workspace.scan ? (
        <Alert
          type="info"
          showIcon
          className="scan-warning"
          message="下一步：填写目录后点击“扫描目录”。扫描只做基础图片索引，差品、优品、转化落差、直播详细数据和大屏复盘会在点击对应按钮后再生成。"
        />
      ) : null}

      <Modal
        title="直播数据表格已处理"
        open={tableProcessModalOpen && Boolean(workspace.scan?.table_process)}
        onCancel={() => setTableProcessModalOpen(false)}
        onOk={() => setTableProcessModalOpen(false)}
        okText="知道了"
        cancelButtonProps={{ style: { display: "none" } }}
        width={760}
      >
        <Space direction="vertical" size={8} className="full-width">
          {workspace.scan?.table_process?.message ? <Text>{workspace.scan.table_process.message}</Text> : null}
          {workspace.scan?.table_process?.processed_sessions.map((item) => (
            <Text key={item.table_file}>
              {item.session_name}: 共 {item.total_products} 个商品，按
              {getBadProductRuleLabel(workspace.scan?.table_process?.bad_product_rule)}
              定义差品，选出 {item.selected_bad_products} 个，匹配到 {item.matched_products} 个商品图片，复制 {item.copied_images} 张图片
              {item.unmatched_product_ids.length ? `，未匹配 ${item.unmatched_product_ids.length} 个商品ID` : ""}
            </Text>
          ))}
        </Space>
      </Modal>

      {workspace.scan?.skipped_files.length ? (
        <Alert
          type="warning"
          showIcon
          className="scan-warning"
          message={`有 ${workspace.scan.skipped_files.length} 个文件未能读取`}
        />
      ) : null}

      <OverviewMetrics overview={reportsState.overview} sessionCount={workspace.scan?.sessions.length ?? 0} />

      <Suspense fallback={<Spin className="page-loading" />}>
        {renderActiveView()}
      </Suspense>
    </AppLayout>
  );
}
