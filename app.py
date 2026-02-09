import streamlit as st
import pandas as pd
import pymongo
import plotly.express as px
from datetime import datetime
import time

# --- إعداد الصفحة ---
st.set_page_config(page_title="ITQAN Dashboard", layout="wide", page_icon="📊")

# --- الاتصال بقاعدة البيانات ---
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])

client = init_connection()
db = client.itqan_db

# --- دوال التعامل مع الداتا ---
def get_user(username, password):
    return db.users.find_one({"username": username, "password": password})

def add_ticket(user_data, type, item, details):
    ticket = {
        "user_name": user_data['name'],
        "user_room": user_data['room'],
        "type": type,
        "item": item, # نوع الطلب (قهوة، طابعة..)
        "details": details,
        "status": "New",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_only": datetime.now().strftime("%Y-%m-%d") # عشان التحليلات اليومية
    }
    db.tickets.insert_one(ticket)

def get_data_as_dataframe():
    # بنجيب الداتا ونحولها لـ DataFrame عشان التحليل
    data = list(db.tickets.find())
    if data:
        df = pd.DataFrame(data)
        return df
    return pd.DataFrame()

# --- دالة تسجيل الدخول ---
def login():
    st.sidebar.title("🔐 Login System")
    if 'user' in st.session_state:
        return st.session_state['user']

    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        user = get_user(username, password)
        if user:
            user['_id'] = str(user['_id'])
            st.session_state['user'] = user
            st.rerun()
        else:
            st.sidebar.error("بيانات خطأ")
    return None

# ==================== بداية التطبيق ====================
user = login()

