# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO
import os

# ---------------------------
# DB SETUP
# ---------------------------
DB_FILE = "machine_data.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Table for outputs
cursor.execute("""
CREATE TABLE IF NOT EXISTS machine_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    date TEXT,
    machine TEXT,
    size_running TEXT,
    material TEXT,
    pn_rating TEXT,
    expected_output REAL,
    actual_output REAL,
    deviation REAL,
    remarks TEXT,
    added_by TEXT
)
""")

# Table for run logs (size changes)
cursor.execute("""
CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    machine TEXT,
    size TEXT,
    start_time TEXT,
    end_time TEXT,
    run_hours REAL,
    remarks TEXT,
    added_by TEXT
)
""")
conn.commit()

# ---------------------------
# Constants for dropdowns
# ---------------------------
MACHINES = [f"Machine {i}" for i in range(1, 11)]

HDPE_PN = ["6", "8", "10", "12.5", "16", "20", "25"]
HDPE_SIZES = ["16", "20", "25", "32", "40", "50", "63", "75", "90", "110",
              "125", "140", "160", "180", "200", "225", "250", "280", "315",
              "355", "400", "450", "500", "560", "630"]

PPR_PN = ["16", "20", "25"]
PPR_SIZES = ["20", "25", "32", "40", "50", "63", "75", "90", "110"]

MATERIALS = ["HDPE", "PPR", "PP"]

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="Machine Output & Run Tracker", layout="wide")

# Header with logo (if present)
col_logo, col_title = st.columns([0.15, 0.85])
logo_path = "logo.jpg"
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=100)
with col_title:
    st.markdown("<h1 style='color:#f26a21;'>DANCO Machine Performance Tracker</h1>", unsafe_allow_html=True)
    st.markdown("**Quality • Trust • Innovation**")
st.markdown("---")

# Sidebar
menu = ["Data Entry", "Log Size Change", "Dashboard", "Export"]
choice = st.sidebar.selectbox("Navigation", menu)

# ---------------------------
# Helpers
# ---------------------------
def calculate_deviation(expected, actual):
    if expected and expected > 0:
        return round(((actual - expected) / expected) * 100, 2)
    return 0.0

def finalize_previous_run(machine, new_start_iso, user=None, remarks=None):
    """
    When a new size starts for a machine, find the most recent run_log entry
    for that machine with NULL end_time and set its end_time to new_start
    and compute run_hours.
    """
    cursor.execute("SELECT id, start_time FROM run_log WHERE machine=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1", (machine,))
    row = cursor.fetchone()
    if row:
        rid, start_iso = row
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(new_start_iso)
        run_hours = (end_dt - start_dt).total_seconds() / 3600.0
        cursor.execute("UPDATE run_log SET end_time=?, run_hours=? WHERE id=?", (new_start_iso, round(run_hours, 3), rid))
        conn.commit()

def get_current_run_for_machine(machine):
    cursor.execute("SELECT size, start_time FROM run_log WHERE machine=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1", (machine,))
    r = cursor.fetchone()
    if r:
        return {"size": r[0], "start_time": r[1]}
    return None

def compute_total_running_hours():
    # Sum of run_hours for completed runs
    df_done = pd.read_sql("SELECT run_hours FROM run_log WHERE run_hours IS NOT NULL", conn)
    sum_done = df_done['run_hours'].sum() if not df_done.empty else 0.0

    # For ongoing runs, compute (now - start_time)
    cursor.execute("SELECT start_time FROM run_log WHERE end_time IS NULL")
    rows = cursor.fetchall()
    sum_ongoing = 0.0
    now = datetime.now()
    for (start_iso,) in rows:
        start_dt = datetime.fromisoformat(start_iso)
        sum_ongoing += (now - start_dt).total_seconds() / 3600.0
    return round(sum_done + sum_ongoing, 3)

def reset_form_state():
    # Reset keys in session_state to defaults to clear form
    keys = ["entry_date", "entry_machine", "entry_material", "entry_pn", "entry_size",
            "entry_expected", "entry_actual", "entry_remarks", "entry_added_by",
            "log_machine", "log_material", "log_pn", "log_size", "log_start_time",
            "log_remarks", "log_added_by"]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

