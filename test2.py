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
import logging
import pandas as pd
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#########################
# SCRAPER CONFIGURATION
#########################
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

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

# Function to normalize price string to numeric value
def normalize_price(price_str):
    if not price_str or price_str == "Price Not Available":
        return float('inf')
    # Extract numeric value from price string (e.g., "₹1,499" to 1499)
    price_num = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(price_num)
    except ValueError:
        return float('inf')

# Function to extract Amazon ASIN from URL
def extract_asin(url):
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    # Try alternative pattern
    asin_match = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    # Try to find it in the query parameters
    asin_match = re.search(r"[?&]asin=([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    
    return None

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

# Function to get Amazon product details using requests (no Selenium)
@st.cache_data(ttl=3600, show_spinner=False)
def get_amazon_product_details_requests(url):
    if not url.startswith(("http://", "https://")):
        return {"title": "Invalid URL", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}
    
    headers = {"User-Agent": get_random_user_agent(),
              "Accept-Language": "en-US,en;q=0.9",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}
    
    try:
        # Extract ASIN from URL
        asin = extract_asin(url)
        if not asin:
            return {"title": "Could not extract ASIN from URL", "price": "N/A", "asin": "N/A", "image_url": "", "model_number": ""}
        
        # Make the request
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"title": f"HTTP Error: {response.status_code}", "price": "N/A", "asin": asin, "image_url": "", "model_number": ""}
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Get title
        title_element = soup.select_one("#productTitle")
        title = title_element.get_text().strip() if title_element else "Title Not Found"
        
        # Get price - try multiple selectors
        price = "Price Not Available"
        for price_selector in [".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", ".a-price-whole"]:
            price_element = soup.select_one(price_selector)
            if price_element:
                price = price_element.get_text().strip()
                break
        
        # Get image URL
        image_element = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
        image_url = image_element.get('src') if image_element else ""
        
        # Try to get model number
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
        
        # If model number not found in bullets, try product description
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

