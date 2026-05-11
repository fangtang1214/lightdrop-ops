import { useState } from "react";
import type { OverviewResponse, ProductGroup } from "../api";
import { api } from "../api";
import { emptyReports, getVisibleReportRanges, type ReportMap } from "../shared/constants";

export function useReports() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [reports, setReports] = useState<ReportMap>(emptyReports);
  const [topProducts, setTopProducts] = useState<ProductGroup[]>([]);

  function clearReports() {
    setOverview(null);
    setReports(emptyReports);
    setTopProducts([]);
  }

  async function refreshReports(sessionCount: number, minCount: number) {
    const ranges = getVisibleReportRanges(sessionCount);
    const [overviewResult, topResult, ...recentResults] = await Promise.all([
      api.getOverview(),
      api.getTopProducts(20),
      ...ranges.map((range) => api.getRecent(range, minCount)),
    ]);
    setOverview(overviewResult);
    setTopProducts(topResult.products);
    setReports(
      Object.fromEntries(
        ranges.map((range, index) => [range, recentResults[index]]),
      ) as ReportMap,
    );
  }

  return { overview, reports, topProducts, clearReports, refreshReports };
}
