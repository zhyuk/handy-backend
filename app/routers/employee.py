import os
import httpx
import json
import base64
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import asc, extract, text
from sqlalchemy.orm import Session, joinedload
from pathlib import Path
from dotenv import load_dotenv
import uuid
from datetime import datetime, timedelta, date
from calendar import monthrange

from models import Member, Store, StoreMap, MemberRequest, StoreMembers, StoreMembersTodo, StoreMembersWork, StoreCommunity, StoreMembersWorkLog, StoreMembersDetail, ScheduleChangeRequest, DailyClosingReport
from database import get_db
from schemas.employee import VerifyCode, MemberRequestSchemas, TodoListRequest, TodoListResponse, TodoListModifyRequest, WorkRequest, WrokResponse, NoticeResponse, WeeklyWorkRequest, WeeklyWorkResponse, MonthlyScheduleRequest, ClosingReportRequest
from utils.uitls import format_phone_number, get_coords_from_address


router = APIRouter(prefix="/api/employee", tags=["직원유형"])

CLOSING_UPLOAD_DIR = "uploads/closing/"
if not os.path.exists(CLOSING_UPLOAD_DIR):
    os.makedirs(CLOSING_UPLOAD_DIR)

# ======= 매장코드 조회 ======= #
@router.post("/verify-code")
async def verify_store_code(req: VerifyCode, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장코드 조회 API
    ----------------------------------------
    """
    # print(req)

    storeInfo = db.query(Store).filter(Store.code == req.code).first()

    # 일치하는 매장이 존재하지 않을 경우
    if not storeInfo:
        raise HTTPException(status_code=404, detail="조회되지 않는 매장 코드에요")
    
    storeMap = db.query(StoreMap).filter(storeInfo.id == StoreMap.store_id).first()
    
    # 세부주소가 존재할 경우 병합
    address_parts = [storeInfo.address, storeInfo.addressDetail]
    full_address = " ".join([part for part in address_parts if part])

    if not storeMap:
        lat, lng = await get_coords_from_address(storeInfo.address)

        storeMap = StoreMap(
            store_id = storeInfo.id,
            lat = lat,
            lng = lng
        )

        db.add(storeMap)
        db.commit()
        db.refresh(storeMap)

    return_info = {
        "id": storeInfo.id,
        "name": storeInfo.name,
        "address": full_address,
        "phone": format_phone_number(storeInfo.number),
        "lat": float(storeMap.lat),
        "lng": float(storeMap.lng)
    }

    return return_info
# ======= 매장코드 조회 ======= #

# ======= 가입신청 하기 ======= #
@router.post("/member/request")
async def add_member_request(req: MemberRequestSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    직원 가입신청 API
    ----------------------------------------
    """
    # print(req)

    try:
        request = MemberRequest(
            store_id = req.store_id,
            member_id = 1,
            bank = req.bank,
            accountName = req.accountName,
            accountNumber = req.accountNumber
        )

        db.add(request)
        db.commit()
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")
# ======= 가입신청 하기 ======= #

# ======= 본인 근무일정 조회 ======= #
@router.post("/work/today", response_model=WrokResponse)
async def get_today_work(req: WorkRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    개인별 근무일정 조회 API 

    * 오늘 기준 근무일정 조회
    ----------------------------------------
    """
    # print(req)
    today_weekday = datetime.now().weekday()
    print("today_weekday:" , today_weekday)

    try:
        today_work = db.query(StoreMembersWork).filter(StoreMembersWork.employee_id == req.employee_id, StoreMembersWork.day_of_week == today_weekday).first()

        if not today_work:
            raise HTTPException(status_code=404, detail="오늘 예정된 근무 일정이 없습니다.")
        
        return today_work
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="근무 일정 조회 중 서버 오류가 발생했습니다.")
# ======= 본인 근무일정 조회 ======= #

# ======= 체크리스트 조회 ======= #
@router.post("/todo", response_model=list[TodoListResponse])
async def get_todo_list(req: TodoListRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    체크리스트 조회 API
    ----------------------------------------
    """
    print(req)

    try:
        todoList = db.query(StoreMembersTodo).filter(StoreMembersTodo.store_id == 1, StoreMembersTodo.employee_id == 1).order_by(asc(StoreMembersTodo.is_achieved)).all()
        

        return todoList
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")
# ======= 체크리스트 조회 ======= #    

# ======= 체크리스트 상태변경 ======= #
@router.post("/todo/modify", response_model=list[TodoListResponse])
async def modify_todo(req: TodoListModifyRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    체크리스트 상태변경 API
    ----------------------------------------
    """
    print(req)

    try:
        modify_todo = db.query(StoreMembersTodo).filter(StoreMembersTodo.store_id == req.store_id, StoreMembersTodo.id == req.id).first()

        modify_todo.is_achieved = not modify_todo.is_achieved

        db.add(modify_todo)
        db.commit()

        todoList = db.query(StoreMembersTodo).filter(StoreMembersTodo.store_id == 1, StoreMembersTodo.employee_id == 1).order_by(asc(StoreMembersTodo.is_achieved)).all()

        return todoList
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")
# ======= 체크리스트 상태변경 ======= #

# ======= 공지사항 리턴 ======= #
@router.post("/notice", response_model=list[NoticeResponse])
async def get_notice_list(req: TodoListRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장별 공지사항 리턴 API

    * 최신 2개 공지사항만 리턴
    ----------------------------------------
    """
    # print(req)

    try:
        notices = (
            db.query(StoreCommunity, Member.name)
            .join(StoreMembers, StoreMembers.id == StoreCommunity.employee_id)
            .join(Member, Member.id == StoreMembers.member_id)
            .filter(StoreCommunity.store_id == req.store_id, StoreCommunity.category == "공지사항")
            .order_by(asc(StoreCommunity.created_at))
            .limit(2)
            .all()
        )

        result = []
        for notice, author_name in notices:
            result.append({
                "id": notice.id,
                "writer": author_name,
                "title": notice.title,
                "created_at": notice.created_at,
            })

        return result

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="공지사항 로드 중 서버 오류가 발생했습니다.")
# ======= 공지사항 리턴 ======= #

# ======= 이번주 근무일정 조회 ======= #
@router.post("/work")
async def get_weekly_work(req: WeeklyWorkRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    이번주 근무일정 조회 API
    ----------------------------------------
    """
    print("req:", req)

    try:
        weeklyWork = db.query(StoreMembersWork).filter(StoreMembersWork.employee_id == req.employee_id, StoreMembersWork.store_id == req.store_id).all()

        return weeklyWork

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="공지사항 로드 중 서버 오류가 발생했습니다.")
# ======= 이번주 근무일정 조회 ======= #

# ======= 이번달 급여 조회 ======= #
@router.post("/salary/preview")
async def get_weekly_work(req: WeeklyWorkRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    이번달 급여 조회 API

    * 근무시간 기준 실시간 반영
    ----------------------------------------
    """
    print("req:", req)

    req.employee_id = 1
    req.store_id = 1

    try:
        year = datetime.now().year
        month = datetime.now().month

        # 이번달 완료된 근무 로그 조회 (end_time이 있는 것만)
        logs = db.query(StoreMembersWorkLog).filter(
            StoreMembersWorkLog.employee_id == req.employee_id,
            StoreMembersWorkLog.store_id == req.store_id,
            StoreMembersWorkLog.end_time.isnot(None),
            extract('year', StoreMembersWorkLog.work_date) == year,
            extract('month', StoreMembersWorkLog.work_date) == month,
        ).all()

        # 시급 조회
        detail = db.query(StoreMembersDetail).filter(
            StoreMembersDetail.store_member_id == req.employee_id
        ).first()

        if not detail or not detail.hourly_rate:
            raise HTTPException(status_code=404, detail="시급 정보가 없습니다.")

        hourly_rate = detail.hourly_rate

        total_seconds = 0
        overtime_seconds = 0

        for log in logs:
            dow = log.work_date.weekday()
            dow_sunday_based = (dow + 1) % 7

            schedule = db.query(StoreMembersWork).filter(
                StoreMembersWork.employee_id == req.employee_id,
                StoreMembersWork.store_id == req.store_id,
                StoreMembersWork.day_of_week == dow_sunday_based,
            ).first()

            if not schedule:
                continue

            scheduled_start = datetime.combine(log.work_date, schedule.work_start)
            scheduled_end = datetime.combine(log.work_date, schedule.work_end)
            actual_end = datetime.combine(log.work_date, log.end_time)
            overtime_threshold = scheduled_end + timedelta(minutes=30)

            # 기본 근무시간은 예정 기준으로 고정
            base_seconds = (scheduled_end - scheduled_start).total_seconds()
            total_seconds += base_seconds

            # 초과근무는 예정 퇴근 +30분 이후 실제 퇴근까지
            if actual_end > overtime_threshold:
                overtime_seconds += (actual_end - overtime_threshold).total_seconds()

        total_hours = total_seconds / 3600
        overtime_hours = overtime_seconds / 3600

        # 기본 급여 + 초과 수당 (시급의 0.5배 추가)
        base_salary = int(total_hours * hourly_rate)
        overtime_pay = int(overtime_hours * hourly_rate * 0.5)
        estimated_salary = base_salary + overtime_pay

        return {
            "total_hours": round(total_hours, 2),
            "estimated_salary": estimated_salary,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="급여 조회 중 오류가 발생했습니다.")
# ======= 이번주 근무일정 조회 ======= #

# ======= 일정 조회 ======= #
@router.get("/schedule/change")
def get_schedule_changes(store_id: int, employee_id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    일정 변경 요청 내역 조회 API
    ----------------------------------------
    """
        
    requests = (
        db.query(ScheduleChangeRequest)
        .filter(
            ScheduleChangeRequest.store_id == store_id,
            ScheduleChangeRequest.employee_id == employee_id,
            ScheduleChangeRequest.is_deleted == False,
        )
        .order_by(ScheduleChangeRequest.created_at.desc())
        .all()
    )

    result = []
    for r in requests:
        result.append({
            "id": r.id,
            "type": r.type,  # "schedule_change" | "vacation"
            "status": r.status,  # "pending" | "approved" | "rejected"
            "origin_date": str(r.origin_date) if r.origin_date else None,
            "origin_start": str(r.origin_start)[:5] if r.origin_start else None,
            "origin_end": str(r.origin_end)[:5] if r.origin_end else None,
            "desired_date": str(r.desired_date),
            "desired_start": str(r.desired_start)[:5] if r.desired_start else None,
            "desired_end": str(r.desired_end)[:5] if r.desired_end else None,
            "reason": r.reason,
            "created_at": str(r.created_at),
        })

    return result

@router.get("/schedule/{store_id}/detail")
def get_all_schedule_detail(store_id: int, year: int, month: int, day: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    요일별 전체 직원 스케줄 조회 API
    ----------------------------------------
    """
    print(year, month, day)

    target_date = date(year, month, day)

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part),
        joinedload(StoreMembersWork.employee).joinedload(StoreMembers.member)  # ← 체인
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.work_date == target_date,
        StoreMembersWork.is_holiday == False,
    ).all()

    # part_id 기준으로 그룹핑
    part_map: dict = {}
    for s in schedules:
        if not s.part:
            continue
        pid = s.part.id
        if pid not in part_map:
            part_map[pid] = {
                "part_id": s.part.id,
                "part_name": s.part.name,
                "start_time": str(s.part.start_time)[:5],
                "end_time": str(s.part.end_time)[:5],
                "employees": []
            }
        part_map[pid]["employees"].append({
            "id": s.employee.id,
            "name": s.employee.member.name
        })

    # start_time 기준 정렬
    return sorted(part_map.values(), key=lambda x: x["start_time"])

@router.get("/schedule/{store_id}/{employee_id}")
async def get_schedule(store_id: int, employee_id: int, year: int, month: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    월별 개인 스케줄 조회 API
    ----------------------------------------
    """

    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part)  # StorePart relationship
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.employee_id == employee_id,
        StoreMembersWork.work_date >= start_date,
        StoreMembersWork.work_date <= end_date,
    ).all()

    result = {}
    for s in schedules:
        key = f"{s.work_date.year}-{s.work_date.month}-{s.work_date.day}"
        result[key] = {
            "work_start": str(s.work_start)[:5] if s.work_start else None,
            "work_end": str(s.work_end)[:5] if s.work_end else None,
            "is_holiday": s.is_holiday,
            "part_name": s.part.name if s.part else None
        }
    return result

@router.get("/schedule/{store_id}")
def get_all_schedule(store_id: int, year: int, month: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    월별 전체 직원 스케줄 조회 API
    ----------------------------------------
    """

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
            part_name = s.part.name
            summary[key][part_name] = summary[key].get(part_name, 0) + 1

    return summary
# ======= 일정 조회 ======= #

@router.post("/salary/preview")
async def get_weekly_work(req: WeeklyWorkRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    이번달 급여 조회 API

    * 근무시간 기준 실시간 반영
    ----------------------------------------
    """
    print("req:", req)

    req.employee_id = 1
    req.store_id = 1

    try:
        year = datetime.now().year
        month = datetime.now().month

        # 이번달 완료된 근무 로그 조회 (end_time이 있는 것만)
        logs = db.query(StoreMembersWorkLog).filter(
            StoreMembersWorkLog.employee_id == req.employee_id,
            StoreMembersWorkLog.store_id == req.store_id,
            StoreMembersWorkLog.end_time.isnot(None),
            extract('year', StoreMembersWorkLog.work_date) == year,
            extract('month', StoreMembersWorkLog.work_date) == month,
        ).all()

        # 시급 조회
        detail = db.query(StoreMembersDetail).filter(
            StoreMembersDetail.store_member_id == req.employee_id
        ).first()

        if not detail or not detail.hourly_rate:
            raise HTTPException(status_code=404, detail="시급 정보가 없습니다.")

        hourly_rate = detail.hourly_rate

        total_seconds = 0
        overtime_seconds = 0

        for log in logs:
            dow = log.work_date.weekday()
            dow_sunday_based = (dow + 1) % 7

            schedule = db.query(StoreMembersWork).filter(
                StoreMembersWork.employee_id == req.employee_id,
                StoreMembersWork.store_id == req.store_id,
                StoreMembersWork.day_of_week == dow_sunday_based,
            ).first()

            if not schedule:
                continue

            scheduled_start = datetime.combine(log.work_date, schedule.work_start)
            scheduled_end = datetime.combine(log.work_date, schedule.work_end)
            actual_end = datetime.combine(log.work_date, log.end_time)
            overtime_threshold = scheduled_end + timedelta(minutes=30)

            # 기본 근무시간은 예정 기준으로 고정
            base_seconds = (scheduled_end - scheduled_start).total_seconds()
            total_seconds += base_seconds

            # 초과근무는 예정 퇴근 +30분 이후 실제 퇴근까지
            if actual_end > overtime_threshold:
                overtime_seconds += (actual_end - overtime_threshold).total_seconds()

        total_hours = total_seconds / 3600
        overtime_hours = overtime_seconds / 3600

        # 기본 급여 + 초과 수당 (시급의 0.5배 추가)
        base_salary = int(total_hours * hourly_rate)
        overtime_pay = int(overtime_hours * hourly_rate * 0.5)
        estimated_salary = base_salary + overtime_pay

        return {
            "total_hours": round(total_hours, 2),
            "estimated_salary": estimated_salary,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="급여 조회 중 오류가 발생했습니다.")
# ======= 이번주 근무일정 조회 ======= #

# ======= 일정 조회 ======= #
@router.get("/schedule/change")
def get_schedule_changes(store_id: int, employee_id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    일정 변경 요청 내역 조회 API
    ----------------------------------------
    """
        
    requests = (
        db.query(ScheduleChangeRequest)
        .filter(
            ScheduleChangeRequest.store_id == store_id,
            ScheduleChangeRequest.employee_id == employee_id,
            ScheduleChangeRequest.is_deleted == False,
        )
        .order_by(ScheduleChangeRequest.created_at.desc())
        .all()
    )

    result = []
    for r in requests:
        result.append({
            "id": r.id,
            "type": r.type,  # "schedule_change" | "vacation"
            "status": r.status,  # "pending" | "approved" | "rejected"
            "origin_date": str(r.origin_date) if r.origin_date else None,
            "origin_start": str(r.origin_start)[:5] if r.origin_start else None,
            "origin_end": str(r.origin_end)[:5] if r.origin_end else None,
            "desired_date": str(r.desired_date),
            "desired_start": str(r.desired_start)[:5] if r.desired_start else None,
            "desired_end": str(r.desired_end)[:5] if r.desired_end else None,
            "reason": r.reason,
            "created_at": str(r.created_at),
        })

    return result

@router.get("/schedule/{store_id}/detail")
def get_all_schedule_detail(store_id: int, year: int, month: int, day: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    요일별 전체 직원 스케줄 조회 API
    ----------------------------------------
    """
    print(year, month, day)

    target_date = date(year, month, day)

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part),
        joinedload(StoreMembersWork.employee).joinedload(StoreMembers.member)  # ← 체인
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.work_date == target_date,
        StoreMembersWork.is_holiday == False,
    ).all()

    # part_id 기준으로 그룹핑
    part_map: dict = {}
    for s in schedules:
        if not s.part:
            continue
        pid = s.part.id
        if pid not in part_map:
            part_map[pid] = {
                "part_id": s.part.id,
                "part_name": s.part.name,
                "start_time": str(s.part.start_time)[:5],
                "end_time": str(s.part.end_time)[:5],
                "employees": []
            }
        part_map[pid]["employees"].append({
            "id": s.employee.id,
            "name": s.employee.member.name
        })

    # start_time 기준 정렬
    return sorted(part_map.values(), key=lambda x: x["start_time"])

@router.get("/schedule/{store_id}/{employee_id}")
async def get_schedule(store_id: int, employee_id: int, year: int, month: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    월별 개인 스케줄 조회 API
    ----------------------------------------
    """
    from calendar import monthrange
    from datetime import date

    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    schedules = db.query(StoreMembersWork).options(
        joinedload(StoreMembersWork.part)  # StorePart relationship
    ).filter(
        StoreMembersWork.store_id == store_id,
        StoreMembersWork.employee_id == employee_id,
        StoreMembersWork.work_date >= start_date,
        StoreMembersWork.work_date <= end_date,
    ).all()

    result = {}
    for s in schedules:
        key = f"{s.work_date.year}-{s.work_date.month}-{s.work_date.day}"
        result[key] = {
            "work_start": str(s.work_start)[:5] if s.work_start else None,
            "work_end": str(s.work_end)[:5] if s.work_end else None,
            "is_holiday": s.is_holiday,
            "part_name": s.part.name if s.part else None
        }
    return result

@router.post("/closing-report")
def add_closing_report(req: ClosingReportRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    마감 보고 추가 API
    ----------------------------------------
    """
    
    saved_image_path = None

    # 1. 영수증 이미지 처리 (Base64 -> 파일 저장)
    if req.receipt_image_url and req.receipt_image_url.startswith("data:image"):
        try:
            # base64 데이터 추출 (data:image/png;base64, 이후의 값)
            header, encoded = req.receipt_image_url.split(",", 1)
            # 확장자 추출 (png, jpg 등)
            ext = header.split("/")[1].split(";")[0]
            
            new_filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(CLOSING_UPLOAD_DIR, new_filename)
            
            # 디코딩 후 파일 쓰기
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(encoded))
            
            # DB에 저장될 웹 접근 경로
            saved_image_path = f"/uploads/closing/{new_filename}"
        except Exception as e:
            print(f"이미지 저장 실패: {e}")
            # 이미지 저장 실패가 전체 로직을 멈추게 하고 싶지 않다면 pass, 
            # 엄격하게 처리하려면 HTTPException을 던지세요.

    # 2. DB 객체 생성 및 저장
    new_report = DailyClosingReport(
        store_id=req.store_id,
        employee_id=req.employee_id,
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
        manager_note=req.manager_note
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {"message": "마감 보고가 완료되었습니다.", "id": new_report.id}

@router.get("/closing-report/check")
def check_closing_status(store_id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장의 당일 마감 보고 조회 API

    * 오늘 날짜에 해당 매장의 마감 보고가 있는 경우, True 리턴
    ----------------------------------------
    """
    
    exists = db.query(DailyClosingReport).filter(
        DailyClosingReport.store_id == store_id,
        DailyClosingReport.report_date == date.today()
    ).first()
    
    return {"is_completed": True if exists else False}
# ======= 마감 보고 ======= #