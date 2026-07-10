import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dataclasses import dataclass, field
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


@dataclass
class ForecastResult:
    success:       bool
    metric:        str
    periods:       int
    forecast_df:   Optional[pd.DataFrame] = None
    historical_df: Optional[pd.DataFrame] = None
    insight:       str = ""
    error:         str = ""
    model_used:    str = ""


def _get_historical_data(db_path: str, metric: str, region: str = None) -> pd.DataFrame:
    """
    Pulls monthly aggregated data from the sales table.
    metric: 'revenue' | 'quantity' | 'orders'
    """
    engine = create_engine(f"sqlite:///{db_path}")

    metric_col = {
        "revenue":  "SUM(revenue)",
        "quantity": "SUM(quantity)",
        "orders":   "COUNT(*)"
    }.get(metric.lower(), "SUM(revenue)")

    region_filter = f"AND region = '{region}'" if region else ""

    query = f"""
        SELECT
            strftime('%Y-%m-01', date) as ds,
            {metric_col}              as y
        FROM sales
        WHERE date IS NOT NULL
              {region_filter}
        GROUP BY strftime('%Y-%m', date)
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
        raise ValueError(f"Could not fetch historical data: {e}")


def _forecast_with_prophet(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    """Uses Facebook Prophet for time-series forecasting."""
    from prophet import Prophet

    model = Prophet(
        yearly_seasonality  = True,
        weekly_seasonality  = False,
        daily_seasonality   = False,
        seasonality_mode    = "multiplicative",
        interval_width      = 0.80,
        changepoint_prior_scale = 0.05
    )
    model.fit(df)

    future    = model.make_future_dataframe(periods=periods, freq="MS")
    forecast  = model.predict(future)

    result = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    result.columns = ["date", "forecast", "lower", "upper"]
    result["forecast"] = result["forecast"].clip(lower=0)
    result["lower"]    = result["lower"].clip(lower=0)
    result["upper"]    = result["upper"].clip(lower=0)
    return result


def _forecast_with_linear(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    """Fallback: simple linear trend when Prophet is unavailable."""
    from sklearn.linear_model import LinearRegression

    df = df.copy()
    df["t"] = np.arange(len(df))

    X = df[["t"]].values
    y = df["y"].values

    model = LinearRegression()
    model.fit(X, y)

    future_t    = np.arange(len(df), len(df) + periods).reshape(-1, 1)
    future_pred = model.predict(future_t).clip(min=0)

    # Simple std-based confidence interval
    residuals = y - model.predict(X)
    std        = residuals.std()

    last_date    = df["ds"].max()
    future_dates = pd.date_range(
        start  = last_date + pd.DateOffset(months=1),
        periods = periods,
        freq   = "MS"
    )

    historical_result = pd.DataFrame({
        "date":     df["ds"],
        "forecast": model.predict(X).clip(min=0),
        "lower":    (model.predict(X) - std).clip(min=0),
        "upper":    (model.predict(X) + std).clip(min=0)
    })

    future_result = pd.DataFrame({
        "date":     future_dates,
        "forecast": future_pred,
        "lower":    (future_pred - std).clip(min=0),
        "upper":    (future_pred + std).clip(min=0)
    })

    return pd.concat([historical_result, future_result], ignore_index=True)


def run_forecast(
    db_path:  str,
    metric:   str   = "revenue",
    periods:  int   = 6,
    region:   str   = None
) -> ForecastResult:
    """
    Main entry point for forecasting.
    Returns ForecastResult with historical + forecast DataFrames.
    """
    # Validate periods
    periods = max(1, min(periods, 24))

    try:
        df = _get_historical_data(db_path, metric, region)
    except ValueError as e:
        return ForecastResult(
            success = False,
            metric  = metric,
            periods = periods,
            error   = str(e)
        )

    if len(df) < 6:
        return ForecastResult(
            success = False,
            metric  = metric,
            periods = periods,
            error   = f"Not enough historical data ({len(df)} months found, need at least 6)"
        )

    # Split historical vs forecast
    historical = df.copy()

    # Try Prophet first, fall back to linear
    try:
        forecast_df  = _forecast_with_prophet(df, periods)
        model_used   = "Prophet (Facebook)"
    except Exception:
        try:
            forecast_df = _forecast_with_linear(df, periods)
            model_used  = "Linear trend (fallback)"
        except Exception as e:
            return ForecastResult(
                success = False,
                metric  = metric,
                periods = periods,
                error   = f"Forecasting failed: {e}"
            )

    # Future rows only (after last historical date)
    last_hist   = historical["ds"].max()
    future_only = forecast_df[forecast_df["date"] > last_hist].copy()

    # Build insight
    if not future_only.empty:
        avg_forecast = future_only["forecast"].mean()
        avg_hist     = historical["y"].tail(3).mean()
        change_pct   = ((avg_forecast - avg_hist) / avg_hist * 100) if avg_hist > 0 else 0
        direction    = "increase" if change_pct > 0 else "decrease"
        region_str   = f" for {region}" if region else ""

        insight = (
            f"Forecast{region_str}: {metric} is expected to "
            f"{direction} by {abs(change_pct):.1f}% over the next {periods} months "
            f"(avg ₹{avg_forecast:,.0f}/month vs recent ₹{avg_hist:,.0f}/month). "
            f"Model: {model_used}."
        )
    else:
        insight = f"Forecast generated using {model_used}."

    return ForecastResult(
        success       = True,
        metric        = metric,
        periods       = periods,
        forecast_df   = forecast_df,
        historical_df = historical,
        insight       = insight,
        model_used    = model_used
    )


def forecast_to_dict(result: ForecastResult) -> dict:
    """Converts ForecastResult to JSON-serializable dict."""
    if not result.success:
        return {"success": False, "error": result.error}

    last_hist = result.historical_df["ds"].max()

    forecast_rows = []
    for _, row in result.forecast_df.iterrows():
        forecast_rows.append({
            "date":        row["date"].strftime("%Y-%m"),
            "forecast":    round(float(row["forecast"]), 2),
            "lower":       round(float(row["lower"]), 2),
            "upper":       round(float(row["upper"]), 2),
            "is_future":   row["date"] > last_hist
        })

    historical_rows = []
    for _, row in result.historical_df.iterrows():
        historical_rows.append({
            "date":  row["ds"].strftime("%Y-%m"),
            "actual": round(float(row["y"]), 2)
        })

    return {
        "success":      True,
        "metric":       result.metric,
        "periods":      result.periods,
        "model":        result.model_used,
        "insight":      result.insight,
        "forecast":     forecast_rows,
        "historical":   historical_rows
    }