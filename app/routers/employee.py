import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import asc, extract
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
import uuid
from datetime import datetime, timedelta

from models import Member, Store, StoreMap, MemberRequest, StoreMembers, StoreMembersTodo, StoreMembersWork, StoreCommunity, StoreMembersWorkLog, StoreMembersDetail
from database import get_db
from schemas.employee import VerifyCode, MemberRequestSchemas, TodoListRequest, TodoListResponse, TodoListModifyRequest, WorkRequest, WrokResponse, NoticeResponse, WeeklyWorkRequest, WeeklyWorkResponse
from utils.uitls import format_phone_number, get_coords_from_address


router = APIRouter(prefix="/api/employee", tags=["직원유형"])

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