if user:
    # القائمة الجانبية (معلومات المستخدم)
    st.sidebar.divider()
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    st.sidebar.write(f"🛡️ **{user['role']}**")
    
    if st.sidebar.button("تسجيل خروج", type="primary"):
        del st.session_state['user']
        st.rerun()

    # ==================== (1) لوحة الأدمن (Admin Dashboard) ====================
    if user['role'] == "Admin":
        st.title("📊 لوحة القيادة والتحكم")
        
        admin_tabs = st.tabs(["📈 التحليلات والتقارير", "👥 إدارة الموظفين", "🎫 مراقبة الطلبات"])
        
        # --- تاب 1: التحليلات (Analytics) ---
        with admin_tabs[0]:
            df = get_data_as_dataframe()
            
            if not df.empty:
                # إحصائيات سريعة
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("إجمالي الطلبات", len(df))
                col2.metric("طلبات الأوفيس", len(df[df['type'] == "Office"]))
                col3.metric("طلبات IT", len(df[df['type'] == "IT"]))
                col4.metric("قيد الانتظار", len(df[df['status'] == "New"]))
                
                st.divider()
                
                # الرسم البياني 1: أكثر الغرف طلباً (Bar Chart)
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🏠 أكثر المكاتب طلباً")
                    room_counts = df['user_room'].value_counts().reset_index()
                    room_counts.columns = ['المكتب', 'عدد الطلبات']
                    fig1 = px.bar(room_counts, x='المكتب', y='عدد الطلبات', color='عدد الطلبات', color_continuous_scale='Viridis')
                    st.plotly_chart(fig1, use_container_width=True)

                # الرسم البياني 2: أكثر الموظفين طلباً (Bar Chart)
                with c2:
                    st.subheader("👤 أكثر الموظفين نشاطاً")
                    person_counts = df['user_name'].value_counts().reset_index()
                    person_counts.columns = ['الموظف', 'عدد الطلبات']
                    fig2 = px.bar(person_counts, x='الموظف', y='عدد الطلبات', color='عدد الطلبات', color_continuous_scale='Magma')
                    st.plotly_chart(fig2, use_container_width=True)
                
                st.divider()

                # الرسم البياني 3: توزيع الطلبات (Pie Chart)
                c3, c4 = st.columns(2)
                with c3:
                    st.subheader("☕ أكثر المشروبات طلباً")
                    # بنفلتر طلبات الأوفيس بس
                    office_df = df[df['type'] == "Office"]
                    # بناخد اسم المشروب قبل علامة "-" (عشان نفصل السكر)
                    office_df['main_item'] = office_df['item'].apply(lambda x: x.split('-')[0].strip())
                    item_counts = office_df['main_item'].value_counts().reset_index()
                    item_counts.columns = ['المشروب', 'العدد']
                    fig3 = px.pie(item_counts, values='العدد', names='المشروب', hole=0.4)
                    st.plotly_chart(fig3, use_container_width=True)

                with c4:
                    st.subheader("🛠️ مشاكل الـ IT الشائعة")
                    it_df = df[df['type'] == "IT"]
                    if not it_df.empty:
                        it_counts = it_df['item'].value_counts().reset_index()
                        it_counts.columns = ['نوع المشكلة', 'العدد']
                        fig4 = px.pie(it_counts, values='العدد', names='نوع المشكلة')
                        st.plotly_chart(fig4, use_container_width=True)
                    else:
                        st.info("مفيش داتا للـ IT لسه")
            else:
                st.info("لسه مفيش أي طلبات اتعملت عشان نطلع تحليلات.")

        # --- تاب 2: إدارة الموظفين (Users) ---
        with admin_tabs[1]:
            st.subheader("إضافة وحذف الموظفين")
            
            with st.expander("➕ إضافة مستخدم جديد (أدمن أو موظف)", expanded=True):
                with st.form("new_user_form"):
                    c1, c2 = st.columns(2)
                    n_name = c1.text_input("الاسم بالكامل")
                    n_user = c2.text_input("اسم المستخدم (Login)")
                    c3, c4 = st.columns(2)
                    n_pass = c3.text_input("كلمة المرور", type="password")
                    n_room = c4.text_input("المكتب / الغرفة")
                    n_role = st.selectbox("الوظيفة", ["Employee", "Admin", "Office Boy", "IT Support"])
                    
                    if st.form_submit_button("حفظ المستخدم"):
                        if db.users.find_one({"username": n_user}):
                            st.error("اسم المستخدم ده موجود قبل كده!")
                        else:
                            db.users.insert_one({
                                "username": n_user, "password": n_pass, "name": n_name,
                                "role": n_role, "room": n_room
                            })
                            st.success("تم الإضافة بنجاح!")
                            time.sleep(1)
                            st.rerun()
            
            st.divider()
            st.write("🔻 **قائمة المستخدمين الحاليين:**")
            users = list(db.users.find())
            for u in users:
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.text(f"👤 {u['name']}")
                c2.text(f"📍 {u['room']}")
                c3.text(f"🛡️ {u['role']}")
                if c4.button("حذف", key=u['username']):
                    db.users.delete_one({"_id": u['_id']})
                    st.rerun()

        # --- تاب 3: مراقبة الطلبات الحية (Live Tickets) ---
        with admin_tabs[2]:
            st.subheader("جميع الطلبات المفتوحة")
            open_tickets = list(db.tickets.find({"status": "New"}))
            if open_tickets:
                for t in open_tickets:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([1, 4, 1])
                        col1.warning(t['type'])
                        col2.write(f"**{t['user_name']}** ({t['user_room']}) طلب: {t['item']}")
                        if col3.button("إغلاق", key=str(t['_id'])):
                            from bson.objectid import ObjectId
                            db.tickets.update_one({"_id": ObjectId(t['_id'])}, {"$set": {"status": "Done"}})
                            st.rerun()
            else:
                st.success("العمل مستقر، مفيش طلبات معلقة.")

    # ==================== (2) لوحة الموظف (Employees Only) ====================
    elif user['role'] == "Employee":
        st.title(f"👋 أهلاً {user['name'].split()[0]}")
        
        req_tabs = st.tabs(["☕ طلب بوفيه", "💻 دعم فني"])
        
        with req_tabs[0]:
            c1, c2 = st.columns(2)
            drink = c1.selectbox("المشروب", ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون"])
            sugar = c1.selectbox("السكر", ["بدون", "مظبوط", "زيادة", "سكر دايت"])
            notes = c2.text_input("أي ملاحظات؟")
            if st.button("اطلب الآن 🚀", use_container_width=True):
                add_ticket(user, "Office", f"{drink} - {sugar}", notes)
                st.success("تم إرسال طلبك!")

        with req_tabs[1]:
            issue = st.selectbox("المشكلة في إيه؟", ["الإنترنت", "الكمبيوتر", "الطابعة", "برنامج Excel/Word"])
            desc = st.text_area("اشرح المشكلة باختصار")
            if st.button("أرسل للدعم الفني 🛠️", use_container_width=True):
                add_ticket(user, "IT", issue, desc)
                st.success("تم التبليغ!")

    # ==================== (3) لوحة مقدمي الخدمة (Office Boy / IT) ====================
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        st.header(f"طلبات {role_type}")
        
        tickets = list(db.tickets.find({"type": role_type, "status": "New"}))
        if tickets:
            for t in tickets:
                with st.container(border=True):
                    st.subheader(f"{t['user_room']}")
                    st.write(f"👤 {t['user_name']}")
                    st.info(f"📋 {t['item']}")
                    if t['details']: st.write(f"📝 {t['details']}")
                    st.caption(t['timestamp'])
                    if st.button("تم التنفيذ ✅", key=str(t['_id'])):
                        from bson.objectid import ObjectId
                        db.tickets.update_one({"_id": ObjectId(t['_id'])}, {"$set": {"status": "Done"}})
                        st.rerun()
        else:
            st.success("مفيش طلبات جديدة، استريح شوية ☕")

else:
    st.info("يرجى تسجيل الدخول")
