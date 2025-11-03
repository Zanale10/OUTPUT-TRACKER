import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px
from io import BytesIO

# -----------------------------
# DATABASE SETUP
# -----------------------------
conn = sqlite3.connect("machine_data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS machine_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    machine TEXT,
    size_running TEXT,
    material TEXT,
    expected_output REAL,
    actual_output REAL,
    deviation REAL,
    remarks TEXT,
    added_by TEXT
)
""")
conn.commit()

# -----------------------------
# PAGE CONFIGURATION
# -----------------------------
st.set_page_config(page_title="Machine Output Tracker", layout="wide")

# -----------------------------
# HEADER WITH LOGO
# -----------------------------
col1, col2 = st.columns([0.15, 0.85])
with col1:
    st.image("logo.jpg", width=100)  # Ensure your logo file is named logo.jpg
with col2:
    st.markdown("<h1 style='color:#f26a21;'>DANCO Machine Output Tracker</h1>", unsafe_allow_html=True)
    st.markdown("**Quality • Trust • Innovation**")

st.markdown("---")

# -----------------------------
# SIDEBAR NAVIGATION
# -----------------------------
menu = ["Data Entry", "Dashboard", "Export / Reports"]
choice = st.sidebar.selectbox("Navigation", menu)

# -----------------------------
# DATA ENTRY PAGE
# -----------------------------
if choice == "Data Entry":
    st.subheader("📥 Enter Daily Machine Data")

    with st.form("data_entry_form"):
        date = st.date_input("Select Date", datetime.now())
        machine = st.selectbox("Select Machine", [f"Machine {i}" for i in range(1, 11)])
        size_running = st.selectbox(
            "Select Pipe Size (mm & PN rating)",
            [
                "20 mm PN 10", "25 mm PN 10", "32 mm PN 10", "40 mm PN 10",
                "50 mm PN 10", "63 mm PN 10", "75 mm PN 10", "90 mm PN 10",
                "110 mm PN 10", "125 mm PN 10", "160 mm PN 10"
            ]
        )

        # Material dropdown
        material = st.selectbox(
            "Select Material",
            ["HDPE", "PPR", "PP"]
        )

        expected_output = st.number_input("Expected Output (kg/hr)", min_value=0.0)
        actual_output = st.number_input("Actual Output (kg/hr)", min_value=0.0)
        remarks = st.text_area("Remarks")
        added_by = st.text_input("Added By")

        deviation = 0
        if expected_output > 0:
            deviation = ((actual_output - expected_output) / expected_output) * 100

        submitted = st.form_submit_button("💾 Save Entry")

        if submitted:
            cursor.execute("""
                INSERT INTO machine_data (date, machine, size_running, material, expected_output, actual_output, deviation, remarks, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (date.strftime("%Y-%m-%d"), machine, size_running, material, expected_output, actual_output, deviation, remarks, added_by))
            conn.commit()
            st.success("✅ Data saved successfully!")

# -----------------------------
# DASHBOARD PAGE
# -----------------------------
elif choice == "Dashboard":
    st.subheader("📊 Machine Performance Dashboard")

    df = pd.read_sql("SELECT * FROM machine_data", conn)

    if df.empty:
        st.info("No data available yet. Please add entries in the Data Entry section.")
    else:
        # Summary stats
        avg_dev = df["deviation"].mean()
        total_entries = len(df)
        st.metric("Average Deviation (%)", f"{avg_dev:.2f}")
        st.metric("Total Entries Recorded", total_entries)

        # Color coding function
        def color_deviation(val):
            if 1 <= abs(val) <= 10:
                color = 'background-color: #d6f5d6'  # Light green
            else:
                color = 'background-color: #f5cccc'  # Light red
            return color

        # Styled table with color code
        st.markdown("### 📋 Detailed Data with Color-Coded Deviations")
        styled_df = df.style.applymap(color_deviation, subset=["deviation"]).format({
            "expected_output": "{:.2f} kg/hr",
            "actual_output": "{:.2f} kg/hr",
            "deviation": "{:.2f}%"
        })
        st.dataframe(styled_df, use_container_width=True)

        # Bar chart: Machine vs Output
        st.markdown("### 📈 Output Comparison by Machine")
        fig = px.bar(
            df,
            x="machine",
            y=["expected_output", "actual_output"],
            barmode="group",
            title="Expected vs Actual Output (kg/hr)",
            labels={"value": "Output (kg/hr)", "machine": "Machine"},
            color_discrete_sequence=["#f26a21", "#1f77b4"]
        )
        st.plotly_chart(fig, use_container_width=True)

        # Filter section
        st.markdown("### 🔍 Filter Data")
        machines = st.multiselect("Select Machine(s) to View", df["machine"].unique())
        materials = st.multiselect("Select Material(s) to View", df["material"].unique())

        filtered_df = df.copy()
        if machines:
            filtered_df = filtered_df[filtered_df["machine"].isin(machines)]
        if materials:
            filtered_df = filtered_df[filtered_df["material"].isin(materials)]

        if not filtered_df.empty:
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("No data matches your selected filters.")

# -----------------------------
# EXPORT / REPORTS PAGE
# -----------------------------
elif choice == "Export / Reports":
    st.subheader("📤 Export Data to Excel or CSV")

    df = pd.read_sql("SELECT * FROM machine_data", conn)

    if df.empty:
        st.info("No data to export yet.")
    else:
        # Download as Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Machine Data")
            writer.close()
        excel_data = output.getvalue()

        st.download_button(
            label="📥 Download Excel File",
            data=excel_data,
            file_name="machine_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Download as CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Download CSV File",
            data=csv,
            file_name="machine_data.csv",
            mime="text/csv"
        )

        st.success("✅ You can now download your live machine data in Excel or CSV format.")

# -----------------------------
# END OF APP
# -----------------------------
