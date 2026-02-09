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

# --- كود تشغيل الصوت (JavaScript) ---
def play_sound():
    sound_code = """
    <audio autoplay>
    <source src="https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3" type="audio/mpeg">
    </audio>
    """
    components.html(sound_code, height=0, width=0)

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
    
    if st.sidebar.button("تسجيل خروج", type="primary"):
        del st.session_state['user']
        st.rerun()

    # ---------------------------------------------------------
    # السيناريو الأول: الأدمن (Admin)
    # ---------------------------------------------------------
    if user['role'] == "Admin":
        st.title("📊 لوحة القيادة (Admin Dashboard)")
        
        # تابات الأدمن
        admin_tabs = st.tabs(["📈 التحليلات", "📝 تقديم طلب", "👥 الموظفين", "👀 مراقبة الطلبات"])
        
        # 1. التحليلات (مفصلة ومنظفة)
        with admin_tabs[0]:
            data = list(db.tickets.find())
            if data:
                df = pd.DataFrame(data)
                
                # KPIs عامة
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي التذاكر", len(df))
                c2.metric("طلبات اليوم", len(df[df['date_only'] == datetime.now().strftime("%Y-%m-%d")]))
                c3.metric("المعلق (Pending)", len(df[df['status'] == "New"]), delta_color="inverse")
                
                st.divider()
                
                # قسمين منفصلين (Office vs IT)
                col_office, col_it = st.columns(2)
                
                # --- تحليلات الأوفيس ---
                with col_office:
                    st.markdown("### ☕ تحليلات الأوفيس")
                    office_df = df[df['type'] == "Office"]
                    
                    if not office_df.empty:
                        # تنظيف اسم المشروب (عشان يحسب كل القهوة مع بعض)
                        # بياخد الكلمة الأولى قبل الشرطة "-"
                        office_df['clean_item'] = office_df['item'].apply(lambda x: x.split('-')[0].strip())
                        
                        # Pie Chart للمشروبات
                        fig1 = px.pie(office_df, names='clean_item', title='المشروبات الأكثر طلباً')
                        st.plotly_chart(fig1, use_container_width=True)
                        
                        # Bar Chart للغرف
                        room_counts = office_df['user_room'].value_counts().reset_index()
                        room_counts.columns = ['المكتب', 'العدد']
                        fig2 = px.bar(room_counts, x='المكتب', y='العدد', title='أكثر المكاتب استهلاكاً للبوفيه')
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.info("لا توجد بيانات بوفيه")

                # --- تحليلات الـ IT ---
                with col_it:
                    st.markdown("### 💻 تحليلات الدعم الفني")
                    it_df = df[df['type'] == "IT"]
                    
                    if not it_df.empty:
                        # Pie Chart للمشاكل
                        fig3 = px.pie(it_df, names='item', title='توزيع المشاكل التقنية', hole=0.4)
                        st.plotly_chart(fig3, use_container_width=True)
                        
                        # Bar Chart للموظفين
                        user_counts = it_df['user_name'].value_counts().reset_index()
                        user_counts.columns = ['الموظف', 'العدد']
                        fig4 = px.bar(user_counts, x='الموظف', y='العدد', title='الموظفين الأكثر طلباً للدعم')
                        st.plotly_chart(fig4, use_container_width=True)
                    else:
                        st.info("لا توجد بيانات IT")

            else:
                st.info("لا توجد بيانات كافية للتحليل")

        # 2. الأدمن يطلب لنفسه
        with admin_tabs[1]:
            st.subheader("طلب سريع ليك يا ريس ☕")
            req_type = st.radio("نوع الطلب", ["بوفيه", "دعم فني"], horizontal=True)
            
            if req_type == "بوفيه":
                c1, c2 = st.columns(2)
                drink = c1.selectbox("المشروب", ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون"])
                sugar = c1.selectbox("السكر", ["بدون", "مظبوط", "زيادة"])
                notes = c2.text_input("ملاحظات")
                if st.button("إرسال الطلب 🚀"):
                    add_ticket(user, "Office", f"{drink} - {sugar}", notes)
                    st.toast("تم تسجيل طلبك!")
            else:
                issue = st.selectbox("المشكلة", ["إنترنت", "طابعة", "كمبيوتر", "برامج"])
                desc = st.text_area("وصف المشكلة")
                if st.button("تسجيل تذكرة"):
                    add_ticket(user, "IT", issue, desc)
                    st.toast("تم تسجيل المشكلة")

        # 3. إدارة الموظفين
        with admin_tabs[2]:
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

        # 4. مراقبة الطلبات
        with admin_tabs[3]:
            if st.button("تحديث القائمة 🔄"):
                st.rerun()
            tickets = list(db.tickets.find({"status": "New"}))
            if not tickets:
                st.success("مفيش طلبات معلقة")
            for t in tickets:
                st.warning(f"{t['type']} | {t['user_name']} ({t['user_room']}): {t['item']}")

    # ---------------------------------------------------------
    # السيناريو الثاني: الموظف (Employee)
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
    # السيناريو الثالث: مقدمي الخدمة (Office Boy / IT Support)
    # ---------------------------------------------------------
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        
        st.header(f"📋 طلبات {role_type} (مباشر)")
        
        # --- دوال المساعدة للإخفاء الفوري ---
        def mark_done(ticket_id):
            # تحديث الداتا بيز
            update_ticket_status(ticket_id, "Done")
            # تحديث الجلسة لإخفاء العنصر فوراً
            st.session_state[f"done_{ticket_id}"] = True
            # تشغيل الصوت
            play_sound()

        # جلب الطلبات "New" فقط من الداتا بيز
        tickets = list(db.tickets.find({"type": role_type, "status": "New"}))
        
        # فلتر إضافي: استبعاد الطلبات اللي لسه معمولة Done حالاً في السيشن دي
        active_tickets = [t for t in tickets if not st.session_state.get(f"done_{str(t['_id'])}", False)]
        
        if not active_tickets:
            st.success("✅ الله ينور.. مفيش طلبات جديدة!")
            st.image("https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif", width=150)
        else:
            for t in active_tickets:
                t_id = str(t['_id'])
                
                # شكل الكارت
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### 📍 {t['user_room']}")
                        st.write(f"👤 **{t['user_name']}**")
                        st.info(f"📋 {t['item']}")
                        if t['details']: st.write(f"📝 {t['details']}")
                        st.caption(f"🕒 {t['timestamp']}")
                    
                    with c2:
                        st.write("")
                        st.write("")
                        # زرار التنفيذ (Callback)
                        st.button(
                            "تم التنفيذ ✅", 
                            key=f"btn_{t_id}", 
                            type="primary", 
                            on_click=mark_done, 
                            args=(t_id,)
                        )

        # التحديث التلقائي كل 3 ثواني
        time.sleep(3)
        st.rerun()

else:
    st.info("الرجاء تسجيل الدخول")
