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
from math import inf
import pandas as pd
from urllib.parse import quote_plus
import logging
from concurrent.futures import ThreadPoolExecutor
import json

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def normalize_price(price_str):
    if not price_str or price_str == "Price Not Available":
        return float('inf')
    price_num = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(price_num)
    except ValueError:
        return float('inf')

def extract_asin(url):
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    asin_match = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    asin_match = re.search(r"[?&]asin=([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    return None

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    service = Service()
    return webdriver.Chrome(service=service, options=options)

def tokenize(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return set(text.split())

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()

@st.cache_data(ttl=3600, show_spinner=False)
def get_amazon_product_details_requests(url):
    if not url.startswith(("http://", "https://")):
        return {"title": "Invalid URL", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}
    
    headers = {"User-Agent": get_random_user_agent(),
              "Accept-Language": "en-US,en;q=0.9",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}
    
    try:
        asin = extract_asin(url)
        if not asin:
            return {"title": "Could not extract ASIN from URL", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"title": f"HTTP Error: {response.status_code}", "price": "N/A", "asin": asin, "image_url": "", "model_number": ""}
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.select_one("#productTitle")
        title = title_element.get_text().strip() if title_element else "Title Not Found"
        
        price = "Price Not Available"
        for price_selector in [".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", ".a-price-whole"]:
            price_element = soup.select_one(price_selector)
            if price_element:
                price = price_element.get_text().strip()
                break
        
        image_element = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
        image_url = image_element.get('src') if image_element else ""
        
        model_number = ""
        detail_bullets = soup.select_one("#detailBullets_feature_div")
        if detail_bullets:
            bullets = detail_bullets.select("li")
            for bullet in bullets:
                bullet_text = bullet.get_text().strip().lower()
                if "model" in bullet_text:
                    model_match = re.search(r'model.*?([A-Za-z0-9-]+)', bullet_text)
                    if model_match:
                        model_number = model_match.group(1).strip()
                        break
        
        if not model_number:
            product_description = soup.select_one("#productDescription")
            if product_description:
                description_text = product_description.get_text().lower()
                model_match = re.search(r'model\s*(?:number|#|no)?[:\s]+([A-Za-z0-9-]+)', description_text)
                if model_match:
                    model_number = model_match.group(1).strip()
        
        return {
            "title": title,
            "price": price,
            "asin": asin,
            "image_url": image_url,
            "model_number": model_number
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        logger.error(f"Request error fetching Amazon product: {error_msg}")
        return {"title": f"Connection Error: {error_msg}", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error fetching Amazon product: {error_msg}")
        return {"title": f"Error: {error_msg}", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}

@st.cache_data(ttl=3600, show_spinner=False)
def get_flipkart_product(product_name, model_number=None):
    headers = {"User-Agent": get_random_user_agent()}

    # Create a more specific search query
    if model_number and len(model_number) > 2:
        search_query = quote_plus(f"{product_name} {model_number}")
    else:
        # Remove common stop words from product name
        cleaned_name = re.sub(r'\b(with|for|and|the|a|an|by|in|on|at|to|of)\b', '', product_name, flags=re.IGNORECASE)
        name_parts = cleaned_name.split()
        search_terms = ' '.join(name_parts[:8]) if len(name_parts) > 8 else cleaned_name
        search_query = quote_plus(search_terms)

    search_url = f"https://www.flipkart.com/search?q={search_query}"

    try:
        for attempt in range(3):  # Retry logic
            try:
                response = requests.get(search_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                if attempt < 2:
                    time.sleep(2)
                continue
        else:
            return {
                "flipkart_price": "Connection Error",
                "flipkart_link": search_url,
                "flipkart_image": "",
                "flipkart_title": ""
            }

        soup = BeautifulSoup(response.content, "html.parser")
        products = soup.find_all("div", {"class": "_1AtVbE"})

        if not products:
            return {
                "flipkart_price": "Price Not Available",
                "flipkart_link": search_url,
                "flipkart_image": "",
                "flipkart_title": ""
            }

        best_match = None
        highest_score = 0

        for product in products[:5]:  # Limit to first 5 for performance
            title_tag = product.find("div", {"class": "_4rR01T"}) or product.find("a", {"class": "s1Q9rs"})
            if not title_tag:
                continue

            product_title = title_tag.text.strip()

            # Basic match scoring
            score = 0
            if model_number and model_number.lower() in product_title.lower():
                score += 10

            for word in product_name.lower().split():
                if len(word) > 3 and word.lower() in product_title.lower():
                    score += 1

            product_link = product.find("a", {"class": "_1fQZEK"}) or product.find("a", {"class": "s1Q9rs"})
            price_tag = product.find("div", {"class": "_30jeq3"})
            image_tag = product.find("img", {"class": "_396cs4"})

            if not (product_link and price_tag):
                continue

            price = price_tag.text.strip()
            product_url = "https://www.flipkart.com" + product_link.get("href")
            image_url = image_tag.get("src") if image_tag else ""

            if score > highest_score:
                highest_score = score
                best_match = {
                    "flipkart_price": price,
                    "flipkart_link": product_url,
                    "flipkart_image": image_url,
                    "flipkart_title": product_title,
                    "match_score": score
                }

        if best_match:
            return best_match

        # Fallback to first valid product
        for product in products:
            title_tag = product.find("div", {"class": "_4rR01T"}) or product.find("a", {"class": "s1Q9rs"})
            product_link = product.find("a", {"class": "_1fQZEK"}) or product.find("a", {"class": "s1Q9rs"})
            price_tag = product.find("div", {"class": "_30jeq3"})
            image_tag = product.find("img", {"class": "_396cs4"})

            if title_tag and product_link and price_tag:
                return {
                    "flipkart_price": price_tag.text.strip(),
                    "flipkart_link": "https://www.flipkart.com" + product_link.get("href"),
                    "flipkart_image": image_tag.get("src") if image_tag else "",
                    "flipkart_title": title_tag.text.strip(),
                    "match_score": 0
                }

        return {
            "flipkart_price": "Price Not Available",
            "flipkart_link": search_url,
            "flipkart_image": "",
            "flipkart_title": ""
        }

    except Exception as e:
        logger.error(f"Error fetching Flipkart data: {str(e)}")
        return {
            "flipkart_price": f"Error: {str(e)}",
            "flipkart_link": search_url,
            "flipkart_image": "",
            "flipkart_title": ""
        }

def extract_search_terms(product_data):
    title = product_data.get('title', '')
    model = product_data.get('model_number', '')

    if not title or title in ["Invalid URL", "Title Not Found"] or title.startswith("Error:"):
        return "", ""

    # Extract meaningful words
    words = title.split()
    name = ' '.join(words[:7]) if len(words) > 7 else title
    name = re.sub(r'\b(with|for|and|the|a|an|by|in|on|at|to|of)\b', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()

    return name, model

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
    result = {}
    for row in rows:
        try:
            prices_data = eval(row[2], {"__builtins__": {}}, {"inf": float('inf')})
            result[row[0]] = {"name": row[1], "prices": prices_data}
        except Exception as e:
            print(f"Error parsing prices for {row[0]}: {e}")
            result[row[0]] = {"name": row[1], "prices": []}
    return result

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

st.set_page_config(page_title="E-Commerce Price Tracker", page_icon="🛒", layout="wide")
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
        
        # Main input section - always visible
        url = st.text_input("Enter Amazon Product URL")
        user_email = st.text_input("Your Email", value=st.session_state.get("user_email", ""))
        threshold = st.number_input("Set Threshold Price (₹)", min_value=0.0, step=100.0, value=0.0)
        
        # Button to trigger product fetch and comparison
        fetch_button = st.button("Track Product")
        
        if url and fetch_button:
            with st.spinner("Fetching product details..."):
                # Get detailed product information
                product_details = get_amazon_product_details_requests(url)
                
                if product_details["title"] not in ["Invalid URL", "Could not extract ASIN from URL"] and not product_details["title"].startswith(("Error:", "HTTP Error:", "Connection Error:")):
                    # Extract search terms for Flipkart
                    search_name, model = extract_search_terms(product_details)
                    
                    # Get Flipkart product details using the improved matcher
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        flipkart_future = executor.submit(get_flipkart_product, search_name, model)
                        flipkart_data = flipkart_future.result()
                    
                    st.subheader("📌 Product Details")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 🛒 Amazon")
                        if product_details["image_url"]:
                            st.image(product_details["image_url"], width=200)
                        st.markdown(f"**{product_details['title']}**")
                        st.markdown(f"Price: {product_details['price']}")
                        st.markdown(f"[View on Amazon]({url})")
                        if product_details["model_number"]:
                            st.markdown(f"Model: {product_details['model_number']}")
                        st.markdown(f"ASIN: {product_details['asin']}")
                    
                    with col2:
                        st.markdown("### 🛍️ Flipkart")
                        if flipkart_data["flipkart_image"]:
                            st.image(flipkart_data["flipkart_image"], width=200)
                        st.markdown(f"**{flipkart_data['flipkart_title']}**")
                        st.markdown(f"Price: {flipkart_data['flipkart_price']}")
                        st.markdown(f"[View on Flipkart]({flipkart_data['flipkart_link']})")
    
    # Display match confidence
                        confidence = flipkart_data.get("confidence", "Unknown")
                        if confidence == "Very High":
                            st.success("✓ Very high confidence match")
                        elif confidence == "High":
                            st.success("✓ High confidence match")
                        elif confidence == "Moderate":
                            st.info("ℹ️ Moderate confidence match - please verify")
                        elif confidence == "Low":
                            st.warning("⚠️ Low confidence match - this may not be the same product")
                        elif confidence in ["None", "Error"]:
                            st.error("❌ Could not find a matching product on Flipkart")
                    
                    # Price comparison visualization
                    try:
                        amazon_price = normalize_price(product_details['price'])
                        flipkart_price = normalize_price(flipkart_data['flipkart_price'])
                        
                        if amazon_price != float('inf') and flipkart_price != float('inf'):
                            st.subheader("💰 Price Comparison")
                            price_data = {
                                'Platform': ['Amazon', 'Flipkart'],
                                'Price': [amazon_price, flipkart_price]
                            }
                            chart_data = pd.DataFrame(price_data)
                            
                            fig, ax = plt.subplots(figsize=(10, 5))
                            bars = ax.bar(chart_data['Platform'], chart_data['Price'], color=['#FF9900', '#2874F0'])
                            ax.set_ylabel('Price (₹)')
                            ax.set_title('Price Comparison')
                            
                            # Add price labels on top of bars
                            for bar in bars:
                                height = bar.get_height()
                                ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                                        f'₹{int(height)}', ha='center', va='bottom')
                            
                            # Highlight better deal
                            if amazon_price < flipkart_price:
                                st.pyplot(fig)
                                st.success(f"💸 Amazon is cheaper by ₹{int(flipkart_price - amazon_price)} ({int((flipkart_price - amazon_price) / flipkart_price * 100)}% less)")
                            elif flipkart_price < amazon_price:
                                st.pyplot(fig)
                                st.success(f"💸 Flipkart is cheaper by ₹{int(amazon_price - flipkart_price)} ({int((amazon_price - flipkart_price) / amazon_price * 100)}% less)")
                            else:
                                st.pyplot(fig)
                                st.info("⚖️ Both platforms have the same price")
                    except Exception as e:
                        st.warning(f"Could not compare prices: {str(e)}")
                    
                    # Save to tracking database
                    price_val = normalize_price(product_details['price'])
                    if price_val == float('inf'):
                        st.error("❌ Could not extract price from Amazon. Please try again.")
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if url not in st.session_state["tracked_products"]:
                            st.session_state["tracked_products"][url] = {
                                "name": product_details["title"],
                                "prices": [(timestamp, price_val)],
                                "email": user_email,
                                "threshold": threshold
                            }
                        else:
                            st.session_state["tracked_products"][url]["prices"].append((timestamp, price_val))
                        
                        save_tracked_product(conn, url, product_details["title"], st.session_state["tracked_products"][url]["prices"])
                        st.success(f"✅ Now tracking '{product_details['title']}' at ₹{price_val}")
                        if price_val <= threshold:
                            st.balloons()
                            st.success("🎉 Price is below your threshold!")
                else:
                    st.error(f"Could not process the Amazon URL: {product_details['title']}")
                    st.info("Try entering a direct Amazon product URL that includes '/dp/' in the format: https://www.amazon.in/product-name/dp/ASIN")

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