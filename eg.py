import streamlit as st
import sqlite3
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import smtplib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest

####################################
# DATABASE SETUP
####################################
def init_db():
    conn = sqlite3.connect("products.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_products (
            url TEXT PRIMARY KEY,
            name TEXT,
            prices TEXT
        )
    ''')
    return conn

def create_user_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

####################################
# AUTHENTICATION
####################################
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(name, email, password):
    hashed = hash_password(password)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return "Registration Successful!"
    except sqlite3.IntegrityError:
        return "Email already registered!"
    finally:
        conn.close()

def login_user(email, password):
    hashed = hash_password(password)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed))
    return cursor.fetchone()

def logout_user():
    st.session_state["authenticated"] = False
    st.session_state["user_email"] = None
    st.rerun()

####################################
# SCRAPING
####################################
def fetch_amazon_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')

        title = soup.find("span", {"id": "productTitle"}).get_text(strip=True)
        price = soup.find("span", {"class": "a-price-whole"}).get_text(strip=True)
        price = float(price.replace(",", "").replace("₹", ""))

        return title, price
    except:
        return None, None

####################################
# EMAIL ALERT (optional)
####################################
def send_email_alert(email, product, price):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("your_email@gmail.com", "your_password")
        msg = f"Subject: Price Alert!\n\nPrice dropped for '{product}' to ₹{price}."
        server.sendmail("your_email@gmail.com", email, msg)
        server.quit()
    except Exception as e:
        st.warning(f"Email failed: {e}")

####################################
# ML UTILS
####################################
def predict_future(prices):
    if len(prices) < 2: return None
    X = np.arange(len(prices)).reshape(-1, 1)
    y = np.array(prices).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    return model.predict([[len(prices)]])[0][0]

def detect_anomalies(prices):
    if len(prices) < 2: return []
    model = IsolationForest(contamination=0.1)
    res = model.fit_predict(np.array(prices).reshape(-1, 1))
    return [i for i, v in enumerate(res) if v == -1]

####################################
# DATABASE OPS
####################################
def save_tracked_product(conn, url, name, prices):
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO tracked_products (url, name, prices) VALUES (?, ?, ?)",
                   (url, name, str(prices)))
    conn.commit()

def load_tracked_products(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tracked_products")
    return {row[0]: {"name": row[1], "prices": eval(row[2])} for row in cursor.fetchall()}

####################################
# MAIN APP
####################################
create_user_db()
conn = init_db()
st.title("🛒 Price Tracking System")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab2:
        name = st.text_input("Name")
        email = st.text_input("Email")
        pwd = st.text_input("Password", type="password")
        if st.button("Register"):
            st.success(register_user(name, email, pwd))
    with tab1:
        email = st.text_input("Login Email")
        pwd = st.text_input("Login Password", type="password")
        if st.button("Login"):
            if login_user(email, pwd):
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email
                st.rerun()
            else:
                st.error("Invalid credentials")
else:
    st.sidebar.subheader(f"Logged in as: {st.session_state['user_email']}")
    if st.sidebar.button("Logout"):
        logout_user()

    conn = init_db()
    tracked = load_tracked_products(conn)
    if "tracked_products" not in st.session_state:
        st.session_state["tracked_products"] = tracked

    option = st.sidebar.radio("Menu", ["Add Product", "View Tracked", "Price Chart"])

    if option == "Add Product":
        url = st.text_input("Enter Amazon Product URL")
        threshold = st.number_input("Price Threshold ₹", min_value=0.0, step=100.0)
        if st.button("Track Product"):
            title, price = fetch_amazon_details(url)
            if title and price:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if url not in st.session_state["tracked_products"]:
                    st.session_state["tracked_products"][url] = {"name": title, "prices": [(ts, price)]}
                else:
                    st.session_state["tracked_products"][url]["prices"].append((ts, price))
                save_tracked_product(conn, url, title, st.session_state["tracked_products"][url]["prices"])
                st.success(f"Tracking {title} at ₹{price}")
                if price <= threshold:
                    send_email_alert(st.session_state["user_email"], title, price)
                    st.balloons()
            else:
                st.error("Failed to fetch product details")

    elif option == "View Tracked":
        st.subheader("📋 Your Tracked Products")
        for url, info in st.session_state["tracked_products"].items():
            st.write(f"**{info['name']}** — ₹{info['prices'][-1][1]} ([Link]({url}))")

    elif option == "Price Chart":
        st.subheader("📈 Visualize Price Trend")
        urls = list(st.session_state["tracked_products"].keys())
        if urls:
            choice = st.selectbox("Select a product", urls)
            data = st.session_state["tracked_products"][choice]
            times, prices = zip(*data["prices"])
            plt.plot(times, prices, marker='o')
            plt.xticks(rotation=45)
            plt.title(data["name"])
            plt.xlabel("Date")
            plt.ylabel("Price ₹")
            st.pyplot(plt)
            pred = predict_future(prices)
            if pred:
                st.info(f"Predicted next price: ₹{pred:.2f}")
            anomalies = detect_anomalies(prices)
            if anomalies:
                st.warning(f"⚠️ Anomalies at: {anomalies}")
        else:
            st.warning("No tracked products found.")
