import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from config import GEMINI_API_KEY
import requests
import re

# Gemini API Configuration
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
HEADERS = {
    "Content-Type": "application/json"
}

# Page config
st.set_page_config(
    page_title="Product Recommendations",
    page_icon="🎯",
    layout="wide"
)

# Custom color scheme
COLORS = {
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'success': '#2ca02c',
    'danger': '#d62728',
    'background': '#f0f2f6'
}

# ========== UTILITIES ========== #
def extract_price(price_str):
    """Extracts the first numeric value from a price string."""
    if not isinstance(price_str, str):
        return None
    price_str = price_str.replace(',', '').strip()
    numbers = re.findall(r'\d+', price_str)
    return int(numbers[0]) if numbers else None

def extract_weight_info(weight_str):
    """Extract weight in grams and piece count from weight string."""
    if not isinstance(weight_str, str):
        return None, None
    
    weight_grams = None
    piece_count = None
    
    # Extract grams
    gram_match = re.search(r'(\d+)\s*g', weight_str.lower())
    if gram_match:
        weight_grams = int(gram_match.group(1))
    
    # Extract piece count (take average if range is given)
    piece_match = re.search(r'(\d+)[-\s]*(\d+)?\s*(?:pcs|pieces)', weight_str.lower())
    if piece_match:
        if piece_match.group(2):  # Range given
            piece_count = (int(piece_match.group(1)) + int(piece_match.group(2))) / 2
        else:
            piece_count = int(piece_match.group(1))
    
    return weight_grams, piece_count

def normalize_price(price, weight_str):
    """Calculate price per 100g and price per piece if applicable."""
    if not price:
        return None, None
    
    weight_grams, piece_count = extract_weight_info(weight_str)
    
    price_per_100g = None
    price_per_piece = None
    
    if weight_grams:
        price_per_100g = (price / weight_grams) * 100
    
    if piece_count:
        price_per_piece = price / piece_count
    
    return price_per_100g, price_per_piece

def call_gemini_api(prompt: str) -> str:
    """Make a call to Gemini API"""
    try:
        payload = {
            "contents": [{
                "parts":[{"text": prompt}]
            }]
        }
        
        response = requests.post(GEMINI_API_URL, headers=HEADERS, json=payload)
        
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            st.warning(f"API Error: {response.status_code}")
            return "Unable to generate insight at the moment."
            
    except Exception as e:
        st.error(f"Error calling Gemini API: {str(e)}")
        return "Error generating insight."

def get_price_insight(japfa_price, licious_price, product_name, japfa_weight, licious_weight):
    """Get AI-powered pricing insights."""
    prompt = f"""
    Analyze the pricing strategy for this product:
    Product: {product_name}
    
    Price Comparison:
    - Japfa: ₹{japfa_price} ({japfa_weight})
    - Licious: ₹{licious_price} ({licious_weight})
    
    Provide a concise, business-focused recommendation in 2-3 sentences about:
    1. Whether the price positioning is optimal
    2. Specific pricing strategy recommendation
    3. Potential market opportunity or risk
    Focus on actionable insights and market positioning.
    """
    return call_gemini_api(prompt)

# Load Data
@st.cache_data
def load_data():
    with open('japfa_past/japfa_pune_2025_04_14_17_49_23.json', 'r') as f:
        japfa = json.load(f)
    with open('licious_past/licious_pune_2025_04_14_17_09_46.json', 'r') as f:
        licious = json.load(f)
    matched = pd.read_csv('matched_products_weighted.csv')
    return japfa, licious, matched

# Main
st.title("🎯 Product Strategy Recommendations")
st.write("Analyze pricing opportunities and get AI-powered recommendations for product strategy")