# ---------------------------
# DATA ENTRY PAGE
# ---------------------------
if choice == "Data Entry":
    st.subheader("📥 Enter Daily Machine Data (Expected vs Actual - kg/hr)")

    with st.form("data_entry", clear_on_submit=False):
        # use session_state keys for resets
        entry_date = st.date_input("Date", key="entry_date", value=datetime.now().date())
        entry_machine = st.selectbox("Machine", MACHINES, key="entry_machine")
        entry_material = st.selectbox("Material", MATERIALS, key="entry_material")

        # dynamic PN and size depending on material; for PP we allow free text
        entry_pn = ""
        entry_size = ""
        if entry_material == "HDPE":
            entry_pn = st.selectbox("PN Rating", HDPE_PN, key="entry_pn")
            entry_size = st.selectbox("Size (mm)", HDPE_SIZES, key="entry_size")
        elif entry_material == "PPR":
            entry_pn = st.selectbox("PN Rating", PPR_PN, key="entry_pn")
            entry_size = st.selectbox("Size (mm)", PPR_SIZES, key="entry_size")
        else:  # PP free text
            entry_pn = st.text_input("PN Rating (free text)", key="entry_pn")
            entry_size = st.text_input("Size (free text)", key="entry_size")

        # combine size with pn for storage
        combined_size = f"{entry_size} mm PN {entry_pn}" if entry_size and entry_pn else (f"{entry_size}" if entry_size else "")

        entry_expected = st.number_input("Expected Output (kg/hr)", min_value=0.0, key="entry_expected")
        entry_actual = st.number_input("Actual Output (kg/hr)", min_value=0.0, key="entry_actual")
        entry_remarks = st.text_area("Remarks", key="entry_remarks")
        entry_added_by = st.text_input("Added By", key="entry_added_by")

        deviation_val = calculate_deviation(entry_expected, entry_actual)
        st.write(f"**Deviation:** {deviation_val:.2f}%")

        submitted = st.form_submit_button("Save Entry")

        if submitted:
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO machine_data (timestamp, date, machine, size_running, material, pn_rating, expected_output, actual_output, deviation, remarks, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                entry_date.strftime("%Y-%m-%d"),
                entry_machine,
                combined_size,
                entry_material,
                entry_pn,
                float(entry_expected),
                float(entry_actual),
                float(deviation_val),
                entry_remarks,
                entry_added_by
            ))
            conn.commit()
            st.success("✅ Output entry saved.")

            # Clear form fields
            reset_form_state()
            st.experimental_rerun()

# ---------------------------
# LOG SIZE CHANGE PAGE
# ---------------------------
elif choice == "Log Size Change":
    st.subheader("🔁 Log Size Change (Start a new run for a machine)")

    with st.form("log_form", clear_on_submit=False):
        log_date = st.date_input("Date", key="log_date", value=datetime.now().date())
        log_machine = st.selectbox("Machine", MACHINES, key="log_machine")
        log_material = st.selectbox("Material", MATERIALS, key="log_material")

        if log_material == "HDPE":
            log_pn = st.selectbox("PN Rating", HDPE_PN, key="log_pn")
            log_size = st.selectbox("Size (mm)", HDPE_SIZES, key="log_size")
            combined = f"{log_size} mm PN {log_pn}"
        elif log_material == "PPR":
            log_pn = st.selectbox("PN Rating", PPR_PN, key="log_pn")
            log_size = st.selectbox("Size (mm)", PPR_SIZES, key="log_size")
            combined = f"{log_size} mm PN {log_pn}"
        else:
            log_pn = st.text_input("PN Rating (free text)", key="log_pn")
            log_size = st.text_input("Size (free text)", key="log_size")
            combined = f"{log_size} {('PN ' + log_pn) if log_pn else ''}".strip()

        # Start time (allow user to set time; default to now)
        default_time = datetime.now()
        log_start_dt = st.time_input("Start Time (HH:MM)", value=default_time.time(), key="log_start_time")
        log_remarks = st.text_area("Remarks (optional)", key="log_remarks")
        log_added_by = st.text_input("Added By", key="log_added_by")

        submitted_log = st.form_submit_button("Start New Run")

        if submitted_log:
            # compute ISO start datetime using the log_date + log_start_dt
            start_dt = datetime.combine(log_date, log_start_dt)
            start_iso = start_dt.isoformat()

            # finalize previous run for this machine (set its end_time to this start)
            finalize_previous_run(log_machine, start_iso, user=log_added_by, remarks=log_remarks)

            # insert the new run_log with NULL end_time (ongoing)
            cursor.execute("""
                INSERT INTO run_log (date, machine, size, start_time, end_time, run_hours, remarks, added_by)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
            """, (log_date.strftime("%Y-%m-%d"), log_machine, combined, start_iso, log_remarks, log_added_by))
            conn.commit()
            st.success(f"✅ New run started for {log_machine}: {combined}")

            # Clear and rerun to update dashboard info
            reset_form_state()
            st.experimental_rerun()

