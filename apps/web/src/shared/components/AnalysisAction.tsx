import { Button } from "antd";
import { Play } from "lucide-react";

export function AnalysisAction({
  loading,
  disabled,
  onAnalyze,
}: {
  loading: boolean;
  disabled: boolean;
  onAnalyze: () => void;
}) {
  return (
    <Button type="primary" icon={<Play size={16} />} loading={loading} disabled={disabled} onClick={onAnalyze}>
      开始分析
    </Button>
  );
}
