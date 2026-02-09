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

# --- (1) تهيئة المنيو ---
def init_menu():
    default_drinks = ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون", "نعناع", "كركديه"]
    for d in default_drinks:
        db.menu.update_one(
            {"name": d}, 
            {"$setOnInsert": {"name": d, "available": True}}, 
            upsert=True
        )

# --- (2) تهيئة الغرف (الرومات) - جديد ---
def init_rooms():
    # لو مفيش غرف خالص، حط دول كبداية
    if db.rooms.count_documents({}) == 0:
        default_rooms = ["IT Office", "HR Room", "Accounts", "CEO Office", "Reception", "Sales Team"]
        for r in default_rooms:
            db.rooms.insert_one({"name": r})

init_menu()
init_rooms()

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
    now = datetime.now()
    ticket = {
        "user_name": user_data['name'],
        "user_room": user_data['room'],
        "type": type,
        "item": item,
        "details": details,
        "status": "New",
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date_only": now.strftime("%Y-%m-%d"),
        "month_year": now.strftime("%Y-%m")
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
    
    # زرار تحديث البيانات
    if st.sidebar.button("🔄 تحديث البيانات", use_container_width=True):
        st.rerun()

    # === القوائم الجانبية للأدمن فقط ===
    if user['role'] == "Admin":
        
        # 1. إدارة المشروبات
        with st.sidebar.expander("☕ إدارة المنيو", expanded=False):
            if st.button("🗑️ تنظيف التكرار"):
                db.menu.delete_many({})
                init_menu()
                st.toast("تم التنظيف!")
                time.sleep(1)
                st.rerun()
            
            st.write("المتاح حالياً:")
            menu_items = list(db.menu.find())
            for item in menu_items:
                item_id = str(item['_id'])
                is_available = st.checkbox(item['name'], value=item['available'], key=f"stock_{item_id}")
                if is_available != item['available']:
                    toggle_stock(item_id, is_available)
                    st.rerun()
            
            new_drink = st.text_input("صنف جديد")
            if st.button("إضافة للمنيو"):
                if new_drink and not db.menu.find_one({"name": new_drink.strip()}):
                    db.menu.insert_one({"name": new_drink.strip(), "available": True})
                    st.rerun()

        # 2. إدارة الغرف (الجديد) 🆕
        with st.sidebar.expander("🏢 إدارة الغرف (Teams)", expanded=False):
            st.write("الغرف المتاحة:")
            rooms_list = list(db.rooms.find())
            for r in rooms_list:
                c1, c2 = st.columns([3, 1])
                c1.text(f"📍 {r['name']}")
                if c2.button("❌", key=f"del_room_{r['_id']}"):
                    db.rooms.delete_one({"_id": r['_id']})
                    st.rerun()
            
            new_room = st.text_input("إضافة غرفة/تيم جديد")
            if st.button("إضافة غرفة"):
                if new_room and not db.rooms.find_one({"name": new_room.strip()}):
                    db.rooms.insert_one({"name": new_room.strip()})
                    st.success(f"تم إضافة {new_room}")
                    time.sleep(1)
                    st.rerun()

    # زرار الخروج
    st.sidebar.divider()
    if st.sidebar.button("تسجيل خروج", type="primary", use_container_width=True):
        del st.session_state['user']
        if 'trash_bin' in st.session_state:
            del st.session_state['trash_bin']
        st.rerun()

    # ---------------------------------------------------------
    # السيناريو الأول: الأدمن (Admin)
    # ---------------------------------------------------------
    if user['role'] == "Admin":
        st.title("📊 لوحة المدير")
        admin_tabs = st.tabs(["📈 التحليلات المتقدمة", "📝 طلب خاص", "👥 إدارة الموظفين", "👀 المراقبة"])
        
        # 1. التحليلات (محدثة جداً)
        with admin_tabs[0]:
            all_data = list(db.tickets.find())
            
            if all_data:
                df = pd.DataFrame(all_data)
                
                # تنظيف الداتا
                df['datetime'] = pd.to_datetime(df['timestamp'], errors='coerce')
                if 'month_year' not in df.columns:
                    df['month_year'] = df['datetime'].dt.strftime('%Y-%m')
                # تنظيف اسم المشروب (عشان التحليل)
                df['item_clean'] = df['item'].apply(lambda x: x.split('-')[0].strip() if '-' in str(x) else str(x))

                # --- الفلاتر ---
                st.subheader("📅 الفلاتر")
                col_m, col_d = st.columns(2)
                unique_months = sorted([m for m in df['month_year'].dropna().unique() if isinstance(m, str)], reverse=True)
                selected_month = col_m.selectbox("الشهر:", unique_months)
                
                month_df = df[df['month_year'] == selected_month]
                
                available_days = sorted(month_df['date_only'].unique())
                day_options = ["الكل"] + list(available_days)
                selected_day = col_d.selectbox("اليوم:", day_options)
                
                if selected_day != "الكل":
                    final_df = month_df[month_df['date_only'] == selected_day]
                else:
                    final_df = month_df
                
                if not final_df.empty:
                    st.divider()
                    
                    # --- (أ) أكثر الأشخاص طلباً ---
                    st.subheader("🏆 مين أكتر ناس بتطلب؟")
                    top_users = final_df['user_name'].value_counts().reset_index()
                    top_users.columns = ['الموظف', 'عدد الطلبات']
                    
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        # رسم بياني بالألوان يوضح الموظف + بيطلب إيه
                        fig_users = px.bar(final_df, x='user_name', color='item_clean', title="توزيع طلبات الموظفين (بالأصناف)")
                        st.plotly_chart(fig_users, use_container_width=True)
                    with c2:
                        st.write("🔝 الترتيب:")
                        st.dataframe(top_users, hide_index=True)

                    st.divider()

                    # --- (ب) أكثر الغرف طلباً ---
                    st.subheader("🏢 مين أكتر غرفة بتستهلك؟")
                    top_rooms = final_df['user_room'].value_counts().reset_index()
                    top_rooms.columns = ['الغرفة', 'عدد الطلبات']
                    
                    c3, c4 = st.columns([2, 1])
                    with c3:
                        fig_rooms = px.bar(final_df, x='user_room', color='item_clean', title="استهلاك الغرف (بالأصناف)")
                        st.plotly_chart(fig_rooms, use_container_width=True)
                    with c4:
                        st.write("🔝 ترتيب الغرف:")
                        st.dataframe(top_rooms, hide_index=True)

                    st.divider()

                    # --- (ج) تحليل شخص بعينه ---
                    st.subheader("🕵️ فتش عن موظف")
                    all_users_in_period = final_df['user_name'].unique()
                    target_user = st.selectbox("اختار الموظف عشان تشوف تفاصيله:", ["اختر..."] + list(all_users_in_period))
                    
                    if target_user != "اختر...":
                        user_df = final_df[final_df['user_name'] == target_user]
                        st.info(f"إجمالي طلبات {target_user}: {len(user_df)}")
                        # رسم بياني دائري لمشروبات الشخص ده بس
                        fig_person = px.pie(user_df, names='item_clean', title=f"مشروبات {target_user} المفضلة")
                        st.plotly_chart(fig_person, use_container_width=True)

                else:
                    st.warning("مفيش بيانات للفترة دي")
            else:
                st.info("السيستم فاضي")

        # 2. طلب للأدمن
        with admin_tabs[1]:
            type_ = st.radio("نوع الطلب", ["بوفيه", "IT"], horizontal=True)
            if type_ == "بوفيه":
                available_drinks = [d['name'] for d in db.menu.find({"available": True})]
                if available_drinks:
                    c1, c2 = st.columns(2)
                    item = c1.selectbox("الصنف", available_drinks)
                    sugar = c1.selectbox("السكر", ["سادة", "مظبوط", "زيادة", "معلقة"])
                    notes = c2.text_input("ملاحظات")
                    if st.button("اطلب ☕"):
                        add_ticket(user, "Office", f"{item} - {sugar}", notes)
                        st.toast("تمام")
            else:
                issue = st.selectbox("المشكلة", ["نت", "طابعة", "PC"])
                if st.button("بلغ IT"):
                    add_ticket(user, "IT", issue, "")
                    st.toast("تم")

        # 3. إدارة الموظفين (بالتعديل الجديد للرومات)
        with admin_tabs[2]:
            st.subheader("إضافة موظف جديد")
            with st.form("new_user"):
                c1, c2 = st.columns(2)
                name = c1.text_input("الاسم")
                uname = c2.text_input("اليوزر")
                
                c3, c4 = st.columns(2)
                pwd = c3.text_input("باسورد", type="password")
                
                # هنا التعديل: اختيار الروم من القائمة اللي الأدمن عملها
                # بنجيب الرومات من الداتا بيز
                available_rooms = [r['name'] for r in db.rooms.find()]
                if not available_rooms:
                    available_rooms = ["General"] # قيمة افتراضية لو مفيش رومات
                
                room = c4.selectbox("المكتب / التيم", available_rooms)
                
                role_map = {"موظف": "Employee", "بوفيه": "Office Boy", "IT": "IT Support", "مدير": "Admin"}
                role_ar = st.selectbox("الوظيفة", list(role_map.keys()))
                
                if st.form_submit_button("حفظ الموظف"):
                    if not db.users.find_one({"username": uname}):
                        db.users.insert_one({"name": name, "username": uname, "password": pwd, "room": room, "role": role_map[role_ar]})
                        st.success("تم")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("اليوزر ده موجود قبل كده")
            
            st.divider()
            st.write("📋 الموظفين الحاليين:")
            for u in db.users.find():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.text(f"{u['name']} ({u['role']})")
                c2.text(u['room'])
                if c3.button("حذف", key=u['username']):
                    db.users.delete_one({"_id": u['_id']})
                    st.rerun()

        # 4. مراقبة الطلبات
        with admin_tabs[3]:
            if st.button("تحديث القائمة"): st.rerun()
            for t in db.tickets.find({"status": "New"}):
                st.warning(f"{t['type']} | {t['user_name']} | {t['item']}")

    # ---------------------------------------------------------
    # السيناريو الثاني: الموظف
    # ---------------------------------------------------------
    elif user['role'] == "Employee":
        st.title(f"أهلاً 👋 {user['name'].split()[0]}")
        tabs = st.tabs(["☕ طلب بوفيه", "💻 دعم فني"])
        
        with tabs[0]:
            available_drinks = [d['name'] for d in db.menu.find({"available": True})]
            if available_drinks:
                c1, c2 = st.columns(2)
                item = c1.selectbox("هتشرب إيه؟", available_drinks)
                sugar = c1.selectbox("السكر", ["سادة", "على الريحة", "مظبوط", "زيادة", "معلقة", "2 معلقة", "3 معالق"])
                notes = c2.text_input("ملاحظات")
                if st.button("اطلب 🚀", use_container_width=True):
                    add_ticket(user, "Office", f"{item} - {sugar}", notes)
                    st.success("تم الإرسال!")
            else:
                st.error("البوفيه مغلق")

        with tabs[1]:
            issue = st.selectbox("المشكلة", ["نت", "طابعة", "PC", "برامج"])
            desc = st.text_area("وصف")
            if st.button("بلغ IT 🛠️", use_container_width=True):
                add_ticket(user, "IT", issue, desc)
                st.success("تم التبليغ")

    # ---------------------------------------------------------
    # السيناريو الثالث: مقدمي الخدمة
    # ---------------------------------------------------------
    elif user['role'] in ["Office Boy", "IT Support"]:
        role_type = "Office" if user['role'] == "Office Boy" else "IT"
        st.header(f"📋 طلبات {role_type} (مباشر)")

        if 'trash_bin' not in st.session_state:
            st.session_state['trash_bin'] = []

        def move_to_trash(ticket_id):
            st.session_state['trash_bin'].append(ticket_id)
            play_sound()
            update_ticket_status(ticket_id, "Done")

        all_tickets = list(db.tickets.find({"type": role_type, "status": "New"}))
        visible_tickets = [t for t in all_tickets if str(t['_id']) not in st.session_state['trash_bin']]

        if not visible_tickets:
            st.success("✅ كله تمام.. مفيش طلبات!")
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
                        if t['details']: st.caption(t['details'])
                        st.caption(t['timestamp'])
                    with c2:
                        st.write("")
                        st.write("")
                        st.button(
                            "تم ✅", 
                            key=f"btn_{t_id}", 
                            type="primary", 
                            on_click=move_to_trash, 
                            args=(t_id,)
                        )
            time.sleep(1)
            st.rerun()

else:
    st.info("سجل دخول")
