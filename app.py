import streamlit as st
import pandas as pd
import pymongo
import plotly.express as px
from datetime import datetime
import time
import streamlit.components.v1 as components
from bson.objectid import ObjectId

# --- إعداد الصفحة ---
st.set_page_config(page_title="نظام إتقان", layout="wide", page_icon="☕")

# --- الاتصال بقاعدة البيانات ---
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])

client = init_connection()
db = client.itqan_db

# --- تهيئة المنيو لأول مرة ---
def init_menu():
    if db.menu.count_documents({}) == 0:
        default_drinks = ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون", "نعناع", "كركديه"]
        for d in default_drinks:
            db.menu.insert_one({"name": d, "available": True})

init_menu()

# --- تشغيل الصوت ---
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

def toggle_stock(item_id, status):
    db.menu.update_one({"_id": ObjectId(item_id)}, {"$set": {"available": status}})

# --- تسجيل الدخول ---
def login():
    st.sidebar.title("🔐 نظام إتقان")
    if 'user' in st.session_state:
        return st.session_state['user']

    username = st.sidebar.text_input("اسم المستخدم", placeholder="اكتب اليوزر هنا")
    password = st.sidebar.text_input("كلمة السر", type="password")
    
    if st.sidebar.button("تسجيل دخول"):
        user = get_user(username, password)
        if user:
            user['_id'] = str(user['_id'])
            st.session_state['user'] = user
            st.rerun()
        else:
            st.sidebar.error("بيانات غلط يا هندسة.. جرب تاني!")
    return None

# ==================== بداية التطبيق ====================
user = login()

