import os
import base64
import uuid
from collections import defaultdict
from calendar import monthrange
from datetime import datetime, timedelta, date
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import asc, extract
from sqlalchemy.orm import Session, joinedload

from models import (
    Member, Store, StoreMap, MemberRequest, StoreMembers,
    StoreMembersTodo, StoreMembersWork, StoreCommunity,
    StoreMembersWorkLog, StoreMembersDetail, ScheduleChangeRequest,
    DailyClosingReport, WorkLogChangeRequest, StorePart
)
from database import get_db
from schemas.employee import (
    VerifyCode, MemberRequestSchemas,
    TodoListRequest, TodoListResponse, TodoListModifyRequest,
    WrokResponse, NoticeResponse, WeeklyWorkRequest,
    ClosingReportRequest, WorkTimeRequest, WorkMonthRequest,
    WorkChangeRequest, NoticeRequestSchemas
)
from utils.uitls import format_phone_number, get_coords_from_address
from routers.auth import get_current_member_with_refresh

router = APIRouter(prefix="/api/employee", tags=["직원유형"])

# ===== 업로드 디렉토리 설정 ===== #
for _dir in ["uploads/closing/", "uploads/profile/", "uploads/documents/"]:
    os.makedirs(_dir, exist_ok=True)

CLOSING_UPLOAD_DIR = "uploads/closing/"
PROFILE_UPLOAD_DIR = "uploads/profile/"
DOCUMENT_UPLOAD_DIR = "uploads/documents/"


# ===== 공통 헬퍼 ===== #
def get_employee_or_404(db: Session, store_id: int, member_id: int) -> StoreMembers:
    employee = db.query(StoreMembers).filter(
        StoreMembers.store_id == store_id,
        StoreMembers.member_id == member_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="직원 정보를 찾을 수 없습니다.")
    return employee


async def save_file(file: UploadFile, upload_dir: str) -> str:
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    return f"/{upload_dir}{filename}"


# ======= 매장코드 조회 ======= #
@router.post("/verify-code")
async def verify_store_code(req: VerifyCode, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.code == req.code).first()
    if not store:
        raise HTTPException(status_code=404, detail="조회되지 않는 매장 코드에요")

    store_map = db.query(StoreMap).filter(StoreMap.store_id == store.id).first()
    full_address = " ".join(filter(None, [store.address, store.addressDetail]))

    if not store_map:
        lat, lng = await get_coords_from_address(store.address)
        store_map = StoreMap(store_id=store.id, lat=lat, lng=lng)
        db.add(store_map)
        db.commit()
        db.refresh(store_map)

    return {
        "id": store.id,
        "name": store.name,
        "address": full_address,
        "phone": format_phone_number(store.number),
        "lat": float(store_map.lat),
        "lng": float(store_map.lng),
    }


