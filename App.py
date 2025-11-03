# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, time
import plotly.express as px
from io import BytesIO
import os

# -----------------------
# CONFIG
# -----------------------
DB_FILE = "tracker.db"
LOGO_FILE = "logo.jpg"  # replace with your filename if different
ADMIN_PASSCODE = "PRD2025"

# -----------------------
# DB SETUP (local SQLite)
# -----------------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS machine_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    date TEXT,
    machine TEXT,
    material TEXT,
    size TEXT,
    pn TEXT,
    expected_output REAL,
    actual_output REAL,
    deviation REAL,
    remarks TEXT,
    added_by TEXT
)
""")

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS expected_output (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material TEXT,
    size TEXT,
    pn TEXT,
    machine TEXT,
    expected REAL
)
""")
conn.commit()

# -----------------------
# CONSTANTS
# -----------------------
MACHINES = [f"Machine {i}" for i in range(1, 11)]

HDPE_PN = ["6", "8", "10", "12.5", "16", "20", "25"]
HDPE_SIZES = ["16","20","25","32","40","50","63","75","90","110","125","140","160","180","200","225","250","280","315","355","400","450","500","560","630"]

PPR_PN = ["16","20","25"]
PPR_SIZES = ["20","25","32","40","50","63","75","90","110"]

MATERIALS = ["HDPE","PPR","PP"]  # PP free-text

# -----------------------
# UI CONFIG
# -----------------------
st.set_page_config(page_title="Output Tracker", layout="wide")

# -----------------------
# Session role handling
# -----------------------
if "role" not in st.session_state:
    st.session_state.role = None
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = ""

def logout():
    st.session_state.role = None
    st.session_state.logged_in_user = ""
    # clear some form keys if exist
    keys = [k for k in list(st.session_state.keys()) if k.startswith("entry_") or k.startswith("log_") or k.startswith("exp_")]
    for k in keys:
        del st.session_state[k]
    st.experimental_rerun()

# -----------------------
# Top: Logo + Title + Role chooser (simple two-button flow)
# -----------------------
col_logo, col_title, col_role = st.columns([0.12, 0.68, 0.20])
with col_logo:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=80)
with col_title:
    st.markdown("<h1 style='color:#f26a21;'>DANCO Machine Output Tracker</h1>", unsafe_allow_html=True)
    st.write("Quality • Trust • Innovation")
with col_role:
    if st.session_state.role is None:
        if st.button("Continue as Other"):
            st.session_state.role = "other"
            st.session_state.logged_in_user = "Other"
            st.experimental_rerun()
        if st.button("Login as Admin"):
            # show password input
            passcode = st.text_input("Enter admin passcode", type="password", key="login_pass")
            if st.button("Submit Passcode"):
                if passcode == ADMIN_PASSCODE:
                    st.session_state.role = "admin"
                    st.session_state.logged_in_user = "Admin"
                    st.success("Logged in as Admin")
                    st.experimental_rerun()
                else:
                    st.error("Incorrect passcode")
    else:
        st.markdown(f"**Role:** {st.session_state.role.capitalize()}  ")
        st.markdown(f"**User:** {st.session_state.logged_in_user}")
        if st.button("Logout"):
            logout()

st.markdown("---")

# -----------------------
# Sidebar Navigation (role-aware)
# -----------------------
base_menu = ["Machine Tracker", "Log Size Change", "Dashboard", "Help", "Export"]
if st.session_state.role == "admin":
    menu = ["Machine Tracker", "Log Size Change", "Expected Output Settings", "Dashboard", "Help", "Export"]
else:
    menu = base_menu

choice = st.sidebar.selectbox("Navigation", menu)

# -----------------------
# Helper functions
# -----------------------
def calculate_deviation(expected, actual):
    try:
        if expected and expected > 0:
            return round(((actual - expected) / expected) * 100, 2)
    except:
        pass
    return 0.0

def finalize_previous_run(machine, new_start_iso):
    cursor.execute("SELECT id, start_time FROM run_log WHERE machine=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1", (machine,))
    row = cursor.fetchone()
    if row:
        rid, start_iso = row
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = datetime.fromisoformat(new_start_iso)
            run_hours = (end_dt - start_dt).total_seconds() / 3600.0
            cursor.execute("UPDATE run_log SET end_time=?, run_hours=? WHERE id=?", (new_start_iso, round(run_hours,3), rid))
            conn.commit()
        except Exception as e:
            # ignore parse errors
            pass

