from fastapi import FastAPI, HTTPException, Query

from inflation_api_service import (
    BigQueryConfigError,
    BigQueryQueryError,
    InvalidDateError,
    InvalidInpcValueError,
    MissingInflationDataError,
    calculate_inflation_period,
)


app = FastAPI(
    title="Inflacion Copilot MX API",
    version="0.1.0",
)


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
