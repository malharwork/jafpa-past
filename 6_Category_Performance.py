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
    page_title="Category Performance Analysis",
    page_icon="📊",
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

def get_category_insight(category_data):
    """Get AI-powered category insights."""
    prompt = f"""
    Analyze this category data and provide strategic recommendations:
    {category_data}
    
    Provide 3-4 specific, actionable recommendations for:
    1. Pricing strategy and optimization
    2. Product mix and portfolio management
    3. Competitive positioning and market opportunities
    4. Growth potential and areas of improvement
    
    Focus on business impact and practical implementation.
    Consider both weight-based and piece-based pricing where applicable.
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
st.title("📊 Category Performance Analysis")
st.write("Analyze category-wise performance, pricing strategies, and competitive positioning")

try:
    japfa_data, licious_data, matched_df = load_data()
    
    # Prepare category data
    category_data = {}
    for product in japfa_data:
        category = product.get('category_name', 'Unknown')
        price = extract_price(product.get('discounted_price', '0'))
        weight_str = product.get('weight', '')
        
        if category not in category_data:
            category_data[category] = {
                'count': 0,
                'total_price': 0,
                'prices': [],
                'weights': [],
                'price_per_100g': [],
                'price_per_piece': [],
                'products': []
            }
        
        if price:
            price_per_100g, price_per_piece = normalize_price(price, weight_str)
            category_data[category]['count'] += 1
            category_data[category]['total_price'] += price
            category_data[category]['prices'].append(price)
            category_data[category]['weights'].append(weight_str)
            if price_per_100g:
                category_data[category]['price_per_100g'].append(price_per_100g)
            if price_per_piece:
                category_data[category]['price_per_piece'].append(price_per_piece)
            category_data[category]['products'].append(product)
    
    # Calculate metrics
    category_metrics = []
    for category, data in category_data.items():
        if data['count'] > 0:
            avg_price = data['total_price'] / data['count']
            price_range = max(data['prices']) - min(data['prices'])
            avg_price_100g = np.mean(data['price_per_100g']) if data['price_per_100g'] else None
            avg_price_piece = np.mean(data['price_per_piece']) if data['price_per_piece'] else None
            
            category_metrics.append({
                'Category': category,
                'Product Count': data['count'],
                'Average Price': avg_price,
                'Price Range': price_range,
                'Avg Price/100g': avg_price_100g,
                'Avg Price/Piece': avg_price_piece
            })
    
    df_categories = pd.DataFrame(category_metrics)
    
    # Category Overview
    st.header("Category Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    total_products = sum(df_categories['Product Count'])
    avg_category_size = np.mean(df_categories['Product Count'])
    avg_price_overall = np.mean(df_categories['Average Price'])
    
    col1.metric("Total Categories", len(df_categories))
    col2.metric("Total Products", total_products)
    col3.metric("Avg Category Size", f"{avg_category_size:.1f}")
    col4.metric("Avg Price", f"₹{avg_price_overall:.2f}")
    
    # Category Distribution
    st.subheader("Category Distribution Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        # Product Count by Category
        fig = px.bar(
            df_categories,
            x='Category',
            y='Product Count',
            title='Product Distribution by Category',
            color='Average Price',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Average Price by Category
        fig = px.bar(
            df_categories,
            x='Category',
            y='Average Price',
            title='Average Price by Category',
            color='Price Range',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Category Deep Dive
    st.header("Category Deep Dive")
    selected_category = st.selectbox("Select Category for Analysis", df_categories['Category'].unique())
    
    if selected_category:
        cat_data = category_data[selected_category]
        
        # Category metrics
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "Products in Category",
            cat_data['count'],
            f"{(cat_data['count']/total_products)*100:.1f}% of portfolio"
        )
        
        col2.metric(
            "Average Price",
            f"₹{np.mean(cat_data['prices']):.2f}",
            f"Range: ₹{min(cat_data['prices'])} - ₹{max(cat_data['prices'])}"
        )
        
        if cat_data['price_per_100g']:
            col3.metric(
                "Avg Price/100g",
                f"₹{np.mean(cat_data['price_per_100g']):.2f}",
                f"Range: ₹{min(cat_data['price_per_100g']):.2f} - ₹{max(cat_data['price_per_100g']):.2f}"
            )
        
        if cat_data['price_per_piece']:
            col4.metric(
                "Avg Price/Piece",
                f"₹{np.mean(cat_data['price_per_piece']):.2f}",
                f"Range: ₹{min(cat_data['price_per_piece']):.2f} - ₹{max(cat_data['price_per_piece']):.2f}"
            )
        
        # Price Distribution
        st.subheader("Price Distribution")
        col1, col2 = st.columns(2)
        
        with col1:
            # Price distribution histogram
            fig = px.histogram(
                cat_data['prices'],
                title=f'Price Distribution: {selected_category}',
                nbins=20,
                color_discrete_sequence=[COLORS['primary']]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if cat_data['price_per_100g']:
                # Price per 100g distribution
                fig = px.histogram(
                    cat_data['price_per_100g'],
                    title=f'Price per 100g Distribution: {selected_category}',
                    nbins=20,
                    color_discrete_sequence=[COLORS['secondary']]
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Product List
        st.subheader("Products in Category")
        for product in cat_data['products']:
            with st.expander(f"📦 {product['title']}"):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if product.get('image_url'):
                        st.image(product['image_url'], width=200)
                
                with col2:
                    st.write(f"**Regular Price:** ₹{product.get('regular_price', 'N/A')}")
                    st.write(f"**Discounted Price:** ₹{product.get('discounted_price', 'N/A')}")
                    st.write(f"**Weight/Quantity:** {product.get('weight', 'N/A')}")
                    
                    price = extract_price(product.get('discounted_price', '0'))
                    if price:
                        price_per_100g, price_per_piece = normalize_price(price, product.get('weight', ''))
                        if price_per_100g:
                            st.write(f"**Price per 100g:** ₹{price_per_100g:.2f}")
                        if price_per_piece:
                            st.write(f"**Price per Piece:** ₹{price_per_piece:.2f}")
                    
                    st.write(f"**Description:** {product.get('description', 'N/A')}")
        
        # AI Insights
        st.subheader("💡 Strategic Insights")
        category_info = {
            'category': selected_category,
            'product_count': cat_data['count'],
            'avg_price': np.mean(cat_data['prices']),
            'price_range': f"₹{min(cat_data['prices'])}-₹{max(cat_data['prices'])}",
            'avg_price_per_100g': np.mean(cat_data['price_per_100g']) if cat_data['price_per_100g'] else None,
            'avg_price_per_piece': np.mean(cat_data['price_per_piece']) if cat_data['price_per_piece'] else None
        }
        insight = get_category_insight(category_info)
        st.write(insight)

except Exception as e:
    st.error(f"Error loading or processing data: {str(e)}")
    st.write("Please check if all required data files are present and properly formatted.") 