# Function to get product from Flipkart with more accurate matching from comp.py
@st.cache_data(ttl=3600, show_spinner=False)
def get_flipkart_product(product_name, model_number=None):
    headers = {"User-Agent": get_random_user_agent()}
    
    # Create a more specific search query if model number is available
    if model_number and len(model_number) > 2:
        search_query = quote_plus(f"{product_name} {model_number}")
    else:
        # Extract key terms from product name to improve search
        # Remove common words that don't help in product identification
        cleaned_name = re.sub(r'\b(with|for|and|the|a|an|by|in|on|at|to|of)\b', '', product_name, flags=re.IGNORECASE)
        # Get first 5-8 words which usually contain the most relevant product info
        name_parts = cleaned_name.split()
        if len(name_parts) > 8:
            search_terms = ' '.join(name_parts[:8])
        else:
            search_terms = cleaned_name
        search_query = quote_plus(search_terms)
    
    search_url = f"https://www.flipkart.com/search?q={search_query}"
    
    try:
        for attempt in range(3):  # Try up to 3 times
            try:
                response = requests.get(search_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                if attempt < 2:  # Don't sleep on the last attempt
                    time.sleep(2)
                continue
        else:  # This executes if the loop completes without a break
            return {"flipkart_price": "Connection Error", "flipkart_link": search_url, "flipkart_image": "", "flipkart_title": ""}
        
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all product containers
        products = soup.find_all("div", {"class": "_1AtVbE"})
        if not products:
            return {"flipkart_price": "Price Not Available", "flipkart_link": search_url, "flipkart_image": "", "flipkart_title": ""}
        
        best_match = None
        highest_score = 0
        
        # Find the product that best matches our search criteria
        for product in products[:5]:  # Check first 5 results
            # Find product title
            title_tag = product.find("div", {"class": "_4rR01T"})
            if not title_tag:
                title_tag = product.find("a", {"class": "s1Q9rs"})
            
            if not title_tag:
                continue
                
            product_title = title_tag.text.strip()
            
            # Calculate similarity score (very basic implementation)
            score = 0
            if model_number and model_number.lower() in product_title.lower():
                score += 10  # Strong boost for model number match
            
            # Check for key words from product name
            for word in product_name.lower().split():
                if len(word) > 3 and word.lower() in product_title.lower():
                    score += 1
            
            # Find product link
            product_link = product.find("a", {"class": "_1fQZEK"})
            if not product_link:
                product_link = product.find("a", {"class": "s1Q9rs"})
            
            if not product_link:
                continue
                
            # Find price
            price_tag = product.find("div", {"class": "_30jeq3"})
            if not price_tag:
                continue
                
            price = price_tag.text.strip()
            
            # Find image
            image_tag = product.find("img", {"class": "_396cs4"})
            image_url = image_tag.get("src") if image_tag else ""
            
            # If this is the best match so far, update
            if score > highest_score:
                highest_score = score
                product_url = "https://www.flipkart.com" + product_link.get("href")
                best_match = {
                    "flipkart_price": price, 
                    "flipkart_link": product_url, 
                    "flipkart_image": image_url,
                    "flipkart_title": product_title,
                    "match_score": score
                }
        
        # If we found a match, return it
        if best_match:
            return best_match
        
        # Fallback: return first product if no good match found
        first_product = products[0]
        title_tag = first_product.find("div", {"class": "_4rR01T"}) or first_product.find("a", {"class": "s1Q9rs"})
        product_link = first_product.find("a", {"class": "_1fQZEK"}) or first_product.find("a", {"class": "s1Q9rs"})
        price_tag = first_product.find("div", {"class": "_30jeq3"})
        image_tag = first_product.find("img", {"class": "_396cs4"})
        
        if title_tag and product_link and price_tag:
            product_title = title_tag.text.strip()
            product_url = "https://www.flipkart.com" + product_link.get("href")
            price = price_tag.text.strip()
            image_url = image_tag.get("src") if image_tag else ""
            
            return {
                "flipkart_price": price, 
                "flipkart_link": product_url, 
                "flipkart_image": image_url,
                "flipkart_title": product_title,
                "match_score": 0
            }
        
        return {"flipkart_price": "Price Not Available", "flipkart_link": search_url, "flipkart_image": "", "flipkart_title": ""}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching Flipkart data: {error_msg}")
        return {"flipkart_price": f"Error: {error_msg}", "flipkart_link": search_url, "flipkart_image": "", "flipkart_title": ""}

# Function to extract product name from Amazon product data (from comp.py)
def extract_search_terms(product_data):
    title = product_data.get('title', '')
    model = product_data.get('model_number', '')
    
    # If we couldn't get a valid title, return empty
    if title in ["Invalid URL", "Title Not Found", ""] or title.startswith("Error:"):
        return "", ""
    
    # Get the first 5-7 words which typically contain the core product info
    words = title.split()
    if len(words) > 7:
        name = ' '.join(words[:7])
    else:
        name = title
    
    # Remove common words that don't help in product identification
    name = re.sub(r'\b(with|for|and|the|a|an|by|in|on|at|to|of)\b', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name, model

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
    return {row[0]: {"name": row[1], "prices": eval(row[2])} for row in rows}

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

    option = st.sidebar.radio("Choose Option", ["Add/Update Product", "List Tracked Products", "Visualize Price Trend", "Price Comparison"])

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
            st.markdown(f"Current Price: ₹{info['prices'][-1][1]}")
            st.markdown(f"[View Product]({url})")
            st.markdown("---")

    elif option == "Visualize Price Trend":
        st.subheader("📈 Price Trend")
        urls = list(st.session_state["tracked_products"].keys())
        if urls:
            selected = st.selectbox("Choose Product", urls)
            data = st.session_state["tracked_products"][selected]
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
    
    # New option for price comparison functionality from comp.py
    elif option == "Price Comparison":
        st.subheader("🔍 Price Comparison Tool")
        st.write("Enter an Amazon product URL to compare prices with Flipkart.")
        amazon_url = st.text_input("Amazon Product URL", key="comparison_url")

    if amazon_url:
            try:
                with st.spinner("Fetching product details..."):
                    # Use the requests-based approach instead of Selenium
                    product_details = get_amazon_product_details_requests(amazon_url)
                    
                    if product_details["title"] not in ["Invalid URL", "Could not extract ASIN from URL"] and not product_details["title"].startswith(("Error:", "HTTP Error:", "Connection Error:")):
                        # Extract search terms for Flipkart
                        search_name, model = extract_search_terms(product_details)
                        
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            flipkart_future = executor.submit(get_flipkart_product, search_name, model)
                            flipkart_data = flipkart_future.result()
                        
                        # Display product and comparison
                        st.subheader("📌 Product Details")
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            if product_details["image_url"]:
                                st.image(product_details["image_url"], width=200)
                            else:
                                st.info("No product image available")
                        
                        with col2:
                            st.write(f"**Product Name:** {product_details['title']}")
                            if product_details["model_number"]:
                                st.write(f"**Model Number:** {product_details['model_number']}")
                            st.write(f"**Amazon ASIN:** {product_details['asin']}")
                        
                        # Price comparison section
                        st.subheader("🔍 Product Comparison")
                        
                        # Display platform comparison in two columns
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("### 🛍 Amazon")
                            st.write(f"**Price:** {product_details['price']}")
                            st.markdown(f"[View on Amazon]({amazon_url})")
                            if product_details["image_url"]:
                                st.image(product_details["image_url"], width=150)
                        
                        with col2:
                            st.write("### 🛒 Flipkart")
                            st.write(f"**Price:** {flipkart_data['flipkart_price']}")
                            st.markdown(f"[View on Flipkart]({flipkart_data['flipkart_link']})")
                            if flipkart_data["flipkart_image"]:
                                st.image(flipkart_data["flipkart_image"], width=150)
                            if flipkart_data.get("match_score", 0) > 5:
                                st.info("✓ High confidence product match")
                        
                        # Price comparison analysis
                        amazon_price = normalize_price(product_details['price'])
                        flipkart_price = normalize_price(flipkart_data['flipkart_price'])
                        
                        if amazon_price != float('inf') and flipkart_price != float('inf'):
                            price_diff = abs(amazon_price - flipkart_price)
                            if amazon_price > flipkart_price:
                                price_diff_percent = (price_diff / amazon_price) * 100
                                st.success(f"💰 Flipkart is cheaper by ₹{price_diff:.2f} ({price_diff_percent:.1f}%)")
                            elif flipkart_price > amazon_price:
                                price_diff_percent = (price_diff / flipkart_price) * 100
                                st.success(f"💰 Amazon is cheaper by ₹{price_diff:.2f} ({price_diff_percent:.1f}%)")
                            else:
                                st.info("🏆 Both platforms have the same price!")
                        
                        # Add tracking option
                        if st.button("Track This Product"):
    user_email = st.session_state.get("user_email", "")
    price_val = normalize_price(product_details["price"])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not user_email:
        st.warning("Please log in to track products")
    else:
        # Add product to tracking database
        tracking_data = {
            "email": user_email,
            "product_url": amazon_url,  # Using amazon_url from the context
            "product_name": product_details["title"],
            "current_price": price_val,
            "target_price": price_val,  # Default target price is current price
            "timestamp": timestamp
        }
        
        # Check if product is already being tracked by this user
        existing_tracking = db.collection("tracked_products").where(
            "email", "==", user_email
        ).where(
            "product_url", "==", amazon_url  # Using amazon_url from the context
        ).get()
        
        if existing_tracking:
            st.info("You're already tracking this product!")
        else:
            # Add new tracking record
            db.collection("tracked_products").add(tracking_data)
            st.success("Product added to tracking! You'll be notified of price changes.")
            
            # Add UI to set target price
            st.subheader("Set Your Target Price")
            target_price = st.number_input(
                "Target Price", 
                min_value=0.01, 
                max_value=float(price_val)*2,
                value=float(price_val)*0.9,  # Default to 10% discount
                step=0.01
            )
            
            if st.button("Update Target Price"):
                # Update the target price in the database
                for doc in existing_tracking:
                    db.collection("tracked_products").document(doc.id).update({
                        "target_price": target_price
                    })
                st.success(f"Target price updated to ${target_price:.2f}")