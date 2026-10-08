from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.availability.repository import AvailabilityRepository
from app.domains.availability.models import AvailabilityException
from app.domains.availability.schemas import DateOverrideInput, DateOverrideRead, ScheduleReplace, WorkingHourRead
from app.domains.availability.service import AvailabilityService
from app.domains.users.models import User


router = APIRouter(prefix="/availability", tags=["availability"])


def serialize_schedule(repository: AvailabilityRepository, user_id: object) -> list[WorkingHourRead]:
    hours = repository.list_hours(user_id)  # type: ignore[arg-type]
    breaks = repository.list_breaks([hour.id for hour in hours])
    return [WorkingHourRead.model_validate({**hour.__dict__, "breaks": [br for br in breaks if br.working_hour_id == hour.id]}) for hour in hours]


@router.get("", response_model=list[WorkingHourRead])
def get_schedule(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkingHourRead]:
    return serialize_schedule(AvailabilityRepository(db), current_user.id)


@router.put("", response_model=list[WorkingHourRead])
def replace_schedule(payload: ScheduleReplace, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkingHourRead]:
    repository = AvailabilityRepository(db)
    repository.replace(current_user.id, payload)
    return serialize_schedule(repository, current_user.id)


@router.get("/overrides", response_model=list[DateOverrideRead])
def list_overrides(
    start: date | None = None,
    end: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AvailabilityException]:
    return AvailabilityService(db).list_overrides(current_user, start, end)


@router.put("/overrides/{override_date}", response_model=DateOverrideRead)
def set_override(
    override_date: date,
    payload: DateOverrideInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AvailabilityException:
    return AvailabilityService(db).set_override(current_user, override_date, payload)


@router.delete("/overrides/{override_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_override(
    override_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    AvailabilityService(db).delete_override(current_user, override_date)
