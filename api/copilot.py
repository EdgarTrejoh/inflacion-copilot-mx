from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from copilot_api_service import (
    CopilotDataNotFoundError,
    CopilotDependencyError,
    CopilotQueryRejectedError,
    InvalidCopilotRequestError,
    get_copilot_date_range,
    get_copilot_history,
    process_copilot_query,
)


router = APIRouter(prefix="/copilot", tags=["inflacion-copilot"])


class CopilotQueryRequest(BaseModel):
    question: str | None = None


@router.post("/query")
def copilot_query(payload: CopilotQueryRequest) -> dict:
    try:
        return process_copilot_query(payload.question)
    except InvalidCopilotRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CopilotQueryRejectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CopilotDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CopilotDependencyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/history")
def copilot_history(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    try:
        return get_copilot_history(start_date=start_date, end_date=end_date)
    except InvalidCopilotRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CopilotDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CopilotDependencyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/date-range")
def copilot_date_range() -> dict:
    try:
        return get_copilot_date_range()
    except CopilotDependencyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