def get_current_run_for_machine(machine):
    cursor.execute("SELECT size, start_time FROM run_log WHERE machine=? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1", (machine,))
    r = cursor.fetchone()
    if r:
        return {"size": r[0], "start_time": r[1]}
    return None

def compute_total_running_hours():
    df_done = pd.read_sql("SELECT run_hours FROM run_log WHERE run_hours IS NOT NULL", conn)
    sum_done = df_done['run_hours'].sum() if not df_done.empty else 0.0
    cursor.execute("SELECT start_time FROM run_log WHERE end_time IS NULL")
    rows = cursor.fetchall()
    sum_ongoing = 0.0
    now = datetime.now()
    for (start_iso,) in rows:
        try:
            start_dt = datetime.fromisoformat(start_iso)
            sum_ongoing += (now - start_dt).total_seconds() / 3600.0
        except:
            pass
    return round(sum_done + sum_ongoing, 3)

def get_expected_from_db(material, size, pn, machine):
    cursor.execute("SELECT expected FROM expected_output WHERE material=? AND size=? AND pn=? AND machine=?", (material, str(size), str(pn), machine))
    r = cursor.fetchone()
    return float(r[0]) if r else None

def reset_form_keys(prefixes):
    for key in list(st.session_state.keys()):
        for p in prefixes:
            if key.startswith(p):
                del st.session_state[key]

# -----------------------
# PAGE: Machine Tracker (Data Entry)
# -----------------------
if choice == "Machine Tracker":
    st.subheader("📥 Enter Production Output (kg/hr)")

    with st.form("entry_form", clear_on_submit=False):
        e_date = st.date_input("Date", key="entry_date", value=date.today())
        e_machine = st.selectbox("Machine", MACHINES, key="entry_machine")
        e_material = st.selectbox("Material", MATERIALS, key="entry_material")

        if e_material == "HDPE":
            e_pn = st.selectbox("PN Rating", HDPE_PN, key="entry_pn")
            e_size = st.selectbox("Size (mm)", HDPE_SIZES, key="entry_size")
        elif e_material == "PPR":
            e_pn = st.selectbox("PN Rating", PPR_PN, key="entry_pn")
            e_size = st.selectbox("Size (mm)", PPR_SIZES, key="entry_size")
        else:
            e_pn = st.text_input("PN Rating (free text)", key="entry_pn")
            e_size = st.text_input("Size (free text)", key="entry_size")

        combined_size = f"{e_size} mm PN {e_pn}" if e_size and e_pn else (str(e_size) if e_size else "")

        # auto-fill expected if HDPE lookup exists
        expected_lookup = None
        if e_material == "HDPE":
            expected_lookup = get_expected_from_db(e_material, e_size, e_pn, e_machine)

        e_expected = st.number_input("Expected Output (kg/hr) - editable", value=float(expected_lookup) if expected_lookup is not None else 0.0, min_value=0.0, key="entry_expected")
        e_actual = st.number_input("Actual Output (kg/hr)", min_value=0.0, key="entry_actual")
        e_remarks = st.text_area("Remarks", key="entry_remarks")
        e_added_by = st.text_input("Added By", key="entry_added_by")

        deviation_val = calculate_deviation(e_expected, e_actual)
        st.markdown(f"**Deviation:** {deviation_val:.2f}%")

        submitted = st.form_submit_button("Save Output Entry")

        if submitted:
            ts = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO machine_logs (timestamp, date, machine, material, size, pn, expected_output, actual_output, deviation, remarks, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ts, e_date.strftime("%Y-%m-%d"), e_machine, e_material, combined_size, str(e_pn), float(e_expected), float(e_actual), float(deviation_val), e_remarks, e_added_by))
            conn.commit()
            st.success("✅ Output entry saved.")

            # reset form fields
            reset_form_keys(["entry_"])
            st.experimental_rerun()