# ======= 가입신청 ======= #
@router.post("/member/request")
async def add_member_request(
    req: MemberRequestSchemas,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    try:
        request = MemberRequest(
            store_id=req.store_id,
            member_id=current_member.id,
            bank=req.bank,
            accountName=req.accountName,
            accountNumber=req.accountNumber,
        )
        db.add(request)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")


# ======= 오늘 근무일정 조회 ======= #
@router.post("/work/today", response_model=WrokResponse)
async def get_today_work(
    req: WeeklyWorkRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    today_work = db.query(StoreMembersWork).filter(
        StoreMembersWork.employee_id == employee.id,
        StoreMembersWork.work_date == today
    ).first()

    if not today_work:
        raise HTTPException(status_code=404, detail="오늘 예정된 근무 일정이 없습니다.")

    return today_work


# ======= 근무 상태 조회 ======= #
@router.post("/work/status")
async def get_work_status(
    req: WeeklyWorkRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    log = db.query(StoreMembersWorkLog).filter(
        StoreMembersWorkLog.employee_id == employee.id,
        StoreMembersWorkLog.work_date == today
    ).order_by(StoreMembersWorkLog.work_date.desc()).first()

    return {"status": log.status if log else None}


# ======= 체크리스트 조회 ======= #
@router.post("/todo", response_model=list[TodoListResponse])
async def get_todo_list(
    req: TodoListRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    common = db.query(StoreMembersTodo).filter(
        StoreMembersTodo.store_id == req.store_id,
        StoreMembersTodo.type == "public"
    ).order_by(asc(StoreMembersTodo.is_achieved)).all()

    personal = db.query(StoreMembersTodo).filter(
        StoreMembersTodo.store_id == req.store_id,
        StoreMembersTodo.employee_id == employee.id,
        StoreMembersTodo.created_at == today
    ).order_by(asc(StoreMembersTodo.is_achieved)).all()

    todo_list = sorted(common + personal, key=lambda x: x.is_achieved)
    return todo_list


# ======= 체크리스트 상태변경 ======= #
@router.post("/todo/modify", response_model=list[TodoListResponse])
async def modify_todo(
    req: TodoListModifyRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    try:
        todo = db.query(StoreMembersTodo).filter(
            StoreMembersTodo.store_id == req.store_id,
            StoreMembersTodo.id == req.id
        ).first()
        if not todo:
            raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")

        todo.is_achieved = not todo.is_achieved
        db.commit()

        common = db.query(StoreMembersTodo).filter(
            StoreMembersTodo.store_id == req.store_id,
            StoreMembersTodo.type == "public"
        ).order_by(asc(StoreMembersTodo.is_achieved)).all()

        personal = db.query(StoreMembersTodo).filter(
            StoreMembersTodo.store_id == req.store_id,
            StoreMembersTodo.employee_id == employee.id,
            StoreMembersTodo.created_at == today
        ).order_by(asc(StoreMembersTodo.is_achieved)).all()

        return sorted(common + personal, key=lambda x: x.is_achieved)

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")


# ======= 공지사항 ======= #
@router.post("/notice", response_model=list[NoticeResponse])
async def get_notice_list(req: NoticeRequestSchemas, db: Session = Depends(get_db)):
    notices = (
        db.query(StoreCommunity, Member.name)
        .join(StoreMembers, StoreMembers.id == StoreCommunity.employee_id)
        .join(Member, Member.id == StoreMembers.member_id)
        .filter(StoreCommunity.store_id == req.store_id, StoreCommunity.category == "공지사항")
        .order_by(asc(StoreCommunity.created_at))
        .limit(2)
        .all()
    )
    return [{"id": n.id, "writer": name, "title": n.title, "created_at": n.created_at} for n, name in notices]


# ======= 이번주 근무일정 ======= #
@router.post("/work")
async def get_weekly_work(
    req: WeeklyWorkRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)

    # 이번주 일요일~토요일 범위
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    weekday = today.weekday()  # 0=월 ~ 6=일
    monday = today - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)

    schedules = db.query(StoreMembersWork).filter(
        StoreMembersWork.employee_id == employee.id,
        StoreMembersWork.store_id == req.store_id,
        StoreMembersWork.work_date >= monday,
        StoreMembersWork.work_date <= sunday,
    ).order_by(StoreMembersWork.work_date, StoreMembersWork.part_id).all()

    # 날짜별 그룹핑 (여러 파트 → 하나로)
    from collections import defaultdict
    day_map = {}
    for s in schedules:
        key = s.work_date.isoformat()
        dow = s.work_date.weekday()  # 0=월~6=일
        js_dow = (dow + 1) % 7
        if key not in day_map:
            day_map[key] = {
                "work_date": key,
                "day_of_week": js_dow,
                "work_start": str(s.work_start)[:5] if s.work_start else None,
                "work_end": str(s.work_end)[:5] if s.work_end else None,
                "is_holiday": s.is_holiday,
            }
        else:
            # 더 늦은 퇴근 시간으로 업데이트
            if s.work_end and (day_map[key]["work_end"] is None or s.work_end > datetime.strptime(day_map[key]["work_end"], "%H:%M").time()):
                day_map[key]["work_end"] = str(s.work_end)[:5]

    return list(day_map.values())


# ======= 이번달 급여 미리보기 ======= #
@router.post("/salary/preview")
async def get_salary_preview(
    req: WeeklyWorkRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    year, month = datetime.now(ZoneInfo("Asia/Seoul")).year, datetime.now(ZoneInfo("Asia/Seoul")).month

    logs = db.query(StoreMembersWorkLog).filter(
        StoreMembersWorkLog.employee_id == employee.id,
        StoreMembersWorkLog.store_id == req.store_id,
        StoreMembersWorkLog.end_time.isnot(None),
        extract('year', StoreMembersWorkLog.work_date) == year,
        extract('month', StoreMembersWorkLog.work_date) == month,
    ).all()

    detail = db.query(StoreMembersDetail).filter(
        StoreMembersDetail.store_member_id == employee.id
    ).first()

    if not detail or not detail.hourly_rate:
        raise HTTPException(status_code=404, detail="시급 정보가 없습니다.")

    hourly_rate = detail.hourly_rate
    total_seconds = overtime_seconds = 0

    for log in logs:
        dow_sunday = (log.work_date.weekday() + 1) % 7
        schedule = db.query(StoreMembersWork).filter(
            StoreMembersWork.employee_id == employee.id,
            StoreMembersWork.store_id == req.store_id,
            StoreMembersWork.day_of_week == dow_sunday,
        ).first()
        if not schedule:
            continue

        sched_start = datetime.combine(log.work_date, schedule.work_start)
        sched_end = datetime.combine(log.work_date, schedule.work_end)
        actual_end = datetime.combine(log.work_date, log.end_time)
        ot_threshold = sched_end + timedelta(minutes=30)

        total_seconds += (sched_end - sched_start).total_seconds()
        if actual_end > ot_threshold:
            overtime_seconds += (actual_end - ot_threshold).total_seconds()

    total_hours = total_seconds / 3600
    overtime_hours = overtime_seconds / 3600
    estimated_salary = int(total_hours * hourly_rate) + int(overtime_hours * hourly_rate * 0.5)

    return {"total_hours": round(total_hours, 2), "estimated_salary": estimated_salary}


# ======= 일정 변경 요청 내역 ======= #
@router.get("/schedule/change")
def get_schedule_changes(
    store_id: int,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, store_id, current_member.id)

    requests = db.query(ScheduleChangeRequest).filter(
        ScheduleChangeRequest.store_id == store_id,
        ScheduleChangeRequest.employee_id == employee.id,
        ScheduleChangeRequest.is_deleted == False,
    ).order_by(ScheduleChangeRequest.created_at.desc()).all()

    return [{
        "id": r.id,
        "type": r.type,
        "status": r.status,
        "origin_date": str(r.origin_date) if r.origin_date else None,
        "origin_start": str(r.origin_start)[:5] if r.origin_start else None,
        "origin_end": str(r.origin_end)[:5] if r.origin_end else None,
        "desired_date": str(r.desired_date),
        "desired_start": str(r.desired_start)[:5] if r.desired_start else None,
        "desired_end": str(r.desired_end)[:5] if r.desired_end else None,
        "reason": r.reason,
        "created_at": str(r.created_at),
    } for r in requests]


# ======= 요일별 전체 직원 스케줄 ======= #
@router.get("/schedule/{store_id}/detail")
def get_all_schedule_detail(store_id: int, year: int, month: int, day: int, db: Session = Depends(get_db)):
    target_date = date(year, month, day)

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part),
        joinedload(StoreMembersWork.employee).joinedload(StoreMembers.member)
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.work_date == target_date,
        StoreMembersWork.is_holiday == False,
    ).all()

    part_map: dict = {}
    for s in schedules:
        if not s.part:
            continue
        pid = s.part.id
        if pid not in part_map:
            part_map[pid] = {
                "part_id": pid,
                "part_name": s.part.name,
                "start_time": str(s.part.start_time)[:5],
                "end_time": str(s.part.end_time)[:5],
                "employees": []
            }
        part_map[pid]["employees"].append({"id": s.employee.id, "name": s.employee.member.name})

    return sorted(part_map.values(), key=lambda x: x["start_time"])


# ======= 월별 개인 스케줄 ======= #
@router.get("/schedule/{store_id}")
async def get_schedule(
    store_id: int,
    year: int,
    month: int,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, store_id, current_member.id)

    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part)
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.employee_id == employee.id,
        StoreMembersWork.work_date >= start_date,
        StoreMembersWork.work_date <= end_date,
    ).all()

    return {
        f"{s.work_date.year}-{s.work_date.month}-{s.work_date.day}": {
            "work_start": str(s.work_start)[:5] if s.work_start else None,
            "work_end": str(s.work_end)[:5] if s.work_end else None,
            "is_holiday": s.is_holiday,
            "part_name": s.part.name if s.part else None,
        }
        for s in schedules
    }

# ======= 월별 전체 직원 스케줄 ======= #
@router.get("/schedule/{store_id}/all")
def get_all_schedule(store_id: int, year: int, month: int, db: Session = Depends(get_db)):
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part)
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.is_holiday == False,
        StoreMembersWork.work_date >= start_date,
        StoreMembersWork.work_date <= end_date,
    ).all()

    summary: dict = {}
    for s in schedules:
        key = f"{s.work_date.year}-{s.work_date.month}-{s.work_date.day}"
        if key not in summary:
            summary[key] = {}
        if s.part:
            summary[key][s.part.name] = summary[key].get(s.part.name, 0) + 1

    return summary

