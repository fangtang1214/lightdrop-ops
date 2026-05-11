import type { BadProductRule, RecentReportResponse } from "../api";

export type ReportMap = Partial<Record<number, RecentReportResponse>>;
export type AppView = "products" | "dashboardReview" | "transcripts" | "serviceStatus";
export type ProductAnalysisView = "analysis" | "goodProducts" | "conversionDrop" | "liveData";

export const emptyReports: ReportMap = {};
export const plannedReportRanges = [4, 6, 10];
export const defaultBadProductRule: BadProductRule = "bottom_20";
export const badProductRuleOptions: Array<{ label: string; value: BadProductRule }> = [
  { label: "转化排名倒数20个", value: "bottom_20" },
  { label: "转化率为0", value: "zero_conversion" },
];

export function getBadProductRuleLabel(rule: BadProductRule | undefined | null) {
  return badProductRuleOptions.find((option) => option.value === rule)?.label ?? badProductRuleOptions[0].label;
}

export function getVisibleReportRanges(sessionCount: number) {
  if (sessionCount > 0 && sessionCount < 4) {
    return [sessionCount];
  }
  return plannedReportRanges.filter((range) => sessionCount >= range);
}
