from pathlib import Path
from threading import Lock

from backend.app.models.schemas import (
    LiveDashboardSummary,
    ProductGroupRecord,
    ScanResponse,
    TableProcessSummary,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_PATH = REPO_ROOT / "data" / "cache" / "workspace.json"


class AnalysisStore:
    def __init__(self) -> None:
        self.scan: ScanResponse | None = None
        self.groups: list[ProductGroupRecord] = []
        self._lock = Lock()
        self._load()

    def set_scan(self, scan: ScanResponse) -> None:
        with self._lock:
            self.scan = scan
            self.groups = []
            self._save_unlocked()

    def set_groups(self, groups: list[ProductGroupRecord]) -> None:
        with self._lock:
            self.groups = groups
            self._save_unlocked()

    def set_table_process(self, table_process: TableProcessSummary | None) -> None:
        scan = self.require_scan()
        scan.table_process = table_process
        self._save()

    def set_live_dashboard(self, live_dashboard: LiveDashboardSummary | None) -> None:
        scan = self.require_scan()
        scan.live_dashboard = live_dashboard
        self._save()

    def require_scan(self) -> ScanResponse:
        if self.scan is None:
            raise RuntimeError("请先扫描差品图片总目录")
        return self.scan

    def require_groups(self) -> list[ProductGroupRecord]:
        if not self.groups:
            raise RuntimeError("请先执行图片匹配")
        return self.groups

    def _save(self) -> None:
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self) -> None:
        WORKSPACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scan": self.scan.model_dump(mode="json") if self.scan is not None else None,
            "groups": [group.model_dump(mode="json") for group in self.groups],
        }
        WORKSPACE_PATH.write_text(
            __import__("json").dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not WORKSPACE_PATH.exists():
            return
        try:
            payload = __import__("json").loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
            if payload.get("scan"):
                self.scan = ScanResponse.model_validate(payload["scan"])
            self.groups = [
                ProductGroupRecord.model_validate(group)
                for group in payload.get("groups", [])
            ]
        except Exception:
            self.scan = None
            self.groups = []


analysis_store = AnalysisStore()
