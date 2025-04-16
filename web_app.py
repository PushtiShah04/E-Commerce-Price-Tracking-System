import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import smtplib

# Dictionary to store tracked products with price trends
tracked_products = {}

# Function to fetch product details from a URL
def fetch_product_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    try:
        name = soup.find("span", {"id": "productTitle"}).get_text(strip=True)
        price = soup.find("span", {"class": "a-price-whole"}).get_text(strip=True)
        price = float(price.replace(",", ""))
    except AttributeError:
        return None, None
    return name, price

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

# Streamlit app UI
st.title("Product Price Tracker")

# Sidebar for navigation
option = st.sidebar.selectbox(
    "Choose an option",
    ["Add/Update Product", "List Tracked Products", "Visualize Price Trend"]
)

if option == "Add/Update Product":
    st.header("Add or Update Product")
    url = st.text_input("Enter the product URL:")
    email = st.text_input("Enter your email for purchase confirmation:")
    threshold = st.number_input("Enter your price threshold for automatic purchase (₹):", min_value=0.0, step=0.1)
    
    if st.button("Track Product"):
        name, price = fetch_product_details(url)
        if name and price:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if url in tracked_products:
                old_price = tracked_products[url]['prices'][-1][1]
                if old_price != price:
                    st.info(f"Price updated for {name}: ₹{old_price} → ₹{price}")
                tracked_products[url]['prices'].append((timestamp, price))
                if price <= threshold:
                    st.success(f"Price for {name} dropped below your threshold of ₹{threshold}. Attempting automatic purchase...")
                    send_purchase_email(email, name, price)
            else:
                st.success(f"Adding new product: {name} at ₹{price}")
                tracked_products[url] = {'name': name, 'prices': [(timestamp, price)]}
        else:
            st.error("Failed to fetch product details. Check the URL.")

elif option == "List Tracked Products":
    st.header("Tracked Products")
    if tracked_products:
        for url, details in tracked_products.items():
            st.markdown(f"**{details['name']}** - ₹{details['prices'][-1][1]} (Latest Price)  \n[Product Link]({url})")
    else:
        st.info("No products are currently being tracked.")

elif option == "Visualize Price Trend":
    st.header("Visualize Price Trend")
    url = st.text_input("Enter the product URL to visualize:")
    if st.button("Show Trend"):
        if url in tracked_products:
            product = tracked_products[url]
            timestamps, prices = zip(*product['prices'])
            plt.figure(figsize=(10, 6))
            plt.plot(timestamps, prices, marker='o', label=f"{product['name']} Price Trend")
            plt.xlabel('Timestamp')
            plt.ylabel('Price (₹)')
            plt.title(f"Price Trend for {product['name']}")
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.tight_layout()
            st.pyplot(plt)
        else:
            st.error("Product not found in tracked products.")
