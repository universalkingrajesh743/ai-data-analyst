import io
import pandas as pd
from fpdf import FPDF
from datetime import datetime


class ReportPDF(FPDF):

    def header(self):
        self.set_fill_color(99, 102, 241)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.set_xy(0, 2)
        self.cell(0, 14, "  AI Personal Data Analyst - Session Report", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            0, 10,
            f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}  |  Page {self.page_no()}",
            align="C"
        )

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(99, 102, 241)
        self.set_fill_color(240, 240, 255)
        # Sanitize title
        safe = title.encode("latin-1", "replace").decode("latin-1")
        self.cell(0, 9, f"  {safe}", fill=True, ln=True)
        self.ln(2)

    def body_text(self, text: str, color=(40, 40, 40)):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*color)
        safe = text.encode("latin-1", "replace").decode("latin-1")
        self.multi_cell(0, 5, safe)
        self.ln(1)

    def add_query_block(self, idx, question, sql, explanation, insight, row_count):
        label = f"Query {idx}: {question[:65]}{'...' if len(question) > 65 else ''}"
        self.section_title(label)

        if insight:
            self.set_fill_color(230, 244, 255)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(50, 50, 180)
            safe_insight = insight.encode("latin-1", "replace").decode("latin-1")
            self.cell(0, 7, f"  Insight: {safe_insight}", fill=True, ln=True)
            self.ln(2)

        if explanation:
            self.body_text(f"Explanation: {explanation}")

        if sql:
            self.set_font("Courier", "", 8)
            self.set_text_color(30, 30, 30)
            self.set_fill_color(245, 245, 245)
            safe_sql = sql.encode("latin-1", "replace").decode("latin-1")
            self.multi_cell(0, 5, safe_sql, fill=True)
            self.ln(2)

        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"  Rows returned: {row_count}", ln=True)
        self.ln(3)

    def add_data_table(self, df: pd.DataFrame, max_rows: int = 12):
        if df is None or df.empty:
            return

        df_show   = df.head(max_rows)
        cols      = df_show.columns.tolist()
        page_w    = self.w - 20
        col_w     = min(page_w / max(len(cols), 1), 44)

        # Header
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(99, 102, 241)
        self.set_text_color(255, 255, 255)
        for col in cols:
            label = str(col)[:14].encode("latin-1", "replace").decode("latin-1")
            self.cell(col_w, 6, label, border=0, fill=True, align="C")
        self.ln()

        # Rows
        self.set_font("Helvetica", "", 7)
        self.set_text_color(40, 40, 40)
        for i, (_, row) in enumerate(df_show.iterrows()):
            if i % 2 == 0:
                self.set_fill_color(248, 248, 255)
            else:
                self.set_fill_color(255, 255, 255)
            for col in cols:
                val = str(row[col])[:14].encode("latin-1", "replace").decode("latin-1")
                self.cell(col_w, 5, val, border=0, fill=True, align="C")
            self.ln()

        if len(df) > max_rows:
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(130, 130, 130)
            self.cell(0, 5, f"  ... {len(df) - max_rows} more rows (download CSV for full data)", ln=True)
        self.ln(3)


def generate_pdf_report(session_data: list, session_id: str) -> bytes:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Cover
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 10, "Session Summary", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Session ID : {session_id[:16]}...", ln=True)
    pdf.cell(0, 6, f"Total queries : {len(session_data)}", ln=True)
    pdf.cell(0, 6, f"Generated at  : {datetime.now().strftime('%d %b %Y %H:%M:%S')}", ln=True)
    pdf.ln(6)

    if not session_data:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, "No queries in this session yet.", ln=True)
    else:
        for idx, item in enumerate(session_data, start=1):
            pdf.add_query_block(
                idx         = idx,
                question    = item.get("question", ""),
                sql         = item.get("sql", ""),
                explanation = item.get("explanation", ""),
                insight     = item.get("insight", ""),
                row_count   = item.get("row_count", 0)
            )
            df = item.get("df")
            if df is not None and not df.empty:
                pdf.add_data_table(df)

    # Return as bytes using dest='S' which returns a string in fpdf2
    result = pdf.output()
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    return result.encode("latin-1")