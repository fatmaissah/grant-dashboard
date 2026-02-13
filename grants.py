import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Grant Tracking Dashboard", layout="wide")

# =====================================================
# DATABASE SETUP
# =====================================================
DB_NAME = "grants.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

# -----------------------------
# CREATE TABLES IF NOT EXISTS
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

# =====================================================
# HELPER FUNCTIONS
# =====================================================
def log_action(grant_id, action):
    c.execute("""
        INSERT INTO audit_trail (grant_id, action, timestamp, user)
        VALUES (?, ?, ?, ?)
    """, (grant_id, action, datetime.now().isoformat(), "Admin"))
    conn.commit()

def load_data():
    df = pd.read_sql("SELECT * FROM grants", conn)
    if not df.empty:
        df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")
        df["submitted_date"] = pd.to_datetime(df["submitted_date"], errors="coerce")
    return df

# =====================================================
# LOAD DATA
# =====================================================
df = load_data()

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "➕ Add / Edit Grant", "📈 Analytics", "🕒 Audit Trail"]
)

# =====================================================
# TAB 1: DASHBOARD (DELETE FROM TABLE)
# =====================================================
with tab1:
    st.title("📊 Grant Dashboard")

    df = load_data()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Grants", len(df))
    col2.metric("Draft", len(df[df.status == "Draft"]))
    col3.metric("Submitted", len(df[df.status == "Submitted"]))
    col4.metric("Funded", len(df[df.status == "Funded"]))

    st.subheader("⏰ Upcoming Deadlines (30 Days)")
    if not df.empty:
        upcoming = df[
            (df.deadline >= datetime.today()) &
            (df.deadline <= datetime.today() + timedelta(days=30))
        ]
        st.dataframe(upcoming, use_container_width=True)

    st.subheader("📁 All Grants")

    if not df.empty:
        st.dataframe(df, use_container_width=True)

        st.markdown("### 🗑️ Delete Grant")

        selected_id = st.selectbox("Select Grant ID", df["id"])

        confirm = st.checkbox("I confirm deletion")

        if st.button("Delete Selected Grant"):
            if confirm:
                c.execute("DELETE FROM grants WHERE id=?", (int(selected_id),))
                conn.commit()
                log_action(int(selected_id), "Deleted")
                st.success("Grant deleted successfully.")
                st.rerun()
            else:
                st.warning("Please confirm deletion.")
    else:
        st.info("No grants available.")

# =====================================================
# TAB 2: ADD / EDIT
# =====================================================
with tab2:
    st.title("➕ Add / Edit Grant")

    df = load_data()
    grant_titles = ["New Grant"] + df.title.tolist() if not df.empty else ["New Grant"]
    selected = st.selectbox("Select Grant", grant_titles)

    grant_data = {}
    if selected != "New Grant":
        grant_data = df[df.title == selected].iloc[0].to_dict()

    with st.form("grant_form"):
        title = st.text_input("Title", grant_data.get("title", ""))
        funder = st.text_input("Funder", grant_data.get("funder", ""))
        funding_amount = st.number_input("Funding Amount", value=float(grant_data.get("funding_amount", 0)))
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "TZS"])
        theme = st.text_input("Theme", grant_data.get("theme", ""))
        status = st.selectbox("Status", ["Draft", "Submitted", "Funded"])
        deadline = st.date_input("Deadline", grant_data.get("deadline", datetime.today()))
        submitted_date = st.date_input("Submitted Date", grant_data.get("submitted_date", datetime.today()))
        organization_involved = st.text_area("Organizations Involved", grant_data.get("organization_involved", ""))
        description = st.text_area("Description", grant_data.get("description", ""))
        key_personnel = st.text_area("Key Personnel", grant_data.get("key_personnel", ""))

        submitted = st.form_submit_button("💾 Save")

    if submitted:
        deadline_val = deadline.isoformat() if deadline else None
        submitted_val = submitted_date.isoformat() if submitted_date else None

        if selected == "New Grant":
            c.execute("""
                INSERT INTO grants
                (title, funder, funding_amount, currency, theme, status,
                 deadline, submitted_date, description,
                 organization_involved, key_personnel, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, funder, funding_amount, currency, theme, status,
                deadline_val, submitted_val, description,
                organization_involved, key_personnel,
                datetime.now().isoformat()
            ))
            conn.commit()

            new_id = c.lastrowid
            log_action(new_id, "Created")
            st.success("Grant added successfully.")

        else:
            grant_id = int(grant_data["id"])
            c.execute("""
                UPDATE grants SET
                    title=?, funder=?, funding_amount=?, currency=?,
                    theme=?, status=?, deadline=?, submitted_date=?,
                    description=?, organization_involved=?, key_personnel=?
                WHERE id=?
            """, (
                title, funder, funding_amount, currency,
                theme, status, deadline_val, submitted_val,
                description, organization_involved, key_personnel,
                grant_id
            ))
            conn.commit()
            log_action(grant_id, "Updated")
            st.success("Grant updated successfully.")

        st.rerun()

# =====================================================
# TAB 3: ANALYTICS
# =====================================================
with tab3:
    st.title("📈 Analytics")

    df = load_data()

    if not df.empty:
        st.subheader("Funding by Status")
        st.bar_chart(df.groupby("status")["funding_amount"].sum())

        st.subheader("Funding Trend by Year")
        trend = df.groupby(df.deadline.dt.year)["funding_amount"].sum()
        st.line_chart(trend)

        st.subheader("Top Funders")
        funders = df.groupby("funder")["funding_amount"].sum().sort_values(ascending=False)
        st.bar_chart(funders)

        st.subheader("Average Funding by Theme")
        themes = df.groupby("theme")["funding_amount"].mean()
        st.bar_chart(themes)
    else:
        st.info("No data available.")

# =====================================================
# TAB 4: AUDIT TRAIL
# =====================================================
with tab4:
    st.title("🕒 Audit Trail")

    audit_df = pd.read_sql("SELECT * FROM audit_trail", conn)

    if not audit_df.empty:
        audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"], errors="coerce")
        audit_df = audit_df.sort_values("timestamp", ascending=False)

        st.subheader("Full Audit Log")
        st.dataframe(audit_df, use_container_width=True)

        st.subheader("Recent Actions")
        st.table(audit_df.head(10)[["grant_id", "action", "user", "timestamp"]])
    else:
        st.info("No audit records yet.")

