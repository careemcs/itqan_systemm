import streamlit as st
import pandas as pd
import pymongo
import plotly.express as px
from datetime import datetime
import time

# --- إعداد الصفحة ---
st.set_page_config(page_title="ITQAN Cloud", layout="wide", page_icon="☁️")

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
        "item": item,
        "details": details,
        "status": "New",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date_only": datetime.now().strftime("%Y-%m-%d")
    }
    db.tickets.insert_one(ticket)

def update_ticket_status(ticket_id, status):
    from bson.objectid import ObjectId
    db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": {"status": status}})

# --- تسجيل الدخول ---
def login():
    st.sidebar.title("🔐 ITQAN System")
    if 'user' in st.session_state:
        return st.session_state['user']

    username = st.sidebar.text_input("اسم المستخدم")
    password = st.sidebar.text_input("كلمة المرور", type="password")
    
    if st.sidebar.button("دخول"):
        user = get_user(username, password)
        if user:
            user['_id'] = str(user['_id'])
            st.session_state['user'] = user
            st.rerun()
        else:
            st.sidebar.error("بيانات خطأ")
    return None

# ==================== التطبيق الرئيسي ====================
user = login()

if user:
    # القائمة الجانبية
    st.sidebar.divider()
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    
    if st.sidebar.button("تسجيل خروج"):
        del st.session_state['user']
        st.rerun()

    # ---------------------------------------------------------
    # السيناريو الأول: الأدمن (تحكم كامل + تحليلات + بدون تحديث مزعج)
    # ---------------------------------------------------------
    if user['role'] == "Admin":
        st.title("📊 لوحة القيادة (Admin Dashboard)")
        
        # تابات الأدمن
        tabs = st.tabs(["📈 التحليلات", "👥 الموظفين", "👀 مراقبة الطلبات"])
        
        # 1. التحليلات (Dashboard)
        with tabs[0]:
            data = list(db.tickets.find())
            if data:
                df = pd.DataFrame(data)
                
                # KPIs
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي الطلبات", len(df))
                c2.metric("طلبات اليوم", len(df[df['date_only'] == datetime.now().strftime("%Y-%m-%d")]))
                c3.metric("قيد الانتظار", len(df[df['status'] == "New"]))
                
                st.divider()
                
                # Charts
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🏠 أكثر المكاتب طلباً")
                    room_counts = df['user_room'].value_counts().reset_index()
                    room_counts.columns = ['المكتب', 'العدد']
                    fig1 = px.bar(room_counts, x='المكتب', y='العدد', color='العدد')
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    st.subheader("☕ أكثر الأصناف طلباً")
                    item_counts = df['item'].value_counts().reset_index()
                    item_counts.columns = ['الصنف', 'العدد']
                    fig2 = px.pie(item_counts, values='العدد', names='الصنف')
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("لا توجد بيانات كافية للتحليل")

        # 2. إدارة الموظفين
        with tabs[1]:
            st.subheader("إضافة موظف جديد")
            with st.form("add_user"):
                c1, c2 = st.columns(2)
                name = c1.text_input("الاسم")
                u_name = c2.text_input("اسم المستخدم")
                c3, c4 = st.columns(2)
                pwd = c3.text_input("كلمة المرور", type="password")
                room = c4.text_input("المكتب")
                role = st.selectbox("الصلاحية", ["Employee", "Office Boy", "IT Support", "Admin"])
                
                if st.form_submit_button("حفظ"):
                    if db.users.find_one({"username": u_name}):
                        st.error("مستخدم موجود بالفعل")
                    else:
                        db.users.insert_one({"name": name, "username": u_name, "password": pwd, "room": room, "role": role})
                        st.success("تم الحفظ")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()
            st.write("قائمة الموظفين:")
            for u in db.users.find():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.text(u['name'])
                c2.text(u['role'])
                c3.text(u['room'])
                if c4.button("حذف", key=str(u['_id'])):
                    db.users.delete_one({"_id": u['_id']})
                    st.rerun()

        # 3. مراقبة الطلبات (يدوي للأدمن عشان ما يعملش ريفريش وهو شغال)
        with tabs[2]:
            st.subheader("الطلبات الحالية")
            if st.button("تحديث القائمة 🔄"):
                st.rerun()
            
            tickets = list(db.tickets.find({"status": "New"}))
            for t in tickets:
                st.warning(f"{t['type']} | {t['user_name']} ({t['user_room']}): {t['item']}")

    # ---------------------------------------------------------
    # السيناريو الثاني: الموظف (نموذج إدخال ثابت بدون تحديث)
    # ---------------------------------------------------------
    elif user['role'] == "Employee":
        st.title(f"👋 أهلاً {user['name'].split()[0]}")
        
        req_tabs = st.tabs(["☕ بوفيه", "💻 دعم فني"])
        
        with req_tabs[0]:
            c1, c2 = st.columns(2)
            drink = c1.selectbox("المشروب", ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون"])
            sugar = c1.selectbox("السكر", ["بدون", "مظبوط", "زيادة"])
            notes = c2.text_input("ملاحظات")
            if st.button("إرسال الطلب 🚀", use_container_width=True):
                add_ticket(user, "Office", f"{drink} - {sugar}", notes)
                st.success("تم الإرسال!")

        with req_tabs[1]:
            issue = st.selectbox("المشكلة", ["إنترنت", "طابعة", "كمبيوتر", "برامج"])
            desc = st.text_area("وصف المشكلة")
            if st.button("تبليغ IT 🛠️", use_container_width=True):
                add_ticket(user, "IT", issue, desc)
                st.success("تم التبليغ!")

    # ---------------------------------------------------------
    # السيناريو الثالث: مقدمي الخدمة (تحديث تلقائي لحظي ⚡)
    # ---------------------------------------------------------
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        
        # عداد تنازلي للتحديث (شكلي فقط)
        placeholder = st.empty()
        
        st.header(f"📋 طلبات {role_type} (مباشر)")
        
        # جلب الطلبات
        tickets = list(db.tickets.find({"type": role_type, "status": "New"}))
        
        if not tickets:
            st.success("✅ مفيش طلبات جديدة.. كله تمام!")
            st.image("https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif", width=200) # صورة استرخاء
        else:
            for t in tickets:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### 📍 {t['user_room']}")
                        st.write(f"👤 **{t['user_name']}**")
                        st.info(f"☕ {t['item']}")
                        if t['details']: st.write(f"📝 {t['details']}")
                        st.caption(f"🕒 {t['timestamp']}")
                    
                    with c2:
                        st.write("")
                        st.write("")
                        # زرار إنجاز المهمة
                        if st.button("تم التنفيذ ✅", key=str(t['_id']), type="primary"):
                            update_ticket_status(t['_id'], "Done")
                            st.rerun()

        # === كود التحديث التلقائي السحري ===
        # بيشتغل بس هنا (للأوفيس والـ IT)
        # بيستنى 3 ثواني ويعمل ريفريش عشان يجيب الطلبات الجديدة
        time.sleep(3)
        st.rerun()

else:
    st.info("الرجاء تسجيل الدخول")
