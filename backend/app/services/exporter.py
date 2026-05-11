from pathlib import Path
from time import time
from uuid import uuid4

from openpyxl import Workbook

from backend.app.models.schemas import ProductGroupRecord

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORT_ROOT = REPO_ROOT / "data" / "cache" / "exports"
EXPORT_MAX_AGE_SECONDS = 24 * 60 * 60


def export_groups_to_excel(groups: list[ProductGroupRecord]) -> Path:
    cleanup_old_exports()
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "高频差品"
    sheet.append(
        [
            "商品组ID",
            "代表图路径",
            "出现次数",
            "出现直播场次",
            "所有图片路径",
            "是否高频差品",
            "备注",
        ]
    )

    for group in groups:
        sheet.append(
            [
                group.product_group_id,
                group.representative_image,
                group.appear_count,
                "、".join(group.appeared_sessions),
                "\n".join(image.file_path for image in group.images),
                "是" if group.appear_count >= 2 else "否",
                "",
            ]
        )

    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(max_length + 2, 12), 60)

    output_path = EXPORT_ROOT / f"lightdrop-products-report-{uuid4().hex}.xlsx"
    workbook.save(output_path)
    return output_path


def cleanup_old_exports() -> None:
    if not EXPORT_ROOT.exists():
        return

    expire_before = time() - EXPORT_MAX_AGE_SECONDS
    for path in EXPORT_ROOT.glob("*.xlsx"):
        try:
            if path.stat().st_mtime < expire_before:
                path.unlink()
        except OSError:
            continue
