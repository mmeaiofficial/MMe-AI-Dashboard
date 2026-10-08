"""Departments, teams, membership and employee profiles, with data scopes applied."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session as DbSession

from ...audit.writer import record
from ...authz import engine as E
from ...core.db import get_db
from ...core.deps import Caller, requires
from ...core.models import Department, Employee, Team, TeamMember, User

router = APIRouter(tags=["organization"])

TEAM_KINDS = Literal["sales", "marketing", "tech", "ai_automation", "customer_success", "finance_ops", "custom"]


def visible_user_ids(caller: Caller, permission: str) -> Select:
    """Subquery of user ids inside the caller's scope for ``permission`` (people records)."""
    c = E.criteria(caller.subject, permission)
    q = select(User.id).where(User.organization_id == c.organization_id)
    if c.all_records:
        return q
    conds = [User.id.in_(c.user_ids)]
    if c.team_ids:
        conds.append(User.id.in_(select(TeamMember.user_id).where(TeamMember.team_id.in_(c.team_ids))))
    if c.department_ids:
        conds.append(User.department_id.in_(c.department_ids))
    return q.where(or_(*conds))


def _org_obj(db: DbSession, caller: Caller, model, obj_id: uuid.UUID):
    obj = db.get(model, obj_id)
    if obj is None or obj.organization_id != caller.user.organization_id or getattr(obj, "deleted_at", None) is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return obj


# ---------- departments ----------
class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    head_user_id: Optional[uuid.UUID] = None


def _dept_out(d: Department) -> dict:
    return {"id": str(d.id), "name": d.name, "head_user_id": str(d.head_user_id) if d.head_user_id else None}


