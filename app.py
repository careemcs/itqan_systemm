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

# --- تهيئة المنيو ---
def init_menu():
    default_drinks = ["قهوة", "شاي", "نسكافيه", "مياه", "ينسون", "نعناع", "كركديه"]
    for d in default_drinks:
        db.menu.update_one(
            {"name": d}, 
            {"$setOnInsert": {"name": d, "available": True}}, 
            upsert=True
        )

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
    # القائمة الجانبية (معلومات المستخدم)
    st.sidebar.divider()
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    
    # 🔴🔴 زرار التحديث (الحل السحري) 🔴🔴
    # الزرار ده موجود لكل الناس في القائمة الجانبية
    # لما تدوس عليه بيعمل ريفريش للداتا من غير ما يخرجك
    if st.sidebar.button("🔄 تحديث البيانات", use_container_width=True):
        st.rerun()

    # === إدارة المنيو (للأدمن والأوفيس بوي) ===
    if user['role'] in ["Admin", "Office Boy"]:
        with st.sidebar.expander("☕ إدارة المنيو", expanded=False):
            if user['role'] == "Admin":
                if st.button("🗑️ إعادة ضبط المنيو", help="مسح التكرار"):
                    db.menu.delete_many({})
                    init_menu()
                    st.toast("تم التنظيف!")
                    time.sleep(1)
                    st.rerun()
                st.divider()

            st.write("المتاح حالياً:")
            menu_items = list(db.menu.find())
            for item in menu_items:
                item_id = str(item['_id'])
                is_available = st.checkbox(item['name'], value=item['available'], key=f"stock_{item_id}")
                if is_available != item['available']:
                    toggle_stock(item_id, is_available)
                    st.rerun()
            
            if user['role'] == "Admin":
                st.divider()
                new_drink = st.text_input("صنف جديد")
                if st.button("إضافة"):
                    if new_drink:
                        clean_name = new_drink.strip()
                        if not db.menu.find_one({"name": clean_name}):
                            db.menu.insert_one({"name": clean_name, "available": True})
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
        admin_tabs = st.tabs(["📈 التحليلات والتقارير", "📝 طلب خاص", "👥 الموظفين", "👀 مراقبة"])
        
        # 1. التحليلات
        with admin_tabs[0]:
            all_data = list(db.tickets.find())
            
            if all_data:
                df = pd.DataFrame(all_data)
                
                st.subheader("📅 فلترة التقارير")
                col_filter1, col_filter2 = st.columns(2)
                
                if 'month_year' not in df.columns:
                    df['month_year'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m')
                
                available_months = sorted(df['month_year'].unique(), reverse=True)
                selected_month = col_filter1.selectbox("اختر الشهر للعرض:", available_months)
                
                filtered_df = df[df['month_year'] == selected_month]
                
                if not filtered_df.empty:
                    c1, c2, c3 = st.columns(3)
                    c1.metric(f"طلبات {selected_month}", len(filtered_df))
                    c2.metric("بوفيه", len(filtered_df[filtered_df['type'] == "Office"]))
                    c3.metric("دعم فني", len(filtered_df[filtered_df['type'] == "IT"]))
                    
                    st.divider()
                    
                    c_off, c_it = st.columns(2)
                    with c_off:
                        st.caption("☕ بوفيه (الشهر ده)")
                        off_df = filtered_df[filtered_df['type'] == "Office"]
                        if not off_df.empty:
                            off_df['item_clean'] = off_df['item'].apply(lambda x: x.split('-')[0].strip())
                            fig = px.pie(off_df, names='item_clean', title='المشروبات')
                            fig.update_traces(textinfo='value+percent')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("مفيش بوفيه الشهر ده")

                    with c_it:
                        st.caption("💻 دعم فني (الشهر ده)")
                        it_df = filtered_df[filtered_df['type'] == "IT"]
                        if not it_df.empty:
                            fig_it = px.bar(it_df['item'].value_counts().reset_index(), x='item', y='count', title='المشاكل')
                            st.plotly_chart(fig_it, use_container_width=True)
                        else:
                            st.info("مفيش IT الشهر ده")

                    st.divider()
                    
                    st.subheader("⚙️ إدارة بيانات الشهر")
                    col_act1, col_act2 = st.columns(2)
                    
                    with col_act1:
                        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label=f"📥 تحميل تقرير {selected_month} (Excel)",
                            data=csv,
                            file_name=f"report_{selected_month}.csv",
                            mime="text/csv",
                        )
                    
                    with col_act2:
                        with st.expander("🗑️ منطقة الخطر (حذف البيانات)"):
                            st.warning(f"تحذير: هتمسح كل بيانات شهر {selected_month} نهائياً!")
                            confirm_delete = st.checkbox(f"أنا متأكد، امسح بيانات {selected_month}")
                            if st.button("تأكيد الحذف النهائي 🧨", disabled=not confirm_delete):
                                db.tickets.delete_many({"month_year": selected_month})
                                st.success(f"تم مسح بيانات {selected_month} بالسلامة!")
                                time.sleep(2)
                                st.rerun()

                else:
                    st.warning("مفيش بيانات في الشهر ده")
            else:
                st.info("السيستم لسه فاضي تماماً")

        # 2. الأدمن يطلب
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

        # 3. إدارة الموظفين
        with admin_tabs[2]:
            st.subheader("إضافة موظف")
            with st.form("new_user"):
                c1, c2 = st.columns(2)
                name = c1.text_input("الاسم")
                uname = c2.text_input("اليوزر")
                c3, c4 = st.columns(2)
                pwd = c3.text_input("باسورد", type="password")
                room = c4.text_input("المكتب")
                role_map = {"موظف": "Employee", "بوفيه": "Office Boy", "IT": "IT Support", "مدير": "Admin"}
                role_ar = st.selectbox("الوظيفة", list(role_map.keys()))
                
                if st.form_submit_button("حفظ"):
                    if not db.users.find_one({"username": uname}):
                        db.users.insert_one({"name": name, "username": uname, "password": pwd, "room": room, "role": role_map[role_ar]})
                        st.success("تم")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("موجود قبل كده")
            
            st.write("الموظفين:")
            for u in db.users.find():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.text(f"{u['name']} ({u['role']})")
                c2.text(u['room'])
                if c3.button("حذف", key=u['username']):
                    db.users.delete_one({"_id": u['_id']})
                    st.rerun()

        # 4. مراقبة الطلبات
        with admin_tabs[3]:
            # زرار تحديث داخلي للتاب دي كمان
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
