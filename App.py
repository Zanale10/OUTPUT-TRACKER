import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
import os

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Output Tracker", layout="wide")
st.title(" Production Output Tracker")

DATA_FILE = "output_data.xlsx"

# -------------------- LOAD OR INIT DATA --------------------
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    else:
        return pd.DataFrame(columns=[
            "Date", "Machine", "Size", "Operator", "Expected Output",
            "Actual Output", "Start Time", "End Time", "Remarks"
        ])

def save_data(df):
    with pd.ExcelWriter(DATA_FILE, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)

# -------------------- INITIALIZE --------------------
df = load_data()

# -------------------- TABS --------------------
tabs = st.tabs(["🧾 Data Entry", "📊 Dashboard", "📤 Export", "❓ Help"])

# -------------------- DATA ENTRY TAB --------------------
with tabs[0]:
    st.header("Log New Production Output")

    with st.form("entry_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.date.today())
        machine = st.text_input("Machine Name *")
        size = st.text_input("Size *")
        operator = st.text_input("Operator Name *")
        expected_output = st.number_input("Expected Output", min_value=0.0, step=0.1)
        actual_output = st.number_input("Actual Output", min_value=0.0, step=0.1)
        start_time = st.time_input("Start Time", datetime.datetime.now().time())
        end_time = st.time_input("End Time", datetime.datetime.now().time())
        remarks = st.text_area("Remarks (optional)")

        submitted = st.form_submit_button("💾 Submit Entry")

        if submitted:
            if not (machine and size and operator):
                st.warning("Please fill in all required fields (*)")
            else:
                new_row = {
                    "Date": date,
                    "Machine": machine,
                    "Size": size,
                    "Operator": operator,
                    "Expected Output": expected_output,
                    "Actual Output": actual_output,
                    "Start Time": start_time,
                    "End Time": end_time,
                    "Remarks": remarks
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success("✅ Entry saved successfully!")

# -------------------- DASHBOARD TAB --------------------
with tabs[1]:
    st.header(" Production Dashboard")

    if not df.empty:
        df["% Change"] = ((df["Actual Output"] - df["Expected Output"]) / df["Expected Output"]) * 100
        df["Running Hours"] = (
            pd.to_datetime(df["End Time"].astype(str)) - pd.to_datetime(df["Start Time"].astype(str))
        ).dt.total_seconds() / 3600

        # Filters
        col1, col2 = st.columns(2)
        machines = col1.multiselect("Filter by Machine", df["Machine"].unique(), default=list(df["Machine"].unique()))
        sizes = col2.multiselect("Filter by Size", df["Size"].unique(), default=list(df["Size"].unique()))
        df_filtered = df[df["Machine"].isin(machines) & df["Size"].isin(sizes)]

        # KPIs
        total_expected = df_filtered["Expected Output"].sum()
        total_actual = df_filtered["Actual Output"].sum()
        avg_change = df_filtered["% Change"].mean()
        total_hours = df_filtered["Running Hours"].sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Expected", f"{total_expected:,.0f}")
        c2.metric("Total Actual", f"{total_actual:,.0f}")
        c3.metric("Running Hours", f"{total_hours:,.2f}")
        c4.metric("Avg % Change", f"{avg_change:.2f}%")

        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.info("No production entries yet. Add data under the 'Data Entry' tab.")

# -------------------- EXPORT TAB --------------------
with tabs[2]:
    st.header("📤 Export Production Log")

    if not df.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Production Log")
        st.download_button(
            "Download Excel File",
            data=output.getvalue(),
            file_name=f"production_log_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No data to export.")

# -------------------- HELP TAB --------------------
with tabs[3]:
    st.header("❓ How to Use the App")
    st.markdown("""
    **Welcome to the Output Tracker!**
    
    - 🧾 **Data Entry:** Fill in production details and click *Submit Entry* to save.
    - 📊 **Dashboard:** View live data, apply filters, and monitor KPIs.
    - 📤 **Export:** Download all data to Excel for reporting.
    - 🌐 **Access:** Once deployed, anyone with the link can enter or view data.

    💡 *Tip:* The app saves all data in a local file called `output_data.xlsx` in the app directory.
    """)

