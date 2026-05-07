import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import openai
import json
import time
import plotly.express as px
from twilio.rest import Client

# ---------------- CONFIG & DB ----------------
st.set_page_config(page_title="NexPal AI", layout="wide")

# SECURITY: Admin passkey for restricted sections
ADMIN_PASSKEY = "admin123" 

def get_db():
    conn = sqlite3.connect("nexpal.db", check_same_thread=False)
    return conn

conn = get_db()
cursor = conn.cursor()

# ---------------- TWILIO SETUP ----------------
try:
    TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
    TWILIO_NUMBER = st.secrets["TWILIO_WHATSAPP_NUMBER"]
    ADMIN_NUMBER = st.secrets["ADMIN_WHATSAPP"]
    wa_client = Client(TWILIO_SID, TWILIO_TOKEN)
except Exception as e:
    st.error(f"Configuration Error: {e}")

# ---------------- TEAM WHATSAPP MAP ----------------
TEAM_WHATSAPP_MAP = {

    "HVAC": st.secrets.get(
        "HVAC_WHATSAPP",
        ADMIN_NUMBER
    ),

    "PLUMBING": st.secrets.get(
        "MAINTENANCE_WHATSAPP",
        ADMIN_NUMBER
    ),

    "ELECTRICAL": st.secrets.get(
        "MAINTENANCE_WHATSAPP",
        ADMIN_NUMBER
    ),

    "JANITORIAL": st.secrets.get(
        "SOFTSERVICE_WHATSAPP",
        ADMIN_NUMBER
    ),

    "PANTRY": st.secrets.get(
        "SOFTSERVICE_WHATSAPP",
        ADMIN_NUMBER
    ),

    "GENERAL": ADMIN_NUMBER
}

def send_whatsapp(to_number, message):
    try:
        response = wa_client.messages.create(
            from_=TWILIO_NUMBER,
            body=message,
            to=to_number
        )

        print("WHATSAPP SENT:", response.sid)

    except Exception as e:
        st.sidebar.error(f"WhatsApp Error: {str(e)}")
        print("TWILIO ERROR:", e)
    
# Create Tables
cursor.executescript("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, 
    issue TEXT, 
    location TEXT, 
    category TEXT, 
    sub_category TEXT, 
    priority TEXT, 
    role TEXT, 
    loop TEXT, 
    status TEXT,
    sla_deadline TEXT,
    feedback TEXT,
    reopened_count INTEGER DEFAULT 0,
    last_updated TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT UNIQUE,
    department TEXT,
    uom TEXT,
    opening_stock INTEGER,
    reorder_level INTEGER
);
CREATE TABLE IF NOT EXISTS inventory_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    date TEXT,
    type TEXT,
    quantity INTEGER
);
CREATE TABLE IF NOT EXISTS vendors_amc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name TEXT,
    service_type TEXT,
    expiry_date TEXT,
    contact TEXT
);
""")
conn.commit()

ticket_id = cursor.lastrowid

# ---------------- DEPARTMENT & ROLE MAPPING ----------------
DEPT_MAP = {
    "JANITORIAL": "Soft Service Department", 
    "PANTRY": "Soft Service Department",
    "ELECTRICAL": "Maintenance Department",
    "PLUMBING": "Maintenance Department",
    "HVAC": "Maintenance Department",
    "GENERAL": "Help Desk"
}

# ---------------- AI ENGINE ----------------
def analyze_complaint(user_input):
    prompt = f"""
    Analyze: '{user_input}'. 
    Return JSON: {{'category': '...', 'sub_category':'...', 'location': '...', 'priority': '...'}}. 
    
    Sub-Category Rules:
    - HVAC: 'AC Cold', 'AC Hot', 'AC Maintenance'
    - ELECTRICAL: 'Lighting', 'Power Issue', 'Lift Malfunction'
    - PLUMBING: 'Leakage', 'Clogging', 'Water Pressure'
    - JANITORIAL: 'Cleaning', 'Restock', 'Pest Control', 
    - PANTRY: 'Refill', 'Coffee Machine Complaint', 'Water Bottles Request'

    Location Formatting:
    1. Expand: 'ws'->'Workstation', 'mr'->'Meeting Room', 'br'->'Board Room', 'GRR'->'Gents Restroom'.
    2. Floors: '1F'->'1st Floor', 'GF'->'Ground Floor'.
    3. Format: [Floor], [Location Name] [Number/ID].
    
    Allowed Categories: {list(DEPT_MAP.keys())}
    """
    try:
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except: return None

def compute_sla_countdown(sla_time):
    if pd.isna(sla_time): return "N/A"
    now = datetime.now()
    delta = sla_time - now
    if delta.total_seconds() <= 0: return "⏰ Overdue"
    mins = int(delta.total_seconds() // 60)
    secs = int(delta.total_seconds() % 60)
    return f"{mins:02d}:{secs:02d}"

# ---------- ESCALATION ALERT FUNCTION ----------

def send_escalation_alert(ticket_row):

    escalation_msg = f"""
