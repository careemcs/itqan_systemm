import streamlit as st
import pandas as pd
import pymongo
from datetime import datetime
import time

# --- إعداد الصفحة ---
st.set_page_config(page_title="ITQAN Cloud", layout="wide", page_icon="☁️")

# --- الاتصال بقاعدة البيانات (MongoDB) ---
@st.cache_resource
def init_connection():
    try:
        return pymongo.MongoClient(st.secrets["mongo"]["connection_string"])
    except:
        st.error("مشكلة في الاتصال بقاعدة البيانات.. تأكد من الأسرار (Secrets)")
        return None

client = init_connection()

# اسم قاعدة البيانات
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
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    db.tickets.insert_one(ticket)

def get_tickets(type, status="New"):
    items = list(db.tickets.find({"type": type, "status": status}))
    # تحويل ObjectId لنص عشان العرض
    for item in items:
        item['_id'] = str(item['_id'])
    return items

def update_ticket_status(ticket_id, new_status):
    from bson.objectid import ObjectId
    db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": {"status": new_status}})

def update_cups(room, reset=False):
    if reset:
        db.cups.update_one({"room": room}, {"$set": {"count": 0}}, upsert=True)
    else:
        db.cups.update_one({"room": room}, {"$inc": {"count": 1}}, upsert=True)

def get_cups():
    return list(db.cups.find({"count": {"$gt": 0}}))

# --- تسجيل مستخدمين افتراضيين (لأول مرة فقط) ---
if db.users.count_documents({}) == 0:
    users = [
        {"username": "admin", "password": "123", "name": "Eng. Karim", "role": "Admin", "room": "IT Office"},
        {"username": "ali", "password": "123", "name": "Ali Adel", "role": "Employee", "room": "Yellow Room"},
        {"username": "office", "password": "123", "name": "Amr Office", "role": "Office Boy", "room": "Kitchen"},
        {"username": "it", "password": "123", "name": "Support Team", "role": "IT Support", "room": "IT Room"}
    ]
    db.users.insert_many(users)

# --- نظام تسجيل الدخول ---
def login():
    st.sidebar.title("🔐 تسجيل الدخول")
    if 'user' in st.session_state:
        return st.session_state['user']

    username = st.sidebar.text_input("اسم المستخدم")
    password = st.sidebar.text_input("كلمة المرور", type="password")
    
    if st.sidebar.button("دخول"):
        user = get_user(username, password)
        if user:
            user['_id'] = str(user['_id'])
            st.session_state['user'] = user
            st.success("تم الدخول بنجاح")
            st.rerun()
        else:
            st.sidebar.error("بيانات خطأ! جرب (admin / 123)")
    return None

# --- التطبيق الرئيسي ---
user = login()

if user:
    st.sidebar.markdown("---")
    st.sidebar.write(f"👤 **{user['name']}**")
    st.sidebar.write(f"📍 **{user['room']}**")
    
    if st.sidebar.button("خروج"):
        del st.session_state['user']
        st.rerun()

    # ==================== (1) الموظف ====================
    if user['role'] in ["Employee", "Admin"]:
        st.title(f"👋 أهلاً {user['name'].split()[0]}")
        
        t1, t2, t3 = st.tabs(["☕ طلب بوفيه", "💻 دعم فني", "🧹 أكواب"])
        
        with t1:
            c1, c2 = st.columns(2)
            item = c1.selectbox("المشروب", ["قهوة", "شاي", "نسكافيه", "مياه"])
            sugar = c1.selectbox("السكر", ["بدون", "مظبوط", "زيادة"])
            note = c2.text_input("ملاحظات")
            if st.button("إرسال طلب 🚀"):
                add_ticket(user, "Office", f"{item} - {sugar}", note)
                st.success("تم!")

        with t2:
            issue = st.selectbox("المشكلة", ["نت", "طابعة", "جهاز", "سوفتوير"])
            desc = st.text_area("تفاصيل")
            if st.button("تبليغ IT 🛠️"):
                add_ticket(user, "IT", issue, desc)
                st.success("تم!")

        with t3:
            if st.button("🥤 في أكواب فارغة"):
                update_cups(user['room'])
                st.toast("وصل التبليغ للأوفيس!")

    # ==================== (2) الأوفيس ====================
    if user['role'] in ["Office Boy", "Admin"]:
        st.divider()
        st.header("🍵 الأوفيس")
        
        # الأكواب
        cups = get_cups()
        if cups:
            cols = st.columns(4)
            for c in cups:
                with cols[0]:
                    st.error(f"🏠 {c['room']}: {c['count']}")
                    if st.button("تنظيف", key=c['room']):
                        update_cups(c['room'], reset=True)
                        st.rerun()
        
        # الطلبات
        reqs = get_tickets("Office")
        if reqs:
            for r in reqs:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"**{r['user_name']}** ({r['user_room']}) -> {r['item']}")
                    if c2.button("✅", key=r['_id']):
                        update_ticket_status(r['_id'], "Done")
                        st.rerun()
        else:
            st.info("مفيش طلبات جديدة")

    # ==================== (3) IT Support ====================
    if user['role'] in ["IT Support", "Admin"]:
        st.divider()
        st.header("🔧 الدعم الفني")
        reqs = get_tickets("IT")
        if reqs:
            for r in reqs:
                st.error(f"🚨 {r['user_name']} ({r['user_room']}): {r['item']}")
                st.write(f"التفاصيل: {r['details']}")
                if st.button("تم الحل ✅", key=r['_id']):
                    update_ticket_status(r['_id'], "Done")
                    st.rerun()
                st.markdown("---")
        else:
            st.success("السيستم تمام")

else:
    st.title("ITQAN Cloud ☁️")
    st.info("من فضلك سجل دخول (admin / 123)")