@router.get("/departments")
def list_departments(caller: Caller = Depends(requires("org.departments.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Department).where(Department.organization_id == caller.user.organization_id, Department.deleted_at.is_(None)).order_by(Department.name)).all()
    return [_dept_out(d) for d in rows]


@router.post("/departments", status_code=201)
def create_department(body: DepartmentIn, caller: Caller = Depends(requires("org.departments.create")), db: DbSession = Depends(get_db)) -> dict:
    d = Department(organization_id=caller.user.organization_id, name=body.name.strip(), head_user_id=body.head_user_id)
    db.add(d)
    db.flush()
    record(db, caller.ctx, "org.department_created", "department", d.id, after=_dept_out(d))
    return _dept_out(d)


# ---------- teams ----------
class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: TEAM_KINDS = "custom"
    department_id: Optional[uuid.UUID] = None
    lead_user_id: Optional[uuid.UUID] = None


def _team_out(t: Team, members: Optional[list[dict]] = None) -> dict:
    out = {"id": str(t.id), "name": t.name, "kind": t.kind, "department_id": str(t.department_id) if t.department_id else None,
           "lead_user_id": str(t.lead_user_id) if t.lead_user_id else None}
    if members is not None:
        out["members"] = members
    return out


def _teams_in_scope(caller: Caller, permission: str):
    c = E.criteria(caller.subject, permission)
    q = select(Team).where(Team.organization_id == c.organization_id, Team.deleted_at.is_(None))
    if c.all_records:
        return q
    conds = []
    if c.team_ids:
        conds.append(Team.id.in_(c.team_ids))
    if c.department_ids:
        conds.append(Team.department_id.in_(c.department_ids))
    conds.append(Team.lead_user_id.in_(c.user_ids))
    return q.where(or_(*conds))


@router.get("/teams")
def list_teams(caller: Caller = Depends(requires("org.teams.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    return [_team_out(t) for t in db.scalars(_teams_in_scope(caller, "org.teams.view").order_by(Team.name)).all()]


@router.post("/teams", status_code=201)
def create_team(body: TeamIn, caller: Caller = Depends(requires("org.teams.create")), db: DbSession = Depends(get_db)) -> dict:
    t = Team(organization_id=caller.user.organization_id, name=body.name.strip(), kind=body.kind,
             department_id=body.department_id, lead_user_id=body.lead_user_id)
    db.add(t)
    db.flush()
    record(db, caller.ctx, "org.team_created", "team", t.id, after=_team_out(t))
    return _team_out(t)


@router.get("/teams/{team_id}")
def get_team(team_id: uuid.UUID, caller: Caller = Depends(requires("org.teams.view")), db: DbSession = Depends(get_db)) -> dict:
    t = db.scalar(_teams_in_scope(caller, "org.teams.view").where(Team.id == team_id))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    rows = db.execute(select(User.id, User.full_name, User.email, TeamMember.is_manager)
                      .join(TeamMember, TeamMember.user_id == User.id).where(TeamMember.team_id == t.id).order_by(User.full_name)).all()
    return _team_out(t, [{"user_id": str(i), "full_name": n, "email": e, "is_manager": m} for i, n, e, m in rows])


class MemberIn(BaseModel):
    user_id: uuid.UUID
    is_manager: bool = False


@router.put("/teams/{team_id}/members")
def set_member(team_id: uuid.UUID, body: MemberIn, caller: Caller = Depends(requires("org.teams.edit")), db: DbSession = Depends(get_db)) -> dict:
    t = _org_obj(db, caller, Team, team_id)
    u = _org_obj(db, caller, User, body.user_id)
    m = db.get(TeamMember, (t.id, u.id))
    if m is None:
        db.add(TeamMember(team_id=t.id, user_id=u.id, organization_id=t.organization_id, is_manager=body.is_manager))
    else:
        m.is_manager = body.is_manager
    record(db, caller.ctx, "org.team_member_set", "team", t.id, after={"user_id": str(u.id), "is_manager": body.is_manager})
    return {"ok": True}


@router.delete("/teams/{team_id}/members/{user_id}")
def remove_member(team_id: uuid.UUID, user_id: uuid.UUID, caller: Caller = Depends(requires("org.teams.edit")), db: DbSession = Depends(get_db)) -> dict:
    t = _org_obj(db, caller, Team, team_id)
    m = db.get(TeamMember, (t.id, user_id))
    if m is not None:
        db.delete(m)
        record(db, caller.ctx, "org.team_member_removed", "team", t.id, after={"user_id": str(user_id)})
    return {"ok": True}


# ---------- employees ----------
def _emp_out(u: User, e: Optional[Employee]) -> dict:
    return {"user_id": str(u.id), "email": u.email, "full_name": u.full_name, "avatar_url": u.avatar_url, "status": u.status,
            "department_id": str(u.department_id) if u.department_id else None,
            "designation": e.designation if e else None, "employment_type": e.employment_type if e else None,
            "manager_user_id": str(e.manager_user_id) if e and e.manager_user_id else None,
            "joined_on": e.joined_on.isoformat() if e and e.joined_on else None,
            "phone": e.phone if e else None, "location": e.location if e else None}


@router.get("/employees")
def list_employees(caller: Caller = Depends(requires("org.employees.view")), db: DbSession = Depends(get_db)) -> list[dict]:
    ids = visible_user_ids(caller, "org.employees.view")
    rows = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                      .where(User.id.in_(ids)).order_by(User.full_name, User.email)).all()
    return [_emp_out(u, e) for u, e in rows]


@router.get("/employees/{user_id}")
def get_employee(user_id: uuid.UUID, caller: Caller = Depends(requires("org.employees.view")), db: DbSession = Depends(get_db)) -> dict:
    row = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                     .where(User.id == user_id, User.id.in_(visible_user_ids(caller, "org.employees.view")))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return _emp_out(*row)


class EmployeePatch(BaseModel):
    designation: Optional[str] = Field(default=None, max_length=120)
    employment_type: Optional[Literal["full_time", "part_time", "intern", "contract"]] = None
    manager_user_id: Optional[uuid.UUID] = None
    joined_on: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    location: Optional[str] = Field(default=None, max_length=120)


@router.patch("/employees/{user_id}")
def update_employee(user_id: uuid.UUID, body: EmployeePatch, caller: Caller = Depends(requires("org.employees.edit")), db: DbSession = Depends(get_db)) -> dict:
    row = db.execute(select(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
                     .where(User.id == user_id, User.id.in_(visible_user_ids(caller, "org.employees.edit")))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    u, e = row
    if e is None:
        e = Employee(user_id=u.id, organization_id=u.organization_id)
        db.add(e)
    before = _emp_out(u, e)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("manager_user_id") == u.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Someone can't be their own manager.")
    for k, v in changes.items():
        setattr(e, k, v)
    db.flush()
    record(db, caller.ctx, "org.employee_updated", "user", u.id, before=before, after=_emp_out(u, e))
    return _emp_out(u, e)
