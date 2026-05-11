from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import UploadFile

from backend.app.models.schemas import TranscriptSentence, TranscriptTask


REPO_ROOT = Path(__file__).resolve().parents[3]
TRANSCRIPT_ROOT = REPO_ROOT / "data" / "transcripts"
UPLOAD_ROOT = TRANSCRIPT_ROOT / "uploads"
TASK_ROOT = TRANSCRIPT_ROOT / "tasks"

SUPPORTED_MEDIA_EXTENSIONS = {
    ".aac",
    ".amr",
    ".avi",
    ".flac",
    ".flv",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
    ".wmv",
}


@dataclass(frozen=True)
class TranscriptSettings:
    provider: str
    dashscope_api_key: str | None
    dashscope_model: str
    language_hints: list[str]
    diarization_enabled: bool
    speaker_count: int | None
    public_base_url: str | None
    extract_audio: bool
    oss_endpoint: str | None
    oss_bucket: str | None
    oss_access_key_id: str | None
    oss_access_key_secret: str | None
    oss_prefix: str
    oss_url_expires: int

    @property
    def oss_enabled(self) -> bool:
        return bool(
            self.oss_endpoint
            and self.oss_bucket
            and self.oss_access_key_id
            and self.oss_access_key_secret
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def get_transcript_settings() -> TranscriptSettings:
    language_hints = [
        item.strip()
        for item in os.getenv("DASHSCOPE_LANGUAGE_HINTS", "zh,en").split(",")
        if item.strip()
    ]
    return TranscriptSettings(
        provider=os.getenv("TRANSCRIPT_PROVIDER", "dashscope").strip().lower(),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("DASH_SCOPE_API_KEY"),
        dashscope_model=os.getenv("DASHSCOPE_MODEL", "paraformer-v2"),
        language_hints=language_hints,
        diarization_enabled=_bool_env("DASHSCOPE_DIARIZATION_ENABLED", True),
        speaker_count=_int_env("DASHSCOPE_SPEAKER_COUNT"),
        public_base_url=os.getenv("TRANSCRIPT_PUBLIC_BASE_URL"),
        extract_audio=_bool_env("TRANSCRIPT_EXTRACT_AUDIO", False),
        oss_endpoint=os.getenv("ALIYUN_OSS_ENDPOINT") or os.getenv("OSS_ENDPOINT"),
        oss_bucket=os.getenv("ALIYUN_OSS_BUCKET") or os.getenv("OSS_BUCKET"),
        oss_access_key_id=os.getenv("ALIYUN_ACCESS_KEY_ID")
        or os.getenv("OSS_ACCESS_KEY_ID"),
        oss_access_key_secret=os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        or os.getenv("OSS_ACCESS_KEY_SECRET"),
        oss_prefix=os.getenv("TRANSCRIPT_OSS_PREFIX", "lightdrop-transcripts"),
        oss_url_expires=_int_env("TRANSCRIPT_OSS_URL_EXPIRES") or 172800,
    )


def _clean_file_name(file_name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", file_name).strip(" .")
    return cleaned or "media"


def _task_path(task_id: str) -> Path:
    return TASK_ROOT / f"{task_id}.json"


def _task_upload_dir(task_id: str) -> Path:
    return UPLOAD_ROOT / task_id


def _task_media_path(task: TranscriptTask) -> Path:
    return _task_upload_dir(task.id) / task.file_name


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=lambda item: getattr(item, "__dict__", str(item))))


