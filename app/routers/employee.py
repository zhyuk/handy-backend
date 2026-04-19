import os
import httpx
import json
import base64
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import asc, extract, text
from sqlalchemy.orm import Session, joinedload, aliased
from pathlib import Path
from dotenv import load_dotenv
import uuid
from datetime import datetime, timedelta, date
from calendar import monthrange
from typing import Optional

from models import Member, Store, StoreMap, MemberRequest, StoreMembers, StoreMembersTodo, StoreMembersWork, StoreCommunity, StoreMembersWorkLog, StoreMembersDetail, ScheduleChangeRequest, DailyClosingReport, WorkLogChangeRequest, StorePart
from database import get_db
from schemas.employee import VerifyCode, MemberRequestSchemas, TodoListRequest, TodoListResponse, TodoListModifyRequest, WorkRequest, WrokResponse, NoticeResponse, WeeklyWorkRequest, WeeklyWorkResponse, MonthlyScheduleRequest, ClosingReportRequest, MyInfoModifyRequest, WorkTimeRequest, WorkMonthRequest, WorkChangeRequest, WorkChangeRequestLogSchemas
from utils.uitls import format_phone_number, get_coords_from_address


router = APIRouter(prefix="/api/employee", tags=["직원유형"])

# 
CLOSING_UPLOAD_DIR = "uploads/closing/"
if not os.path.exists(CLOSING_UPLOAD_DIR):
    os.makedirs(CLOSING_UPLOAD_DIR)

# 프로필사진 보관 폴더
PROFILE_UPLOAD_DIR = "uploads/profile/"
if not os.path.exists(PROFILE_UPLOAD_DIR):
    os.makedirs(PROFILE_UPLOAD_DIR)

# 이력서 / 근로계약서 / 보건증 파일 보관 폴더
DOCUMENT_UPLOAD_DIR = "uploads/documents/"
if not os.path.exists(DOCUMENT_UPLOAD_DIR):
    os.makedirs(DOCUMENT_UPLOAD_DIR)

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
    # today_weekday = datetime.now().weekday() + 1
    # print("today_weekday:" , today_weekday)
    today = datetime.now().date()
    print(datetime.now().date())

    try:
        today_work = db.query(StoreMembersWork).filter(StoreMembersWork.employee_id == req.employee_id, StoreMembersWork.work_date == today).first()

        if not today_work:
            raise HTTPException(status_code=404, detail="오늘 예정된 근무 일정이 없습니다.")
        
        return today_work
    
    except Exception as e:
        # db.rollback()
        raise HTTPException(status_code=500, detail="근무 일정 조회 중 서버 오류가 발생했습니다.")
# ======= 본인 근무일정 조회 ======= #

# ======= 본인 근무 상태 조회 ======= #
@router.post("/work/status")
async def get_work_status(req: WorkRequest, db: Session = Depends(get_db)):
    today = datetime.now().date()
    
    try:
        log = (
            db.query(StoreMembersWorkLog)
            .filter(
                StoreMembersWorkLog.employee_id == req.employee_id,
                StoreMembersWorkLog.work_date == today)
            .order_by(StoreMembersWorkLog.work_date.desc())
            .first()
        )

        if not log:
            return {"status": None}

        return {"status": log.status}  # "working" | "off_work" | "on_break"

    except Exception as e:
        raise HTTPException(status_code=500, detail="근무 상태 조회 중 서버 오류가 발생했습니다.")

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


