# app.py
import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
import os
import time
import plotly.express as px

# ------------------ CONFIG ------------------
st.set_page_config(page_title="DANCO Output Tracker", layout="wide")
LOGO_FILENAME = "366a80a6-1cef-4a1f-98ef-5e1e9e5ef4db.jpg"  # keep this file in same folder
DATA_FILE = "production_log.xlsx"
LOCK_FILE = DATA_FILE + ".lock"

# ------------------ HEADER ------------------
col1, col2 = st.columns([0.18, 0.82])
with col1:
    if os.path.exists(LOGO_FILENAME):
        st.image(LOGO_FILENAME, width=110)
with col2:
    st.markdown("<h1 style='color:#F15A24; margin-bottom:0;'>🏭 DANCO Production Output Tracker</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:grey; margin-top:0;'>Quality • Trust • Innovation</div>", unsafe_allow_html=True)
st.markdown("---")

# ------------------ PPR Expected Reference Table (fixed) ------------------
# Keys match the "Size & PN" strings used in the form (e.g. "20MM PN 16")
# Values map machine -> expected output (or None if not defined)
PPR_EXPECTED = {
    "20MM PN 16": {"MC 2": 75, "MC 5": 75, "MC 9": 75, "MC 10": 100},
    "20MM PN 20": {"MC 2": 85, "MC 5": 85, "MC 9": 85, "MC 10": 110},
    "20MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "25MM PN 16": {"MC 2": 155, "MC 5": 130, "MC 9": 130, "MC 10": 170},
    "25MM PN 20": {"MC 2": 160, "MC 5": 140, "MC 9": 140, "MC 10": 195},
    "25MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "32MM PN 16": {"MC 2": 165, "MC 5": 150, "MC 9": 150, "MC 10": 195},
    "32MM PN 20": {"MC 2": 170, "MC 5": 155, "MC 9": 150, "MC 10": 195},
    "32MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "40MM PN 16": {"MC 2": 165, "MC 5": 150, "MC 9": 150, "MC 10": 195},
    "40MM PN 20": {"MC 2": 165, "MC 5": 150, "MC 9": 150, "MC 10": 195},
    "40MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "50MM PN 16": {"MC 2": 165, "MC 5": 150, "MC 9": 150, "MC 10": 195},
    "50MM PN 20": {"MC 2": 165, "MC 5": 150, "MC 9": 150, "MC 10": 195},
    "50MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "63MM PN 16": {"MC 2": 170, "MC 5": 165, "MC 9": 155, "MC 10": 200},
    "63MM PN 20": {"MC 2": 175, "MC 5": 170, "MC 9": 165, "MC 10": 205},
    "63MM PN 25": {"MC 2": None, "MC 5": None, "MC 9": None, "MC 10": None},

    "75MM PN 16": {"MC 2": 170, "MC 5": 165, "MC 9": 155, "MC 10": None},
    "75MM PN 20": {"MC 2": 175, "MC 5": 170, "MC 9": 165, "MC 10": None},

    "90MM PN 16": {"MC 2": 170, "MC 5": 165, "MC 9": 155, "MC 10": None},
    "90MM PN 20": {"MC 2": 175, "MC 5": 170, "MC 9": 165, "MC 10": None},

    "110MM PN 16": {"MC 2": 170, "MC 5": 165, "MC 9": 160, "MC 10": None},
    "110MM PN 20": {"MC 2": 175, "MC 5": 170, "MC 9": 170, "MC 10": None},
}

# --------------- Size & PN choices per material ----------------
MATERIAL_SPECS = {
    "HDPE": {
        "sizes": ["16MM","20MM","25MM","32MM","40MM","50MM","63MM","75MM","90MM","110MM",
                  "125MM","140MM","160MM","180MM","200MM","225MM","250MM","280MM",
                  "315MM","355MM","400MM","450MM","500MM","560MM","630MM"],
        "pn": ["6","8","10","12.5","16","20","25"]
    },
    "PPR": {
        "sizes": ["20MM","25MM","32MM","40MM","50MM","63MM","75MM","90MM","110MM"],
        "pn": ["16","20","25"]
    },
    "PP": {
        "sizes": [], "pn": []
    }
}