if user:
    # القائمة الجانبية
    st.sidebar.divider()
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    
    # === إدارة المنيو (التصحيح هنا) ===
    if user['role'] in ["Admin", "Office Boy"]:
        with st.sidebar.expander("☕ إدارة المشروبات (المتاح والخلصان)", expanded=False):
            st.write("علم صح (✅) عالموجود، وشيل الصح لو خلصان:")
            menu_items = list(db.menu.find())
            for item in menu_items:
                # استخدمنا الآيدي (ID) هنا عشان نضمن عدم التكرار حتى لو الاسم متكرر
                item_id = str(item['_id'])
                is_available = st.checkbox(item['name'], value=item['available'], key=f"stock_{item_id}")
                
                if is_available != item['available']:
                    toggle_stock(item_id, is_available)
                    status_text = "متاح" if is_available else "خلصان"
                    st.toast(f"تمام.. {item['name']} بقى {status_text}")
                    time.sleep(0.5)
                    st.rerun()
            
            # إضافة مشروب جديد (أدمن بس)
            if user['role'] == "Admin":
                st.divider()
                new_drink = st.text_input("ضيف صنف جديد للقائمة")
                if st.button("إضافة للمنيو"):
                    if new_drink:
                        # بنشيل المسافات الزيادة عشان التكرار
                        clean_name = new_drink.strip()
                        if db.menu.find_one({"name": clean_name}):
                            st.warning("المشروب ده موجود أصلاً!")
                        else:
                            db.menu.insert_one({"name": clean_name, "available": True})
                            st.success(f"تم إضافة {clean_name} للمنيو")
                            time.sleep(1)
                            st.rerun()

    if st.sidebar.button("خروج", type="primary"):
        del st.session_state['user']
        if 'trash_bin' in st.session_state:
            del st.session_state['trash_bin']
        st.rerun()

    # ---------------------------------------------------------
    # السيناريو الأول: الأدمن
    # ---------------------------------------------------------
    if user['role'] == "Admin":
        st.title("📊 لوحة التحكم والإدارة")
        admin_tabs = st.tabs(["📈 التحليلات", "📝 اطلب لنفسك", "👥 الموظفين", "👀 مراقبة الكل"])
        
        # 1. التحليلات
        with admin_tabs[0]:
            data = list(db.tickets.find())
            if data:
                df = pd.DataFrame(data)
                c1, c2, c3 = st.columns(3)
                c1.metric("إجمالي الطلبات", len(df))
                c2.metric("طلبات النهاردة", len(df[df['date_only'] == datetime.now().strftime("%Y-%m-%d")]))
                c3.metric("لسه ماتعملش (Pending)", len(df[df['status'] == "New"]))
                st.divider()
                
                c_off, c_it = st.columns(2)
                with c_off:
                    st.subheader("☕ البوفيه والمشاريب")
                    off_df = df[df['type'] == "Office"]
                    if not off_df.empty:
                        off_df['item_clean'] = off_df['item'].apply(lambda x: x.split('-')[0].strip())
                        fig = px.pie(off_df, names='item_clean', title='أكتر مشاريب بتتطلب')
                        fig.update_traces(textinfo='value+percent') 
                        st.plotly_chart(fig, use_container_width=True)
                        
                        fig2 = px.bar(off_df['user_room'].value_counts().reset_index(), x='user_room', y='count', title='مين بيطلب أكتر (المكاتب)')
                        fig2.update_traces(texttemplate='%{y}', textposition='outside')
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.info("مفيش طلبات بوفيه لسه")

                with c_it:
                    st.subheader("💻 الدعم الفني (IT)")
                    it_df = df[df['type'] == "IT"]
                    if not it_df.empty:
                        fig_it = px.pie(it_df, names='item', title='أنواع المشاكل')
                        fig_it.update_traces(textinfo='value+percent')
                        st.plotly_chart(fig_it, use_container_width=True)
                    else:
                        st.info("مفيش مشاكل IT (الحمد لله)")
            else:
                st.info("لسه السيستم جديد، مفيش داتا نعرضها.")

        # 2. الأدمن يطلب لنفسه
        with admin_tabs[1]:
            type_ = st.radio("عاوز تطلب إيه؟", ["بوفيه", "دعم فني (IT)"], horizontal=True)
            if type_ == "بوفيه":
                available_drinks = [d['name'] for d in db.menu.find({"available": True})]
                if available_drinks:
                    c1, c2 = st.columns(2)
                    item = c1.selectbox("هتشرب إيه؟", available_drinks)
                    sugar_opts = ["سادة", "على الريحة", "مظبوط", "زيادة", "سكر خفيف", "نص معلقة", "معلقة", "معلقة ونص", "معلقتين", "3 معالق"]
                    sugar = c1.selectbox("السكر", sugar_opts)
                    notes = c2.text_input("ملاحظات (اختياري)")
                    if st.button("اطلب يا ريس ☕"):
                        add_ticket(user, "Office", f"{item} - {sugar}", notes)
                        st.toast("طلبك وصل!")
                else:
                    st.error("البوفيه مفيهوش حاجة متاحة دلوقتي!")
            else:
                issue = st.selectbox("المشكلة فين؟", ["النت فاصل", "الطابعة", "الكمبيوتر", "برامج (Excel/Word)"])
                desc = st.text_area("تفاصيل المشكلة")
                if st.button("بلغ الـ IT"):
                    add_ticket(user, "IT", issue, desc)
                    st.toast("تم التبليغ!")

        # 3. إدارة الموظفين
        with admin_tabs[2]:
            st.subheader("إضافة موظف جديد")
            with st.form("new_user"):
                c1, c2 = st.columns(2)
                name = c1.text_input("الاسم بالكامل")
                uname = c2.text_input("اسم المستخدم (للدخول)")
                c3, c4 = st.columns(2)
                pwd = c3.text_input("كلمة السر", type="password")
                room = c4.text_input("رقم المكتب / الغرفة")
                role_map = {"موظف": "Employee", "عامل بوفيه": "Office Boy", "دعم فني": "IT Support", "مدير (Admin)": "Admin"}
                role_ar = st.selectbox("الوظيفة", list(role_map.keys()))
                
                if st.form_submit_button("حفظ الموظف"):
                    if db.users.find_one({"username": uname}):
                        st.error("اسم المستخدم ده موجود قبل كده، شوف غيره!")
                    else:
                        db.users.insert_one({"name": name, "username": uname, "password": pwd, "room": room, "role": role_map[role_ar]})
                        st.success("تم إضافة الموظف بنجاح!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()
            st.write("📋 **قائمة الموظفين:**")
            for u in db.users.find():
                col1, col2, col3 = st.columns([2, 2, 1])
                role_display = {"Employee": "موظف", "Office Boy": "بوفيه", "IT Support": "IT", "Admin": "مدير"}.get(u['role'], u['role'])
                col1.text(f"{u['name']} ({role_display})")
                col2.text(u['room'])
                if col3.button("حذف", key=u['username']):
                    db.users.delete_one({"_id": u['_id']})
                    st.rerun()

        # 4. مراقبة الطلبات
        with admin_tabs[3]:
            if st.button("تحديث القائمة 🔄"): st.rerun()
            tickets = list(db.tickets.find({"status": "New"}))
            if not tickets:
                st.success("الجو رايق.. مفيش طلبات معلقة.")
            for t in tickets:
                st.warning(f"🔔 {t['type']} | {t['user_name']} | {t['item']}")

    # ---------------------------------------------------------
    # السيناريو الثاني: الموظف
    # ---------------------------------------------------------
    elif user['role'] == "Employee":
        st.title(f"منور يا هندسة 👋 {user['name'].split()[0]}")
        tabs = st.tabs(["☕ طلب بوفيه", "💻 دعم فني"])
        
        with tabs[0]:
            available_drinks = [d['name'] for d in db.menu.find({"available": True})]
            
            if available_drinks:
                c1, c2 = st.columns(2)
                item = c1.selectbox("هتشرب إيه؟", available_drinks)
                sugar_opts = ["سادة", "على الريحة", "مظبوط", "زيادة", "سكر خفيف", "نص معلقة", "معلقة", "معلقة ونص", "معلقتين", "3 معالق"]
                sugar = c1.selectbox("السكر", sugar_opts)
                notes = c2.text_input("أي ملاحظات؟ (اختياري)")
                
                if st.button("اطلب 🚀", use_container_width=True):
                    add_ticket(user, "Office", f"{item} - {sugar}", notes)
                    st.success("تمام.. طلبك وصل للأوفيس!")
            else:
                st.error("⚠️ معلش، البوفيه مغلق أو المشروبات خلصت.")

        with tabs[1]:
            issue = st.selectbox("المشكلة فين؟", ["النت فاصل", "الطابعة مش شغالة", "الكمبيوتر تقيل", "برامج (Office/Windows)"])
            desc = st.text_area("أوصف المشكلة باختصار")
            if st.button("بلغ الـ IT 🛠️", use_container_width=True):
                add_ticket(user, "IT", issue, desc)
                st.success("تم التبليغ وهيكلموك حالاً.")

    # ---------------------------------------------------------
    # السيناريو الثالث: مقدمي الخدمة
    # ---------------------------------------------------------
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        title_ar = "طلبات البوفيه ☕" if role_type == "Office" else "بلاغات الدعم الفني 🔧"
        st.header(f"📋 {title_ar} (مباشر)")

        if 'trash_bin' not in st.session_state:
            st.session_state['trash_bin'] = []

        def move_to_trash(ticket_id):
            st.session_state['trash_bin'].append(ticket_id)
            play_sound()
            update_ticket_status(ticket_id, "Done")

        all_tickets = list(db.tickets.find({"type": role_type, "status": "New"}))
        visible_tickets = [t for t in all_tickets if str(t['_id']) not in st.session_state['trash_bin']]

        if not visible_tickets:
            st.success("✅ تسلم ايدك.. مفيش طلبات جديدة!")
            st.image("https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif", width=150)
            time.sleep(1)
            st.rerun()
        else:
            for t in visible_tickets:
                t_id = str(t['_id'])
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(f"📍 {t['user_room']}")
                        st.write(f"👤 **{t['user_name']}**")
                        st.info(f"☕ {t['item']}")
                        if t['details']: st.caption(f"📝 ملاحظة: {t['details']}")
                        st.caption(t['timestamp'])
                    with c2:
                        st.write("")
                        st.write("")
                        st.button(
                            "تم التمام ✅", 
                            key=f"btn_{t_id}", 
                            type="primary", 
                            on_click=move_to_trash, 
                            args=(t_id,)
                        )
            
            time.sleep(1)
            st.rerun()

else:
    st.info("من فضلك سجل دخول الأول")
