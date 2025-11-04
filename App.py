import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from io import BytesIO
import datetime

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Connect to your Supabase PostgreSQL
conn = psycopg2.connect(DATABASE_URL)

# --- Load environment variables ---
load_dotenv()

# --- Database Connection ---
def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# --- App Title ---
st.set_page_config(page_title="Production Output Tracker", layout="wide")
st.title(" Production Output Tracker")

# --- Tabs ---
tabs = st.tabs(["Data Entry", "Dashboard", "Export Reports"])

# --- DATA ENTRY TAB ---
with tabs[0]:
    st.header("🧾 Log Production Output")
    with st.form("data_entry_form"):
        date = st.date_input("Date", datetime.date.today())
        machine = st.text_input("Machine Name")
        size = st.text_input("Size")
        operator = st.text_input("Operator Name")
        expected_output = st.number_input("Expected Output", min_value=0)
        actual_output = st.number_input("Actual Output", min_value=0)
        start_time = st.time_input("Start Time", datetime.datetime.now().time())
        end_time = st.time_input("End Time", datetime.datetime.now().time())
        remarks = st.text_area("Remarks (optional)")

        submitted = st.form_submit_button("Submit Entry")

        if submitted:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS production_log (
                        id SERIAL PRIMARY KEY,
                        date DATE,
                        machine TEXT,
                        size TEXT,
                        operator TEXT,
                        expected_output FLOAT,
                        actual_output FLOAT,
                        start_time TIME,
                        end_time TIME,
                        remarks TEXT
                    );
                """)
                cur.execute("""
                    INSERT INTO production_log (date, machine, size, operator, expected_output, actual_output, start_time, end_time, remarks)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (date, machine, size, operator, expected_output, actual_output, start_time, end_time, remarks))
                conn.commit()
                cur.close()
                conn.close()
                st.success("✅ Entry saved successfully!")
            except Exception as e:
                st.error(f"❌ Database error: {e}")

# --- DASHBOARD TAB ---
with tabs[1]:
    st.header(" Production Dashboard")

    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM production_log", conn)
        conn.close()

        if not df.empty:
            df["% Change"] = ((df["actual_output"] - df["expected_output"]) / df["expected_output"]) * 100
            df["running_hours"] = (
                pd.to_datetime(df["end_time"].astype(str)) - pd.to_datetime(df["start_time"].astype(str))
            ).dt.total_seconds() / 3600

            # --- Filters ---
            col1, col2 = st.columns(2)
            machine_filter = col1.multiselect("Filter by Machine", df["machine"].unique())
            size_filter = col2.multiselect("Filter by Size", df["size"].unique())

            if machine_filter:
                df = df[df["machine"].isin(machine_filter)]
            if size_filter:
                df = df[df["size"].isin(size_filter)]

            # --- Aggregate KPIs ---
            total_expected = df["expected_output"].sum()
            total_actual = df["actual_output"].sum()
            total_hours = df["running_hours"].sum()
            avg_change = df["% Change"].mean()

            # --- KPI Display ---
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Expected Output", f"{total_expected:,.0f}")
            kpi2.metric("Actual Output", f"{total_actual:,.0f}")
            kpi3.metric("Running Hours", f"{total_hours:,.2f}")
            delta_color = "normal"
            if avg_change < 0:
                delta_color = "inverse"
            elif avg_change > 10:
                delta_color = "off"
            kpi4.metric("% Change (avg)", f"{avg_change:.2f}%", delta=None, delta_color=delta_color)

            # --- Data Table ---
            def color_logic(val):
                if val < 0:
                    return "background-color: red; color: white;"
                elif val > 10:
                    return "background-color: yellow;"
                return ""

            st.dataframe(df.style.map(color_logic, subset=["% Change"]))
        else:
            st.info("No data available yet.")
    except Exception as e:
        st.error(f"❌ Error loading dashboard: {e}")

# --- EXPORT TAB ---
with tabs[2]:
    st.header("📤 Export Data to Excel")

    try:
        conn = get_connection()
        df_export = pd.read_sql("SELECT * FROM production_log", conn)
        conn.close()

        if not df_export.empty:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Production Log")
            st.download_button(
                label="Download Excel File",
                data=output.getvalue(),
                file_name="production_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No data to export.")
    except Exception as e:
        st.error(f"❌ Error exporting data: {e}")
