import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import type { BadProductRule, ScanResponse, TaskStatusResponse } from "../api";
import { api } from "../api";

type ApplyScanResult = (result: ScanResponse) => void;

const pollIntervalMs = 700;
const taskCancelledMessage = "__TASK_CANCELLED__";

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useAnalysisActions({
  scan,
  rootPath,
  threshold,
  badProductRule,
  applyScanResult,
  refreshReports,
}: {
  scan: ScanResponse | null;
  rootPath: string;
  threshold: number;
  badProductRule: BadProductRule;
  applyScanResult: ApplyScanResult;
  refreshReports: () => Promise<void>;
}) {
  const [loadingTask, setLoadingTask] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const activeRunRef = useRef(0);
  const mountedRef = useRef(true);
  const loading = loadingTask !== null;

  useEffect(() => {
    mountedRef.current = true;
    setLoadingTask(null);
    setTaskStatus(null);
    return () => {
      mountedRef.current = false;
      activeRunRef.current += 1;
    };
  }, []);

  async function waitForTask<T>(taskId: string): Promise<T> {
    const runId = activeRunRef.current;
    while (true) {
      if (activeRunRef.current !== runId || !mountedRef.current) {
        throw new Error(taskCancelledMessage);
      }

      const status = await api.getTask(taskId);
      if (activeRunRef.current !== runId || !mountedRef.current) {
        throw new Error(taskCancelledMessage);
      }
      setTaskStatus(status);

      if (status.status === "completed" || status.status === "done") {
        return status.result as T;
      }
      if (status.status === "failed") {
        throw new Error(status.error || status.message || "任务执行失败");
      }

      await sleep(pollIntervalMs);
    }
  }

  async function runTask(taskName: string, task: () => Promise<void>) {
    const runId = activeRunRef.current + 1;
    activeRunRef.current = runId;
    setLoadingTask(taskName);
    setTaskStatus(null);
    try {
      await task();
      return true;
    } catch (error) {
      if (!(error instanceof Error && error.message === taskCancelledMessage)) {
        message.error(error instanceof Error ? error.message : "操作失败");
      }
      return false;
    } finally {
      if (activeRunRef.current === runId && mountedRef.current) {
        setLoadingTask(null);
      }
    }
  }

  function runScan(task: () => Promise<void>) {
    return runTask("scan", task);
  }

  function loadingFor(taskName: string) {
    return loadingTask === taskName;
  }

  async function runMatch() {
    return runTask("match", async () => {
      let currentScan = scan;
      if (
        !currentScan?.table_process?.processed_sessions.length
        || currentScan.table_process.bad_product_rule !== badProductRule
      ) {
        const liveDataTask = await api.runLiveData(badProductRule);
        currentScan = await waitForTask<ScanResponse>(liveDataTask.task_id);
        applyScanResult(currentScan);
      }
      const matchTask = await api.runMatch(threshold, badProductRule);
      await waitForTask(matchTask.task_id);
      await refreshReports();
      message.success("匹配完成");
    });
  }

  async function analyzeLiveData() {
    await runTask("liveData", async () => {
      const task = await api.runLiveData(badProductRule);
      applyScanResult(await waitForTask<ScanResponse>(task.task_id));
      message.success("直播详细数据分析完成");
    });
  }

  async function analyzeGoodProducts() {
    await runTask("goodProducts", async () => {
      const task = await api.runGoodProducts();
      applyScanResult(await waitForTask<ScanResponse>(task.task_id));
      message.success("优品分析完成");
    });
  }

  async function analyzeConversionDrop() {
    await runTask("conversionDrop", async () => {
      const task = await api.runConversionDrop();
      applyScanResult(await waitForTask<ScanResponse>(task.task_id));
      message.success("转化落差分析完成");
    });
  }

  async function analyzeDashboardReview(sessionName?: string) {
    await runTask("dashboardReview", async () => {
      if (!scan) {
        const scannedRootPath = rootPath.trim();
        if (!scannedRootPath) {
          throw new Error("请先填写目录");
        }
        applyScanResult(await api.scanFolder(scannedRootPath));
      }
      const task = await api.runDashboardReview(sessionName);
      applyScanResult(await waitForTask<ScanResponse>(task.task_id));
      message.success("大屏复盘分析完成");
    });
  }

  return {
    loading,
    loadingTask,
    taskStatus,
    loadingFor,
    waitForTask,
    runTask,
    runScan,
    runMatch,
    analyzeLiveData,
    analyzeGoodProducts,
    analyzeConversionDrop,
    analyzeDashboardReview,
  };
}
