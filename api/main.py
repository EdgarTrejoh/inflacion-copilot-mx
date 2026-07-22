from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.copilot import router as copilot_router
from api.cors import get_allowed_origins
from inflation_api_service import (
    BigQueryConfigError,
    BigQueryQueryError,
    InvalidDateError,
    InvalidInpcValueError,
    InvalidParameterError,
    MissingInflationDataError,
    calculate_average_period_inflation,
    calculate_inflation_period,
    calculate_monthly_comparable_inflation,
)


app = FastAPI(
    title="Inflacion Copilot MX API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(copilot_router)
app.include_router(copilot_router, prefix="/api", include_in_schema=False)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "inflacion-copilot-api",
    }


@app.get("/inflation/period")
def inflation_period(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    try:
        return calculate_inflation_period(start_date=start_date, end_date=end_date)
    except InvalidDateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingInflationDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidInpcValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BigQueryConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except BigQueryQueryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/inflation/average-period")
def inflation_average_period(
    current_year: int | None = Query(default=None),
    previous_year: int | None = Query(default=None),
    month_limit: int | None = Query(default=None),
) -> dict:
    try:
        return calculate_average_period_inflation(
            current_year=current_year,
            previous_year=previous_year,
            month_limit=month_limit,
        )
    except InvalidParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingInflationDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidInpcValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BigQueryConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except BigQueryQueryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/inflation/monthly-comparable")
def inflation_monthly_comparable(
    current_year: int | None = Query(default=None),
    previous_year: int | None = Query(default=None),
    month_limit: int | None = Query(default=None),
) -> dict:
    try:
        return calculate_monthly_comparable_inflation(
            current_year=current_year,
            previous_year=previous_year,
            month_limit=month_limit,
        )
    except InvalidParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingInflationDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidInpcValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BigQueryConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except BigQueryQueryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
