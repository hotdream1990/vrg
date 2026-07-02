"""Router lịch chạy job định kỳ (schedule_job) — chỉ admin (gắn require_admin ở main)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import schedule_repo, scheduler

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleUpdate(BaseModel):
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    enabled: bool


@router.get("")
def list_schedules() -> dict:
    """Danh sách job định kỳ: lịch + mô tả + lần chạy gần nhất + lần chạy kế tiếp."""
    out = []
    for job in schedule_repo.list_jobs():
        meta = scheduler.JOB_REGISTRY.get(job["name"])
        if not meta:
            continue  # job đã gỡ khỏi registry (vd marketscreener) → không hiện
        out.append({
            **job,
            "label": meta.get("label", job["name"]),
            "purpose": meta.get("purpose"),
            "last_run": schedule_repo.last_run_for(meta["source"]),
            "next_run": scheduler.next_run(job["name"]),
        })
    return {"jobs": out}


@router.put("/{name}")
def update_schedule(name: str, body: ScheduleUpdate) -> dict:
    """Đổi giờ/phút + bật/tắt 1 job → đồng bộ lại scheduler."""
    if name not in scheduler.JOB_REGISTRY:
        raise HTTPException(404, "Job không tồn tại")
    schedule_repo.update_job(name, body.hour, body.minute, body.enabled)
    scheduler.sync()
    return {"ok": True}


@router.post("/{name}/run")
def run_schedule(name: str) -> dict:
    """Chạy job ngay (thủ công) — trả kết quả quét."""
    if name not in scheduler.JOB_REGISTRY:
        raise HTTPException(404, "Job không tồn tại")
    return scheduler.run_now(name)
