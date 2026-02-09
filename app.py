import streamlit as st
import pandas as pd
import pymongo
import plotly.express as px
from datetime import datetime
import time
import streamlit.components.v1 as components
from bson.objectid import ObjectId

# --- إعداد الصفحة ---
st.set_page_config(page_title="ITQAN Cloud", layout="wide", page_icon="☁️")

# --- الاتصال بقاعدة البيانات ---
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])

client = init_connection()
db = client.itqan_db

# --- تشغيل الصوت ---
def play_sound():
    sound_code = """
    <audio autoplay>
    <source src="https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3" type="audio/mpeg">
    </audio>
    """
    components.html(sound_code, height=0, width=0)

# --- دوال الداتا بيز ---
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
    st.sidebar.divider()
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    
    if st.sidebar.button("تسجيل خروج", type="primary"):
        del st.session_state['user']
        if 'trash_bin' in st.session_state:
            del st.session_state['trash_bin']
        st.rerun()

    # ---------------------------------------------------------
    # السيناريو الأول: الأدمن
    # ---------------------------------------------------------
    if user['role'] == "Admin":
        st.title("📊 Admin Dashboard")
        admin_tabs = st.tabs(["📈 التحليلات", "📝 تقديم طلب", "👥 الموظفين", "👀 مراقبة الطلبات"])
        
        # 1. التحليلات
        with admin_tabs[0]:
            data = list(db.tickets.find())
            if data:
                df = pd.DataFrame(data)
                c1, c2, c3 = st.columns(3)
                c1.metric("الكل", len(df))
                c2.metric("اليوم", len(df[df['date_only'] == datetime.now().strftime("%Y-%m-%d")]))
                c3.metric("المعلق", len(df[df['status'] == "New"]))
                st.divider()
                
                c_off, c_it = st.columns(2)
                with c_off:
                    st.write("☕ **الأوفيس**")
                    off_df = df[df['type'] == "Office"]
                    if not off_df.empty:
                        off_df['item_clean'] = off_df['item'].apply(lambda x: x.split('-')[0].strip())
                        st.plotly_chart(px.pie(off_df, names='item_clean'), use_container_width=True)
                        st.plotly_chart(px.bar(off_df['user_room'].value_counts().reset_index(), x='user_room', y='count'), use_container_width=True)
                with c_it:
                    st.write("💻 **IT**")
                    it_df = df[df['type'] == "IT"]
                    if not it_df.empty:
                        st.plotly_chart(px.pie(it_df, names='item'), use_container_width=True)
                        st.plotly_chart(px.bar(it_df['user_name'].value_counts().reset_index(), x='user_name', y='count'), use_container_width=True)
            else:
                st.info("لا توجد بيانات")

        # 2. طلب للأدمن
        with admin_tabs[1]:
            type_ = st.radio("النوع", ["بوفيه", "IT"], horizontal=True)
            if type_ == "بوفيه":
                c1, c2 = st.columns(2)
                item = c1.selectbox("الصنف", ["قهوة", "شاي", "نسكافيه", "مياه"])
                sugar = c1.selectbox("سكر", ["مظبوط", "زيادة", "بدون"])
                if st.button("اطلب"):
                    add_ticket(user, "Office", f"{item} - {sugar}", "")
                    st.toast("تم!")
            else:
                issue = st.selectbox("المشكلة", ["نت", "طابعة", "PC"])
                if st.button("بلغ"):
                    add_ticket(user, "IT", issue, "")
                    st.toast("تم!")

        # 3. الموظفين
        with admin_tabs[2]:
            with st.form("new_user"):
                name = st.text_input("الاسم")
                uname = st.text_input("اليوزر")
                pwd = st.text_input("باسورد", type="password")
                room = st.text_input("المكتب")
                role = st.selectbox("وظيفة", ["Employee", "Office Boy", "IT Support", "Admin"])
                if st.form_submit_button("إضافة"):
                    db.users.insert_one({"name": name, "username": uname, "password": pwd, "room": room, "role": role})
                    st.success("تم")
                    time.sleep(1)
                    st.rerun()

        # 4. المراقبة
        with admin_tabs[3]:
            if st.button("تحديث"): st.rerun()
            for t in db.tickets.find({"status": "New"}):
                st.warning(f"{t['type']} - {t['user_name']} - {t['item']}")

    # ---------------------------------------------------------
    # السيناريو الثاني: الموظف
    # ---------------------------------------------------------
    elif user['role'] == "Employee":
        st.title(f"👋 {user['name']}")
        tabs = st.tabs(["☕ بوفيه", "💻 IT"])
        with tabs[0]:
            c1, c2 = st.columns(2)
            item = c1.selectbox("مشروبك", ["قهوة", "شاي", "نسكافيه", "مياه"])
            sugar = c1.selectbox("السكر", ["مظبوط", "زيادة", "بدون"])
            if st.button("اطلب 🚀", use_container_width=True):
                add_ticket(user, "Office", f"{item} - {sugar}", "")
                st.success("تم الإرسال")
        with tabs[1]:
            issue = st.selectbox("المشكلة", ["نت", "طابعة", "PC"])
            if st.button("بلغ IT 🛠️", use_container_width=True):
                add_ticket(user, "IT", issue, "")
                st.success("تم التبليغ")

    # ---------------------------------------------------------
    # السيناريو الثالث: مقدمي الخدمة (Live View) ⚡⚡
    # ---------------------------------------------------------
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        st.header(f"📋 طلبات {role_type} (مباشر)")

        # 1. تهيئة "سلة المهملات المحلية" (Trash Bin)
        if 'trash_bin' not in st.session_state:
            st.session_state['trash_bin'] = []

        # --- الـ Callback السحري ---
        # الدالة دي بتشتغل فوراً عند الضغط
        def move_to_trash(ticket_id):
            # أ. رمي في السلة فوراً
            st.session_state['trash_bin'].append(ticket_id)
            # ب. تشغيل الصوت
            play_sound()
            # ج. تحديث الداتا بيز في الخلفية
            update_ticket_status(ticket_id, "Done")

        # 2. جلب الطلبات من الداتا بيز
        all_tickets = list(db.tickets.find({"type": role_type, "status": "New"}))

        # 3. الفلترة (الخطوة الأهم):
        # اعرض فقط الطلبات اللي مش موجودة في سلة المهملات
        visible_tickets = [t for t in all_tickets if str(t['_id']) not in st.session_state['trash_bin']]

        if not visible_tickets:
            st.success("✅ كله تمام يا ريس.. مفيش طلبات!")
            st.image("https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif", width=150)
            # ريح السيرفر ثانية واحدة
            time.sleep(1)
            st.rerun()
        else:
            for t in visible_tickets:
                t_id = str(t['_id'])
                # كارت الطلب
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(f"📍 {t['user_room']}")
                        st.write(f"👤 {t['user_name']}")
                        st.info(f"☕ {t['item']}")
                        st.caption(t['timestamp'])
                    with c2:
                        st.write("")
                        st.write("")
                        # الزرار اللي بيودي للسلة
                        st.button(
                            "تم ✅", 
                            key=f"btn_{t_id}", 
                            type="primary", 
                            on_click=move_to_trash, # استدعاء دالة النقل للسلة
                            args=(t_id,)
                        )
            
            # تحديث سريع جداً عشان الاستجابة
            time.sleep(1)
            st.rerun()

else:
    st.info("سجل دخول")
