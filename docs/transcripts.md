# 视频转文字配置

当前实现使用阿里云百炼 DashScope Paraformer 录音文件识别。阿里云接口要求输入文件必须是公网可访问的 HTTP/HTTPS URL，因此本地上传后需要满足以下两种配置之一。

## 推荐：上传到阿里云 OSS

```powershell
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
$env:ALIYUN_OSS_ENDPOINT="https://oss-cn-hangzhou.aliyuncs.com"
$env:ALIYUN_OSS_BUCKET="你的 bucket"
$env:ALIYUN_ACCESS_KEY_ID="你的 AccessKey ID"
$env:ALIYUN_ACCESS_KEY_SECRET="你的 AccessKey Secret"
```

可选配置：

```powershell
$env:DASHSCOPE_MODEL="paraformer-v2"
$env:DASHSCOPE_LANGUAGE_HINTS="zh,en"
$env:DASHSCOPE_DIARIZATION_ENABLED="true"
$env:DASHSCOPE_SPEAKER_COUNT="2"
$env:TRANSCRIPT_EXTRACT_AUDIO="true"
$env:TRANSCRIPT_OSS_PREFIX="lightdrop-transcripts"
$env:TRANSCRIPT_OSS_URL_EXPIRES="172800"
```

使用 OSS 模式时，`TRANSCRIPT_EXTRACT_AUDIO=true` 会尝试调用本机 `ffmpeg` 从视频抽取 16k 单声道 MP3；如果没有安装 `ffmpeg`，系统会自动改用原始视频文件提交。

## 备选：公网访问本服务

如果后端服务通过公网域名或内网穿透暴露，可以设置：

```powershell
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
$env:TRANSCRIPT_PUBLIC_BASE_URL="https://你的公网域名"
```

这种方式会让阿里云从 `https://你的公网域名/api/transcripts/media/{task_id}` 下载文件。

## 接口

- `POST /api/transcripts/upload` 上传音视频文件并创建任务。
- `GET /api/transcripts` 查看任务列表。
- `GET /api/transcripts/{task_id}` 查看任务状态和结果。
- `POST /api/transcripts/{task_id}/retry` 重新提交失败或待配置任务。
- `GET /api/transcripts/{task_id}/export?format=txt|srt|md` 导出结果。

任务文件和结果保存在 `data/transcripts`，服务重启后仍可查看。
