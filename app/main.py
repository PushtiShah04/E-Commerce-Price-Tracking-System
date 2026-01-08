import streamlit as st
import sqlite3
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import re
import random
import time
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# Add the import for inf
import math
from math import inf

#########################
# SCRAPER CONFIGURATION
#########################
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
]

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    service = Service()  # Add path to chromedriver if needed: Service("/path/to/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def tokenize(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return set(text.split())

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()

##############################
# AMAZON SCRAPER
##############################
def scrape_amazon_product(url):
    driver = setup_driver()
    driver.get(url)
    time.sleep(3)

    try:
        title = driver.find_element(By.ID, 'productTitle').text
        price_elem = driver.find_element(By.CSS_SELECTOR, '.a-price .a-offscreen')
        price = price_elem.get_attribute('innerHTML')
        image = driver.find_element(By.ID, 'landingImage').get_attribute('src')
        driver.quit()
        return {"title": title, "price": price, "link": url, "image": image}
    except Exception as e:
        print("Amazon Scraping Error:", e)
        driver.quit()
        return None

##############################
# FLIPKART SCRAPER
##############################
def get_flipkart_price(product_title):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    query = clean_text(product_title).replace(" ", "+")
    search_url = f"https://www.flipkart.com/search?q={query}"
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    products = soup.find_all("a", class_="_1fQZEK") + soup.find_all("a", class_="IRpwTa")
    product_list = []

    for product in products:
        title = product.find("div", class_="_4rR01T") or product.find("div", class_="IRpwTa")
        if title:
            product_title_text = title.get_text()
            product_link = "https://www.flipkart.com" + product["href"]
            product_price = product.find("div", class_="_30jeq3")
            product_list.append({
                "title": product_title_text,
                "link": product_link,
                "price": product_price.get_text() if product_price else "N/A"
            })

    best_match = None
    best_score = 0
    amazon_keywords = tokenize(product_title)

    for item in product_list:
        flipkart_keywords = tokenize(item['title'])
        match_score = len(amazon_keywords.intersection(flipkart_keywords))
        if match_score > best_score:
            best_score = match_score
            best_match = item

    if best_match and best_score > 0:
        return {
            "found": True,
            "flipkart_name": best_match["title"],
            "flipkart_price": best_match["price"],
            "flipkart_link": best_match["link"]
        }

    return {"found": False, "related": product_list[:3]}

