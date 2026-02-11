
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Grant Tracking Dashboard", layout="wide")

# -----------------------------
# Paths & DB setup
# -----------------------------
DB_NAME = "grants.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

# -----------------------------
# Ensure tables exist
# -----------------------------
c.execute("""
CREATE TABLE IF NOT EXISTS grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    funder TEXT,
    funding_amount REAL,
    currency TEXT,
    theme TEXT,
    status TEXT,
    deadline TEXT,
    submitted_date TEXT,
    description TEXT,
    organization_involved TEXT,
    key_personnel TEXT,
    created_at TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_id INTEGER,
    action TEXT,
    timestamp TEXT,
    user TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_id INTEGER,
    file_name TEXT,
    file_path TEXT,
    uploaded_at TEXT
)
""")

conn.commit()

# -----------------------------
# Insert sample data if empty
# -----------------------------
count = c.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
if count == 0:
    sample_grants = [
        ("AI for Climate-Smart Irrigation", "UKRI", 250000, "GBP", "AI & Climate", "Submitted",
         datetime(2026, 3, 20).isoformat(), datetime(2026, 2, 5).isoformat(),
         "Machine learning and IoT for optimizing irrigation for smallholder farmers.",
         "DLab Tanzania", "PI: Dr A. Jongo | Data Scientist: T. Mer | Email: ajongo@dlab.or.tz", datetime.now().isoformat()),

        ("Digital Health Analytics", "Bill & Melinda Gates Foundation", 150000, "USD", "Health Data", "Draft",
         datetime(2026, 4, 15).isoformat(), None,
         "Using big data to track health trends in Tanzania.",
         "University of Dar es Salaam", "PI: Dr S. Mwanga | Data Analyst: T. Mer | Email: smwanga@uni.tz", datetime.now().isoformat()),

        ("Sustainable Fisheries Project", "FAO", 200000, "USD", "Blue Economy", "Funded",
         datetime(2026, 1, 30).isoformat(), datetime(2026, 1, 10).isoformat(),
         "Improving coastal fisheries management using data-driven models.",
         "Coastal Research Institute", "PI: Dr N. Mkapa | Data Scientist: T. Mer | Email: nmkapa@uni.tz", datetime.now().isoformat())
    ]

    c.executemany("""
    INSERT INTO grants (title, funder, funding_amount, currency, theme, status, deadline,
    submitted_date, description, organization_involved, key_personnel, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_grants)
    conn.commit()

# -----------------------------
# Load data
# -----------------------------
df = pd.read_sql("SELECT * FROM grants", conn)
df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")
df["submitted_date"] = pd.to_datetime(df["submitted_date"], errors="coerce")

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "➕ Add / Edit Grant", "📈 Analytics", "🕒 Audit Trail"]
)

# =====================================================
# TAB 1: DASHBOARD
# =====================================================
with tab1:
    st.title("📊 Grant Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Grants", len(df))
    col2.metric("Draft", len(df[df.status == "Draft"]))
    col3.metric("Submitted", len(df[df.status == "Submitted"]))
    col4.metric("Funded", len(df[df.status == "Funded"]))

    st.subheader("⏰ Upcoming Deadlines (30 Days)")
    upcoming = df[(df.deadline >= datetime.today()) & (df.deadline <= datetime.today() + timedelta(days=30))]
    st.dataframe(upcoming, width="stretch")

    st.subheader("📁 All Grants")
    st.dataframe(df, width="stretch")

# =====================================================
# TAB 2: ADD / EDIT / DELETE
# =====================================================
with tab2:
    st.title("➕ Add / Edit Grant")

    grant_titles = ["New Grant"] + df.title.dropna().tolist()
    selected = st.selectbox("Select Grant", grant_titles)

    if selected == "New Grant":
        grant_data = {}
    else:
        grant_data = df[df.title == selected].iloc[0].to_dict()

    with st.form("grant_form"):
        title = st.text_input("Title", grant_data.get("title", ""))
        funder = st.text_input("Funder", grant_data.get("funder", ""))
        funding_amount = st.number_input("Funding Amount", value=float(grant_data.get("funding_amount", 0)))
        currency = st.selectbox("Currency", ["USD", "GBP", "EUR", "TZS"], index=0)
        theme = st.text_input("Theme", grant_data.get("theme", ""))
        status = st.selectbox("Status", ["Draft", "Submitted", "Funded"], index=0)
        deadline = st.date_input("Deadline", grant_data.get("deadline", datetime.today()))
        submitted_date = st.date_input("Submitted Date", grant_data.get("submitted_date", datetime.today()))
        organization_involved = st.text_area("Organizations Involved", grant_data.get("organization_involved", ""))
        description = st.text_area("Description", grant_data.get("description", ""))
        key_personnel = st.text_area("Key Personnel", grant_data.get("key_personnel", ""))

        uploaded_file = st.file_uploader("Attach Proposal (PDF/DOC)", type=["pdf", "docx"])
    
        submitted = st.form_submit_button("💾 Save")

if submitted and selected == "New Grant":
    # sanitize dates
    deadline_val = deadline.isoformat() if deadline else None
    submitted_val = submitted_date.isoformat() if submitted_date else None

    c.execute("""
        INSERT INTO grants
        (title, funder, funding_amount, currency, theme, status, deadline,
         submitted_date, description, organization_involved, key_personnel, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, funder, funding_amount, currency, theme, status,
        deadline_val, submitted_val,
        description, organization_involved, key_personnel,
        datetime.now().isoformat()
    ))
    conn.commit()

    st.success("✅ New grant added")

    # reset form values
    for key in ["title","funder","funding_amount","theme","organization_involved","description","key_personnel","deadline","submitted_date"]:
        st.session_state[key] = ""

    st.rerun()

        else:
            grant_id = int(grant_data["id"])
            c.execute("""
                UPDATE grants SET
                title=?, funder=?, funding_amount=?, currency=?, theme=?, status=?,
                deadline=?, submitted_date=?, description=?, organization_involved=?, key_personnel=?
                WHERE id=?
            """, (
                title, funder, funding_amount, currency, theme, status,
                deadline.isoformat(), submitted_date.isoformat(),
                description, organization_involved, key_personnel, grant_id
            ))
            conn.commit()
            st.success("✅ Grant updated")
            st.rerun()


    if selected != "New Grant":
        if st.button("🗑️ Delete Grant"):
            c.execute("DELETE FROM grants WHERE id=?", (grant_data["id"],))
            conn.commit()
            st.success("Grant deleted")
            st.experimental_rerun()

