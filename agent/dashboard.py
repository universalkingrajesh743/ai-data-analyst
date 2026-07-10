import pandas as pd
from sqlalchemy import create_engine, inspect, text


# ── Schema discovery ──────────────────────────────────────────────────────────

def discover_schema(engine) -> dict:
    """Auto-discovers tables, columns, and their types."""
    inspector = inspect(engine)
    schema    = {}
    for table in inspector.get_table_names():
        cols = inspector.get_columns(table)
        schema[table] = {
            "columns":     [c["name"] for c in cols],
            "col_types":   {c["name"]: str(c["type"]).upper() for c in cols},
        }
        try:
            with engine.connect() as conn:
                schema[table]["row_count"] = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table}`")
                ).fetchone()[0]
        except Exception:
            schema[table]["row_count"] = 0
    return schema


def _q(engine, sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, engine)
    except Exception:
        return pd.DataFrame()


# ── Column role detector ──────────────────────────────────────────────────────

def find_column(cols: list, keywords: list) -> str:
    """Returns first column name matching any keyword (case-insensitive)."""
    for kw in keywords:
        for col in cols:
            if kw.lower() in col.lower():
                return col
    return None


def find_numeric_columns(schema_table: dict) -> list:
    """Returns all numeric columns in a table."""
    numeric_types = ["INT","REAL","FLOAT","NUMERIC","DECIMAL","DOUBLE","NUMBER","MONEY"]
    return [
        col for col, typ in schema_table["col_types"].items()
        if any(nt in typ for nt in numeric_types)
    ]


def find_date_column(schema_table: dict) -> str:
    """Returns first date-like column."""
    date_kws = ["date","time","created","updated","timestamp","day","month","year"]
    for col in schema_table["columns"]:
        if any(kw in col.lower() for kw in date_kws):
            return col
    return None


def find_category_columns(schema_table: dict, exclude: list = []) -> list:
    """Returns text columns that look like categories."""
    text_types    = ["TEXT","VARCHAR","CHAR","STRING"]
    exclude_kws   = ["name","email","address","comment","description",
                     "note","remark","reason","id","url","password"]
    result = []
    for col, typ in schema_table["col_types"].items():
        if col in exclude:
            continue
        if any(tt in typ for tt in text_types):
            if not any(kw in col.lower() for kw in exclude_kws):
                result.append(col)
    return result


# ── Smart KPI builder ─────────────────────────────────────────────────────────

def build_kpis(engine, schema: dict) -> dict:
    """Builds KPIs dynamically from whatever tables exist."""
    kpis = {}

    for table, info in schema.items():
        num_cols  = find_numeric_columns(info)
        date_col  = find_date_column(info)
        row_count = info["row_count"]

        if row_count == 0:
            continue

        kpis[f"{table}_count"] = {
            "label": f"Total {table.replace('_',' ').title()}",
            "value": f"{row_count:,}",
            "icon":  "📋"
        }

        # Sum/avg of numeric columns
        for col in num_cols[:3]:
            col_lower = col.lower()
            # Skip ID-like columns
            if any(kw in col_lower for kw in ["id","key","code","number","rank","index"]):
                continue
            try:
                result = _q(engine, f"SELECT ROUND(SUM(`{col}`),0) as total, ROUND(AVG(`{col}`),2) as avg FROM `{table}` WHERE `{col}` IS NOT NULL")
                if not result.empty and result.iloc[0]["total"]:
                    total = float(result.iloc[0]["total"])
                    avg   = float(result.iloc[0]["avg"])
                    label = col.replace("_"," ").title()

                    # Format based on likely meaning
                    is_money  = any(kw in col_lower for kw in ["amount","revenue","salary","price","cost","fee","pay","bill","total","profit","sales","income"])
                    is_pct    = any(kw in col_lower for kw in ["pct","percent","rate","ratio","discount"])
                    is_rating = any(kw in col_lower for kw in ["rating","score","grade","marks","kpi"])

                    if is_money:
                        kpis[f"{table}_{col}_total"] = {
                            "label": f"Total {label}",
                            "value": f"₹{total:,.0f}" if total > 1000 else f"₹{total:,.2f}",
                            "icon":  "💰"
                        }
                        kpis[f"{table}_{col}_avg"] = {
                            "label": f"Avg {label}",
                            "value": f"₹{avg:,.0f}" if avg > 100 else f"₹{avg:,.2f}",
                            "icon":  "📊"
                        }
                    elif is_pct:
                        kpis[f"{table}_{col}_avg"] = {
                            "label": f"Avg {label}",
                            "value": f"{avg:.1f}%",
                            "icon":  "📉"
                        }
                    elif is_rating:
                        kpis[f"{table}_{col}_avg"] = {
                            "label": f"Avg {label}",
                            "value": f"{avg:.2f}",
                            "icon":  "⭐"
                        }
            except Exception:
                continue

    return kpis


# ── Smart chart builder ───────────────────────────────────────────────────────

def build_charts(engine, schema: dict) -> list:
    """
    Dynamically builds chart data for any schema.
    Returns list of chart dicts: {title, type, data, x, y}
    """
    charts = []

    for table, info in schema.items():
        if info["row_count"] == 0:
            continue

        num_cols  = find_numeric_columns(info)
        date_col  = find_date_column(info)
        cat_cols  = find_category_columns(info)

        # Filter out ID-like numeric columns
        value_cols = [
            c for c in num_cols
            if not any(kw in c.lower() for kw in ["id","key","code","rank","index","number"])
        ]

        if not value_cols:
            continue

        primary_value = value_cols[0]
        pv_label      = primary_value.replace("_"," ").title()

        # ── Chart 1: Time series trend ────────────────────────────────────────
        if date_col:
            df = _q(engine, f"""
                SELECT
                    strftime('%Y-%m', `{date_col}`) as period,
                    ROUND(SUM(`{primary_value}`), 2) as value
                FROM `{table}`
                WHERE `{date_col}` IS NOT NULL
                AND `{primary_value}` IS NOT NULL
                GROUP BY period
                ORDER BY period
                LIMIT 36
            """)
            if not df.empty and len(df) > 2:
                charts.append({
                    "title": f"📈 {table.title()} — {pv_label} over time",
                    "type":  "line",
                    "data":  df.to_dict(orient="records"),
                    "x":     "period",
                    "y":     "value",
                    "table": table
                })

        # ── Chart 2: Category breakdown ───────────────────────────────────────
        for cat_col in cat_cols[:2]:
            df = _q(engine, f"""
                SELECT
                    `{cat_col}` as category,
                    ROUND(SUM(`{primary_value}`), 2) as value,
                    COUNT(*) as count
                FROM `{table}`
                WHERE `{cat_col}` IS NOT NULL
                AND `{primary_value}` IS NOT NULL
                GROUP BY `{cat_col}`
                ORDER BY value DESC
                LIMIT 10
            """)
            if not df.empty and 1 < len(df) <= 10:
                chart_type = "pie" if len(df) <= 6 else "bar"
                charts.append({
                    "title": f"{'🥧' if chart_type=='pie' else '📊'} {table.title()} by {cat_col.replace('_',' ').title()}",
                    "type":  chart_type,
                    "data":  df.to_dict(orient="records"),
                    "x":     "category",
                    "y":     "value",
                    "table": table
                })

        # ── Chart 3: Count by category ────────────────────────────────────────
        for cat_col in cat_cols[:1]:
            df = _q(engine, f"""
                SELECT
                    `{cat_col}` as category,
                    COUNT(*) as count
                FROM `{table}`
                WHERE `{cat_col}` IS NOT NULL
                GROUP BY `{cat_col}`
                ORDER BY count DESC
                LIMIT 8
            """)
            if not df.empty and 1 < len(df) <= 8:
                charts.append({
                    "title": f"📋 {table.title()} count by {cat_col.replace('_',' ').title()}",
                    "type":  "bar",
                    "data":  df.to_dict(orient="records"),
                    "x":     "category",
                    "y":     "count",
                    "table": table
                })

        # ── Chart 4: Multiple metrics comparison ──────────────────────────────
        if len(value_cols) >= 2 and cat_cols:
            col1 = value_cols[0]
            col2 = value_cols[1]
            cat  = cat_cols[0]
            df   = _q(engine, f"""
                SELECT
                    `{cat}` as category,
                    ROUND(AVG(`{col1}`),2) as metric1,
                    ROUND(AVG(`{col2}`),2) as metric2
                FROM `{table}`
                WHERE `{cat}` IS NOT NULL
                GROUP BY `{cat}`
                ORDER BY metric1 DESC
                LIMIT 8
            """)
            if not df.empty and len(df) > 1:
                charts.append({
                    "title": f"⚖️ {table.title()} — {col1.replace('_',' ')} vs {col2.replace('_',' ')}",
                    "type":  "grouped_bar",
                    "data":  df.to_dict(orient="records"),
                    "x":     "category",
                    "y":     ["metric1","metric2"],
                    "y_labels": [col1.replace("_"," ").title(), col2.replace("_"," ").title()],
                    "table": table
                })

    return charts


# ── Top lists builder ─────────────────────────────────────────────────────────

def build_top_lists(engine, schema: dict) -> list:
    """Builds top-N tables for text+number pairs."""
    top_lists = []

    for table, info in schema.items():
        if info["row_count"] == 0:
            continue

        num_cols = find_numeric_columns(info)
        value_cols = [
            c for c in num_cols
            if not any(kw in c.lower() for kw in ["id","key","code","rank","index","number"])
        ]
        name_col = find_column(info["columns"],
                               ["name","title","product","item","employee",
                                "customer","doctor","student","company","branch"])

        if not name_col or not value_cols:
            continue

        primary_value = value_cols[0]
        df = _q(engine, f"""
            SELECT
                `{name_col}` as name,
                ROUND(SUM(`{primary_value}`),2) as value,
                COUNT(*) as count
            FROM `{table}`
            WHERE `{name_col}` IS NOT NULL
            GROUP BY `{name_col}`
            ORDER BY value DESC
            LIMIT 10
        """)

        if not df.empty and len(df) > 1:
            top_lists.append({
                "title":    f"🏆 Top {table.title()} by {primary_value.replace('_',' ').title()}",
                "data":     df.to_dict(orient="records"),
                "value_col": primary_value.replace("_"," ").title(),
                "table":    table
            })

    return top_lists


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_dashboard_data(db_path: str) -> dict:
    """
    Universal dashboard generator — works on ANY SQLite database.
    Auto-discovers schema and builds appropriate KPIs + charts.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    schema = discover_schema(engine)

    kpis      = build_kpis(engine, schema)
    charts    = build_charts(engine, schema)
    top_lists = build_top_lists(engine, schema)

    # ── Special handling for known sales schema ───────────────────────────────
    tables = list(schema.keys())
    is_sales_db = "sales" in tables and "returns" in tables

    extra = {}
    if is_sales_db:
        extra["monthly_trend"] = _q(engine, """
            SELECT strftime('%Y-%m', date) as month,
                   ROUND(SUM(revenue),0)   as revenue,
                   COUNT(*)                as orders
            FROM sales GROUP BY month ORDER BY month
        """).to_dict(orient="records")

        extra["by_region"] = _q(engine, """
            SELECT region,
                   ROUND(SUM(revenue),0) as revenue,
                   COUNT(*)              as orders
            FROM sales GROUP BY region ORDER BY revenue DESC
        """).to_dict(orient="records")

        extra["by_category"] = _q(engine, """
            SELECT category,
                   ROUND(SUM(revenue),0) as revenue,
                   COUNT(*)              as orders
            FROM sales GROUP BY category ORDER BY revenue DESC
        """).to_dict(orient="records")

        extra["by_channel"] = _q(engine, """
            SELECT channel,
                   ROUND(SUM(revenue),0) as revenue,
                   COUNT(*)              as orders
            FROM sales GROUP BY channel ORDER BY revenue DESC
        """).to_dict(orient="records")

        extra["qoq"] = _q(engine, """
            SELECT strftime('%Y',date) as year,
                   CASE WHEN strftime('%m',date) IN ('01','02','03') THEN 'Q1'
                        WHEN strftime('%m',date) IN ('04','05','06') THEN 'Q2'
                        WHEN strftime('%m',date) IN ('07','08','09') THEN 'Q3'
                        ELSE 'Q4' END as quarter,
                   ROUND(SUM(revenue),0) as revenue
            FROM sales GROUP BY year, quarter ORDER BY year, quarter
        """).to_dict(orient="records")

        extra["top_products"] = _q(engine, """
            SELECT product,
                   ROUND(SUM(revenue),0) as revenue,
                   SUM(quantity)         as units_sold
            FROM sales GROUP BY product
            ORDER BY revenue DESC LIMIT 5
        """).to_dict(orient="records")

        extra["top_reps"] = _q(engine, """
            SELECT sales_rep,
                   ROUND(SUM(revenue),0) as revenue,
                   COUNT(*)              as orders
            FROM sales GROUP BY sales_rep
            ORDER BY revenue DESC LIMIT 5
        """).to_dict(orient="records")

        extra["returns_summary"] = _q(engine, """
            SELECT reason,
                   COUNT(*)                    as count,
                   ROUND(SUM(refund_amount),0) as total_refunds
            FROM returns GROUP BY reason ORDER BY count DESC
        """).to_dict(orient="records")

        # Rebuild KPIs for sales DB with proper formatting
        kpi_df = _q(engine, """
            SELECT ROUND(SUM(revenue),0) as total_revenue,
                   COUNT(*) as total_orders,
                   ROUND(AVG(revenue),0) as avg_order_value,
                   COUNT(DISTINCT region) as active_regions,
                   COUNT(DISTINCT product) as products_sold,
                   ROUND(AVG(discount_pct),1) as avg_discount
            FROM sales
        """)
        if not kpi_df.empty:
            row  = kpi_df.iloc[0]
            kpis = {
                "total_revenue":   {"label":"💰 Total Revenue",   "value":f"₹{float(row['total_revenue'] or 0):,.0f}",  "icon":"💰"},
                "total_orders":    {"label":"🛒 Total Orders",    "value":f"{int(row['total_orders'] or 0):,}",          "icon":"🛒"},
                "avg_order_value": {"label":"📦 Avg Order Value", "value":f"₹{float(row['avg_order_value'] or 0):,.0f}","icon":"📦"},
                "active_regions":  {"label":"🌍 Regions",         "value":str(int(row['active_regions'] or 0)),          "icon":"🌍"},
                "products_sold":   {"label":"🏷️ Products",        "value":str(int(row['products_sold'] or 0)),           "icon":"🏷️"},
                "avg_discount":    {"label":"🏷️ Avg Discount",    "value":f"{float(row['avg_discount'] or 0):.1f}%",    "icon":"🏷️"},
            }

    engine.dispose()

    return {
        "is_sales_db": is_sales_db,
        "schema":      {t: {"row_count": info["row_count"], "columns": info["columns"]}
                        for t, info in schema.items()},
        "kpis":        kpis,
        "charts":      charts,
        "top_lists":   top_lists,
        **extra
    }