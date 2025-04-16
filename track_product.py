import streamlit as st
from fetch_amazon import fetch_amazon_product
from fetch_flipkart import fetch_flipkart_product

st.title("🔍 Track a New Product")

# Step 1: Get product info from user
product_description = st.text_input("Enter Product Description", key="product_desc")
user_email = st.text_input("Enter your email", key="email")
threshold_price = st.number_input(
    "Set your price threshold (₹)", 
    min_value=0.0, 
    step=1.0, 
    format="%.2f",
    key="price_threshold"
)

if st.button("Track Product", type="primary"):
    if not product_description or not user_email or threshold_price <= 0:
        st.warning("Please enter all fields correctly.")
    else:
        with st.spinner("Fetching product info..."):
            try:
                amazon_result = fetch_amazon_product(product_description)
                flipkart_result = fetch_flipkart_product(product_description)

                if amazon_result or flipkart_result:
                    st.success("Product fetched successfully!")

                    if amazon_result:
                        st.subheader("📦 Amazon")
                        st.write(f"**Title**: {amazon_result['title']}")
                        st.write(f"**Price**: ₹{amazon_result['price']}")
                        st.image(amazon_result['image'])

                    if flipkart_result:
                        st.subheader("🛒 Flipkart")
                        st.write(f"**Title**: {flipkart_result['title']}")
                        st.write(f"**Price**: ₹{flipkart_result['price']}")
                        st.image(flipkart_result['image'])

                else:
                    st.error("❌ Could not fetch product.")

            except Exception as e:
                st.error(f"⚠️ Error: {str(e)}")
