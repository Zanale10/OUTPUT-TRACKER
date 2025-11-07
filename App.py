import streamlit as st
import pandas as pd
import plotly.express as px
import time
import os
from io import BytesIO
import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Danco Output Tracker", layout="wide")

# ---------------- REFRESH LOGIC ----------------
UPLOAD_PATH = "uploaded_output_data.xlsx"
EXPIRY_HOURS = 16

# ---------------- LOGO & TITLE ----------------
col1, col2 = st.columns([0.2, 0.8])
with col1:
    if os.path.exists("danco_logo.jpg"):
        st.image("danco_logo.jpg", width=120)
with col2:
    st.title("🧾 Danco Production Output Tracker")

# ---------------- FILE UPLOAD ----------------
def upload_file():
    uploaded_file = st.file_uploader("Upload Actual Output Excel File", type=["xlsx"])
    if uploaded_file is not None:
        with open(UPLOAD_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("✅ File uploaded successfully! Please refresh or proceed to Dashboard.")
        st.stop()
    else:
        st.info("Please upload a valid Excel file to continue.")
        st.stop()

# ---------------- FILE EXPIRY CHECK ----------------
if os.path.exists(UPLOAD_PATH):
    file_mtime = os.path.getmtime(UPLOAD_PATH)
    age_seconds = time.time() - file_mtime
    if age_seconds > EXPIRY_HOURS * 3600:
        st.warning(f"File expired (>{EXPIRY_HOURS} hours). Please upload a new file.")
        upload_file()
else:
    upload_file()

# ---------------- LOAD DATA ----------------
try:
    df = pd.read_excel(UPLOAD_PATH)
except Exception as e:
    st.error(f"❌ Error reading file: {e}")
    st.stop()

# ---------------- CLEANUP ----------------
numeric_cols = ["EXPECTED", "RECORDED", "EXPECTED WEIGHT", "ACHIEVED TOTAL WEIGHT", "TOTAL HOURS"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ---------------- CALCULATIONS ----------------
if "EXPECTED WEIGHT" in df.columns and "ACHIEVED TOTAL WEIGHT" in df.columns:
    df["% CHANGE"] = ((df["ACHIEVED TOTAL WEIGHT"] - df["EXPECTED WEIGHT"]) / df["EXPECTED WEIGHT"]) * 100

# ---------------- SIDEBAR FILTERS ----------------
st.sidebar.header("🔍 Filters")
if "MONTH" in df.columns:
    month_list = sorted(df["MONTH"].dropna().unique())
    selected_months = st.sidebar.multiselect("Select Month(s)", month_list, default=month_list)
    df = df[df["MONTH"].isin(selected_months)]

if "MACHINE" in df.columns:
    machine_list = df["MACHINE"].dropna().unique()
    selected_machines = st.sidebar.multiselect("Select Machine(s)", machine_list, default=machine_list)
    df = df[df["MACHINE"].isin(selected_machines)]

if "MATERIAL" in df.columns:
    material_list = df["MATERIAL"].dropna().unique()
    selected_materials = st.sidebar.multiselect("Select Material(s)", material_list, default=material_list)
    df = df[df["MATERIAL"].isin(selected_materials)]

# ---------------- KPI CALCULATIONS ----------------
total_expected_weight = round(df["EXPECTED WEIGHT"].sum(), 2) if "EXPECTED WEIGHT" in df.columns else 0
total_achieved_weight = round(df["ACHIEVED TOTAL WEIGHT"].sum(), 2) if "ACHIEVED TOTAL WEIGHT" in df.columns else 0
avg_expected = round(df["EXPECTED"].mean(), 2) if "EXPECTED" in df.columns else 0
avg_recorded = round(df["RECORDED"].mean(), 2) if "RECORDED" in df.columns else 0
percent_change = round(((total_achieved_weight - total_expected_weight) / total_expected_weight) * 100, 2) if total_expected_weight != 0 else 0

# ---------------- KPI STYLING ----------------
kpi_style = """
<div style='
    background-color: #e6e6e6;
    padding: 12px;
    border-radius: 12px;
    text-align: center;
    font-size: 16px;
    font-weight: bold;
    box-shadow: 3px 3px 8px rgba(0,0,0,0.1);
'>
    <div style='font-size:13px;color:#ff6600;'>{label}</div>
    <div style='font-size:22px;color:black;'>{value}</div>
</div>
"""

col1, col2, col3, col4, col5 = st.columns(5)
col1.markdown(kpi_style.format(label="Achieved Weight", value=total_achieved_weight), unsafe_allow_html=True)
col2.markdown(kpi_style.format(label="Expected Weight", value=total_expected_weight), unsafe_allow_html=True)
col3.markdown(kpi_style.format(label="Avg Expected Output", value=avg_expected), unsafe_allow_html=True)
col4.markdown(kpi_style.format(label="Avg Recorded Output", value=avg_recorded), unsafe_allow_html=True)
col5.markdown(kpi_style.format(label="% Change", value=f"{percent_change}%"), unsafe_allow_html=True)

st.markdown("---")

# ---------------- BAR CHART ----------------
if "MACHINE" in df.columns and "PIPE" in df.columns:
    melted_df = df.melt(
        id_vars=["PIPE", "MACHINE"],
        value_vars=["EXPECTED WEIGHT", "ACHIEVED TOTAL WEIGHT"],
        var_name="Type",
        value_name="Weight"
    )
    fig = px.bar(
        melted_df,
        x="Weight",
        y="PIPE",
        color="Type",
        barmode="group",
        text="Weight",
        facet_col="MACHINE",
        title="Expected vs Achieved Weight by Machine & Size",
        color_discrete_map={"EXPECTED WEIGHT": "grey", "ACHIEVED TOTAL WEIGHT": "orange"},
        height=600
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Weight", yaxis_title="Pipe Size")
    st.plotly_chart(fig, use_container_width=True)

# ---------------- RAW DATA ----------------
with st.expander("View Raw Data"):
    columns_to_show = [
        col for col in [
            "MONTH", "MACHINE", "MATERIAL", "PIPE", "EXPECTED", "RECORDED",
            "EXPECTED WEIGHT", "ACHIEVED TOTAL WEIGHT", "% CHANGE"
        ] if col in df.columns
    ]
    st.dataframe(df[columns_to_show])

# ---------------- REUPLOAD BUTTON ----------------
if st.button("🔄 Upload New File / Replace Existing"):
    if os.path.exists(UPLOAD_PATH):
        os.remove(UPLOAD_PATH)
    st.success("File cleared. Please upload a new file below.")
    upload_file()