try:
    japfa_data, licious_data, matched_df = load_data()
    
    # Prepare recommendation data
    product_recommendations = []
    
    # Products where Japfa is significantly cheaper/expensive based on normalized prices
    cheaper_products_100g = []
    expensive_products_100g = []
    cheaper_products_piece = []
    expensive_products_piece = []
    
    for _, row in matched_df.iterrows():
        japfa_prod = next((item for item in japfa_data if item["product_id"] == row["japfa_product_id"]), None)
        licious_prod = next((item for item in licious_data if row["matched_licious_title_rank_1"].lower() in item["title"].lower()), None)
        
        if japfa_prod and licious_prod:
            jp_price = extract_price(japfa_prod.get("discounted_price", ""))
            lc_price = extract_price(licious_prod.get("discounted_price", ""))
            
            if jp_price and lc_price:
                # Calculate normalized prices
                jp_100g, jp_piece = normalize_price(jp_price, japfa_prod.get('weight', ''))
                lc_100g, lc_piece = normalize_price(lc_price, licious_prod.get('weight', ''))
                
                product_data = {
                    'Product': japfa_prod['title'],
                    'Category': japfa_prod.get('category_name', 'Unknown'),
                    'Japfa Price': jp_price,
                    'Licious Price': lc_price,
                    'Japfa Weight': japfa_prod.get('weight', ''),
                    'Licious Weight': licious_prod.get('weight', ''),
                    'Image': japfa_prod.get('image_url', ''),
                    'Description': japfa_prod.get('description', '')
                }
                
                # Compare price per 100g
                if jp_100g is not None and lc_100g is not None:
                    diff_100g = ((jp_100g - lc_100g) / lc_100g) * 100
                    product_data.update({
                        'Price/100g Diff %': diff_100g,
                        'Japfa Price/100g': jp_100g,
                        'Licious Price/100g': lc_100g
                    })
                    
                    if diff_100g < -10:  # Japfa is cheaper by more than 10%
                        cheaper_products_100g.append(product_data)
                    elif diff_100g > 10:  # Japfa is more expensive by more than 10%
                        expensive_products_100g.append(product_data)
                
                # Compare price per piece
                if jp_piece is not None and lc_piece is not None:
                    diff_piece = ((jp_piece - lc_piece) / lc_piece) * 100
                    product_data.update({
                        'Price/Piece Diff %': diff_piece,
                        'Japfa Price/Piece': jp_piece,
                        'Licious Price/Piece': lc_piece
                    })
                    
                    if diff_piece < -10:  # Japfa is cheaper by more than 10%
                        cheaper_products_piece.append(product_data)
                    elif diff_piece > 10:  # Japfa is more expensive by more than 10%
                        expensive_products_piece.append(product_data)
    
    # Display recommendations with tabs for different metrics
    tab1, tab2 = st.tabs(["Analysis by Weight (per 100g)", "Analysis by Piece"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔥 Premium Pricing Opportunities (by Weight)")
            if cheaper_products_100g:
                for product in sorted(cheaper_products_100g, key=lambda x: x['Price/100g Diff %'])[:5]:
                    with st.expander(f"💡 {product['Product']}"):
                        if product['Image']:
                            st.image(product['Image'], width=200)
                        st.write(f"**Category:** {product['Category']}")
                        st.write(f"**Current Price/100g:** ₹{product['Japfa Price/100g']:.2f}")
                        st.write(f"**Competitor Price/100g:** ₹{product['Licious Price/100g']:.2f}")
                        st.write(f"**Price Difference:** {product['Price/100g Diff %']:.1f}%")
                        st.write(f"**Weight Info:** {product['Japfa Weight']}")
                        
                        # Get AI recommendation
                        insight = get_price_insight(
                            product['Japfa Price'],
                            product['Licious Price'],
                            product['Product'],
                            product['Japfa Weight'],
                            product['Licious Weight']
                        )
                        st.write("**Strategic Recommendation:**")
                        st.write(insight)
        
        with col2:
            st.subheader("⚠️ Price Adjustment Needed (by Weight)")
            if expensive_products_100g:
                for product in sorted(expensive_products_100g, key=lambda x: -x['Price/100g Diff %'])[:5]:
                    with st.expander(f"⚠️ {product['Product']}"):
                        if product['Image']:
                            st.image(product['Image'], width=200)
                        st.write(f"**Category:** {product['Category']}")
                        st.write(f"**Current Price/100g:** ₹{product['Japfa Price/100g']:.2f}")
                        st.write(f"**Competitor Price/100g:** ₹{product['Licious Price/100g']:.2f}")
                        st.write(f"**Price Difference:** +{product['Price/100g Diff %']:.1f}%")
                        st.write(f"**Weight Info:** {product['Japfa Weight']}")
                        
                        # Get AI recommendation
                        insight = get_price_insight(
                            product['Japfa Price'],
                            product['Licious Price'],
                            product['Product'],
                            product['Japfa Weight'],
                            product['Licious Weight']
                        )
                        st.write("**Strategic Recommendation:**")
                        st.write(insight)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔥 Premium Pricing Opportunities (by Piece)")
            if cheaper_products_piece:
                for product in sorted(cheaper_products_piece, key=lambda x: x['Price/Piece Diff %'])[:5]:
                    with st.expander(f"💡 {product['Product']}"):
                        if product['Image']:
                            st.image(product['Image'], width=200)
                        st.write(f"**Category:** {product['Category']}")
                        st.write(f"**Current Price/Piece:** ₹{product['Japfa Price/Piece']:.2f}")
                        st.write(f"**Competitor Price/Piece:** ₹{product['Licious Price/Piece']:.2f}")
                        st.write(f"**Price Difference:** {product['Price/Piece Diff %']:.1f}%")
                        st.write(f"**Weight Info:** {product['Japfa Weight']}")
                        
                        # Get AI recommendation
                        insight = get_price_insight(
                            product['Japfa Price'],
                            product['Licious Price'],
                            product['Product'],
                            product['Japfa Weight'],
                            product['Licious Weight']
                        )
                        st.write("**Strategic Recommendation:**")
                        st.write(insight)
        
        with col2:
            st.subheader("⚠️ Price Adjustment Needed (by Piece)")
            if expensive_products_piece:
                for product in sorted(expensive_products_piece, key=lambda x: -x['Price/Piece Diff %'])[:5]:
                    with st.expander(f"⚠️ {product['Product']}"):
                        if product['Image']:
                            st.image(product['Image'], width=200)
                        st.write(f"**Category:** {product['Category']}")
                        st.write(f"**Current Price/Piece:** ₹{product['Japfa Price/Piece']:.2f}")
                        st.write(f"**Competitor Price/Piece:** ₹{product['Licious Price/Piece']:.2f}")
                        st.write(f"**Price Difference:** +{product['Price/Piece Diff %']:.1f}%")
                        st.write(f"**Weight Info:** {product['Japfa Weight']}")
                        
                        # Get AI recommendation
                        insight = get_price_insight(
                            product['Japfa Price'],
                            product['Licious Price'],
                            product['Product'],
                            product['Japfa Weight'],
                            product['Licious Weight']
                        )
                        st.write("**Strategic Recommendation:**")
                        st.write(insight)
    
    # Summary metrics
    st.markdown("---")
    st.subheader("📊 Pricing Strategy Overview")
    
    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
    
    with metrics_col1:
        st.metric(
            "Products Cheaper by Weight",
            f"{len(cheaper_products_100g)} items",
            "Opportunity for premium pricing"
        )
    
    with metrics_col2:
        st.metric(
            "Products Expensive by Weight",
            f"{len(expensive_products_100g)} items",
            "Need price adjustment"
        )
    
    with metrics_col3:
        st.metric(
            "Products Cheaper by Piece",
            f"{len(cheaper_products_piece)} items",
            "Opportunity for premium pricing"
        )
    
    with metrics_col4:
        st.metric(
            "Products Expensive by Piece",
            f"{len(expensive_products_piece)} items",
            "Need price adjustment"
        )

except Exception as e:
    st.error(f"Error loading or processing data: {str(e)}")
    st.write("Please check if all required data files are present and properly formatted.") 