🚨 SLA BREACH ALERT

🎫 Ticket ID: {ticket_row['id']}

Category: {ticket_row['category']}

Issue: {ticket_row['sub_category']}

Location: {ticket_row['location']}

Priority: {ticket_row['priority']}

Current Status: {ticket_row['status']}

⚠️ SLA exceeded.
Admin intervention required.
"""

    send_whatsapp(ADMIN_NUMBER, escalation_msg)

# ---------------- SIDEBAR NAVIGATION ----------------
st.sidebar.title("🏢 NexPal Operations")
page = st.sidebar.radio("Navigate", ["Employee Helpdesk", "Admin Dashboard", "Inventory & AMC"])

if page in ["Admin Dashboard", "Inventory & AMC"]:
    st.sidebar.markdown("---")
    pwd_input = st.sidebar.text_input("Enter Admin Passkey", type="password")
    if pwd_input != ADMIN_PASSKEY:
        if pwd_input: st.error("❌ Incorrect Passkey.")
        else: st.warning("🔒 Restricted access.")
        st.stop()

# ---------------- EMPLOYEE HELPDESK ----------------
if page == "Employee Helpdesk":
    st.header("💬 NexPal Facilities AI")
    
    if "success_msg" in st.session_state:
        st.success(st.session_state.success_msg)
        with st.container(border=True):
            st.markdown(f"### 🎫 Ticket Confirmed")
            st.markdown(f"**Your Request:** \"_{st.session_state.last_issue_text}_\"")
            st.markdown(f"**Mapped Location:** {st.session_state.last_loc}")
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Category", st.session_state.last_cat)
            col_b.metric("Priority", st.session_state.last_pri)
            col_c.write(f"**Routed To:** \n\n {st.session_state.last_dept}")
            
        if st.button("Log Another Request"):
            keys_to_clear = ["success_msg", "last_issue_text", "last_loc", "last_cat", "last_pri", "last_dept", "raw_text"]
            for key in keys_to_clear:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
        st.stop() 

    user_msg = st.text_area("How can we help you?", placeholder="Describe the Issue (e.g., 'AC Over Cooling 1F MR 2')...")
    
    if st.button("Analyze Request") and user_msg:
        res = analyze_complaint(user_msg)
        if res:
            if res.get('category') not in DEPT_MAP: res['category'] = "GENERAL"
            st.session_state.draft = res
            st.session_state.raw_text = user_msg

    if "draft" in st.session_state:
        st.subheader("🔍 Review & Confirm")
        d = st.session_state.draft
        col1, col2 = st.columns(2)
        
        with col1:
            cat_list = list(DEPT_MAP.keys())
            cat = st.selectbox("Category", cat_list, index=cat_list.index(d['category']))
            sub_cat = st.text_input("Detected Issue Type", value=d.get('sub_category', 'General Maintenance'))
            loc = st.text_input("Location", d['location'])
            
        with col2:
            pri_list = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            p_val = d.get('priority', 'MEDIUM').upper()
            if p_val not in pri_list: p_val = "MEDIUM"
            pri = st.selectbox("Priority", pri_list, index=pri_list.index(p_val))
            assigned_dept = DEPT_MAP.get(cat)
            st.info(f"**Action Plan:** Routing this **{sub_cat}** ticket to **{assigned_dept}**.")

        if st.button("Confirm & Submit"):

            now_dt = datetime.now()

            sla_delta = 30 if cat == "HVAC" else 15
            sla_time = now_dt + timedelta(minutes=sla_delta)

            # ---------- SAVE TO DATABASE ----------
            cursor.execute("""
                INSERT INTO complaints 
                (date, issue, location, category, sub_category, priority, role, loop, status, sla_deadline) 
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_dt.strftime("%Y-%m-%d %H:%M"),
                st.session_state.raw_text,
                loc,
                cat,
                sub_cat,
                pri,
                assigned_dept,
                "Helpdesk",
                "Open",
                sla_time.strftime("%Y-%m-%d %H:%M")
            ))

            conn.commit()

            # ---------- GET GENERATED TICKET ID ----------
            ticket_id = cursor.lastrowid

            # ---------- GET TEAM NUMBER ----------
            target_phone = TEAM_WHATSAPP_MAP.get(cat)

            # ---------- SERVICE TEAM MESSAGE ----------
            service_msg = f"""
        🛠️ NEW FACILITY TICKET

        🎫 Ticket ID: {ticket_id}

        Category: {cat}
        Issue: {sub_cat}
        Location: {loc}
        Priority: {pri}
        Employee Message: {st.session_state.raw_text}
        Status: OPEN
        """
            # ---------- Send to Service Team ----------
            if target_phone:
                send_whatsapp(target_phone, service_msg)
            
            # ---------- SUCCESS UI ----------
            st.session_state.success_msg = (
                f"✅ Ticket #{ticket_id} succesfully logged and routed to {assigned_dept}."
            )

            st.session_state.last_issue_text = st.session_state.raw_text
            st.session_state.last_loc = loc
            st.session_state.last_cat = cat
            st.session_state.last_pri = pri
            st.session_state.last_dept = assigned_dept

            del st.session_state.draft

            st.rerun()
        