@router.get("/mypage")
def get_my_info(employee_id: int, store_id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    직원 마이페이지 정보 조회 API

    * employee_id: store_members.id
    * members + store_members + store_members_detail 조인하여 반환
    ----------------------------------------
    """
    print("employee_id : " , employee_id)
    print("store_id : " , store_id)

    result = (
        db.query(StoreMembers, Member, StoreMembersDetail)
        .join(Member, StoreMembers.member_id == Member.id)
        .outerjoin(StoreMembersDetail, StoreMembersDetail.store_member_id == StoreMembers.id)
        .filter(StoreMembers.id == employee_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="직원 정보를 찾을 수 없습니다.")

    store_member, member, detail = result

    store = db.query(Store).filter(Store.id == store_id).first()
    store_name = store.name if store else None

    # 나이 계산
    age = None
    if member.birth:
        today = date.today()
        age = today.year - member.birth.year - (
            (today.month, today.day) < (member.birth.month, member.birth.day)
        )

    # 입사 경과일 계산
    days_since_joined = (date.today() - store_member.joined_at.date()).days + 1

    # 근무 스케줄 조회
    from collections import defaultdict
    day_names = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}

    schedules = (
        db.query(StoreMembersWork, StorePart)
        .outerjoin(StorePart, StoreMembersWork.part_id == StorePart.id)
        .filter(
            StoreMembersWork.employee_id == employee_id,
            StoreMembersWork.store_id == store_id,
            StoreMembersWork.is_holiday == False,
            StoreMembersWork.part_id != None,
        )
        .order_by(StoreMembersWork.day_of_week, StoreMembersWork.part_id)
        .all()
    )

    day_map = defaultdict(lambda: {"day": "", "time": "", "tags": []})
    for work, part in schedules:
        if work.work_start and work.work_end:
            key = work.day_of_week
            if not day_map[key]["day"]:
                day_map[key]["day"] = day_names.get(key, "")
                day_map[key]["time"] = f"{work.work_start.strftime('%H:%M')} ~ {work.work_end.strftime('%H:%M')}"
            if part and part.name:
                day_map[key]["tags"].append(part.name)

    schedule_list = [day_map[k] for k in sorted(day_map.keys())]

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
        "store_name": store_name,
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
        "schedule": schedule_list,
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
    db: Session = Depends(get_db)
    ):
    """
    ----------------------------------------
    [직원] 마이페이지 정보 수정 API

    * 프로필이미지 / 이름 / 은행 / 계좌번호 / 이력서 / 근로계약서 / 보건증 수정 가능

    ----------------------------------------
    """

    user = db.query(StoreMembers).filter(StoreMembers.member_id == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    user_detail = db.query(StoreMembersDetail).filter(StoreMembersDetail.store_member_id == user.id).first()

    user.bank = bank
    user.accountNumber = account_number

    # 프로필 이미지
    if image:
        if original_image_url:
            old_path = original_image_url.lstrip("/")
            if os.path.exists(old_path):
                os.remove(old_path)
        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(PROFILE_UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(await image.read())
        user.image_url = f"/uploads/profile/{filename}"

    # 문서 저장 헬퍼
    async def save_document(file: UploadFile) -> str:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(DOCUMENT_UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        return f"/uploads/documents/{filename}"

    if resume:
        user_detail.resume = await save_document(resume)
    if employment_contract:
        user_detail.employment_contract = await save_document(employment_contract)
    if health_certificate:
        user_detail.health_certificate = await save_document(health_certificate)

    try:
        db.commit()
        db.refresh(user)
        return {"message": "수정되었습니다."}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="서버 오류로 인해 정보 수정에 실패했습니다.")

# ======= 근태 관리 ======= #
@router.post("/work/clock-in")
def add_clock_in(body: WorkTimeRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 출근 처리 API
    ----------------------------------------
    """
    print(body)

    # TODO: JWT 토큰에서 유저 ID 조회하는 방향으로 수정
    user = db.query(Member).filter(Member.id == 1).first()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    employee = db.query(StoreMembers).filter(StoreMembers.store_id == body.store_id, StoreMembers.member_id == user.id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="일치하는 직원 정보를 찾을 수 없습니다.")

    now = datetime.now()
    # print(now)

    today = now.date()
    # print(today)

    workLog = StoreMembersWorkLog(
        store_id = body.store_id,
        employee_id = employee.id,
        work_date = today,
        start_time = now,
        status = "working"
    )

    db.add(workLog)
    db.commit()



@router.post("/work/clock-out")
def add_clock_out(body: WorkTimeRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 퇴근 처리 API
    ----------------------------------------
    """
    print(body)

    # TODO: JWT 토큰에서 유저 ID 조회하는 방향으로 수정
    user = db.query(Member).filter(Member.id == 1).first()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    employee = db.query(StoreMembers).filter(StoreMembers.store_id == body.store_id, StoreMembers.member_id == user.id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="일치하는 직원 정보를 찾을 수 없습니다.")
    

    today = datetime.now().date()

    workLog = db.query(StoreMembersWorkLog).filter(StoreMembersWorkLog.work_date == today, StoreMembersWorkLog.end_time.is_(None)).first()

    if not workLog:
        raise HTTPException(status_code=404, detail="일치하는 출근 정보를 찾을 수 없습니다.")
    
    workLog.end_time = datetime.now()
    workLog.status = "off_work"

    if workLog.break_end_time is None:
        workLog.break_end_time = datetime.now()

    db.commit()

@router.post("/work/break-start")
def add_break_start(body: WorkTimeRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 휴게 시작 처리 API
    ----------------------------------------
    """
    print(body)

    # TODO: JWT 토큰에서 유저 ID 조회하는 방향으로 수정
    user = db.query(Member).filter(Member.id == 1).first()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    employee = db.query(StoreMembers).filter(StoreMembers.store_id == body.store_id, StoreMembers.member_id == user.id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="일치하는 직원 정보를 찾을 수 없습니다.")
    

    today = datetime.now().date()

    workLog = db.query(StoreMembersWorkLog).filter(StoreMembersWorkLog.work_date == today, StoreMembersWorkLog.status == "working", StoreMembersWorkLog.end_time.is_(None)).first()

    if not workLog:
        raise HTTPException(status_code=404, detail="일치하는 출근 정보를 찾을 수 없습니다.")
    
    workLog.break_start_time = datetime.now()
    workLog.status = "on_break"

    db.commit()

@router.post("/work/break-end")
def break_end(body: WorkTimeRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 휴게 종료 처리 API
    ----------------------------------------
    """
    print(body)

    # TODO: JWT 토큰에서 유저 ID 조회하는 방향으로 수정
    user = db.query(Member).filter(Member.id == 1).first()

    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    employee = db.query(StoreMembers).filter(StoreMembers.store_id == body.store_id, StoreMembers.member_id == user.id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="일치하는 직원 정보를 찾을 수 없습니다.")
    

    today = datetime.now().date()

    workLog = db.query(StoreMembersWorkLog).filter(StoreMembersWorkLog.work_date == today, StoreMembersWorkLog.status == "on_break", StoreMembersWorkLog.end_time.is_(None), StoreMembersWorkLog.break_end_time.is_(None)).first()

    if not workLog:
        raise HTTPException(status_code=404, detail="일치하는 출근 정보를 찾을 수 없습니다.")
    
    workLog.break_end_time = datetime.now()
    workLog.status = "working"

    db.commit()

@router.post("/work/logs")
async def get_work_logs(req: WorkMonthRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 출근 기록 조회 API
    ----------------------------------------
    """
    logs = (
        db.query(StoreMembersWorkLog)
        .filter(
            StoreMembersWorkLog.employee_id == req.employee_id,
            StoreMembersWorkLog.store_id == req.store_id,
            extract('year', StoreMembersWorkLog.work_date) == req.year,
            extract('month', StoreMembersWorkLog.work_date) == req.month,
        )
        .all()
    )

    schedules = (
        db.query(StoreMembersWork)
        .filter(
            StoreMembersWork.employee_id == req.employee_id,
            StoreMembersWork.store_id == req.store_id,
            extract('year', StoreMembersWork.work_date) == req.year,
            extract('month', StoreMembersWork.work_date) == req.month,
        )
        .all()
    )

    log_map = {str(l.work_date): l for l in logs}
    today = datetime.now().date()

    result = []
    for sched in schedules:
        date_key = str(sched.work_date)
        log = log_map.get(date_key)

        # 미래 날짜는 skip
        if sched.work_date > today:
            continue

        if log:
            result.append({
                "work_date": sched.work_date,
                "start_time": str(log.start_time) if log.start_time else None,
                "end_time": str(log.end_time) if log.end_time else None,
                "break_start_time": str(log.break_start_time) if log.break_start_time else None,
                "break_end_time": str(log.break_end_time) if log.break_end_time else None,
                "status": log.status,
                "is_holiday": sched.is_holiday or False,
                "sched_start": str(sched.work_start) if sched.work_start else None,
                "sched_end": str(sched.work_end) if sched.work_end else None,
            })
        else:
            # 스케줄 있는데 로그 없음 = 결근
            result.append({
                "work_date": sched.work_date,
                "start_time": None,
                "end_time": None,
                "break_start_time": None,
                "break_end_time": None,
                "status": "absent" if not (sched.is_holiday or False) else None,
                "is_holiday": sched.is_holiday or False,
                "sched_start": str(sched.work_start) if sched.work_start else None,
                "sched_end": str(sched.work_end) if sched.work_end else None,
            })

    return result

@router.post("/worklog/request")
async def work_log_change_request(req: WorkChangeRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 출근 기록 수정 요청 API
    ----------------------------------------
    """

    print(req)

    is_break_change = req.type == "휴게 시간 변경"
    is_missing_work = req.type == "근무 누락"

    if is_break_change:
        old_break_change = db.query(WorkLogChangeRequest).filter(WorkLogChangeRequest.date == req.date, WorkLogChangeRequest.type == "휴게 시간 변경", WorkLogChangeRequest.status == "pending").first()

        if old_break_change:
            raise HTTPException(status_code=409, detail="이미 해당 날짜에 휴게 시간 변경 요청이 존재합니다.")


    if is_missing_work:
        old_missing_work = db.query(WorkLogChangeRequest).filter(WorkLogChangeRequest.date == req.date, WorkLogChangeRequest.type == "근무 누락", WorkLogChangeRequest.status == "pending").first()

        if old_missing_work:
            raise HTTPException(status_code=409, detail="이미 해당 날짜에 근무 누락 수정 요청이 존재합니다.")
        
    



    new_request = WorkLogChangeRequest(
        store_id=req.store_id,
        employee_id=req.employee_id,
        type=req.type,
        date=req.date,
        origin_start=None if is_break_change else req.origin_start,
        origin_end=None if is_break_change else req.origin_end,
        desired_start=None if is_break_change else req.desired_start,
        desired_end=None if is_break_change else req.desired_end,
        desired_break=req.desired_break,
        reason=req.reason,
    )

    db.add(new_request)
    db.commit()

@router.get("/worklog/request")
async def work_log_change_request(employee_id: int, store_id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 출근 기록 수정내역 조회 API
    ----------------------------------------
    """

    requests = db.query(WorkLogChangeRequest).filter(
        WorkLogChangeRequest.employee_id == employee_id,
        WorkLogChangeRequest.store_id == store_id,
    ).order_by(WorkLogChangeRequest.created_at.desc()).all()
    return requests

@router.get("/schedule-change/{id}")
async def get_schedule_change(id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 변경된 스케줄 조회 API
    ----------------------------------------
    """
    change = db.query(ScheduleChangeRequest).filter(ScheduleChangeRequest.id == id).first()
    
    # 기존 일정으로 store_members_work 매칭
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

@router.get("/schedule-work/{id}")
async def get_schedule_work(id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [직원] 추가된 스케줄 조회 API
    ----------------------------------------
    """
    work = db.query(StoreMembersWork).filter(StoreMembersWork.id == id).first()
    part = db.query(StorePart).filter(StorePart.id == work.part_id).first()
    
    return {
        "work_date": work.work_date,
        "work_start": work.work_start,
        "work_end": work.work_end,
        "part_name": part.name if part else None,
    }