# ---------------------------
# DASHBOARD PAGE
# ---------------------------
elif choice == "Dashboard":
    st.subheader("📊 Machine Performance Dashboard")

    # load dataframes
    df_data = pd.read_sql("SELECT * FROM machine_data", conn)
    df_runs = pd.read_sql("SELECT * FROM run_log", conn)

    # Machine filter and Size filter
    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        machine_filter = st.selectbox("Machine Filter", options=["All Machines"] + MACHINES)
    with colB:
        # build size options from runs and data
        size_options = sorted(set(df_runs['size'].dropna().tolist() + df_data['size_running'].dropna().tolist()))
        size_filter = st.selectbox("Size Filter (optional)", options=["All Sizes"] + size_options if size_options else ["All Sizes"])
    with colC:
        compare_mode = st.checkbox("Compare same size across machines", value=False)

    # KPI: Total running hours
    total_running_hours = compute_total_running_hours()
    k1, k2 = st.columns(2)
    with k1:
        st.metric("Total Running Hours (All Machines)", f"{total_running_hours:.2f} hrs")
    with k2:
        if machine_filter != "All Machines":
            # compute running hrs for selected machine
            cursor.execute("SELECT run_hours, start_time FROM run_log WHERE machine=?", (machine_filter,))
            rows = cursor.fetchall()
            sum_done = sum([r[0] for r in rows if r[0] is not None]) if rows else 0.0
            # ongoing
            cursor.execute("SELECT start_time FROM run_log WHERE machine=? AND end_time IS NULL", (machine_filter,))
            ongoing = cursor.fetchall()
            sum_ongoing = 0.0
            now = datetime.now()
            for (start_iso,) in ongoing:
                start_dt = datetime.fromisoformat(start_iso)
                sum_ongoing += (now - start_dt).total_seconds() / 3600.0
            st.metric(f"Running Hours - {machine_filter}", f"{round(sum_done + sum_ongoing,3)} hrs")

    st.markdown("---")

    # Filter dataframes based on filters
    filtered_data = df_data.copy()
    filtered_runs = df_runs.copy()

    if machine_filter != "All Machines":
        filtered_data = filtered_data[filtered_data['machine'] == machine_filter]
        filtered_runs = filtered_runs[filtered_runs['machine'] == machine_filter]

    if size_filter and size_filter != "All Sizes":
        filtered_data = filtered_data[filtered_data['size_running'] == size_filter]
        filtered_runs = filtered_runs[filtered_runs['size'] == size_filter]

    # Show current status per machine (latest ongoing run or last run)
    st.markdown("### Current Machine Status")
    status_rows = []
    for m in MACHINES:
        r = get_current_run_for_machine(m)
        if r:
            start_iso = r['start_time']
            start_dt = datetime.fromisoformat(start_iso)
            hrs = (datetime.now() - start_dt).total_seconds() / 3600.0
            status_rows.append({"machine": m, "status": "Running", "current_size": r['size'], "start_time": start_dt.strftime("%Y-%m-%d %H:%M"), "running_hours": round(hrs, 3)})
        else:
            # last ended run
            cursor.execute("SELECT size, start_time, end_time, run_hours FROM run_log WHERE machine=? ORDER BY start_time DESC LIMIT 1", (m,))
            last = cursor.fetchone()
            if last:
                size, s, e, hrs = last
                status_rows.append({"machine": m, "status": "Idle", "current_size": size, "start_time": s if s else "", "running_hours": hrs if hrs else 0.0})
            else:
                status_rows.append({"machine": m, "status": "Idle", "current_size": "", "start_time": "", "running_hours": 0.0})
    st.table(pd.DataFrame(status_rows))

    st.markdown("---")

    # Charts area (compact)
    st.markdown("### Charts (compact)")
    chart_col1, chart_col2 = st.columns([1, 1.2])

    # Chart: expected vs actual by machine (optionally limited by size)
    with chart_col1:
        st.markdown("#### Expected vs Actual (kg/hr) - Medium Chart")
        if filtered_data.empty:
            st.info("No data available for the selected filters.")
        else:
            # aggregate by machine
            agg = filtered_data.groupby("machine")[["expected_output", "actual_output"]].mean().reset_index()
            fig = px.bar(agg, x="machine", y=["expected_output", "actual_output"], barmode="group",
                         labels={"value":"kg/hr", "machine":"Machine"}, height=360,
                         color_discrete_sequence=["#f26a21", "#1f77b4"])
            st.plotly_chart(fig, use_container_width=True)

    # Chart: compare same size across machines (if requested)
    with chart_col2:
        st.markdown("#### Compare Size Across Machines (if enabled)")
        if compare_mode and size_filter and size_filter != "All Sizes":
            compare_df = df_data[df_data['size_running'] == size_filter]
            if compare_df.empty:
                st.info("No entries for that size.")
            else:
                agg_comp = compare_df.groupby("machine")[["expected_output", "actual_output"]].mean().reset_index()
                fig2 = px.bar(agg_comp, x="machine", y=["expected_output", "actual_output"], barmode="group",
                              labels={"value":"kg/hr", "machine":"Machine"}, height=360,
                              color_discrete_sequence=["#f26a21", "#1f77b4"])
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Enable 'Compare same size across machines' and select a Size to compare.")

    st.markdown("---")

    # Detailed log table (Date, Machine, Size, Starting Time, Run Hours, Remarks)
    st.markdown("### Run Log (Date | Machine | Size | Starting Time | Run Hours | Remarks)")
    if filtered_runs.empty:
        st.info("No runs logged yet (or no runs match your filters).")
    else:
        display_runs = filtered_runs[["date", "machine", "size", "start_time", "end_time", "run_hours", "remarks", "added_by"]].copy()
        display_runs['start_time'] = display_runs['start_time'].apply(lambda x: x.replace("T", " ") if isinstance(x, str) else x)
        display_runs['end_time'] = display_runs['end_time'].apply(lambda x: (x.replace("T", " ") if isinstance(x, str) else x))
        st.dataframe(display_runs.rename(columns={
            "date":"Date", "machine":"Machine", "size":"Size", "start_time":"Start Time",
            "end_time":"End Time", "run_hours":"Run Hours", "remarks":"Remarks", "added_by":"Added By"
        }), use_container_width=True)

    st.markdown("---")

    # Detailed data table with color-coded deviation
    st.markdown("### Detailed Output Entries (with color-coded Deviation)")
    if filtered_data.empty:
        st.info("No output entries match the filters.")
    else:
        def highlight_dev(v):
            try:
                if -10 <= v <= 10:
                    return 'background-color: #d6f5d6'  # light green
                else:
                    return 'background-color: #f5cccc'  # light red
            except:
                return ''
        display_data = filtered_data.copy()
        display_data = display_data[["timestamp", "date", "machine", "size_running", "material", "expected_output", "actual_output", "deviation", "remarks", "added_by"]]
        display_data = display_data.rename(columns={
            "timestamp":"Timestamp","date":"Date","machine":"Machine","size_running":"Size",
            "material":"Material","expected_output":"Expected (kg/hr)","actual_output":"Actual (kg/hr)",
            "deviation":"Deviation (%)","remarks":"Remarks","added_by":"Added By"
        })
        styled = display_data.style.applymap(lambda v: highlight_dev(v) if isinstance(v, (int, float)) else '', subset=["Deviation (%)"]) \
                              .format({"Expected (kg/hr)":"{:.2f}", "Actual (kg/hr)":"{:.2f}", "Deviation (%)":"{:.2f}"})
        st.dataframe(styled, use_container_width=True)

