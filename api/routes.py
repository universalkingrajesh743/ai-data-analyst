import uuid
import os
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from agent.sql_agent import ask_agent, get_schema_description
from agent.memory import get_query_log, get_history
from agent.report_generator import generate_pdf_report
from sqlalchemy import create_engine, inspect, text
import pandas as pd
from agent.data_quality import run_quality_check, format_report_for_display
from agent.forecaster import run_forecast, forecast_to_dict
from agent.root_cause  import run_root_cause
from agent.dashboard   import generate_dashboard_data
from agent.optimizer import analyse_query, format_optimizer_report
from agent.alerting  import check_alerts, format_alert_report

router = APIRouter()

UPLOAD_DIR = "sample_data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question:   str
    session_id: str = None
    db_path:    str = None


class QueryResponse(BaseModel):
    session_id:  str
    question:    str
    sql:         str
    explanation: str
    insight:     str
    chart_type:  str
    columns:     list
    data:        list
    row_count:   int
    error:       str = ""
    validation:  dict = {}


class ReportRequest(BaseModel):
    session_id:   str
    session_data: list


# ── Query endpoint ────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    session_id = req.session_id or str(uuid.uuid4())

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    db_path = req.db_path or "sample_data/sales.db"
    result  = ask_agent(req.question, session_id, db_path=db_path)

    return QueryResponse(
        session_id  = session_id,
        question    = req.question,
        sql         = result.get("sql", ""),
        explanation = result.get("explanation", ""),
        insight     = result.get("insight", ""),
        chart_type  = result.get("chart_type", "none"),
        columns     = result.get("columns", []),
        data        = result.get("data", []),
        row_count   = result.get("row_count", 0),
        error       = result.get("error") or "",
        validation  = result.get("validation") or {},
    )


# ── PDF report endpoint ───────────────────────────────────────────────────────

@router.post("/report/pdf")
def generate_report(req: ReportRequest):
    try:
        session_data = []
        for item in req.session_data:
            df = pd.DataFrame(item.get("data", []))
            session_data.append({
                "question":    item.get("question", ""),
                "sql":         item.get("sql", ""),
                "explanation": item.get("explanation", ""),
                "insight":     item.get("insight", ""),
                "row_count":   item.get("row_count", 0),
                "df":          df if not df.empty else None
            })

        pdf_bytes = generate_pdf_report(session_data, req.session_id)

        if not isinstance(pdf_bytes, bytes):
            pdf_bytes = bytes(pdf_bytes)

        return Response(
            content    = pdf_bytes,
            media_type = "application/pdf",
            headers    = {
                "Content-Disposition": "attachment; filename=analyst_report.pdf",
                "Content-Length":      str(len(pdf_bytes)),
                "Cache-Control":       "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


# ── Database upload endpoint ──────────────────────────────────────────────────

@router.post("/upload-db")
async def upload_database(file: UploadFile = File(...)):
    allowed_exts = [".db", ".sqlite", ".sqlite3"]
    ext          = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_exts:
        raise HTTPException(
            status_code = 400,
            detail      = f"Only .db or .sqlite files allowed. Got: '{file.filename}'"
        )

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    contents  = await file.read()

    if not contents[:16].startswith(b"SQLite format 3"):
        raise HTTPException(
            status_code = 400,
            detail      = "File does not appear to be a valid SQLite database."
        )

    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        engine    = create_engine(f"sqlite:///{save_path}")
        inspector = inspect(engine)
        tables    = {}
        for table in inspector.get_table_names():
            cols = inspector.get_columns(table)
            with engine.connect() as conn:
                count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).fetchone()[0]
            tables[table] = {
                "columns":   [c["name"] for c in cols],
                "row_count": count
            }
        engine.dispose()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read DB: {str(e)}")

    return {
        "filename": file.filename,
        "db_path":  save_path,
        "tables":   tables,
        "message":  f"Successfully loaded {file.filename}"
    }


# ── Schema endpoint ───────────────────────────────────────────────────────────

@router.get("/schema")
def get_schema(db_path: str = "sample_data/sales.db"):
    try:
        schema = get_schema_description(db_path)
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── History endpoints ─────────────────────────────────────────────────────────

@router.get("/history")
def query_history(limit: int = 20):
    return {"queries": get_query_log(limit)}


@router.get("/session/{session_id}")
def session_history(session_id: str):
    return {"messages": get_history(session_id)}


# ── Data quality endpoint ─────────────────────────────────────────────────────

@router.get("/quality")
def data_quality(db_path: str = "sample_data/sales.db"):
    try:
        report = run_quality_check(db_path)
        return format_report_for_display(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ── Forecast endpoint ─────────────────────────────────────────────────────────

@router.get("/forecast")
def forecast_endpoint(
    metric:  str = "revenue",
    periods: int = 6,
    region:  str = None,
    db_path: str = "sample_data/sales.db"
):
    try:
        result = run_forecast(
            db_path = db_path,
            metric  = metric,
            periods = periods,
            region  = region
        )
        return forecast_to_dict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Root cause endpoint ───────────────────────────────────────────────────────

class RootCauseRequest(BaseModel):
    question:       str
    region:         str = "Odisha"
    period:         str = "2024-07"
    compare_period: str = "2024-04"
    metric:         str = "revenue"
    db_path:        str = "sample_data/sales.db"


@router.post("/root-cause")
def root_cause_endpoint(req: RootCauseRequest):
    try:
        result = run_root_cause(
            db_path        = req.db_path,
            question       = req.question,
            region         = req.region,
            period         = req.period,
            compare_period = req.compare_period,
            metric         = req.metric
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dashboard endpoint ────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard_endpoint(db_path: str = "sample_data/sales.db"):
    try:
        return generate_dashboard_data(db_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Optimizer endpoint ────────────────────────────────────────────────────────

class OptimizerRequest(BaseModel):
    sql:     str
    db_path: str = "sample_data/sales.db"


@router.post("/optimize")
def optimize_endpoint(req: OptimizerRequest):
    try:
        report = analyse_query(req.sql, req.db_path)
        return format_optimizer_report(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Alerts endpoint ───────────────────────────────────────────────────────────

@router.get("/alerts")
def alerts_endpoint(
    db_path:                str   = "sample_data/sales.db",
    revenue_drop_threshold: float = 20.0,
    return_rate_threshold:  float = 10.0,
    discount_threshold:     float = 15.0
):
    try:
        report = check_alerts(
            db_path                 = db_path,
            revenue_drop_threshold  = revenue_drop_threshold,
            return_rate_threshold   = return_rate_threshold,
            discount_threshold      = discount_threshold
        )
        return format_alert_report(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def health():
    return {"status": "ok"}