# -----------------------
# PAGE: Log Size Change (start a run)
# -----------------------
elif choice == "Log Size Change":
    st.subheader("🔁 Log Size Change (Start a new run for a machine)")

    with st.form("log_form", clear_on_submit=False):
        log_date = st.date_input("Date", key="log_date", value=date.today())
        log_machine = st.selectbox("Machine", MACHINES, key="log_machine")
        log_material = st.selectbox("Material", MATERIALS, key="log_material")

        if log_material == "HDPE":
            log_pn = st.selectbox("PN Rating", HDPE_PN, key="log_pn")
            log_size = st.selectbox("Size (mm)", HDPE_SIZES, key="log_size")
            log_combined = f"{log_size} mm PN {log_pn}"
        elif log_material == "PPR":
            log_pn = st.selectbox("PN Rating", PPR_PN, key="log_pn")
            log_size = st.selectbox("Size (mm)", PPR_SIZES, key="log_size")
            log_combined = f"{log_size} mm PN {log_pn}"
        else:
            log_pn = st.text_input("PN Rating (free text)", key="log_pn")
            log_size = st.text_input("Size (free text)", key="log_size")
            log_combined = f"{log_size} {('PN ' + log_pn) if log_pn else ''}".strip()

        default_time = datetime.now().time()
        log_time = st.time_input("Start Time (HH:MM)", value=default_time, key="log_start_time")
        log_remarks = st.text_area("Remarks", key="log_remarks")
        log_added_by = st.text_input("Added By", key="log_added_by")

        started = st.form_submit_button("Start New Run")

        if started:
            start_dt = datetime.combine(log_date, log_time)
            start_iso = start_dt.isoformat()
            # finalize previous run
            finalize_previous_run(log_machine, start_iso)
            # insert new run
            cursor.execute("""
                INSERT INTO run_log (date, machine, size, start_time, end_time, run_hours, remarks, added_by)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
            """, (log_date.strftime("%Y-%m-%d"), log_machine, log_combined, start_iso, log_remarks, log_added_by))
            conn.commit()
            st.success(f"✅ Started new run for {log_machine}: {log_combined}")
            reset_form_keys(["log_"])
            st.experimental_rerun()

