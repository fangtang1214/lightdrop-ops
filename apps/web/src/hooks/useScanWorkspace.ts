import { useMemo, useState } from "react";
import type { BadProductRule, ScanResponse } from "../api";
import { api } from "../api";
import { defaultBadProductRule } from "../shared/constants";
import { useLocalStorageState } from "./useLocalStorageState";

const lastRootPathStorageKey = "lightdrop:lastRootPath";
const badProductRuleStorageKey = "lightdrop:badProductRule";
const badProductRules: BadProductRule[] = ["bottom_20", "zero_conversion"];

export function useScanWorkspace() {
  const [rootPath, setRootPath] = useLocalStorageState(lastRootPathStorageKey);
  const [storedBadProductRule, setStoredBadProductRule] = useLocalStorageState(
    badProductRuleStorageKey,
    defaultBadProductRule,
  );
  const [threshold, setThreshold] = useState(8);
  const [minCount, setMinCount] = useState(2);
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [selectedDetailSession, setSelectedDetailSession] = useState<string | null>(null);
  const [selectedDashboardSession, setSelectedDashboardSession] = useState<string | null>(null);

  const tableSessions = scan?.table_process?.processed_sessions ?? [];
  const dashboardSessions = scan?.live_dashboard?.processed_sessions ?? [];
  const badProductRule = badProductRules.includes(storedBadProductRule as BadProductRule)
    ? (storedBadProductRule as BadProductRule)
    : defaultBadProductRule;

  const selectedRankingSession = useMemo(() => {
    if (!tableSessions.length) return null;
    return tableSessions.find((session) => session.session_name === selectedDetailSession) ?? tableSessions[tableSessions.length - 1];
  }, [selectedDetailSession, tableSessions]);

  const selectedDashboard = useMemo(() => {
    if (!dashboardSessions.length) return null;
    return dashboardSessions.find((session) => session.session_name === selectedDashboardSession) ?? dashboardSessions[dashboardSessions.length - 1];
  }, [dashboardSessions, selectedDashboardSession]);

  const selectedSessionText = useMemo(() => {
    if (!scan?.sessions.length) return "未扫描";
    return `${scan.sessions.length} 场 / ${scan.images.length} 张图片`;
  }, [scan]);

  function applyScanResult(result: ScanResponse) {
    setScan(result);
    const processedSessions = result.table_process?.processed_sessions ?? [];
    const nextDetailSession = processedSessions[processedSessions.length - 1]?.session_name ?? null;
    const dashboardSessions = result.live_dashboard?.processed_sessions ?? [];
    const nextDashboardSession = dashboardSessions[dashboardSessions.length - 1]?.session_name ?? null;
    setSelectedDetailSession((current) => {
      if (current && processedSessions.some((session) => session.session_name === current)) {
        return current;
      }
      return nextDetailSession;
    });
    setSelectedDashboardSession((current) => {
      if (current && dashboardSessions.some((session) => session.session_name === current)) {
        return current;
      }
      return nextDashboardSession;
    });
  }

  async function scanFolder() {
    const scannedRootPath = rootPath.trim();
    const result = await api.scanFolder(scannedRootPath);
    setRootPath(scannedRootPath);
    setSelectedDetailSession(null);
    setSelectedDashboardSession(null);
    return result;
  }

  return {
    rootPath,
    setRootPath,
    badProductRule,
    setBadProductRule: setStoredBadProductRule,
    threshold,
    setThreshold,
    minCount,
    setMinCount,
    scan,
    setScan,
    tableSessions,
    dashboardSessions,
    selectedRankingSession,
    selectedDashboard,
    selectedSessionText,
    setSelectedDetailSession,
    setSelectedDashboardSession,
    applyScanResult,
    scanFolder,
  };
}