##############################
# DATABASE
##############################
def create_user_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def init_product_db():
    conn = sqlite3.connect("products.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracked_products (
        url TEXT PRIMARY KEY,
        name TEXT,
        prices TEXT)''')
    conn.commit()
    return conn

def save_tracked_product(conn, url, name, prices):
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO tracked_products (url, name, prices) VALUES (?, ?, ?)",
                   (url, name, str(prices)))
    conn.commit()

def load_tracked_products(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tracked_products")
    rows = cursor.fetchall()
    # Use a safer approach than eval
    result = {}
    for row in rows:
        try:
            prices_data = eval(row[2], {"__builtins__": {}}, {"inf": float('inf')})
            result[row[0]] = {"name": row[1], "prices": prices_data}
        except Exception as e:
            print(f"Error parsing prices for {row[0]}: {e}")
            # Provide a default empty list for prices if parsing fails
            result[row[0]] = {"name": row[1], "prices": []}
    return result

##############################
# AUTH
##############################
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(name, email, password):
    hashed = hash_password(password)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return "✅ Registration Successful!"
    except sqlite3.IntegrityError:
        return "⚠️ Email already exists!"
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

##############################
# ML
##############################
def predict_future_price(prices):
    if len(prices) < 2: return None
    X = np.arange(len(prices)).reshape(-1, 1)
    y = np.array(prices).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    return model.predict([[len(prices)]])[0][0]

def detect_anomalies(prices):
    if len(prices) < 2: return []
    model = IsolationForest(contamination=0.1)
    preds = model.fit_predict(np.array(prices).reshape(-1, 1))
    return [i for i, p in enumerate(preds) if p == -1]

##############################
# STREAMLIT APP
##############################
create_user_db()
conn = init_product_db()

if "tracked_products" not in st.session_state:
    st.session_state["tracked_products"] = load_tracked_products(conn)

st.title("🛒 E-Commerce Price Tracker")

if not st.session_state.get("authenticated", False):
    tab1, tab2 = st.tabs(["Register", "Login"])
    with tab1:
        name = st.text_input("Full Name")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            st.success(register_user(name, email, password))

    with tab2:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            user = login_user(email, password)
            if user:
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email
                st.rerun()
            else:
                st.error("Invalid credentials")

else:
    st.sidebar.markdown(f"👤 Logged in as: {st.session_state['user_email']}")
    if st.sidebar.button("Logout"):
        logout_user()

    option = st.sidebar.radio("Choose Option", ["Add/Update Product", "List Tracked Products", "Visualize Price Trend"])

    if option == "Add/Update Product":
        st.subheader("🔍 Track a New Product")
        url = st.text_input("Enter Amazon Product URL")
        user_email = st.text_input("Your Email")
        threshold = st.number_input("Set Threshold Price (₹)", min_value=1.0, step=100.0)

        if st.button("Track Product"):
            amazon = scrape_amazon_product(url)
            if not amazon:
                st.error("❌ Unable to scrape Amazon product. Please check the URL.")
            else:
                flipkart = get_flipkart_price(amazon["title"])

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 🛒 Amazon")
                    st.image(amazon['image'], width=200)
                    st.markdown(f"**{amazon['title']}**")
                    st.markdown(f"Price: ₹{amazon['price']}")
                    st.markdown(f"[Link]({amazon['link']})")

                with col2:
                    st.markdown("### 🛍️ Flipkart")
                    if flipkart.get("found"):
                        st.markdown(f"**{flipkart['flipkart_name']}**")
                        st.markdown(f"Price: {flipkart['flipkart_price']}")
                        st.markdown(f"[Link]({flipkart['flipkart_link']})")
                    else:
                        st.warning("No exact match. Related products:")
                        for r in flipkart["related"]:
                            st.markdown(f"- {r['title']} ({r['price']}) → [Link]({r['link']})")

                price_val = float(str(amazon["price"]).replace("₹", "").replace(",", ""))
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if url not in st.session_state["tracked_products"]:
                    st.session_state["tracked_products"][url] = {
                        "name": amazon["title"],
                        "prices": [(timestamp, price_val)],
                        "email": user_email,
                        "threshold": threshold
                    }
                else:
                    st.session_state["tracked_products"][url]["prices"].append((timestamp, price_val))

                save_tracked_product(conn, url, amazon["title"], st.session_state["tracked_products"][url]["prices"])
                st.success(f"Tracking '{amazon['title']}' at ₹{price_val}")
                if price_val <= threshold:
                    st.balloons()
                    st.success("🎉 Price is below your threshold!")

    elif option == "List Tracked Products":
        st.subheader("📋 Tracked Products")
        for url, info in st.session_state["tracked_products"].items():
            st.markdown(f"**{info['name']}**")
            if info['prices'] and len(info['prices']) > 0:
                st.markdown(f"Current Price: ₹{info['prices'][-1][1]}")
            else:
                st.markdown("No price data available")
            st.markdown(f"[View Product]({url})")
            st.markdown("---")

    elif option == "Visualize Price Trend":
        st.subheader("📈 Price Trend")
        urls = list(st.session_state["tracked_products"].keys())
        if urls:
            selected = st.selectbox("Choose Product", urls)
            data = st.session_state["tracked_products"][selected]
            if data["prices"] and len(data["prices"]) > 0:
                timestamps, prices = zip(*data["prices"])
                plt.figure(figsize=(10, 5))
                plt.plot(timestamps, prices, marker='o')
                plt.xticks(rotation=45)
                plt.title(f"Price Trend: {data['name']}")
                plt.xlabel("Date")
                plt.ylabel("Price (₹)")
                st.pyplot(plt)

                predicted = predict_future_price([p for _, p in data["prices"]])
                if predicted:
                    st.info(f"Predicted Next Price: ₹{predicted:.2f}")

                anomalies = detect_anomalies([p for _, p in data["prices"]])
                if anomalies:
                    st.warning(f"Anomalies detected at indices: {anomalies}")
            else:
                st.warning("No price data available for this product")
        else:
            st.warning("No products are being tracked yet")