def _get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _format_srt_time(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


class TranscriptService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        TRANSCRIPT_ROOT.mkdir(parents=True, exist_ok=True)
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        TASK_ROOT.mkdir(parents=True, exist_ok=True)

    def create_task(self, upload: UploadFile) -> TranscriptTask:
        original_name = _clean_file_name(upload.filename or "media")
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_MEDIA_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_MEDIA_EXTENSIONS))
            raise ValueError(f"暂不支持 {suffix or '无后缀'} 文件，支持格式：{supported}")

        task_id = uuid.uuid4().hex
        task_dir = _task_upload_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        media_path = task_dir / original_name
        with media_path.open("wb") as output:
            shutil.copyfileobj(upload.file, output)

        task = TranscriptTask(
            id=task_id,
            file_name=original_name,
            file_size=media_path.stat().st_size,
            status="queued",
            provider=get_transcript_settings().provider,
            message="文件已上传，等待转写",
            created_at=_now(),
            updated_at=_now(),
        )
        self.save_task(task)
        return task

    def save_task(self, task: TranscriptTask) -> None:
        task.updated_at = _now()
        with self._lock:
            _task_path(task.id).write_text(
                json.dumps(_model_to_dict(task), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_task(self, task_id: str) -> TranscriptTask:
        path = _task_path(task_id)
        if not path.exists():
            raise KeyError(task_id)
        return TranscriptTask.model_validate_json(path.read_text(encoding="utf-8"))

    def list_tasks(self) -> list[TranscriptTask]:
        tasks = []
        for path in TASK_ROOT.glob("*.json"):
            try:
                tasks.append(TranscriptTask.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    def process_task(self, task_id: str) -> None:
        try:
            task = self.get_task(task_id)
            settings = get_transcript_settings()
            task.provider = settings.provider
            task.status = "processing"
            task.message = "正在准备可供云端读取的音视频文件"
            self.save_task(task)

            if settings.provider != "dashscope":
                raise RuntimeError(f"暂不支持的转写供应商：{settings.provider}")
            if not settings.dashscope_api_key:
                task.status = "waiting_config"
                task.message = "缺少 DASHSCOPE_API_KEY，已保存文件，配置后可重新上传转写"
                self.save_task(task)
                return

            source_path = self._prepare_media_file(task, settings)
            media_url = self._build_media_url(task, source_path, settings)
            if not media_url:
                task.status = "waiting_config"
                task.message = (
                    "阿里云转写需要公网可访问的文件 URL。请配置 OSS 环境变量，"
                    "或配置 TRANSCRIPT_PUBLIC_BASE_URL 指向公网可访问的本服务地址。"
                )
                self.save_task(task)
                return

            task.media_url = media_url
            task.message = "已提交阿里云百炼 Paraformer，正在等待识别结果"
            self.save_task(task)

            result = self._run_dashscope(task, media_url, settings)
            task.text = result["text"]
            task.sentences = result["sentences"]
            task.duration_ms = result["duration_ms"]
            task.transcription_url = result["transcription_url"]
            task.status = "done"
            task.message = f"转写完成，共 {len(task.sentences)} 句"
            self.save_task(task)
        except Exception as exc:
            try:
                task = self.get_task(task_id)
                task.status = "failed"
                task.error = str(exc)
                task.message = "转写失败"
                self.save_task(task)
            except Exception:
                pass

    def media_file(self, task_id: str) -> Path:
        task = self.get_task(task_id)
        media_path = _task_media_path(task)
        if not media_path.exists():
            raise FileNotFoundError(media_path)
        return media_path

    def export(self, task_id: str, file_format: str) -> tuple[str, str, str]:
        task = self.get_task(task_id)
        if task.status != "done":
            raise ValueError("转写完成后才能导出")

        normalized = file_format.lower()
        if normalized == "txt":
            content = task.text
            return content, "text/plain; charset=utf-8", f"{Path(task.file_name).stem}.txt"
        if normalized == "md":
            content = self._to_markdown(task)
            return content, "text/markdown; charset=utf-8", f"{Path(task.file_name).stem}.md"
        if normalized == "srt":
            content = self._to_srt(task)
            return content, "application/x-subrip; charset=utf-8", f"{Path(task.file_name).stem}.srt"
        raise ValueError("仅支持导出 txt、md、srt")

    def _prepare_media_file(self, task: TranscriptTask, settings: TranscriptSettings) -> Path:
        media_path = _task_media_path(task)
        if (
            not settings.extract_audio
            or not settings.oss_enabled
            or media_path.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac"}
        ):
            return media_path

        audio_path = media_path.with_suffix(".mp3")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(media_path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-b:a",
                    "64k",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            return audio_path
        except (FileNotFoundError, subprocess.SubprocessError):
            task.message = "未能用 ffmpeg 抽取音频，已改用原始文件提交转写"
            self.save_task(task)
            return media_path

    def _build_media_url(
        self,
        task: TranscriptTask,
        source_path: Path,
        settings: TranscriptSettings,
    ) -> str | None:
        if settings.oss_enabled:
            return self._upload_to_oss(task, source_path, settings)
        if settings.public_base_url:
            base_url = settings.public_base_url.rstrip("/")
            return f"{base_url}/api/transcripts/media/{quote(task.id)}"
        return None

    def _upload_to_oss(
        self,
        task: TranscriptTask,
        source_path: Path,
        settings: TranscriptSettings,
    ) -> str:
        try:
            import oss2
        except ImportError as exc:
            raise RuntimeError("缺少 oss2 依赖，请先安装 backend/requirements.txt") from exc

        object_name = quote(source_path.name, safe="")
        object_key = f"{settings.oss_prefix.strip('/')}/{task.id}/{object_name}"
        bucket = oss2.Bucket(
            oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret),
            settings.oss_endpoint,
            settings.oss_bucket,
        )
        bucket.put_object_from_file(object_key, str(source_path))
        return bucket.sign_url("GET", object_key, settings.oss_url_expires, slash_safe=True)

    def _run_dashscope(
        self,
        task: TranscriptTask,
        media_url: str,
        settings: TranscriptSettings,
    ) -> dict[str, Any]:
        try:
            import dashscope
            from dashscope.audio.asr import Transcription
            import requests
        except ImportError as exc:
            raise RuntimeError("缺少 dashscope/requests 依赖，请先安装 backend/requirements.txt") from exc

        dashscope.api_key = settings.dashscope_api_key
        params: dict[str, Any] = {
            "model": settings.dashscope_model,
            "file_urls": [media_url],
        }
        if settings.dashscope_model == "paraformer-v2" and settings.language_hints:
            params["language_hints"] = settings.language_hints
        if settings.diarization_enabled:
            params["diarization_enabled"] = True
        if settings.speaker_count is not None:
            params["speaker_count"] = settings.speaker_count

        submit_response = Transcription.async_call(**params)
        if _get_field(submit_response, "status_code") != HTTPStatus.OK:
            raise RuntimeError(_get_field(submit_response, "message", "提交转写任务失败"))

        output = _get_field(submit_response, "output", {})
        dashscope_task_id = _get_field(output, "task_id")
        if not dashscope_task_id:
            raise RuntimeError("阿里云未返回 task_id")
        task.dashscope_task_id = dashscope_task_id
        self.save_task(task)

        wait_response = Transcription.wait(task=dashscope_task_id)
        if _get_field(wait_response, "status_code") != HTTPStatus.OK:
            raise RuntimeError(_get_field(wait_response, "message", "查询转写任务失败"))

        wait_output = _get_field(wait_response, "output", {})
        task_status = _get_field(wait_output, "task_status")
        if task_status != "SUCCEEDED":
            raise RuntimeError(f"阿里云转写任务状态异常：{task_status}")

        results = _get_field(wait_output, "results", []) or []
        first_result = results[0] if results else {}
        if _get_field(first_result, "subtask_status") != "SUCCEEDED":
            raise RuntimeError(_get_field(first_result, "message", "音视频转写子任务失败"))

        transcription_url = _get_field(first_result, "transcription_url")
        if not transcription_url:
            raise RuntimeError("阿里云未返回 transcription_url")

        response = requests.get(transcription_url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        text, sentences, duration_ms = self._parse_dashscope_payload(payload)
        return {
            "text": text,
            "sentences": sentences,
            "duration_ms": duration_ms,
            "transcription_url": transcription_url,
        }

    def _parse_dashscope_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, list[TranscriptSentence], int | None]:
        transcripts = payload.get("transcripts") or []
        lines: list[str] = []
        sentences: list[TranscriptSentence] = []
        duration_ms = (
            payload.get("properties", {}).get("original_duration_in_milliseconds")
            if isinstance(payload.get("properties"), dict)
            else None
        )

        for transcript in transcripts:
            text = transcript.get("text") or ""
            if text:
                lines.append(text)
            if duration_ms is None:
                duration_ms = transcript.get("content_duration_in_milliseconds")
            for sentence in transcript.get("sentences") or []:
                speaker_id = sentence.get("speaker_id")
                sentences.append(
                    TranscriptSentence(
                        index=len(sentences) + 1,
                        start_ms=int(sentence.get("begin_time") or 0),
                        end_ms=int(sentence.get("end_time") or 0),
                        text=sentence.get("text") or "",
                        speaker=f"说话人 {speaker_id}" if speaker_id is not None else None,
                    )
                )

        if not lines and sentences:
            lines = [sentence.text for sentence in sentences]
        return "\n".join(line for line in lines if line), sentences, duration_ms

    def _to_srt(self, task: TranscriptTask) -> str:
        blocks = []
        for index, sentence in enumerate(task.sentences, start=1):
            start = _format_srt_time(sentence.start_ms)
            end = _format_srt_time(sentence.end_ms)
            text = f"{sentence.speaker}：{sentence.text}" if sentence.speaker else sentence.text
            blocks.append(f"{index}\n{start} --> {end}\n{text}")
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    def _to_markdown(self, task: TranscriptTask) -> str:
        lines = [
            f"# {Path(task.file_name).stem}",
            "",
            f"- 文件：{task.file_name}",
            f"- 句数：{len(task.sentences)}",
        ]
        if task.duration_ms is not None:
            lines.append(f"- 时长：{round(task.duration_ms / 1000)} 秒")
        lines.extend(["", "## 转写正文", ""])
        if task.sentences:
            for sentence in task.sentences:
                timestamp = _format_srt_time(sentence.start_ms).replace(",", ".")
                speaker = f"**{sentence.speaker}** " if sentence.speaker else ""
                lines.append(f"- `{timestamp}` {speaker}{sentence.text}")
        else:
            lines.append(task.text)
        return "\n".join(lines).strip() + "\n"


transcript_service = TranscriptService()


def export_file_name_ascii(file_name: str) -> str:
    stem = Path(file_name).stem or "transcript"
    suffix = Path(file_name).suffix or ".txt"
    ascii_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_") or "transcript"
    return f"{ascii_stem}{suffix}"


def guess_media_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