# =====================================================
# TAB 3: ANALYTICS
# =====================================================
with tab3:
    st.title("📈 Analytics")
    if not df.empty:
        st.subheader("Funding by Status")
        st.bar_chart(df.groupby("status")["funding_amount"].sum())

        st.subheader("Funding Trend Over Time")
        trend = df.groupby(df.deadline.dt.year)["funding_amount"].sum()
        st.line_chart(trend)

        st.subheader("Top Funders by Total Amount")
        funders = df.groupby("funder")["funding_amount"].sum().sort_values(ascending=False)
        st.bar_chart(funders)

        st.subheader("Average Funding by Theme")
        themes = df.groupby("theme")["funding_amount"].mean().sort_values(ascending=False)
        st.bar_chart(themes)
    else:
        st.info("No grants available yet. Add some grants to see analytics.")

# =====================================================
# TAB 4: AUDIT TRAIL
# =====================================================
with tab4:
    st.title("🕒 Audit Trail")

    audit_df = pd.read_sql("SELECT * FROM audit_trail", conn)

    if not audit_df.empty:
        # Convert timestamps to datetime
        audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"], errors="coerce")

        # Sort by most recent
        audit_df = audit_df.sort_values("timestamp", ascending=False)

        st.subheader("Full Audit Trail")
        st.dataframe(audit_df, use_container_width=True)

        st.subheader("Recent Actions")
        recent_actions = audit_df.head(10)
        st.table(recent_actions[["grant_id", "action", "user", "timestamp"]])
    else:

        st.info("No audit trail entries yet.")