# ---------------- ADMIN DASHBOARD ----------------
elif page == "Admin Dashboard":
    
    st.header("📊 Facilities Strategic Insights")
    st.caption("⏳ Dashboard auto-refreshes every 10 seconds")

    df = pd.read_sql_query("SELECT * FROM complaints", conn)

    if not df.empty:

        # ---------- SLA PROCESSING ----------
        df['sla_deadline'] = pd.to_datetime(
            df['sla_deadline'],
            errors='coerce'
        )

        now = datetime.now()

        df['SLA Status'] = df['sla_deadline'].apply(
            lambda x: "⏰ Overdue"
            if pd.notnull(x) and x < now
            else "On Time"
        )

        df['Countdown'] = df['sla_deadline'].apply(
            compute_sla_countdown
        )

        # ---------- MAIN KPI ----------
        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "🎫 Total Tickets",
            len(df)
        )

        c2.metric(
            "🟢 Open",
            len(df[df['status'] == 'Open'])
        )

        c3.metric(
            "🛠️ In Progress",
            len(df[df['status'] == 'In Progress'])
        )

        c4.metric(
            "✅ Closed",
            len(df[df['status'] == 'Closed'])
        )

        st.divider()

        # ---------- SLA INSIGHTS ----------
        overdue_count = len(
            df[df['SLA Status'] == "⏰ Overdue"]
        )

        on_time_count = len(
            df[df['SLA Status'] == "On Time"]
        )

        sla_compliance = round(
            (on_time_count / len(df)) * 100,
            1
        ) if len(df) > 0 else 0

        reopened_total = 0

        if 'reopened_count' in df.columns:
            reopened_total = df['reopened_count'].fillna(0).sum()

        st.subheader("📈 SLA & Operations Insights")

        i1, i2, i3, i4 = st.columns(4)

        i1.metric(
            "⏰ SLA Breaches",
            overdue_count
        )

        i2.metric(
            "📊 SLA Compliance",
            f"{sla_compliance}%"
        )

        i3.metric(
            "🔁 Reopened Tickets",
            int(reopened_total)
        )

        i4.metric(
            "🚨 Critical Tickets",
            len(df[df['priority'] == "CRITICAL"])
        )

        st.divider()

        # ---------- CHARTS ----------
        colA, colB = st.columns(2)

        with colA:
            fig1 = px.pie(
                df,
                names='status',
                hole=0.5,
                title="Ticket Status Distribution"
            )

            st.plotly_chart(
                fig1,
                use_container_width=True
            )

        with colB:
            fig2 = px.histogram(
                df,
                x="category",
                color="priority",
                barmode="group",
                title="Priority by Department"
            )

            st.plotly_chart(
                fig2,
                use_container_width=True
            )

        st.divider()

        # ---------- OVERDUE ALERT ----------
        overdue_df = df[
            df['SLA Status'] == "⏰ Overdue"]
        # ---------- SEND ESCALATION ALERTS ----------

        for _, row in overdue_df.iterrows():

            if row['status'] != "Escalated":

                send_escalation_alert(row)

                cursor.execute("""
                    UPDATE complaints
                    SET status = ?
                    WHERE id = ?
                """, (
                    "Escalated",
                    row['id']
                ))
        conn.commit()
        
        if not overdue_df.empty:

            st.error(
                f"🚨 {len(overdue_df)} SLA Breached Tickets!"
            )

            st.dataframe(
                overdue_df[
                    [
                        'id',
                        'issue',
                        'location',
                        'priority',
                        'Countdown'
                    ]
                ],
                use_container_width=True
            )

        st.divider()

        # ---------- TICKET REGISTRY ----------
        st.subheader("📋 Ticket Registry")

        styled_df = df[
            [
                'id',
                'date',
                'issue',
                'category',
                'priority',
                'status',
                'SLA Status',
                'Countdown'
            ]
        ].style.map(
            lambda v:
            "background-color:red;color:white"
            if v == "⏰ Overdue"
            else "",
            subset=["SLA Status"]
        )

        st.dataframe(
            styled_df,
            use_container_width=True
        )

        st.divider()

        # ---------- QUICK STATUS UPDATE ----------
        with st.expander("🛠️ Quick Update Ticket Status"):

            active_ids = df[
                df['status'] != 'Closed'
            ]['id'].tolist()

            if active_ids:

                t_id = st.selectbox(
                    "Select Ticket ID",
                    active_ids
                )

                n_status = st.selectbox(
                    "New Status",
                    [
                        "Open",
                        "In Progress",
                        "On Hold",
                        "Closed"
                    ]
                )

                if st.button("Update Status"):

                    cursor.execute(
                        """
                        UPDATE complaints
                        SET status = ?,
                            last_updated = ?
                        WHERE id = ?
                        """,
                        (
                            n_status,
                            now.strftime("%Y-%m-%d %H:%M"),
                            t_id
                        )
                    )

                    conn.commit()

                    st.success(
                        f"✅ Ticket {t_id} updated to {n_status}"
                    )

                    st.rerun()

            else:
                st.success("🎉 No active tickets")

    else:
        st.info("No tickets found in the database.")

    # ---------- AUTO REFRESH ----------
    time.sleep(10)
    st.rerun()

