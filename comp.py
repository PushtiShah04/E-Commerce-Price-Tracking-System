import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import random
import time
import pandas as pd
from urllib.parse import quote_plus
import logging
from concurrent.futures import ThreadPoolExecutor
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# User-Agent List to Rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
]

# Function to get a random user agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

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

# Function to get product from Flipkart with more accurate matching
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

# Function to extract product name from Amazon product data
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

# Streamlit App
st.set_page_config(page_title="Price Comparison", page_icon="🛒", layout="wide")
st.title("🛒 Price Comparison Tool")

# Main content - Search by URL only
st.write("Enter an Amazon product URL to compare prices with Flipkart.")
amazon_url = st.text_input("Amazon Product URL")

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
                    # Removed the price display line
                    st.markdown(f"[View on Amazon]({amazon_url})")
                    if product_details["image_url"]:
                        st.image(product_details["image_url"], width=150)
                
                with col2:
                    st.write("### 🛒 Flipkart")
                    # Removed the price display line
                    st.markdown(f"[View on Flipkart]({flipkart_data['flipkart_link']})")
                    if flipkart_data["flipkart_image"]:
                        st.image(flipkart_data["flipkart_image"], width=150)
                    if flipkart_data.get("match_score", 0) > 5:
                        st.info("✓ High confidence product match")
                
                # Removed the price analysis section
            else:
                st.error(f"Could not process the Amazon URL: {product_details['title']}")
                st.info("Try entering a direct Amazon product URL that includes '/dp/' in the format: https://www.amazon.in/product-name/dp/ASIN")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.info("Please check your internet connection and try again")