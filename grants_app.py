import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import hashlib
import uuid

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Grant Tracking Dashboard",
    layout="wide"
)

# -----------------------------
# Paths & DB setup
# -----------------------------
DB_NAME = "grants.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

# -----------------------------
# Create tables
# -----------------------------
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT
)
""")

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
# Helper functions
# -----------------------------
def hash_password(password: str) -> str:
    """Hash password with salt for security."""
    salt = uuid.uuid4().hex
    return hashlib.sha256((password + salt).encode()).hexdigest() + ":" + salt

def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify password against stored salted hash."""
    hash_val, salt = stored_hash.split(":")
    return hash_val == hashlib.sha256((provided_password + salt).encode()).hexdigest()

def log_action(grant_id, action, user):
    """Log user actions for audit trail."""
    c.execute("""
        INSERT INTO audit_trail (grant_id, action, timestamp, user)
        VALUES (?, ?, ?, ?)
    """, (grant_id, action, datetime.now().isoformat(), user))
    conn.commit()

def get_grants():
    """Load grants into DataFrame."""
    df = pd.read_sql("SELECT * FROM grants", conn)
    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")
    df["submitted_date"] = pd.to_datetime(df["submitted_date"], errors="coerce")
    return df

# -----------------------------
# Authentication
# -----------------------------
st.sidebar.title("🔐 Login")

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and verify_password(user[1], password):
            st.session_state.user = username
            st.success("✅ Logged in successfully")
        else:
            st.error("❌ Invalid credentials")

    if st.sidebar.button("Create Account"):
        try:
            c.execute("INSERT INTO users VALUES (?, ?)", (username, hash_password(password)))
            conn.commit()
            st.success("🎉 Account created")
        except sqlite3.IntegrityError:
            st.error("⚠️ User already exists")

    st.stop()

st.sidebar.success(f"👤 Logged in as {st.session_state.user}")

# -----------------------------
# Load data
# -----------------------------
df = get_grants()

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
    upcoming = df[
        (df.deadline >= datetime.today()) &
        (df.deadline <= datetime.today() + timedelta(days=30))
    ]
    st.dataframe(upcoming, use_container_width=True)

    st.subheader("📁 All Grants")
    st.dataframe(df, use_container_width=True)

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

        if submitted:
            try:
                if selected == "New Grant":
                    c.execute("""
                        INSERT INTO grants
                        (title, funder, funding_amount, currency, theme, status, deadline,
                         submitted_date, description, organization_involved, key_personnel, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        title, funder, funding_amount, currency, theme, status,
                        deadline.isoformat(), submitted_date.isoformat(),
                        description, organization_involved, key_personnel, datetime.now().isoformat()
                    ))
                    grant_id = c.lastrowid
                    log_action(grant_id, "Created", st.session_state.user)
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
                    log_action(grant_id, "Updated", st.session_state.user)

                if uploaded_file:
                    path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                    with open(path, "wb") as f:
                        f.write(uploaded_file.read())
                    c.execute("""
                        INSERT INTO attachments (grant_id, file_name, file_path, uploaded_at)
                        VALUES (?, ?, ?, ?)
                    """, (grant_id, uploaded_file.name, path, datetime.now().isoformat()))

                conn.commit()
                st.success("✅ Saved successfully")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"⚠️ Error saving grant: {e}")

    if selected != "New Grant":
        st.subheader("Description")
        st.write(grant_data.get("description", ""))
        st.markdown("### Key Personnel")
        st.text(grant_data.get("key_personnel", ""))

        if st.button("🗑️ Delete Grant"):
            c.execute("DELETE FROM grants WHERE id=?", (grant_data["id"],))
            log_action(grant_data["id"], "Deleted", st.session_state.user)
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
        # Group by year of deadline
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
        audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"], errors="coerce")
        audit_df = audit_df.sort_values("timestamp", ascending=False)

        st.dataframe(audit_df, use_container_width=True)

        st.subheader("Recent Actions")
        recent_actions = audit_df.head(10)
        st.table(recent_actions[["grant_id", "action", "user", "timestamp"]])
    else:
        st.info("No audit trail entries yet.")