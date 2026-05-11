import { Button, Card, Col, Input, InputNumber, Row, Select } from "antd";
import { FolderOpen, Play, Search } from "lucide-react";
import type { BadProductRule } from "../api";
import { badProductRuleOptions } from "../shared/constants";

export function CommandBar({
  rootPath,
  threshold,
  minCount,
  badProductRule,
  hasScan,
  scanLoading,
  matchLoading,
  busy,
  onRootPathChange,
  onThresholdChange,
  onMinCountChange,
  onBadProductRuleChange,
  onScan,
  onMatch,
}: {
  rootPath: string;
  threshold: number;
  minCount: number;
  badProductRule: BadProductRule;
  hasScan: boolean;
  scanLoading: boolean;
  matchLoading: boolean;
  busy: boolean;
  onRootPathChange: (value: string) => void;
  onThresholdChange: (value: number) => void;
  onMinCountChange: (value: number) => void;
  onBadProductRuleChange: (value: BadProductRule) => void;
  onScan: () => void;
  onMatch: () => void;
}) {
  return (
    <Card className="control-panel" id="folders">
      <Row gutter={[12, 12]} align="middle">
        <Col xs={24} lg={10}>
          <Input
            value={rootPath}
            onChange={(event) => onRootPathChange(event.target.value)}
            placeholder="D:/直播差品图片库"
            prefix={<FolderOpen size={16} />}
          />
        </Col>
        <Col xs={12} sm={6} lg={3}>
          <InputNumber
            min={0}
            max={64}
            value={threshold}
            onChange={(value) => onThresholdChange(value ?? 8)}
            addonBefore="距离"
            className="full-width"
          />
        </Col>
        <Col xs={12} sm={6} lg={3}>
          <InputNumber
            min={1}
            max={10}
            value={minCount}
            onChange={(value) => onMinCountChange(value ?? 2)}
            addonBefore="次数"
            className="full-width"
          />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <Select
            value={badProductRule}
            onChange={onBadProductRuleChange}
            options={badProductRuleOptions}
            className="full-width"
          />
        </Col>
        <Col xs={24} sm={12} lg={2}>
          <Button block icon={<Search size={16} />} disabled={!rootPath.trim() || busy} loading={scanLoading} onClick={onScan}>
            扫描目录
          </Button>
        </Col>
        <Col xs={24} sm={12} lg={2}>
          <Button block type="primary" icon={<Play size={16} />} disabled={!hasScan || busy} loading={matchLoading} onClick={onMatch}>
            开始匹配
          </Button>
        </Col>
      </Row>
    </Card>
  );
}