# ---------------- INVENTORY & AMC ----------------
elif page == "Inventory & AMC":
    tab1, tab2 = st.tabs(["📦 Stock Management", "🤝 Vendor Contracts"])
    
    with tab1:
        st.header("Inventory Tracker")
        inv_items = pd.read_sql_query("SELECT * FROM inventory", conn)
        
        if not inv_items.empty:
            option_map = {f"{r['item_name']} ({r['uom']})": r['id'] for _, r in inv_items.iterrows()}
            sel_display = st.selectbox("Select Item", list(option_map.keys()))
            item_id = option_map[sel_display]
            
            with st.form("inv_form", clear_on_submit=True):
                colx, coly = st.columns(2)
                t_type = colx.radio("Action", ["Usage", "Purchase"], horizontal=True)
                t_qty = coly.number_input("Quantity", min_value=1)
                if st.form_submit_button("Log Transaction"):
                    cursor.execute("INSERT INTO inventory_log (item_id, date, type, quantity) VALUES (?,?,?,?)",
                                   (item_id, datetime.now().strftime("%Y-%m-%d"), t_type, t_qty))
                    conn.commit()
                    st.success("Transaction Logged.")
                    st.rerun()

            calc_query = """
                SELECT i.item_name, i.uom, i.opening_stock,
                COALESCE(SUM(CASE WHEN l.type = 'Purchase' THEN l.quantity ELSE 0 END), 0) as purchased,
                COALESCE(SUM(CASE WHEN l.type = 'Usage' THEN l.quantity ELSE 0 END), 0) as used,
                (i.opening_stock + COALESCE(SUM(CASE WHEN l.type = 'Purchase' THEN l.quantity ELSE 0 END), 0) - 
                COALESCE(SUM(CASE WHEN l.type = 'Usage' THEN l.quantity ELSE 0 END), 0)) as balance,
                i.reorder_level
                FROM inventory i LEFT JOIN inventory_log l ON i.id = l.item_id GROUP BY i.id
            """
            stock_df = pd.read_sql_query(calc_query, conn)
            st.dataframe(stock_df, use_container_width=True)
            
            for _, row in stock_df[stock_df['balance'] <= stock_df['reorder_level']].iterrows():
                st.error(f"⚠️ Reorder Alert: {row['item_name']} (Current: {row['balance']})")
        else:
            st.warning("No inventory items found.")

    with tab2:
        st.header("Vendor AMC Tracking")
        amc_df = pd.read_sql_query("SELECT * FROM vendors_amc", conn)
        if not amc_df.empty:
            amc_df['expiry_date'] = pd.to_datetime(amc_df['expiry_date'])
            amc_df['Days Left'] = (amc_df['expiry_date'] - datetime.now()).dt.days
            st.dataframe(amc_df, use_container_width=True)
        else:
            st.info("Vendor database is empty.")