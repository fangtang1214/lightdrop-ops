from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from backend.app.models.schemas import TaskStatusResponse


TaskProgress = Callable[[int, str], None]
TaskWork = Callable[[TaskProgress], tuple[str | None, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskRecord:
    def __init__(self, name: str) -> None:
        self.id = uuid4().hex
        self.name = name
        self.status = "queued"
        self.progress = 0
        self.message = "等待执行"
        self.result_kind: str | None = None
        self.result: Any = None
        self.error: str | None = None
        self.created_at = utc_now()
        self.updated_at = self.created_at

    def to_response(self) -> TaskStatusResponse:
        return TaskStatusResponse(
            id=self.id,
            name=self.name,
            status=self.status,
            progress=self.progress,
            message=self.message,
            result_kind=self.result_kind,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class TaskQueue:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._max_tasks = 100

    def submit(self, name: str, work: TaskWork) -> TaskStatusResponse:
        task = TaskRecord(name)
        with self._lock:
            self._tasks[task.id] = task
            self._prune_unlocked()
        self._executor.submit(self._run, task.id, work)
        return task.to_response()

    def get(self, task_id: str) -> TaskStatusResponse | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.to_response()

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            task = self._tasks[task_id]
            for key, value in changes.items():
                setattr(task, key, value)
            task.updated_at = utc_now()
            self._prune_unlocked()

    def _prune_unlocked(self) -> None:
        if len(self._tasks) <= self._max_tasks:
            return

        removable = [
            task
            for task in self._tasks.values()
            if task.status in {"completed", "failed"}
        ]
        removable.sort(key=lambda item: item.updated_at)
        for task in removable[: max(0, len(self._tasks) - self._max_tasks)]:
            self._tasks.pop(task.id, None)

    def _run(self, task_id: str, work: TaskWork) -> None:
        self._update(task_id, status="running", progress=1, message="开始执行")

        def progress(value: int, message: str) -> None:
            self._update(
                task_id,
                progress=max(0, min(value, 99)),
                message=message,
            )

        try:
            result_kind, result = work(progress)
            self._update(
                task_id,
                status="completed",
                progress=100,
                message="完成",
                result_kind=result_kind,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001 - task boundary should capture all failures
            self._update(
                task_id,
                status="failed",
                progress=100,
                message="执行失败",
                error=str(exc),
            )


task_queue = TaskQueue()
