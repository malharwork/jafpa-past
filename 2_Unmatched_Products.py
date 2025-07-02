import streamlit as st
import json
import pandas as pd
import math

# Set page config
st.set_page_config(
    page_title="Unmatched Products - Japfa-Licious Analysis",
    page_icon="🍔",
    layout="wide"
)

# Add custom CSS with a unique identifier
st.markdown("""
    <style>
    div.stMarkdown div.product-card-v2 {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 12px;
        background-color: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
        margin-bottom: 1rem;
        height: 100%;
    }
    
    div.stMarkdown div.product-card-v2:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    div.stMarkdown div.product-card-v2 img.product-image-v2 {
        width: 100%;
        height: 160px !important;
        object-fit: cover;
        border-radius: 6px;
        margin-bottom: 12px;
        display: block;
    }
    
    div.stMarkdown div.product-card-v2 div.product-details-v2 {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    div.stMarkdown div.product-card-v2 div.product-category-v2 {
        font-size: 12px;
        color: #666;
        background-color: #f5f5f5;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 4px;
    }
    
    div.stMarkdown div.product-card-v2 div.product-title-v2 {
        font-size: 14px;
        font-weight: 600;
        color: #1f1f1f;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    div.stMarkdown div.product-card-v2 div.product-description-v2 {
        font-size: 13px;
        color: #666;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    div.stMarkdown div.product-card-v2 div.product-meta-v2 {
        font-size: 12px;
        color: #666;
    }
    
    div.stMarkdown div.product-card-v2 div.product-price-v2 {
        font-size: 16px;
        font-weight: 600;
        color: #2ecc71;
        margin-top: auto;
    }
    
    # .stats-card {
    #     background-color: #f8f9fa;
    #     padding: 1rem;
    #     border-radius: 8px;
    #     margin: 0.5rem 0;
    #     box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    # }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    # Load product matches
    with open('product_matches_not_unique.json', 'r') as f:
        matches_data = json.load(f)
    
    # Load Licious products
    with open('licious_past/licious_pune_2025_04_14_17_09_46.json', 'r') as f:
        licious_data = json.load(f)
    
    return matches_data, licious_data

def get_unmatched_products(matches_data, licious_data, confidence_threshold):
    # Get all matched Licious products above the threshold
    matched_products = set()
    for product_data in matches_data['weighted_matches'].values():
        for match in product_data['matches']:
            if float(match['confidence'].strip('%')) >= confidence_threshold:
                matched_products.add(match['title'])
    
    # Find unmatched products
    unmatched_products = []
    for product in licious_data:
        if product['title'] not in matched_products:
            unmatched_products.append(product)
    
    return unmatched_products

def display_product_card(product):
    category = product.get('category_name', 'Uncategorized')
    weight = product.get('weight', 'N/A')
    description = product.get('description', '')
    mrp = product.get('regular_price', 'N/A')
    final_price = product.get('discounted_price', 'N/A')
    serves = product.get('servings', '')
    
    # Format additional details
    details = []
    if serves:
        details.append(f"{serves}")
    if weight:
        details.append(weight)
    details_text = " • ".join(details) if details else ""
    
    # Create the price display HTML
    price_html = f"₹{final_price}"
    if mrp != 'N/A' and mrp != final_price:
        price_html += f' <span style="text-decoration: line-through; color: #999; font-size: 0.8em; margin-left: 5px;">₹{mrp}</span>'
    
    # Create the card content with updated HTML structure
    card_html = f'''
        <div class="product-card-v2">
            <img src="{product['image_url']}" class="product-image-v2" alt="{product['title']}">
            <div class="product-details-v2">
                <div class="product-category-v2">{category}</div>
                <div class="product-title-v2">{product['title']}</div>
                <div class="product-description-v2">{description}</div>
                <div class="product-meta-v2">{details_text}</div>
                <div class="product-price-v2">{price_html}</div>
            </div>
        </div>
    '''
    
    st.markdown(card_html.strip(), unsafe_allow_html=True)

# Main page content
st.title("🍔 Unmatched Licious Products")

try:
    # Load data
    matches_data, licious_data = load_data()
    
    # Add confidence threshold slider
    confidence_threshold = st.slider(
        "Minimum Confidence Threshold (%)",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
        help="Products with matches below this confidence are considered unmatched"
    )
    
    # Get unmatched products
    unmatched_products = get_unmatched_products(matches_data, licious_data, confidence_threshold)
    
    # Display statistics
    st.markdown("<div class='stats-card'>", unsafe_allow_html=True)
    total_licious = len(licious_data)
    total_unmatched = len(unmatched_products)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Licious Products", total_licious)
    with col2:
        st.metric("Unmatched Products", total_unmatched)
    with col3:
        percentage = (total_unmatched / total_licious) * 100
        st.metric("Percentage Unmatched", f"{percentage:.1f}%")
    
    st.progress(percentage / 100)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Display unmatched products in a grid
    st.subheader(f"Unmatched Products ({total_unmatched})")
    
    # Add filters
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search products by name", "").lower()
    with col2:
        # Get unique categories
        categories = sorted(list(set(p.get('category_name', 'Uncategorized') for p in unmatched_products)))
        selected_category = st.selectbox("Filter by category", ["All Categories"] + categories)
    
    # Filter products based on search and category
    filtered_products = unmatched_products
    if search_term:
        filtered_products = [p for p in filtered_products if search_term in p['title'].lower()]
    if selected_category != "All Categories":
        filtered_products = [p for p in filtered_products if p.get('category_name') == selected_category]
    
    # Show number of filtered products
    if len(filtered_products) != len(unmatched_products):
        st.write(f"Showing {len(filtered_products)} of {len(unmatched_products)} products")
    
    # Create product grid using Streamlit columns
    NUM_COLUMNS = 4  # Number of columns in the grid
    
    # Calculate number of rows needed
    num_products = len(filtered_products)
    num_rows = math.ceil(num_products / NUM_COLUMNS)
    
    # Display products in grid
    for row in range(num_rows):
        cols = st.columns(NUM_COLUMNS)
        for col in range(NUM_COLUMNS):
            idx = row * NUM_COLUMNS + col
            if idx < num_products:
                with cols[col]:
                    display_product_card(filtered_products[idx])
    
except FileNotFoundError as e:
    st.error("Error: Required data files not found. Please ensure all JSON files are present in the directory.")
except Exception as e:
    st.error(f"An error occurred: {str(e)}") 