@router.delete("/schedule/change/{id}")
def delete_schedule_change(
    id: int,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    change = db.query(ScheduleChangeRequest).filter(ScheduleChangeRequest.id == id).first()
    if not change:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

    # 본인 요청인지 확인
    employee = db.query(StoreMembers).filter(
        StoreMembers.id == change.employee_id,
        StoreMembers.member_id == current_member.id
    ).first()
    if not employee:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    change.is_deleted = True
    db.commit()
    return {"success": True}

# ======= 마감 보고 ======= #
@router.post("/closing-report")
def add_closing_report(
    req: ClosingReportRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    saved_image_path = None

    if req.receipt_image_url and req.receipt_image_url.startswith("data:image"):
        try:
            header, encoded = req.receipt_image_url.split(",", 1)
            ext = header.split("/")[1].split(";")[0]
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(CLOSING_UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(encoded))
            saved_image_path = f"/uploads/closing/{filename}"
        except Exception as e:
            print(f"이미지 저장 실패: {e}")

    new_report = DailyClosingReport(
        store_id=req.store_id,
        employee_id=employee.id,
        report_date=req.report_date,
        card_sales=req.card_sales,
        cash_sales=req.cash_sales,
        transfer_sales=req.transfer_sales,
        gift_sales=req.gift_sales,
        discount_amount=req.discount_amount,
        refund_amount=req.refund_amount,
        cash_on_hand=req.cash_on_hand,
        cash_shortage_type=req.cash_shortage_type,
        cash_shortage_amount=req.cash_shortage_amount,
        receipt_image_url=saved_image_path,
        manager_note=req.manager_note,
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return {"message": "마감 보고가 완료되었습니다.", "id": new_report.id}


@router.get("/closing-report/check")
def check_closing_status(store_id: int, db: Session = Depends(get_db)):
    exists = db.query(DailyClosingReport).filter(
        DailyClosingReport.store_id == store_id,
        DailyClosingReport.report_date == date.today()
    ).first()
    return {"is_completed": bool(exists)}


# ======= 마이페이지 ======= #
@router.get("/mypage")
def get_my_info(
    store_id: int,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, store_id, current_member.id)

    result = (
        db.query(StoreMembers, Member, StoreMembersDetail)
        .join(Member, StoreMembers.member_id == Member.id)
        .outerjoin(StoreMembersDetail, StoreMembersDetail.store_member_id == StoreMembers.id)
        .filter(StoreMembers.id == employee.id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="직원 정보를 찾을 수 없습니다.")

    store_member, member, detail = result
    store = db.query(Store).filter(Store.id == store_id).first()

    age = None
    if member.birth:
        today = date.today()
        age = today.year - member.birth.year - (
            (today.month, today.day) < (member.birth.month, member.birth.day)
        )

    days_since_joined = (date.today() - store_member.joined_at.date()).days + 1

    day_names = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}

    parts = db.query(StorePart).filter(StorePart.store_id == store_id).order_by(StorePart.start_time).all()

    schedules = (
        db.query(StoreMembersWork, StorePart)
        .outerjoin(StorePart, StoreMembersWork.part_id == StorePart.id)
        .filter(
            StoreMembersWork.employee_id == employee.id,
            StoreMembersWork.store_id == store_id,
            StoreMembersWork.is_holiday == False,
            StoreMembersWork.part_id.isnot(None),
        )
        .order_by(StoreMembersWork.work_date, StoreMembersWork.part_id)
        .all()
    )

    day_map = defaultdict(lambda: {"day": "", "time": "", "tags": []})

    for work, part in schedules:
        if not work.work_start or not work.work_end:
            continue

        key = work.work_date.weekday() + 1

        if not day_map[key]["day"]:
            day_map[key]["day"] = day_names[key]
            day_map[key]["time"] = f"{work.work_start.strftime('%H:%M')} ~ {work.work_end.strftime('%H:%M')}"
        else:
            current_end = day_map[key]["time"].split(" ~ ")[1]
            new_end = work.work_end.strftime('%H:%M')
            if new_end > current_end:
                start = day_map[key]["time"].split(" ~ ")[0]
                day_map[key]["time"] = f"{start} ~ {new_end}"

        for p in parts:
            if work.work_start < p.end_time and work.work_end > p.start_time:
                if p.name not in day_map[key]["tags"]:
                    day_map[key]["tags"].append(p.name)

    return {
        "name": member.name,
        "birth": member.birth.strftime("%Y.%m.%d") if member.birth else None,
        "age": age,
        "gender": "남자" if member.gender == "male" else "여자" if member.gender == "female" else None,
        "phone": member.phone,
        "image_url": store_member.image_url,
        "bank": store_member.bank,
        "account_number": store_member.accountNumber,
        "joined_at": store_member.joined_at.strftime("%Y.%m.%d"),
        "days_since_joined": days_since_joined,
        "store_name": store.name if store else None,
        "role": store_member.role,
        "employee_type": detail.employee_type if detail else None,
        "salary_cycle": detail.salary_cycle if detail else None,
        "salary_day": detail.salary_day if detail else None,
        "hourly_rate": detail.hourly_rate if detail else None,
        "is_probation": detail.is_probation if detail else False,
        "income_tax": detail.income_tax if detail else None,
        "local_income_tax": detail.local_income_tax if detail else None,
        "national_pension_tax": detail.national_pension_tax if detail else None,
        "health_insurance_tax": detail.health_insurance_tax if detail else None,
        "long_term_care_tax": detail.long_term_care_tax if detail else None,
        "employment_insurance_tax": detail.employment_insurance_tax if detail else None,
        "industrial_accident_tax": detail.industrial_accident_tax if detail else None,
        "resume": detail.resume if detail else None,
        "employment_contract": detail.employment_contract if detail else None,
        "health_certificate": detail.health_certificate if detail else None,
        "schedule": [day_map[k] for k in sorted(day_map.keys())],
    }

@router.post("/mypage/edit")
async def edit_my_info(
    name: str = Form(...),
    bank: str = Form(...),
    account_number: str = Form(...),
    image: Optional[UploadFile] = File(None),
    original_image_url: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
    employment_contract: Optional[UploadFile] = File(None),
    health_certificate: Optional[UploadFile] = File(None),
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = db.query(StoreMembers).filter(StoreMembers.member_id == current_member.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    detail = db.query(StoreMembersDetail).filter(StoreMembersDetail.store_member_id == employee.id).first()

    employee.bank = bank
    employee.accountNumber = account_number

    if image:
        if original_image_url:
            old_path = original_image_url.lstrip("/")
            if os.path.exists(old_path):
                os.remove(old_path)
        employee.image_url = await save_file(image, PROFILE_UPLOAD_DIR)

    if resume:
        detail.resume = await save_file(resume, DOCUMENT_UPLOAD_DIR)
    if employment_contract:
        detail.employment_contract = await save_file(employment_contract, DOCUMENT_UPLOAD_DIR)
    if health_certificate:
        detail.health_certificate = await save_file(health_certificate, DOCUMENT_UPLOAD_DIR)

    try:
        db.commit()
        db.refresh(employee)
        return {"message": "수정되었습니다."}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="서버 오류로 인해 정보 수정에 실패했습니다.")
    
@router.delete("/profile/document")
async def delete_document(
    data: dict,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    field = data.get("field")
    allowed = {"resume", "employment_contract", "health_certificate"}
    if field not in allowed:
        raise HTTPException(status_code=400)

    store_member = db.query(StoreMembers).filter(
        StoreMembers.member_id == current_member.id
    ).first()
    if not store_member:
        raise HTTPException(status_code=404)

    detail = db.query(StoreMembersDetail).filter(
        StoreMembersDetail.store_member_id == store_member.id
    ).first()
    if not detail:
        raise HTTPException(status_code=404)

    setattr(detail, field, None)
    db.commit()
    return {"ok": True}


# ======= 출퇴근/휴게 공통 헬퍼 ======= #
def get_today_worklog(db: Session, employee_id: int, status: str = None, require_no_end: bool = True):
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    q = db.query(StoreMembersWorkLog).filter(
        StoreMembersWorkLog.employee_id == employee_id,
        StoreMembersWorkLog.work_date == today,
    )
    if status:
        q = q.filter(StoreMembersWorkLog.status == status)
    if require_no_end:
        q = q.filter(StoreMembersWorkLog.end_time.is_(None))
    return q.first()


# ======= 출근 ======= #
@router.post("/work/clock-in")
def add_clock_in(
    body: WorkTimeRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, body.store_id, current_member.id)
    now = datetime.now(ZoneInfo("Asia/Seoul"))

    worklog = StoreMembersWorkLog(
        store_id=body.store_id,
        employee_id=employee.id,
        work_date=now.date(),
        start_time=now,
        status="working",
    )
    db.add(worklog)
    db.commit()


# ======= 퇴근 ======= #
@router.post("/work/clock-out")
def add_clock_out(
    body: WorkTimeRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, body.store_id, current_member.id)
    worklog = get_today_worklog(db, employee.id)

    if not worklog:
        raise HTTPException(status_code=404, detail="출근 정보를 찾을 수 없습니다.")

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    worklog.end_time = now
    worklog.status = "off_work"
    if worklog.break_end_time is None:
        worklog.break_end_time = now
    db.commit()


# ======= 휴게 시작 ======= #
@router.post("/work/break-start")
def add_break_start(
    body: WorkTimeRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, body.store_id, current_member.id)
    worklog = get_today_worklog(db, employee.id, status="working")

    if not worklog:
        raise HTTPException(status_code=404, detail="출근 정보를 찾을 수 없습니다.")

    worklog.break_start_time = datetime.now(ZoneInfo("Asia/Seoul"))
    worklog.status = "on_break"
    db.commit()


# ======= 휴게 종료 ======= #
@router.post("/work/break-end")
def add_break_end(
    body: WorkTimeRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, body.store_id, current_member.id)

    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    worklog = db.query(StoreMembersWorkLog).filter(
        StoreMembersWorkLog.employee_id == employee.id,
        StoreMembersWorkLog.work_date == today,
        StoreMembersWorkLog.status == "on_break",
        StoreMembersWorkLog.end_time.is_(None),
        StoreMembersWorkLog.break_end_time.is_(None),
    ).first()

    if not worklog:
        raise HTTPException(status_code=404, detail="휴게 중인 출근 정보를 찾을 수 없습니다.")

    worklog.break_end_time = datetime.now(ZoneInfo("Asia/Seoul"))
    worklog.status = "working"
    db.commit()


# ======= 출근 기록 조회 ======= #
@router.post("/work/logs")
async def get_work_logs(
    req: WorkMonthRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    logs = db.query(StoreMembersWorkLog).filter(
        StoreMembersWorkLog.employee_id == employee.id,
        StoreMembersWorkLog.store_id == req.store_id,
        extract('year', StoreMembersWorkLog.work_date) == req.year,
        extract('month', StoreMembersWorkLog.work_date) == req.month,
    ).all()

    schedules_raw = db.query(StoreMembersWork).filter(
        StoreMembersWork.employee_id == employee.id,
        StoreMembersWork.store_id == req.store_id,
        extract('year', StoreMembersWork.work_date) == req.year,
        extract('month', StoreMembersWork.work_date) == req.month,
    ).all()

    # 파트 목록 조회
    parts = db.query(StorePart).filter(StorePart.store_id == req.store_id).order_by(StorePart.start_time).all()

    # 실제 출퇴근 시간 기준으로 걸치는 파트 태그 계산
    def get_tags(start_time, end_time):
        if not start_time or not end_time:
            return []
        tags = []
        for part in parts:
            if start_time < part.end_time and end_time > part.start_time:
                tags.append(part.name)
        return tags

    sched_map = {}
    for s in schedules_raw:
        key = str(s.work_date)
        if key not in sched_map:
            sched_map[key] = {
                "work_date": s.work_date,
                "is_holiday": s.is_holiday or False,
                "work_start": s.work_start,
                "work_end": s.work_end,
            }
        else:
            if s.work_start and (sched_map[key]["work_start"] is None or s.work_start < sched_map[key]["work_start"]):
                sched_map[key]["work_start"] = s.work_start
            if s.work_end and (sched_map[key]["work_end"] is None or s.work_end > sched_map[key]["work_end"]):
                sched_map[key]["work_end"] = s.work_end

    log_map = {str(l.work_date): l for l in logs}
    result = []

    for key, sched in sched_map.items():
        if sched["work_date"] > today:
            continue
        log = log_map.get(key)
        sched_start = str(sched["work_start"]) if sched["work_start"] else None
        sched_end = str(sched["work_end"]) if sched["work_end"] else None

        if log:
            result.append({
                "work_date": sched["work_date"],
                "start_time": str(log.start_time) if log.start_time else None,
                "end_time": str(log.end_time) if log.end_time else None,
                "break_start_time": str(log.break_start_time) if log.break_start_time else None,
                "break_end_time": str(log.break_end_time) if log.break_end_time else None,
                "status": log.status,
                "is_holiday": sched["is_holiday"],
                "sched_start": sched_start,
                "sched_end": sched_end,
                "tags": get_tags(log.start_time, log.end_time),  # 추가
            })
        else:
            result.append({
                "work_date": sched["work_date"],
                "start_time": None, "end_time": None,
                "break_start_time": None, "break_end_time": None,
                "status": "absent" if not sched["is_holiday"] else None,
                "is_holiday": sched["is_holiday"],
                "sched_start": sched_start,
                "sched_end": sched_end,
                "tags": [],  # 추가
            })
    return result


# ======= 출근 기록 수정 요청 ======= #
@router.post("/worklog/request")
async def work_log_change_request(
    req: WorkChangeRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, req.store_id, current_member.id)

    is_break = req.type == "휴게 시간 변경"
    is_missing = req.type == "근무 누락"

    if is_break and db.query(WorkLogChangeRequest).filter(
        WorkLogChangeRequest.date == req.date,
        WorkLogChangeRequest.type == "휴게 시간 변경",
        WorkLogChangeRequest.status == "pending"
    ).first():
        raise HTTPException(status_code=409, detail="이미 해당 날짜에 휴게 시간 변경 요청이 존재합니다.")

    if is_missing and db.query(WorkLogChangeRequest).filter(
        WorkLogChangeRequest.date == req.date,
        WorkLogChangeRequest.type == "근무 누락",
        WorkLogChangeRequest.status == "pending"
    ).first():
        raise HTTPException(status_code=409, detail="이미 해당 날짜에 근무 누락 수정 요청이 존재합니다.")

    new_request = WorkLogChangeRequest(
        store_id=req.store_id,
        employee_id=employee.id,
        type=req.type,
        date=req.date,
        origin_start=None if is_break else req.origin_start,
        origin_end=None if is_break else req.origin_end,
        desired_start=None if is_break else req.desired_start,
        desired_end=None if is_break else req.desired_end,
        desired_break=req.desired_break,
        reason=req.reason,
    )
    db.add(new_request)
    db.commit()


# ======= 출근 기록 수정내역 조회 ======= #
@router.get("/worklog/request")
async def get_work_log_requests(
    store_id: int,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = get_employee_or_404(db, store_id, current_member.id)

    return db.query(WorkLogChangeRequest).filter(
        WorkLogChangeRequest.employee_id == employee.id,
        WorkLogChangeRequest.store_id == store_id,
    ).order_by(WorkLogChangeRequest.created_at.desc()).all()


# ======= 변경된 스케줄 상세 ======= #
@router.get("/schedule-change/{id}")
async def get_schedule_change(id: int, db: Session = Depends(get_db)):
    change = db.query(ScheduleChangeRequest).filter(ScheduleChangeRequest.id == id).first()
    if not change:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

    work = db.query(StoreMembersWork).filter(
        StoreMembersWork.work_date == change.origin_date,
        StoreMembersWork.work_start == change.origin_start,
        StoreMembersWork.work_end == change.origin_end,
    ).first()

    part = db.query(StorePart).filter(StorePart.id == work.part_id).first() if work else None

    return {
        "type": change.type,
        "origin_date": change.origin_date,
        "origin_start": change.origin_start,
        "origin_end": change.origin_end,
        "desired_date": change.desired_date,
        "desired_start": change.desired_start,
        "desired_end": change.desired_end,
        "part_name": part.name if part else None,
    }


# ======= 추가된 스케줄 상세 ======= #
@router.get("/schedule-work/{id}")
async def get_schedule_work(id: int, db: Session = Depends(get_db)):
    work = db.query(StoreMembersWork).filter(StoreMembersWork.id == id).first()
    if not work:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

    part = db.query(StorePart).filter(StorePart.id == work.part_id).first()

    return {
        "work_date": work.work_date,
        "work_start": work.work_start,
        "work_end": work.work_end,
        "part_name": part.name if part else None,
    }