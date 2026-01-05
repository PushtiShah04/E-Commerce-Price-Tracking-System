import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import smtplib
import json
import os

# Page configuration with custom theme
st.set_page_config(
    page_title="Price Tracking system",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    /* Main background gradient */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d3748 0%, #1a202c 100%);
    }
    
    [data-testid="stSidebar"] .css-1d391kg {
        color: white;
    }
    
    /* Main content area */
    .block-container {
        padding: 2rem;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        margin: 2rem auto;
        backdrop-filter: blur(10px);
    }
    
    /* Headers */
    h1 {
        color: #667eea;
        font-weight: 700;
        text-align: center;
        font-size: 3rem !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        animation: fadeInDown 0.8s ease-in;
    }
    
    h2, h3 {
        color: #764ba2;
        font-weight: 600;
        animation: fadeIn 1s ease-in;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1.1rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* Input fields */
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        border-radius: 10px;
        border: 2px solid #e2e8f0;
        padding: 0.75rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Select box */
    .stSelectbox>div>div {
        border-radius: 10px;
        border: 2px solid #e2e8f0;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    
    /* Success messages */
    .stSuccess {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        animation: slideInRight 0.5s ease-out;
    }
    
    /* Info messages */
    .stInfo {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        animation: slideInLeft 0.5s ease-out;
    }
    
    /* Warning messages */
    .stWarning {
        background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        animation: pulse 1s ease-in-out;
    }
    
    /* Error messages */
    .stError {
        background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        animation: shake 0.5s ease-in-out;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideInRight {
        from {
            transform: translateX(100px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideInLeft {
        from {
            transform: translateX(-100px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-10px); }
        75% { transform: translateX(10px); }
    }
    
    /* Cards for products */
    .product-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        border-left: 5px solid #667eea;
    }
    
    .product-card:hover {
        transform: translateX(10px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Divider */
    hr {
        margin: 2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
    }
    </style>
""", unsafe_allow_html=True)

# File to store tracked products
DATA_FILE = "tracked_products.json"

# Function to load tracked products from file
def load_tracked_products():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

# Function to save tracked products to file
def save_tracked_products():
    with open(DATA_FILE, 'w') as f:
        json.dump(st.session_state.tracked_products, f, indent=4)

# Initialize session state for tracked products
if 'tracked_products' not in st.session_state:
    st.session_state.tracked_products = load_tracked_products()

# Function to fetch product details from a URL
def fetch_product_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Detect if it's Amazon or Flipkart
        if "amazon" in url.lower():
            return fetch_amazon_details(soup)
        elif "flipkart" in url.lower():
            return fetch_flipkart_details(soup)
        else:
            return None, None, "Unknown"
            
    except Exception as e:
        st.error(f"Error fetching product: {str(e)}")
        return None, None, "Unknown"

def fetch_amazon_details(soup):
    # Try multiple selectors for product name
    name = None
    name_selectors = [
        {"id": "productTitle"},
        {"class": "product-title-word-break"},
        {"id": "title"}
    ]
    for selector in name_selectors:
        element = soup.find("span", selector)
        if element:
            name = element.get_text(strip=True)
            break
    
    # Try multiple selectors for price
    price = None
    price_selectors = [
        {"class": "a-price-whole"},
        {"class": "a-price"},
        {"class": "priceblock_ourprice"},
        {"class": "priceblock_dealprice"}
    ]
    for selector in price_selectors:
        element = soup.find("span", selector)
        if element:
            price_text = element.get_text(strip=True)
            # Extract numeric value
            price_text = price_text.replace("₹", "").replace(",", "").replace(".", "").strip()
            if price_text and price_text.isdigit():
                price = float(price_text) / 100  # Convert paise to rupees
                break
    
    if not name or not price:
        return None, None, "Amazon"
        
    return name, price, "Amazon"

def fetch_flipkart_details(soup):
    # Try multiple selectors for product name on Flipkart
    name = None
    name_selectors = [
        {"class": "VU-ZEz"},
        {"class": "B_NuCI"},
        {"class": "_35KyD6"}
    ]
    for selector in name_selectors:
        element = soup.find("span", selector)
        if not element:
            element = soup.find("h1", selector)
        if element:
            name = element.get_text(strip=True)
            break
    
    # Try multiple selectors for price on Flipkart
    price = None
    price_selectors = [
        {"class": "Nx9bqj"},
        {"class": "_30jeq3"},
        {"class": "_25b18c"}
    ]
    for selector in price_selectors:
        element = soup.find("div", selector)
        if element:
            price_text = element.get_text(strip=True)
            # Extract numeric value
            price_text = price_text.replace("₹", "").replace(",", "").strip()
            try:
                price = float(price_text)
                break
            except:
                continue
    
    if not name or not price:
        return None, None, "Flipkart"
        
    return name, price, "Flipkart"

# Function to send an email notification (Simulate purchase confirmation)
def send_purchase_email(email, product_name, price):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("your_email@gmail.com", "your_password")  # Replace with your email credentials
        subject = "Purchase Confirmation"
        body = f"Your product '{product_name}' has been successfully purchased for ₹{price}."
        message = f"Subject: {subject}\n\n{body}"
        server.sendmail("your_email@gmail.com", email, message)
        server.quit()
        st.success(f"Purchase confirmation sent to {email}.")
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")

# App title with emoji
st.markdown("<h1>🛒 Price Tracker Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #718096; font-size: 1.2rem;'>Track prices, save money, shop smart!</p>", unsafe_allow_html=True)

# Sidebar for navigation with icons
st.sidebar.markdown("<h2 style='color: white; text-align: center;'>📋 Navigation</h2>", unsafe_allow_html=True)
option = st.sidebar.selectbox(
    "",
    ["🏠 Dashboard", "➕ Add/Update Product", "📊 List Tracked Products", "📈 Visualize Price Trend", "⚖️ Compare Prices"]
)

# Dashboard
if option == "🏠 Dashboard":
    st.markdown("### Welcome to Price Tracker Pro! 🎉")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 Total Products", len(st.session_state.tracked_products))
    
    with col2:
        amazon_count = sum(1 for details in st.session_state.tracked_products.values() 
                          if details.get('platform') == 'Amazon' or 'amazon' in str(details))
        st.metric("🛒 Amazon Products", amazon_count)
    
    with col3:
        flipkart_count = sum(1 for details in st.session_state.tracked_products.values() 
                            if details.get('platform') == 'Flipkart')
        st.metric("🛍️ Flipkart Products", flipkart_count)
    
    st.markdown("---")
    
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Add New Product", use_container_width=True):
            st.session_state.temp_navigation = "➕ Add/Update Product"
            st.rerun()
    
    with col2:
        if st.button("📊 View All Products", use_container_width=True):
            st.session_state.temp_navigation = "📊 List Tracked Products"
            st.rerun()
    
    with col3:
        if st.button("⚖️ Compare Prices", use_container_width=True):
            st.session_state.temp_navigation = "⚖️ Compare Prices"
            st.rerun()
    
    st.markdown("---")
    
    if st.session_state.tracked_products:
        st.markdown("### 📌 Recent Products")
        recent_products = list(st.session_state.tracked_products.items())[-3:]
        for url, details in recent_products:
            st.markdown(f"""
                <div class="product-card">
                    <h4>{details['name'][:60]}...</h4>
                    <p style="font-size: 1.5rem; color: #667eea; font-weight: 700;">₹{details['prices'][-1][1]:,.2f}</p>
                    <p style="color: #718096;">Platform: {details.get('platform', 'Unknown')}</p>
                </div>
            """, unsafe_allow_html=True)

# Handle temporary navigation
if 'temp_navigation' in st.session_state:
    option = st.session_state.temp_navigation
    del st.session_state.temp_navigation

if option == "➕ Add/Update Product":
    st.markdown("### ➕ Add or Update Product")
    url = st.text_input("🔗 Enter the product URL:")
    email = st.text_input("📧 Enter your email for purchase confirmation:")
    threshold = st.number_input("💰 Enter your price threshold for automatic purchase (₹):", min_value=0.0, step=0.1)
    
    # Option to manually add product details if scraping fails
    manual_entry = st.checkbox("✍️ Unable to fetch details? Enter manually")
    
    if manual_entry:
        manual_name = st.text_input("📦 Enter product name:")
        manual_price = st.number_input("💵 Enter current price (₹):", min_value=0.0, step=0.1)
        
        if st.button("🚀 Track Product"):
            if url and manual_name and manual_price > 0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if url in st.session_state.tracked_products:
                    old_price = st.session_state.tracked_products[url]['prices'][-1][1]
                    if old_price != manual_price:
                        st.info(f"Price updated for {manual_name}: ₹{old_price} → ₹{manual_price}")
                    st.session_state.tracked_products[url]['prices'].append((timestamp, manual_price))
                    if manual_price <= threshold and threshold > 0:
                        st.success(f"Price for {manual_name} dropped below your threshold of ₹{threshold}. Attempting automatic purchase...")
                        send_purchase_email(email, manual_name, manual_price)
                else:
                    st.success(f"Adding new product: {manual_name} at ₹{manual_price}")
                    st.session_state.tracked_products[url] = {'name': manual_name, 'prices': [(timestamp, manual_price)], 'platform': 'Manual'}
                
                # Save to file after adding/updating
                save_tracked_products()
            else:
                st.error("Please fill in all fields (URL, product name, and price).")
    else:
        if st.button("🚀 Track Product"):
            if not url:
                st.error("Please enter a product URL.")
            else:
                with st.spinner("🔍 Fetching product details..."):
                    name, price, platform = fetch_product_details(url)
                if name and price:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if url in st.session_state.tracked_products:
                        old_price = st.session_state.tracked_products[url]['prices'][-1][1]
                        if old_price != price:
                            st.info(f"Price updated for {name}: ₹{old_price} → ₹{price}")
                        st.session_state.tracked_products[url]['prices'].append((timestamp, price))
                        st.session_state.tracked_products[url]['platform'] = platform
                        if price <= threshold and threshold > 0:
                            st.success(f"Price for {name} dropped below your threshold of ₹{threshold}. Attempting automatic purchase...")
                            send_purchase_email(email, name, price)
                    else:
                        st.success(f"✅ Adding new product: {name} at ₹{price} from {platform}")
                        st.session_state.tracked_products[url] = {'name': name, 'prices': [(timestamp, price)], 'platform': platform}
                    
                    # Save to file after adding/updating
                    save_tracked_products()
                else:
                    st.error("Failed to fetch product details. Check the URL or try manual entry option above.")

elif option == "📊 List Tracked Products":
    st.markdown("### 📊 Tracked Products")
    if st.session_state.tracked_products:
        for url, details in st.session_state.tracked_products.items():
            platform_emoji = "🛒" if details.get('platform') == 'Amazon' else "🛍️" if details.get('platform') == 'Flipkart' else "📦"
            st.markdown(f"""
                <div class="product-card">
                    <h4>{platform_emoji} {details['name']}</h4>
                    <p style="font-size: 1.8rem; color: #667eea; font-weight: 700;">₹{details['prices'][-1][1]:,.2f}</p>
                    <p style="color: #718096;">Latest Price • Platform: {details.get('platform', 'Unknown')}</p>
                    <a href="{url}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 600;">🔗 View Product</a>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No products are currently being tracked.")

elif option == "📈 Visualize Price Trend":
    st.markdown("### 📈 Visualize Price Trend")
    if st.session_state.tracked_products:
        # Create a mapping of product names to URLs
        product_names = [details['name'] for details in st.session_state.tracked_products.values()]
        product_urls = list(st.session_state.tracked_products.keys())
        
        selected_product_name = st.selectbox("📦 Select a product to visualize:", ["Select the product"] + product_names)
        
        if st.button("📊 Show Trend"):
            if selected_product_name == "Select the product":
                st.warning("Please select a product from the dropdown menu.")
            else:
                # Find the URL corresponding to the selected product name
                selected_url = None
                for url, details in st.session_state.tracked_products.items():
                    if details['name'] == selected_product_name:
                        selected_url = url
                        break
                
                if selected_url:
                    product = st.session_state.tracked_products[selected_url]
                    timestamps, prices = zip(*product['prices'])
                    
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.plot(timestamps, prices, marker='o', linewidth=3, markersize=8, 
                           color='#667eea', markerfacecolor='#764ba2', markeredgecolor='white', markeredgewidth=2)
                    ax.set_xlabel('Timestamp', fontsize=12, fontweight='bold', color='#2d3748')
                    ax.set_ylabel('Price (₹)', fontsize=12, fontweight='bold', color='#2d3748')
                    ax.set_title(f"Price Trend for {product['name']}", fontsize=16, fontweight='bold', color='#667eea', pad=20)
                    ax.grid(True, alpha=0.3, linestyle='--')
                    ax.set_facecolor('#f7fafc')
                    fig.patch.set_facecolor('white')
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    st.pyplot(fig)
    else:
        st.info("No products are currently being tracked. Add products first to visualize trends.")

elif option == "⚖️ Compare Prices":
    st.markdown("### ⚖️ Compare Prices: Amazon vs Flipkart")
    
    if st.session_state.tracked_products:
        # Filter only Amazon products
        amazon_products = {url: details for url, details in st.session_state.tracked_products.items() 
                          if details.get('platform') == 'Amazon' or 'amazon' in url.lower()}
        
        if amazon_products:
            # Create dropdown with product names
            product_names = [details['name'] for details in amazon_products.values()]
            product_urls = list(amazon_products.keys())
            
            selected_product_name = st.selectbox("🛒 Select an Amazon product to compare:", ["Select a product"] + product_names)
            
            # Manual entry option for comparison
            manual_compare = st.checkbox("✍️ Unable to find on Flipkart? Enter Flipkart price manually")
            
            if manual_compare:
                flipkart_manual_price = st.number_input("💵 Flipkart Price (₹):", min_value=0.0, step=0.1, key="flipkart_manual")
                
                if st.button("⚖️ Compare Now"):
                    if selected_product_name != "Select a product" and flipkart_manual_price > 0:
                        # Find the selected product details
                        amazon_url = None
                        for url, details in amazon_products.items():
                            if details['name'] == selected_product_name:
                                amazon_url = url
                                amazon_name = details['name']
                                amazon_price = details['prices'][-1][1]  # Latest price
                                break
                        
                        if amazon_url:
                            st.markdown("---")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("🛒 Amazon Price", f"₹{amazon_price:,.2f}")
                                st.caption(amazon_name[:50] + "..." if len(amazon_name) > 50 else amazon_name)
                            
                            with col2:
                                st.metric("🛍️ Flipkart Price", f"₹{flipkart_manual_price:,.2f}")
                            
                            with col3:
                                price_diff = abs(amazon_price - flipkart_manual_price)
                                st.metric("💰 Price Difference", f"₹{price_diff:,.2f}")
                            
                            st.markdown("---")
                            
                            if amazon_price < flipkart_manual_price:
                                savings = flipkart_manual_price - amazon_price
                                savings_percent = (savings / flipkart_manual_price) * 100
                                st.success(f"🎉 **Amazon has the better deal!**")
                                st.info(f"💸 You save ₹{savings:,.2f} ({savings_percent:.1f}%) by buying from Amazon")
                            elif flipkart_manual_price < amazon_price:
                                savings = amazon_price - flipkart_manual_price
                                savings_percent = (savings / amazon_price) * 100
                                st.success(f"🎉 **Flipkart has the better deal!**")
                                st.info(f"💸 You save ₹{savings:,.2f} ({savings_percent:.1f}%) by buying from Flipkart")
                            else:
                                st.info("Both platforms have the same price!")
                    elif selected_product_name == "Select a product":
                        st.warning("Please select a product from the dropdown menu.")
                    else:
                        st.error("Please enter Flipkart price.")
            else:
                if st.button("⚖️ Compare Now"):
                    if selected_product_name == "Select a product":
                        st.warning("Please select a product from the dropdown menu.")
                    else:
                        # Find the selected product details
                        amazon_url = None
                        for url, details in amazon_products.items():
                            if details['name'] == selected_product_name:
                                amazon_url = url
                                amazon_name = details['name']
                                amazon_price = details['prices'][-1][1]  # Latest price
                                break
                        
                        if amazon_url:
                            # Search for the product on Flipkart
                            with st.spinner("🔍 Searching for the same product on Flipkart..."):
                                # Extract product keywords from Amazon product name
                                search_query = amazon_name.split('(')[0].strip()  # Remove anything in parentheses
                                # Clean up the search query
                                words = search_query.split()[:5]  # Take first 5 words
                                search_query = ' '.join(words)
                                
                                # Create Flipkart search URL
                                flipkart_search_url = f"https://www.flipkart.com/search?q={search_query.replace(' ', '+')}"
                                
                                st.info(f"🔍 Searching Flipkart for: **{search_query}**")
                                st.markdown(f"[🛍️ Click here to search on Flipkart]({flipkart_search_url})")
                                
                                # Try to fetch Flipkart results
                                try:
                                    headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                                        "Accept-Language": "en-US,en;q=0.9",
                                    }
                                    response = requests.get(flipkart_search_url, headers=headers, timeout=10)
                                    soup = BeautifulSoup(response.content, "html.parser")
                                    
                                    # Try to find first product price in search results
                                    flipkart_price = None
                                    price_selectors = [
                                        {"class": "Nx9bqj"},
                                        {"class": "_30jeq3"},
                                        {"class": "_25b18c"}
                                    ]
                                    for selector in price_selectors:
                                        element = soup.find("div", selector)
                                        if element:
                                            price_text = element.get_text(strip=True)
                                            price_text = price_text.replace("₹", "").replace(",", "").strip()
                                            try:
                                                flipkart_price = float(price_text)
                                                break
                                            except:
                                                continue
                                    
                                    if flipkart_price:
                                        st.markdown("---")
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.metric("🛒 Amazon Price", f"₹{amazon_price:,.2f}")
                                            st.caption(amazon_name[:50] + "..." if len(amazon_name) > 50 else amazon_name)
                                        
                                        with col2:
                                            st.metric("🛍️ Flipkart Price (Estimated)", f"₹{flipkart_price:,.2f}")
                                            st.caption("⚠️ First search result - verify manually")
                                        
                                        with col3:
                                            price_diff = abs(amazon_price_diff = abs(amazon_price - flipkart_price))
                                            st.metric("💰 Price Difference", f"₹{price_diff:,.2f}")
                                        
                                        st.markdown("---")
                                        
                                        if amazon_price < flipkart_price:
                                            savings = flipkart_price - amazon_price
                                            savings_percent = (savings / flipkart_price) * 100
                                            st.success(f"🎉 **Amazon has the better deal!**")
                                            st.info(f"💸 You save ₹{savings:,.2f} ({savings_percent:.1f}%) by buying from Amazon")
                                        elif flipkart_price < amazon_price:
                                            savings = amazon_price - flipkart_price
                                            savings_percent = (savings / amazon_price) * 100
                                            st.success(f"🎉 **Flipkart has the better deal!**")
                                            st.info(f"💸 You save ₹{savings:,.2f} ({savings_percent:.1f}%) by buying from Flipkart")
                                        else:
                                            st.info("Both platforms have the same price!")
                                        
                                        st.warning("⚠️ Note: This is an estimated comparison from search results. Click the Flipkart link above to verify the exact product and price.")
                                    else:
                                        st.warning("⚠️ Could not automatically fetch Flipkart price. Please check the Flipkart search link above or use manual entry.")
                                        st.metric("🛒 Amazon Price", f"₹{amazon_price:,.2f}")
                                        st.caption(amazon_name)
                                except Exception as e:
                                    st.warning("⚠️ Could not automatically search Flipkart. Please check the Flipkart search link above or use manual entry.")
                                    st.metric("🛒 Amazon Price", f"₹{amazon_price:,.2f}")
                                    st.caption(amazon_name)
        else:
            st.info("No Amazon products found in your tracked products. Please add Amazon products first.")
    else:
        st.info("No tracked products found. Please add products first in the 'Add/Update Product' section.")