# ------------------ DATA IO with simple lock ------------------
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    return pd.DataFrame(columns=[
        "Date","Material","Size & PN","Machine","Entered By",
        "Expected Output","Actual Output","Start Time","End Time","Shift Hours","Remarks"
    ])

def acquire_lock(timeout=3):
    start = time.time()
    while True:
        try:
            # try to create lock file atomically
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

def save_data(df):
    got = acquire_lock()
    if not got:
        st.warning("Another user is saving at the moment. Please try again in a moment.")
        return False
    try:
        df.to_excel(DATA_FILE, index=False)
        return True
    finally:
        release_lock()

# ------------------ INITIAL LOAD ------------------
df = load_data()

# ------------------ TABS ------------------
tabs = st.tabs(["📋 Data Entry", "📊 Dashboard", "📤 Export", "ℹ️ Help"])

# ------------------ DATA ENTRY ------------------
with tabs[0]:
    st.header("🧾 Log Production Output")

    with st.form("entry_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.date.today())
        material = st.selectbox("Material Type *", ["HDPE", "PPR", "PP"])

        # build combined Size PN choices for chosen material
        sizes = MATERIAL_SPECS[material]["sizes"]
        pn_values = MATERIAL_SPECS[material]["pn"]
        size_pn_choices = [f"{s} PN {p}" for s in sizes for p in pn_values] if sizes and pn_values else ["N/A"]
        size_pn = st.selectbox("Size & PN *", size_pn_choices)

        machine = st.selectbox("Machine *", ["MC 2", "MC 5", "MC 9", "MC 10", "Other"])
        entered_by = st.text_input("Entered By *")
        # If material is PPR and expected exists for that size+machine, auto-fill expected_output
        expected_auto = None
        if material == "PPR" and size_pn in PPR_EXPECTED:
            expected_auto = PPR_EXPECTED[size_pn].get(machine)
        if expected_auto is not None:
            expected_output = st.number_input("Expected Output (auto-filled, editable)", value=float(expected_auto), step=0.1)
        else:
            expected_output = st.number_input("Expected Output", min_value=0.0, step=0.1)

        actual_output = st.number_input("Actual Output", min_value=0.0, step=0.1)
        start_time = st.time_input("Start Time", value=datetime.datetime.now().time())
        end_time = st.time_input("End Time", value=datetime.datetime.now().time())

        # auto compute shift hours (allow override)
        # If end_time < start_time assume next day
        s_dt = datetime.datetime.combine(datetime.date.today(), start_time)
        e_dt = datetime.datetime.combine(datetime.date.today(), end_time)
        if e_dt < s_dt:
            e_dt += datetime.timedelta(days=1)
        shift_hours_calc = round((e_dt - s_dt).total_seconds() / 3600, 2)
        shift_hours = st.number_input("Shift Hours (auto-calculated, editable)", value=shift_hours_calc, step=0.01)

        remarks = st.text_area("Remarks (optional)")

        submitted = st.form_submit_button("✅ Submit Entry")

        if submitted:
            if not (entered_by and size_pn and machine):
                st.warning("Please fill required fields (Entered By, Size & PN, Machine).")
            else:
                new_row = {
                    "Date": pd.to_datetime(date),
                    "Material": material,
                    "Size & PN": size_pn,
                    "Machine": machine,
                    "Entered By": entered_by,
                    "Expected Output": float(expected_output) if expected_output != "" else None,
                    "Actual Output": float(actual_output),
                    "Start Time": start_time,
                    "End Time": end_time,
                    "Shift Hours": float(shift_hours),
                    "Remarks": remarks
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                ok = save_data(df)
                if ok:
                    st.success("✅ Entry saved successfully!")
                else:
                    st.error("Failed to save entry — please try again.")

# ------------------ DASHBOARD ------------------
with tabs[1]:
    st.header("📊 Production Dashboard")

    if df.empty:
        st.info("No data yet — add entries in the Data Entry tab.")
    else:
        # derived metrics
        df["% Change"] = 0.0
        mask_valid_expected = df["Expected Output"].notna() & (df["Expected Output"] != 0)
        df.loc[mask_valid_expected, "% Change"] = ((df.loc[mask_valid_expected, "Actual Output"] - df.loc[mask_valid_expected, "Expected Output"]) / df.loc[mask_valid_expected, "Expected Output"]) * 100

        # sidebar filters
        st.sidebar.header("🔎 Filters")
        mat_options = list(df["Material"].dropna().unique())
        mat_filter = st.sidebar.multiselect("Material", mat_options, default=mat_options)
        mc_options = list(df["Machine"].dropna().unique())
        mc_filter = st.sidebar.multiselect("Machine", mc_options, default=mc_options)
        # date range filter
        min_date = pd.to_datetime(df["Date"]).min().date()
        max_date = pd.to_datetime(df["Date"]).max().date()
        date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

        filtered = df.copy()
        if mat_filter:
            filtered = filtered[filtered["Material"].isin(mat_filter)]
        if mc_filter:
            filtered = filtered[filtered["Machine"].isin(mc_filter)]
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
            filtered = filtered[(pd.to_datetime(filtered["Date"]).dt.date >= start_date) & (pd.to_datetime(filtered["Date"]).dt.date <= end_date)]

        # KPIs
        total_expected = filtered["Expected Output"].sum(min_count=1) or 0
        total_actual = filtered["Actual Output"].sum(min_count=1) or 0
        total_hours = filtered["Shift Hours"].sum(min_count=1) or 0
        avg_change = filtered["% Change"].mean() if not filtered["% Change"].isna().all() else 0

        # style KPI boxes (grey background)
        st.markdown("""
        <style>
        .kpi-card {
            background:#f0f0f0;
            padding:15px;
            border-radius:8px;
            text-align:center;
        }
        .kpi-number { font-size:20px; font-weight:700; color:#333; }
        .kpi-label { font-size:12px; color:#666; }
        </style>
        """, unsafe_allow_html=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Expected</div><div class='kpi-number'>{total_expected:,.2f}</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Actual</div><div class='kpi-number'>{total_actual:,.2f}</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='kpi-card'><div class='kpi-label'>Total Shift Hours</div><div class='kpi-number'>{total_hours:,.2f}</div></div>", unsafe_allow_html=True)
        k4.markdown(f"<div class='kpi-card'><div class='kpi-label'>Avg % Change</div><div class='kpi-number'>{avg_change:.2f}%</div></div>", unsafe_allow_html=True)

        st.markdown("### 📈 Expected vs Actual by Size (aggregated)")
        # prepare chart data: group by Size & PN and sum expected & actual
        chart_df = filtered.groupby("Size & PN", as_index=False).agg({"Expected Output":"sum", "Actual Output":"sum"})
        if chart_df.empty:
            st.info("No data for selected filters.")
        else:
            # melt for grouped bar chart
            melt = chart_df.melt(id_vars="Size & PN", value_vars=["Expected Output","Actual Output"], var_name="Type", value_name="Value")
            fig = px.bar(melt, x="Size & PN", y="Value", color="Type", barmode="group",
                         labels={"Value":"Quantity","Size & PN":"Size"}, title="Expected vs Actual")
            # show data labels
            fig.update_traces(texttemplate='%{y:.0f}', textposition='outside')
            fig.update_layout(uniformtext_minsize=8, uniformtext_mode='show', legend=dict(title=None), margin=dict(t=60))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 🔎 Table view")
        st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

# ------------------ EXPORT ------------------
with tabs[2]:
    st.header("📤 Export Data")
    if df.empty:
        st.info("No data to export.")
    else:
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        st.download_button("⬇️ Download Excel", data=buffer.getvalue(),
                           file_name=f"production_log_{datetime.date.today()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ------------------ HELP ------------------
with tabs[3]:
    st.header("ℹ️ Help / Notes")
    st.markdown("""
    - The app saves data locally in `production_log.xlsx` in the app folder.
    - For **PPR**, Expected Output auto-fills from the Danco reference table for MC 2 / MC 5 / MC 9 / MC 10.
    - You can override any auto-filled Expected Output before submitting.
    - Sidebar filters control what's shown on dashboard and charts.
    - A simple lock file prevents most simultaneous-write collisions; if you see a save warning, retry after a moment.
    """)
