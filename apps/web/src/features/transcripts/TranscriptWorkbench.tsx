import { Alert, Button, Card, Col, Empty, Input, Row, Space, Table, Tag, Typography, Upload, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Download, FileText, RefreshCw, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { TranscriptSentence, TranscriptTask } from "../../api";
import { api } from "../../api";
import { formatDateTime, formatDuration, formatFileSize, formatTranscriptTime } from "../../shared/formatters";

const { Text } = Typography;

function transcriptStatusTag(status: string) {
  const statusMap: Record<string, { color: string; label: string }> = {
    queued: { color: "blue", label: "排队中" },
    processing: { color: "processing", label: "转写中" },
    done: { color: "green", label: "已完成" },
    failed: { color: "red", label: "失败" },
    waiting_config: { color: "gold", label: "待配置" },
  };
  const item = statusMap[status] ?? { color: "default", label: status };
  return <Tag color={item.color}>{item.label}</Tag>;
}

export function TranscriptWorkbench() {
  const [tasks, setTasks] = useState<TranscriptTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [uploading, setUploading] = useState(false);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? tasks[0] ?? null,
    [selectedTaskId, tasks],
  );

  const hasRunningTask = useMemo(
    () => tasks.some((task) => ["queued", "processing"].includes(task.status)),
    [tasks],
  );

  useEffect(() => {
    void loadTasks();
  }, []);

  useEffect(() => {
    if (!tasks.length || selectedTaskId) return;
    setSelectedTaskId(tasks[0].id);
  }, [selectedTaskId, tasks]);

  useEffect(() => {
    if (!hasRunningTask) return;
    const timer = window.setInterval(() => {
      void loadTasks(true);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasRunningTask]);

  async function loadTasks(silent = false) {
    if (!silent) setLoadingTasks(true);
    try {
      setTasks(await api.listTranscripts());
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : "读取转写任务失败");
      }
    } finally {
      if (!silent) setLoadingTasks(false);
    }
  }

  async function uploadTranscript(file: File) {
    setUploading(true);
    try {
      const task = await api.uploadTranscript(file);
      setSelectedTaskId(task.id);
      await loadTasks(true);
      message.success("已上传，正在创建转写任务");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function retryTranscript(taskId: string) {
    setLoadingTasks(true);
    try {
      const task = await api.retryTranscript(taskId);
      setSelectedTaskId(task.id);
      await loadTasks(true);
      message.success("已重新提交");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "重新提交失败");
    } finally {
      setLoadingTasks(false);
    }
  }

  async function copyTranscriptText() {
    if (!selectedTask?.text) return;
    await navigator.clipboard.writeText(selectedTask.text);
    message.success("转写文本已复制");
  }

  const taskColumns: ColumnsType<TranscriptTask> = [
    {
      title: "文件",
      dataIndex: "file_name",
      render: (value: string, record) => (
        <Button type="link" className="plain-link" onClick={() => setSelectedTaskId(record.id)}>
          {value}
        </Button>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (value: string) => transcriptStatusTag(value),
    },
    {
      title: "大小",
      dataIndex: "file_size",
      width: 100,
      render: formatFileSize,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 170,
      render: formatDateTime,
    },
  ];

  const sentenceColumns: ColumnsType<TranscriptSentence> = [
    {
      title: "时间",
      width: 130,
      render: (_, record) => `${formatTranscriptTime(record.start_ms)} - ${formatTranscriptTime(record.end_ms)}`,
    },
    {
      title: "说话人",
      dataIndex: "speaker",
      width: 110,
      render: (value: string | null | undefined) => value ?? "-",
    },
    {
      title: "内容",
      dataIndex: "text",
    },
  ];

  return (
    <Row gutter={[16, 16]} className="main-grid">
      <Col xs={24} xl={9}>
        <Space direction="vertical" size={16} className="full-width">
          <Card className="section-card transcript-upload-card" title="上传音视频">
            <Upload.Dragger
              accept=".mp4,.mov,.mkv,.avi,.mp3,.wav,.m4a,.flac,.webm,.wmv"
              multiple={false}
              showUploadList={false}
              beforeUpload={(file) => {
                void uploadTranscript(file);
                return false;
              }}
              disabled={uploading}
            >
              <UploadCloud size={30} />
              <Text strong>拖入文件或点击上传</Text>
              <Text type="secondary">视频和音频文件会保存到本地任务目录</Text>
            </Upload.Dragger>
            <Alert
              className="transcript-config-note"
              type="info"
              showIcon
              message="云端转写需要 DASHSCOPE_API_KEY，并配置 OSS 或公网访问地址。"
            />
          </Card>

          <Card
            className="section-card"
            title="转写任务"
            extra={
              <Button
                icon={<RefreshCw size={16} />}
                loading={loadingTasks}
                onClick={() => void loadTasks()}
              >
                刷新
              </Button>
            }
          >
            <Table
              size="small"
              rowKey="id"
              columns={taskColumns}
              dataSource={tasks}
              loading={loadingTasks || uploading}
              pagination={{ pageSize: 7 }}
              rowClassName={(record) => (record.id === selectedTask?.id ? "selected-row" : "")}
              onRow={(record) => ({
                onClick: () => setSelectedTaskId(record.id),
              })}
            />
          </Card>
        </Space>
      </Col>

      <Col xs={24} xl={15}>
        <Card
          className="section-card transcript-result-card"
          title="转写结果"
          extra={
            selectedTask ? (
              <Space wrap>
                {selectedTask.status === "done" ? (
                  <>
                    <Button
                      icon={<FileText size={16} />}
                      disabled={!selectedTask.text}
                      onClick={copyTranscriptText}
                    >
                      复制文本
                    </Button>
                    <Button icon={<Download size={16} />} href={api.transcriptExportUrl(selectedTask.id, "txt")}>
                      TXT
                    </Button>
                    <Button icon={<Download size={16} />} href={api.transcriptExportUrl(selectedTask.id, "srt")}>
                      SRT
                    </Button>
                    <Button icon={<Download size={16} />} href={api.transcriptExportUrl(selectedTask.id, "md")}>
                      MD
                    </Button>
                  </>
                ) : null}
                {["failed", "waiting_config"].includes(selectedTask.status) ? (
                  <Button
                    type="primary"
                    icon={<RefreshCw size={16} />}
                    loading={loadingTasks}
                    onClick={() => void retryTranscript(selectedTask.id)}
                  >
                    重新提交
                  </Button>
                ) : null}
              </Space>
            ) : null
          }
        >
          {selectedTask ? (
            <Space direction="vertical" size={16} className="full-width">
              <Space wrap>
                {transcriptStatusTag(selectedTask.status)}
                <Tag>{selectedTask.provider}</Tag>
                <Tag>{formatFileSize(selectedTask.file_size)}</Tag>
                {selectedTask.duration_ms ? <Tag>{formatDuration(selectedTask.duration_ms / 1000)}</Tag> : null}
                {selectedTask.sentences.length ? <Tag>{selectedTask.sentences.length} 句</Tag> : null}
              </Space>

              {selectedTask.message ? (
                <Alert
                  type={selectedTask.status === "failed" ? "error" : selectedTask.status === "waiting_config" ? "warning" : "info"}
                  showIcon
                  message={selectedTask.message}
                  description={selectedTask.error ?? undefined}
                />
              ) : null}

              {selectedTask.status === "processing" || selectedTask.status === "queued" ? (
                <div className="transcript-processing">
                  <RefreshCw size={18} />
                  <Text>正在处理，列表会自动刷新</Text>
                </div>
              ) : null}

              {selectedTask.text ? (
                <Input.TextArea
                  className="transcript-text"
                  value={selectedTask.text}
                  readOnly
                  autoSize={{ minRows: 8, maxRows: 16 }}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无转写文本" />
              )}

              <Table
                size="small"
                rowKey="index"
                columns={sentenceColumns}
                dataSource={selectedTask.sentences}
                pagination={{ pageSize: 10 }}
              />
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="上传文件后可查看转写结果" />
          )}
        </Card>
      </Col>
    </Row>
  );
}