# -----------------------
# PAGE: Expected Output Settings (admin only)
# -----------------------
elif choice == "Expected Output Settings":
    if st.session_state.role != "admin":
        st.error("Access denied. Only Admin can edit expected outputs.")
    else:
        st.subheader(Expected Output Settings (Admin Only)")

        df_expected = pd.read_sql("SELECT * FROM expected_output ORDER BY material, size, pn, machine", conn)
        if df_expected.empty:
            st.info("No expected-output entries. Add below.")
        else:
            st.dataframe(df_expected, use_container_width=True)

        st.markdown("### Add or Update expected output")
        with st.form("expected_form", clear_on_submit=False):
            s_material = st.selectbox("Material", MATERIALS, key="exp_material")
            if s_material == "HDPE":
                s_pn = st.selectbox("PN", HDPE_PN, key="exp_pn")
                s_size = st.selectbox("Size (mm)", HDPE_SIZES, key="exp_size")
            elif s_material == "PPR":
                s_pn = st.selectbox("PN", PPR_PN, key="exp_pn")
                s_size = st.selectbox("Size (mm)", PPR_SIZES, key="exp_size")
            else:
                s_pn = st.text_input("PN (free text)", key="exp_pn")
                s_size = st.text_input("Size (free text)", key="exp_size")

            s_machine = st.selectbox("Machine", MACHINES, key="exp_machine")
            s_expected = st.number_input("Expected Output (kg/hr)", min_value=0.0, key="exp_expected")
            add_update = st.form_submit_button("Add / Update")

            if add_update:
                cursor.execute("SELECT id FROM expected_output WHERE material=? AND size=? AND pn=? AND machine=?", (s_material, str(s_size), str(s_pn), s_machine))
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE expected_output SET expected=? WHERE id=?", (float(s_expected), row[0]))
                    conn.commit()
                    st.success("✅ Updated existing expected-output entry.")
                else:
                    cursor.execute("INSERT INTO expected_output (material, size, pn, machine, expected) VALUES (?, ?, ?, ?, ?)",
                                   (s_material, str(s_size), str(s_pn), s_machine, float(s_expected)))
                    conn.commit()
                    st.success("✅ Added new expected-output entry.")
                reset_form_keys(["exp_"])
                st.experimental_rerun()

        st.markdown("### Delete an expected-output entry")
        df_expected = pd.read_sql("SELECT * FROM expected_output ORDER BY material, size, pn, machine", conn)
        if not df_expected.empty:
            del_id = st.selectbox("Select ID to delete", options=["None"] + df_expected['id'].astype(str).tolist(), key="del_expected_id")
            if del_id and del_id != "None":
                if st.button("Delete entry"):
                    cursor.execute("DELETE FROM expected_output WHERE id=?", (int(del_id),))
                    conn.commit()
                    st.success("✅ Deleted.")
                    st.experimental_rerun()

# -----------------------
# PAGE: Dashboard
# -----------------------
elif choice == "Dashboard":
    st.subheader(" Dashboard")

    df_logs = pd.read_sql("SELECT * FROM machine_logs", conn)
    df_runs = pd.read_sql("SELECT * FROM run_log", conn)

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        machine_filter = st.selectbox("Machine Filter", options=["All Machines"] + MACHINES)
    with col2:
        size_pool = sorted(set(df_runs['size'].dropna().tolist() + df_logs['size'].dropna().tolist()))
        size_filter = st.selectbox("Size Filter", options=["All Sizes"] + size_pool if size_pool else ["All Sizes"])
    with col3:
        compare_same_size = st.checkbox("Compare same size across machines", value=False)

    # KPIs
    total_hours = compute_total_running_hours()
    k1, k2 = st.columns(2)
    with k1:
        st.metric("Total Running Hours (All Machines)", f"{total_hours:.2f} hrs")
    with k2:
        cursor.execute("SELECT DISTINCT machine FROM run_log WHERE end_time IS NULL")
        running_machines = [r[0] for r in cursor.fetchall()]
        st.metric("Machines Currently Running", len(running_machines))

    st.markdown("---")

    # Machine status table
    status_rows = []
    for m in MACHINES:
        cur = get_current_run_for_machine(m)
        if cur:
            try:
                s_iso = cur['start_time']
                s_dt = datetime.fromisoformat(s_iso)
                hrs = round((datetime.now() - s_dt).total_seconds() / 3600.0, 3)
                status_rows.append({"Machine": m, "Status": "Running", "Current Size": cur['size'], "Start Time": s_dt.strftime("%Y-%m-%d %H:%M"), "Running Hours": hrs})
            except:
                status_rows.append({"Machine": m, "Status": "Running", "Current Size": cur['size'], "Start Time": cur['start_time'], "Running Hours": ""})
        else:
            cursor.execute("SELECT size, start_time, end_time, run_hours FROM run_log WHERE machine=? ORDER BY start_time DESC LIMIT 1", (m,))
            last = cursor.fetchone()
            if last:
                size, s, e, rh = last
                status_rows.append({"Machine": m, "Status": "Idle", "Current Size": size if size else "", "Start Time": s if s else "", "Running Hours": rh if rh else 0.0})
            else:
                status_rows.append({"Machine": m, "Status": "Idle", "Current Size": "", "Start Time": "", "Running Hours": 0.0})
    st.markdown("### Current Machine Status")
    st.table(pd.DataFrame(status_rows))

    st.markdown("---")

    # Apply filters
    df_chart_data = df_logs.copy()
    df_chart_runs = df_runs.copy()
    if machine_filter != "All Machines":
        df_chart_data = df_chart_data[df_chart_data['machine'] == machine_filter]
        df_chart_runs = df_chart_runs[df_chart_runs['machine'] == machine_filter]
    if size_filter != "All Sizes":
        df_chart_data = df_chart_data[df_chart_data['size'] == size_filter]
        df_chart_runs = df_chart_runs[df_chart_runs['size'] == size_filter]

    # Charts area (medium)
    st.markdown("### Charts (Medium size)")
    c1, c2 = st.columns([1,1.2])

    with c1:
        st.markdown("#### Expected vs Actual (kg/hr)")
        if df_chart_data.empty:
            st.info("No output entries for selected filters.")
        else:
            agg = df_chart_data.groupby("machine")[["expected_output","actual_output"]].mean().reset_index()
            fig = px.bar(agg, x="machine", y=["expected_output","actual_output"], barmode="group",
                         labels={"value":"kg/hr","machine":"Machine"}, height=360,
                         color_discrete_sequence=["#f26a21","#1f77b4"])
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("#### Compare Same Size (if enabled)")
        if compare_same_size:
            if size_filter == "All Sizes":
                st.info("Select a specific Size to compare across machines.")
            else:
                compare_df = df_logs[df_logs['size'] == size_filter]
                if compare_df.empty:
                    st.info("No entries for this size.")
                else:
                    agg2 = compare_df.groupby("machine")[["expected_output","actual_output"]].mean().reset_index()
                    fig2 = px.bar(agg2, x="machine", y=["expected_output","actual_output"], barmode="group",
                                  labels={"value":"kg/hr","machine":"Machine"}, height=360,
                                  color_discrete_sequence=["#f26a21","#1f77b4"])
                    st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Enable 'Compare same size across machines' to show comparison chart here.")

    st.markdown("---")

    # Run Log summary (Date | Machine | Size | Start Time | Run Hours)
    st.markdown("### Run Log Summary")
    if df_chart_runs.empty:
        st.info("No run logs for selected filters.")
    else:
        df_display_runs = df_chart_runs[["date","machine","size","start_time","run_hours","remarks","added_by"]].copy()
        df_display_runs['start_time'] = df_display_runs['start_time'].apply(lambda x: x.replace("T"," ") if isinstance(x,str) else x)
        st.dataframe(df_display_runs.rename(columns={
            "date":"Date","machine":"Machine","size":"Size","start_time":"Start Time","run_hours":"Run Hours","remarks":"Remarks","added_by":"Added By"
        }), use_container_width=True)

    st.markdown("---")

    # Detailed output entries color-coded
    st.markdown("### Detailed Output Entries (Deviation color coded)")
    if df_chart_data.empty:
        st.info("No output entries for selected filters.")
    else:
        df_display = df_chart_data.copy()
        df_display = df_display[["timestamp","date","machine","size","material","expected_output","actual_output","deviation","remarks","added_by"]]
        df_display = df_display.rename(columns={
            "timestamp":"Timestamp","date":"Date","machine":"Machine","size":"Size","material":"Material",
            "expected_output":"Expected (kg/hr)","actual_output":"Actual (kg/hr)","deviation":"Deviation (%)",
            "remarks":"Remarks","added_by":"Added By"
        })
        def color_dev(v):
            try:
                if -10 <= v <= 10:
                    return 'background-color: #d6f5d6'
                else:
                    return 'background-color: #f5cccc'
            except:
                return ''
        styled = df_display.style.applymap(lambda v: color_dev(v) if isinstance(v,(int,float)) else '', subset=["Deviation (%)"]) \
                        .format({"Expected (kg/hr)":"{:.2f}","Actual (kg/hr)":"{:.2f}","Deviation (%)":"{:.2f}"})
        st.dataframe(styled, use_container_width=True)

# -----------------------
# PAGE: Help
# -----------------------
elif choice == "Help":
    st.subheader("ℹ️ Help & Quick Guide (for Operators)")
    st.markdown("""
**Short & simple steps — get started quickly**

- **Machine Tracker**
  1. Select the **Date** and **Machine**.
  2. Choose **Material** (HDPE / PPR / PP).
     - For HDPE and PPR the PN and Size dropdowns will appear.
     - For **PP**, type PN and Size manually.
  3. If HDPE and an expected value exists, the **Expected Output** will auto-fill — you can change it if needed.
  4. Enter **Actual Output (kg/hr)** and any **Remarks**.
  5. Click **Save Output Entry** — the form will clear and your record is saved.

- **Log Size Change**
  - Use this when you **start running a different size** on a machine.
  - Enter Machine, Size & Start Time and click **Start New Run**.
  - The app automatically notes the previous run's end time and calculates run hours.

- **Dashboard**
  - See **Total Running Hours**, machine status (Running / Idle), and medium charts.
  - Use Machine and Size filters to focus the view.
  - Use *Compare same size across machines* to compare performance for a particular size.

- **Expected Output Settings** (Admin only)
  - Admins can add/update expected outputs for combinations of Material / Size / PN / Machine.
  - Operators cannot edit these values.

- **Export**
  - Download all data (entries + run logs) as an **Excel** workbook or CSV.

**Notes**
- All data is stored locally in `tracker.db` in the same folder as this app.
- The app works offline — data saved locally. Export to Excel when you want backups.
- If you need help, ask your Admin.

""")

# -----------------------
# PAGE: Export
# -----------------------
elif choice == "Export":
    st.subheader("📤 Export Data")
    df_all = pd.read_sql("SELECT * FROM machine_logs", conn)
    df_runs_all = pd.read_sql("SELECT * FROM run_log", conn)

    if df_all.empty and df_runs_all.empty:
        st.info("No data to export yet.")
    else:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            if not df_all.empty:
                df_all.to_excel(writer, sheet_name="output_entries", index=False)
            if not df_runs_all.empty:
                df_runs_all.to_excel(writer, sheet_name="run_log", index=False)
            writer.save()
        excel_data = output.getvalue()

        st.download_button("📥 Download Excel (entries + run log)", excel_data, "tracker_export.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        if not df_all.empty:
            csv1 = df_all.to_csv(index=False).encode("utf-8")
            st.download_button("📄 Download entries CSV", csv1, "output_entries.csv", "text/csv")
        if not df_runs_all.empty:
            csv2 = df_runs_all.to_csv(index=False).encode("utf-8")
            st.download_button("📄 Download run_log CSV", csv2, "run_log.csv", "text/csv")

# -----------------------
# End - keep DB open (Streamlit reuses process)
# -----------------------