# ---------------------------
# EXPORT PAGE
# ---------------------------
elif choice == "Export":
    st.subheader("📤 Export Data")
    df_all = pd.read_sql("SELECT * FROM machine_data", conn)
    df_runs_all = pd.read_sql("SELECT * FROM run_log", conn)

    if df_all.empty and df_runs_all.empty:
        st.info("No data to export yet.")
    else:
        # Export machine_data as Excel with two sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            if not df_all.empty:
                df_all.to_excel(writer, sheet_name="output_entries", index=False)
            if not df_runs_all.empty:
                df_runs_all.to_excel(writer, sheet_name="run_log", index=False)
            writer.save()
        excel_data = output.getvalue()

        st.download_button("Download Excel file (entries + runs)", excel_data, "machine_tracker_data.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        csv1 = df_all.to_csv(index=False).encode("utf-8") if not df_all.empty else None
        csv2 = df_runs_all.to_csv(index=False).encode("utf-8") if not df_runs_all.empty else None

        if csv1:
            st.download_button("Download entries CSV", csv1, "output_entries.csv", "text/csv")
        if csv2:
            st.download_button("Download run_log CSV", csv2, "run_log.csv", "text/csv")

# ---------------------------
# Close DB on exit
# ---------------------------
# (Do not close here while app still running; DB connection is reused)
