import pandas as pd
import numpy as np
from sqlalchemy import create_engine, inspect, text
from dataclasses import dataclass, field
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


@dataclass
class ForecastResult:
    success:       bool
    metric:        str
    periods:       int
    table:         str = ""
    forecast_df:   Optional[pd.DataFrame] = None
    historical_df: Optional[pd.DataFrame] = None
    insight:       str = ""
    error:         str = ""
    model_used:    str = ""


# ── Schema helpers ────────────────────────────────────────────────────────────

def _discover_best_table(engine) -> dict:
    """
    Finds the best table for forecasting — one with a date column
    and a numeric value column with enough monthly data points.
    """
    inspector = inspect(engine)
    tables    = inspector.get_table_names()

    date_kws  = ["date","time","created","updated","timestamp"]
    value_kws = ["revenue","amount","fee","bill","net","gross","total","cost",
             "price","salary","sales","income","profit","quantity","marks","score"]
    skip_kws  = ["id","key","code","rank","index","number","pct","percent",
                 "rate","age","year","month","day","hour","minute","second",
                 "days","weeks","hours","minutes","count_","num_","no_"]
    skip_types = ["TEXT","VARCHAR","CHAR","STRING","BOOL"]

    best       = None
    best_score = -1

    for table in tables:
        cols      = inspector.get_columns(table)
        col_names = [c["name"] for c in cols]
        col_types = {c["name"]: str(c["type"]).upper() for c in cols}

        # Find date column — must contain actual date strings
        date_col = None
        for col in col_names:
            col_lower = col.lower()
            # Skip columns that are just numbers called 'year' or 'month'
            if col_lower in ["year","month","day","hour","week"]:
                continue
            if any(kw in col_lower for kw in date_kws):
                # Verify it actually has date-like values
                try:
                    with engine.connect() as conn:
                        sample = conn.execute(
                            text(f"SELECT `{col}` FROM `{table}` WHERE `{col}` IS NOT NULL LIMIT 5")
                        ).fetchall()
                    if sample:
                        val = str(sample[0][0])
                        # Must look like a date (contains - or / and length > 6)
                        if (("-" in val or "/" in val) and len(val) >= 8):
                            date_col = col
                            break
                except Exception:
                    continue

        if not date_col:
            continue

        # Find numeric value columns — skip duration/count/age columns
        numeric_types = ["INT","REAL","FLOAT","NUMERIC","DECIMAL","DOUBLE","NUMBER"]
        value_cols = []
        for c in col_names:
            col_lower = c.lower()
            col_type  = col_types.get(c, "")

            # Skip if type is text-like
            if any(st in col_type for st in skip_types):
                continue
            # Must be numeric
            if not any(nt in col_type for nt in numeric_types):
                continue
            # Skip ID-like and duration-like columns
            if any(kw in col_lower for kw in skip_kws):
                continue
            # Must end with or contain value keywords OR be a plain numeric col
            if any(kw in col_lower for kw in value_kws):
                value_cols.insert(0, c)   # priority
            else:
                value_cols.append(c)

        if not value_cols:
            continue

        # Verify we have enough monthly data points for the best value col
        best_value_col = None
        best_months    = 0

        for vc in value_cols[:5]:   # check top 5 candidates
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(f"""
                        SELECT COUNT(DISTINCT strftime('%Y-%m', `{date_col}`)) as months,
                               COUNT(*) as total_rows
                        FROM `{table}`
                        WHERE `{date_col}` IS NOT NULL
                        AND   `{vc}` IS NOT NULL
                        AND   `{vc}` > 0
                    """)).fetchone()

                months     = result[0] if result else 0
                total_rows = result[1] if result else 0

                if months >= 6 and total_rows >= 10:
                    if months > best_months:
                        best_months    = months
                        best_value_col = vc
            except Exception:
                continue

        if not best_value_col:
            continue

        # Score this table
        # Score this table
        score = best_months * 2

        # Strong bonus for financial columns
        financial_kws = ["revenue","amount","fee","bill","net","gross",
                         "total","cost","price","salary","sales","income","profit"]
        neutral_kws   = ["quantity","count","units"]
        weak_kws      = ["marks","score","rating","grade","points"]

        if any(kw in best_value_col.lower() for kw in financial_kws):
            score += 30     # strong preference
        elif any(kw in best_value_col.lower() for kw in neutral_kws):
            score += 10
        elif any(kw in best_value_col.lower() for kw in weak_kws):
            score += 1      # very low preference

        try:
            with engine.connect() as conn:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table}`")
                ).fetchone()[0]
            # Row count bonus is small — don't let it override financial preference
            score += min(count // 200, 5)
        except Exception:
            count = 0

        if score > best_score:
            best_score = score
            best = {
                "table":      table,
                "date_col":   date_col,
                "value_cols": [best_value_col],
                "row_count":  count,
                "months":     best_months
            }

    return best


def _find_category_col(engine, table: str, exclude: list) -> Optional[str]:
    """Finds best categorical column for region/department/branch filtering."""
    inspector = inspect(engine)
    cols      = inspector.get_columns(table)

    cat_kws  = ["region","city","state","department","dept","branch","category",
                "channel","type","status","grade","class","section","sector",
                "specialization","location","division","ward","zone"]
    skip_kws = ["name","email","address","comment","description","id",
                "note","reason","url","password","code"]

    for kw in cat_kws:
        for col in cols:
            cname = col["name"]
            if cname in exclude:
                continue
            if kw in cname.lower() and not any(sk in cname.lower() for sk in skip_kws):
                return cname

    # Fallback: any text column not in exclusions
    for col in cols:
        cname = col["name"]
        ctype = str(col["type"]).upper()
        if cname in exclude:
            continue
        if "TEXT" in ctype or "VARCHAR" in ctype or "CHAR" in ctype:
            if not any(sk in cname.lower() for sk in skip_kws):
                return cname
    return None


# ── Data fetcher ──────────────────────────────────────────────────────────────

def _get_historical_data(
    db_path:      str,
    table:        str,
    date_col:     str,
    value_col:    str,
    category_col: str = None,
    category_val: str = None
) -> pd.DataFrame:

    engine          = create_engine(f"sqlite:///{db_path}")
    category_filter = ""
    if category_col and category_val:
        category_filter = f"AND `{category_col}` = '{category_val}'"

    # Check if date column has full dates or just YYYY-MM format
    try:
        with engine.connect() as conn:
            sample = conn.execute(
                text(f"SELECT `{date_col}` FROM `{table}` WHERE `{date_col}` IS NOT NULL LIMIT 1")
            ).fetchone()
        sample_val = str(sample[0]) if sample else ""

        # If it's already YYYY-MM format (like payroll.month)
        if len(sample_val) == 7 and "-" in sample_val:
            date_expr = f"`{date_col}`"
        else:
            date_expr = f"strftime('%Y-%m', `{date_col}`)"
    except Exception:
        date_expr = f"strftime('%Y-%m', `{date_col}`)"

    query = f"""
        SELECT
            {date_expr} || '-01' as ds,
            SUM(`{value_col}`)   as y
        FROM `{table}`
        WHERE `{date_col}` IS NOT NULL
        AND   `{value_col}` IS NOT NULL
        AND   `{value_col}` > 0
        {category_filter}
        GROUP BY {date_expr}
        ORDER BY ds
    """

    try:
        df = pd.read_sql_query(query, engine)
        engine.dispose()
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = pd.to_numeric(df["y"], errors="coerce")
        df       = df.dropna().reset_index(drop=True)
        return df
    except Exception as e:
        engine.dispose()
        raise ValueError(f"Could not fetch data: {e}")


# ── Forecast models ───────────────────────────────────────────────────────────

def _forecast_with_prophet(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    from prophet import Prophet
    model = Prophet(
        yearly_seasonality      = True,
        weekly_seasonality      = False,
        daily_seasonality       = False,
        seasonality_mode        = "multiplicative",
        interval_width          = 0.80,
        changepoint_prior_scale = 0.05
    )
    model.fit(df)
    future   = model.make_future_dataframe(periods=periods, freq="MS")
    forecast = model.predict(future)
    result   = forecast[["ds","yhat","yhat_lower","yhat_upper"]].copy()
    result.columns = ["date","forecast","lower","upper"]
    result["forecast"] = result["forecast"].clip(lower=0)
    result["lower"]    = result["lower"].clip(lower=0)
    result["upper"]    = result["upper"].clip(lower=0)
    return result


def _forecast_with_linear(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    from sklearn.linear_model import LinearRegression
    df      = df.copy()
    df["t"] = np.arange(len(df))
    X       = df[["t"]].values
    y       = df["y"].values
    model   = LinearRegression()
    model.fit(X, y)
    future_t    = np.arange(len(df), len(df)+periods).reshape(-1,1)
    future_pred = model.predict(future_t).clip(min=0)
    residuals   = y - model.predict(X)
    std         = residuals.std()
    last_date   = df["ds"].max()
    future_dates = pd.date_range(
        start=last_date + pd.DateOffset(months=1),
        periods=periods, freq="MS"
    )
    hist_result = pd.DataFrame({
        "date":     df["ds"],
        "forecast": model.predict(X).clip(min=0),
        "lower":    (model.predict(X) - std).clip(min=0),
        "upper":    (model.predict(X) + std).clip(min=0)
    })
    fut_result = pd.DataFrame({
        "date":     future_dates,
        "forecast": future_pred,
        "lower":    (future_pred - std).clip(min=0),
        "upper":    (future_pred + std).clip(min=0)
    })
    return pd.concat([hist_result, fut_result], ignore_index=True)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_forecast(
    db_path:      str,
    metric:       str  = "auto",
    periods:      int  = 6,
    region:       str  = None,
    table:        str  = None,
    date_col:     str  = None,
    value_col:    str  = None,
    category_col: str  = None
) -> ForecastResult:

    periods = max(1, min(periods, 24))
    engine  = create_engine(f"sqlite:///{db_path}")

    # ── Auto-discover schema ──────────────────────────────────────────────────
    if not table or not date_col or not value_col:
        discovered = _discover_best_table(engine)
        if not discovered:
            engine.dispose()
            return ForecastResult(
                success=False, metric=metric, periods=periods,
                error="No suitable table found for forecasting. Need a table with date and numeric columns."
            )
        table     = discovered["table"]
        date_col  = discovered["date_col"]
        val_cols  = discovered["value_cols"]

        # Pick value column based on metric hint or best guess
        if metric and metric != "auto":
            matched = [c for c in val_cols if metric.lower() in c.lower()]
            value_col = matched[0] if matched else val_cols[0]
        else:
            # Prefer revenue/amount/salary type columns
            pref_kws  = ["revenue","amount","salary","bill","price","total","sales","fee"]
            preferred = [c for c in val_cols
                        if any(kw in c.lower() for kw in pref_kws)]
            value_col = preferred[0] if preferred else val_cols[0]

        # Find category column for filtering
        if region and not category_col:
            category_col = _find_category_col(engine, table, [date_col, value_col])

    engine.dispose()

    metric_label = value_col.replace("_"," ").title()

    # ── Fetch data ────────────────────────────────────────────────────────────
    try:
        df = _get_historical_data(
            db_path, table, date_col, value_col,
            category_col, region
        )
    except ValueError as e:
        return ForecastResult(
            success=False, metric=metric_label,
            periods=periods, table=table, error=str(e)
        )

    if len(df) < 6:
        return ForecastResult(
            success=False, metric=metric_label, periods=periods, table=table,
            error=f"Only {len(df)} monthly data points found in '{table}.{value_col}'. Need at least 6."
        )

    historical = df.copy()

    # ── Forecast ──────────────────────────────────────────────────────────────
    try:
        forecast_df = _forecast_with_prophet(df, periods)
        model_used  = "Prophet (Facebook)"
    except Exception:
        try:
            forecast_df = _forecast_with_linear(df, periods)
            model_used  = "Linear trend (fallback)"
        except Exception as e:
            return ForecastResult(
                success=False, metric=metric_label,
                periods=periods, table=table,
                error=f"Forecasting failed: {e}"
            )

    last_hist   = historical["ds"].max()
    future_only = forecast_df[forecast_df["date"] > last_hist].copy()

    # ── Insight ───────────────────────────────────────────────────────────────
    if not future_only.empty:
        avg_forecast = future_only["forecast"].mean()
        avg_hist     = historical["y"].tail(3).mean()
        change_pct   = ((avg_forecast - avg_hist) / avg_hist * 100) if avg_hist > 0 else 0
        direction    = "increase" if change_pct > 0 else "decrease"
        filter_str   = f" for {region}" if region else ""
        insight = (
            f"Forecast{filter_str} [{table}.{value_col}]: "
            f"{metric_label} is expected to {direction} by "
            f"{abs(change_pct):.1f}% over the next {periods} months "
            f"(avg {avg_forecast:,.1f}/month vs recent {avg_hist:,.1f}/month). "
            f"Model: {model_used}."
        )
    else:
        insight = f"Forecast generated using {model_used}."

    return ForecastResult(
        success       = True,
        metric        = metric_label,
        periods       = periods,
        table         = table,
        forecast_df   = forecast_df,
        historical_df = historical,
        insight       = insight,
        model_used    = model_used
    )


def forecast_to_dict(result: ForecastResult) -> dict:
    if not result.success:
        return {"success": False, "error": result.error}

    last_hist = result.historical_df["ds"].max()

    forecast_rows = []
    for _, row in result.forecast_df.iterrows():
        forecast_rows.append({
            "date":      row["date"].strftime("%Y-%m"),
            "forecast":  round(float(row["forecast"]), 2),
            "lower":     round(float(row["lower"]),    2),
            "upper":     round(float(row["upper"]),    2),
            "is_future": row["date"] > last_hist
        })

    historical_rows = []
    for _, row in result.historical_df.iterrows():
        historical_rows.append({
            "date":   row["ds"].strftime("%Y-%m"),
            "actual": round(float(row["y"]), 2)
        })

    return {
        "success":    True,
        "metric":     result.metric,
        "table":      result.table,
        "periods":    result.periods,
        "model":      result.model_used,
        "insight":    result.insight,
        "forecast":   forecast_rows,
        "historical": historical_rows
    }