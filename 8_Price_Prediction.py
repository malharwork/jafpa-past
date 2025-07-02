import streamlit as st
import json
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import re

# Set page config
st.set_page_config(
    page_title="Price Prediction - Japfa-Licious Analysis",
    page_icon="📊",
    layout="wide"
)

# Add custom CSS
st.markdown("""
    <style>
    .prediction-card {
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        background-color: white;
    }
    .optimal-price {
        color: #28a745;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #e8f5e9;
        border-radius: 4px;
        display: inline-block;
    }
    .current-price {
        color: #1976d2;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #e3f2fd;
        border-radius: 4px;
        display: inline-block;
    }
    .competitor-price {
        color: #ff5722;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #fff3e0;
        border-radius: 4px;
        display: inline-block;
    }
    .increase-action {
        color: #28a745;
        font-weight: 600;
    }
    .decrease-action {
        color: #dc3545;
        font-weight: 600;
    }
    .maintain-action {
        color: #1976d2;
        font-weight: 600;
    }
    .settings-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Load data
@st.cache_data
def load_data():
    # Load product matches
    with open('product_matches_not_unique.json', 'r') as f:
        matches_data = json.load(f)
    
    # Load Japfa products - using the specific file mentioned
    with open('./japfa_past/japfa_pune_2025_04_24_11_21_49.json', 'r') as f:
        japfa_data = json.load(f)
    
    # Load Licious products - using the specific file mentioned
    with open('./licious_past/licious_pune_2025_04_24_11_54_22.json', 'r') as f:
        licious_data = json.load(f)
    
    # Create lookup dictionaries for easy access
    japfa_dict = {item['japfa_id']: item for item in japfa_data}
    licious_dict = {item['licious_id']: item for item in licious_data}
    
    return matches_data, japfa_data, licious_data, japfa_dict, licious_dict

def extract_price(price_str):
    """Convert price string (₹299) to float (299.0)"""
    if not price_str or not isinstance(price_str, str):
        return 0.0
    return float(price_str.replace('₹', '').strip())

def extract_weight_and_pieces(text):
    """Extract weight in grams and number of pieces from product text"""
    if not text:
        return None, None
    
    # Handle Japfa format: "Net: 450g • 10-16 pcs"
    japfa_pattern = r'Net:\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)(?:\s*•\s*(\d+)(?:-\d+)?\s*pcs)?'
    match = re.search(japfa_pattern, text)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        pieces = match.group(3)
        if pieces:
            pieces = int(pieces.split('-')[0])  # Take the lower number if range
        if 'kg' in unit:
            value *= 1000
        return value, pieces
    
    # Handle Licious format: "200 g" or "4 Pieces" or "1 unit"
    licious_weight_pattern = r'(\d+(?:\.\d+)?)\s*([gk](?:rams?)?)'
    licious_pieces_pattern = r'(\d+)\s*(?:Pieces?|units?)'
    
    match = re.search(licious_weight_pattern, text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        if 'k' in unit:
            value *= 1000
        return value, None
    
    match = re.search(licious_pieces_pattern, text, re.IGNORECASE)
    if match:
        return None, int(match.group(1))
    
    # Handle simple piece counts: "5 pcs"
    pieces_pattern = r'(\d+)\s*pcs'
    match = re.search(pieces_pattern, text)
    if match:
        return None, int(match.group(1))
    
    return None, None

def calculate_price_per_gram(price, weight_grams):
    """Calculate price per gram"""
    if not weight_grams:
        return None
    return price / weight_grams

def calculate_price_per_piece(price, pieces):
    """Calculate price per piece"""
    if not pieces:
        return None
    return price / pieces

def calculate_normalized_price(price, weight_grams, pieces):
    """Calculate price normalized to standard quantity (500g or 6 pieces)"""
    result = {}
    
    if weight_grams:
        # Calculate price per 500g
        price_per_500g = (price / weight_grams) * 500
        result['per_500g'] = price_per_500g
    
    if pieces:
        # Calculate price per 6 pieces
        price_per_6pc = (price / pieces) * 6
        result['per_6pc'] = price_per_6pc
    
    return result

def predict_optimal_price(japfa_product, licious_product, margin_factor=0.95):
    """
    Predict optimal price for Japfa product based on competitive analysis with Licious
    
    Parameters:
    - japfa_product: Dict containing Japfa product info
    - licious_product: Dict containing matching Licious product
    - margin_factor: Target price as a percentage of competitor price (e.g., 0.95 = 5% cheaper)
    
    Returns:
    - Dict with optimal price and recommendation
    """
    if not licious_product:
        return {
            "optimal_price": None,
            "recommendation": "No competitor data available",
            "action": "maintain"
        }
    
    # Extract Japfa pricing info
    japfa_regular_price = extract_price(japfa_product.get('regular_price', '0'))
    japfa_discounted_price = extract_price(japfa_product.get('discounted_price', '0'))
    japfa_weight, japfa_pieces = extract_weight_and_pieces(japfa_product.get('weight', ''))
    
    # Only proceed if we have valid pricing information
    if not japfa_regular_price:
        return {
            "optimal_price": None,
            "recommendation": "Missing Japfa pricing information",
            "action": "maintain"
        }
    
    # Extract Licious pricing info
    licious_price = extract_price(licious_product.get('discounted_price', licious_product.get('regular_price', '0')))
    licious_weight, licious_pieces = extract_weight_and_pieces(licious_product.get('weight', ''))
    
    if not licious_price:
        return {
            "optimal_price": None,
            "recommendation": "Missing Licious pricing information",
            "action": "maintain"
        }
    
    # Calculate normalized prices
    japfa_normalized = calculate_normalized_price(japfa_discounted_price, japfa_weight, japfa_pieces)
    licious_normalized = calculate_normalized_price(licious_price, licious_weight, licious_pieces)
    
    # Determine which normalization to use (weight or pieces)
    if 'per_500g' in japfa_normalized and 'per_500g' in licious_normalized:
        # Use weight-based normalization
        japfa_normalized_price = japfa_normalized['per_500g']
        licious_normalized_price = licious_normalized['per_500g']
        normalization_type = "weight"
        normalization_unit = "500g"
    elif 'per_6pc' in japfa_normalized and 'per_6pc' in licious_normalized:
        # Use piece-based normalization
        japfa_normalized_price = japfa_normalized['per_6pc']
        licious_normalized_price = licious_normalized['per_6pc']
        normalization_type = "pieces"
        normalization_unit = "6 pieces"
    else:
        # If normalization not possible, use raw prices (less accurate)
        japfa_normalized_price = japfa_discounted_price
        licious_normalized_price = licious_price
        normalization_type = "none"
        normalization_unit = "unit"
    
    # Calculate optimal normalized price
    optimal_normalized_price = licious_normalized_price * margin_factor
    
    # Calculate scaling factor to go from normalized price back to actual price
    if normalization_type == "weight" and japfa_weight:
        scaling_factor = japfa_weight / 500
    elif normalization_type == "pieces" and japfa_pieces:
        scaling_factor = japfa_pieces / 6
    else:
        scaling_factor = 1
    
    # Calculate optimal absolute price (for the actual product weight/pieces)
    optimal_price = optimal_normalized_price * scaling_factor
    
    # Determine if we should increase, decrease or maintain price
    current_discount_percent = ((japfa_regular_price - japfa_discounted_price) / japfa_regular_price) * 100
    
    if japfa_discounted_price < optimal_price * 0.95:  # More than 5% cheaper than optimal
        new_price = min(japfa_regular_price, optimal_price)
        new_discount_percent = ((japfa_regular_price - new_price) / japfa_regular_price) * 100
        action = "increase"
        recommendation = f"Increase price to ₹{new_price:.2f} (decrease discount from {current_discount_percent:.1f}% to {new_discount_percent:.1f}%)"
    elif japfa_discounted_price > optimal_price * 1.05:  # More than 5% expensive than optimal
        new_price = max(optimal_price, japfa_regular_price * 0.5)  # Don't discount more than 50%
        new_discount_percent = ((japfa_regular_price - new_price) / japfa_regular_price) * 100
        action = "decrease"
        recommendation = f"Decrease price to ₹{new_price:.2f} (increase discount from {current_discount_percent:.1f}% to {new_discount_percent:.1f}%)"
    else:
        action = "maintain"
        recommendation = f"Maintain current price (within 5% of optimal price)"
    
    # Prepare detailed info about normalization
    normalization_info = ""
    if normalization_type != "none":
        normalization_info = f"Based on normalized price per {normalization_unit}: Japfa ₹{japfa_normalized_price:.2f} vs Licious ₹{licious_normalized_price:.2f}"
    
    return {
        "optimal_price": optimal_price,
        "current_price": japfa_discounted_price,
        "competitor_price": licious_price,
        "normalized_japfa_price": japfa_normalized_price if normalization_type != "none" else None,
        "normalized_licious_price": licious_normalized_price if normalization_type != "none" else None,
        "normalization_type": normalization_type,
        "normalization_unit": normalization_unit,
        "normalization_info": normalization_info,
        "recommendation": recommendation,
        "action": action,
        "new_price": locals().get('new_price', japfa_discounted_price)
    }

def main():
    st.title("📊 Price Prediction & Discount Optimization")
    
    st.markdown("""
    This tool analyzes Japfa product prices in comparison to Licious competitors to help optimize pricing strategy.
    Prices are normalized to:
    - **500g** for weight-based products
    - **6 pieces** for piece-based products
    
    Set your pricing strategy parameters and see recommendations for each product.
    """)
    
    try:
        # Load data
        matches_data, japfa_data, licious_data, japfa_dict, licious_dict = load_data()
        
        # Sidebar settings
        st.sidebar.header("Pricing Strategy Settings")
        
        margin_factor = st.sidebar.slider(
            "Price Target (% of competitor price)",
            min_value=80,
            max_value=120,
            value=95,
            help="Set target price as a percentage of the competitor's price. 95% means your price should be 5% lower than competitors."
        ) / 100
        
        min_confidence = st.sidebar.slider(
            "Minimum Match Confidence",
            min_value=50,
            max_value=100,
            value=70,
            help="Only consider matches with confidence level above this threshold."
        )
        
        show_all_products = st.sidebar.checkbox(
            "Show all products",
            value=False,
            help="If unchecked, only shows products with actionable recommendations."
        )
        
        # Filter categories
        all_categories = sorted(set(item['category_name'] for item in japfa_data))
        selected_categories = st.sidebar.multiselect(
            "Filter by Categories",
            options=all_categories,
            default=[],
            help="Select categories to analyze."
        )
        
        # Show data file info
        st.sidebar.header("Data Source")
        st.sidebar.info("""
        Using data from:
        - Japfa: `japfa_pune_2025_04_24_11_21_49.json`
        - Licious: `licious_pune_2025_04_24_11_54_22.json`
        """)
        
        # Progress
        progress_bar = st.progress(0)
        
        # Settings section
        st.header("Analysis Settings")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Target Price", f"{margin_factor*100:.0f}% of competitor")
        with col2:
            st.metric("Min Confidence", f"{min_confidence}%")
        with col3:
            total_products = len(matches_data["weighted_matches"])
            st.metric("Total Products", total_products)
        
        # Process the data
        results = []
        
        for i, (product_id, product_data) in enumerate(matches_data["weighted_matches"].items()):
            # Update progress
            progress_bar.progress((i + 1) / total_products)
            
            # Get Japfa product
            japfa_product = japfa_dict.get(product_id)
            if not japfa_product:
                continue
                
            # Filter by category if specified
            if selected_categories and japfa_product["category_name"] not in selected_categories:
                continue
            
            # Get first matching Licious product with confidence above threshold
            first_match = None
            for match in product_data["matches"]:
                confidence = float(match["confidence"].strip("%"))
                
                if confidence >= min_confidence:
                    licious_id = match["licious_id"]
                    licious_product = licious_dict.get(licious_id)
                    if licious_product:
                        licious_product["match_confidence"] = confidence
                        first_match = licious_product
                        break
            
            # Skip if no match found
            if not first_match:
                continue
            
            # Predict optimal price based on the first match only
            prediction = predict_optimal_price(
                japfa_product, 
                first_match,
                margin_factor=margin_factor
            )
            
            # Skip products without actionable recommendations if show_all_products is False
            if not show_all_products and prediction["action"] == "maintain":
                continue
                
            # Add to results
            results.append({
                "japfa_product": japfa_product,
                "matching_product": first_match,
                "prediction": prediction
            })
        
        # Hide progress bar after processing
        progress_bar.empty()
        
        # Display results
        if results:
            # Create tabs for different views
            tab1, tab2 = st.tabs(["Product List", "Summary Dashboard"])
            
            with tab1:
                # Product List View
                for result in results:
                    japfa_product = result["japfa_product"]
                    licious_product = result["matching_product"]
                    prediction = result["prediction"]
                    
                    # Create a card for each product
                    with st.expander(f"{japfa_product['title']} ({japfa_product.get('category_name', 'Uncategorized')})"):
                        product_col1, product_col2 = st.columns([1, 2])
                        
                        with product_col1:
                            st.image(
                                japfa_product["image_url"],
                                width=200,
                                caption=japfa_product["title"]
                            )
                            st.markdown(f"**Category:** {japfa_product.get('category_name', 'N/A')}")
                            st.markdown(f"**Weight/Pieces:** {japfa_product.get('weight', 'N/A')}")
                            
                            # Match info
                            st.subheader("Matched With")
                            st.markdown(f"**{licious_product['title']}**")
                            st.markdown(f"Match Confidence: {licious_product['match_confidence']}%")
                            st.markdown(f"Weight: {licious_product.get('weight', 'N/A')}")
                        
                        with product_col2:
                            # Price information
                            st.subheader("Price Information")
                            
                            price_col1, price_col2 = st.columns(2)
                            
                            with price_col1:
                                st.markdown("### Japfa")
                                st.markdown(f"**Regular Price:** {japfa_product.get('regular_price', 'N/A')}")
                                st.markdown(f"**Discounted Price:** {japfa_product.get('discounted_price', 'N/A')}")
                                st.markdown(f"**Discount:** {japfa_product.get('discount', 'N/A')}")
                            
                            with price_col2:
                                st.markdown("### Licious")
                                st.markdown(f"**Regular Price:** {licious_product.get('regular_price', 'N/A')}")
                                st.markdown(f"**Discounted Price:** {licious_product.get('discounted_price', 'N/A')}")
                                if licious_product.get('discounted_price') != licious_product.get('regular_price'):
                                    discount = extract_price(licious_product.get('regular_price', '0')) - extract_price(licious_product.get('discounted_price', '0'))
                                    st.markdown(f"**Discount:** ₹{discount:.2f}")
                            
                            # Normalized price comparison (if available)
                            if prediction["normalization_type"] != "none":
                                st.subheader("Normalized Price Comparison")
                                norm_col1, norm_col2 = st.columns(2)
                                
                                with norm_col1:
                                    st.markdown(f"**Normalized Unit:** {prediction['normalization_unit']}")
                                
                                with norm_col2:
                                    jp_norm = prediction["normalized_japfa_price"]
                                    lic_norm = prediction["normalized_licious_price"]
                                    diff_pct = ((jp_norm - lic_norm) / lic_norm) * 100
                                    if diff_pct < 0:
                                        status = "cheaper"
                                        color = "price-better"
                                    else:
                                        status = "more expensive"
                                        color = "price-worse"
                                    
                                    st.markdown(f"**Japfa:** ₹{jp_norm:.2f} vs **Licious:** ₹{lic_norm:.2f}")
                                    st.markdown(f"<span class='{color}'>Japfa is {abs(diff_pct):.1f}% {status}</span>", unsafe_allow_html=True)
                            
                            # Prediction section
                            st.subheader("Price Recommendation")
                            
                            if prediction["optimal_price"]:
                                rec_col1, rec_col2, rec_col3 = st.columns(3)
                                
                                with rec_col1:
                                    st.markdown("**Current Price:**")
                                    st.markdown(f"<span class='current-price'>₹{prediction['current_price']:.2f}</span>", unsafe_allow_html=True)
                                
                                with rec_col2:
                                    st.markdown("**Optimal Price:**")
                                    st.markdown(f"<span class='optimal-price'>₹{prediction['optimal_price']:.2f}</span>", unsafe_allow_html=True)
                                
                                with rec_col3:
                                    st.markdown("**Competitor Price:**")
                                    st.markdown(f"<span class='competitor-price'>₹{prediction['competitor_price']:.2f}</span>", unsafe_allow_html=True)
                                
                                # Recommendation
                                action_class = f"{prediction['action']}-action"
                                st.markdown(f"**Recommendation:** <span class='{action_class}'>{prediction['recommendation']}</span>", unsafe_allow_html=True)
                                
                                if prediction["normalization_info"]:
                                    st.info(prediction["normalization_info"])
                            else:
                                st.warning(prediction["recommendation"])
            
            with tab2:
                # Dashboard View
                st.subheader("Pricing Recommendations Summary")
                
                # Prepare dashboard data
                actions_count = {"increase": 0, "decrease": 0, "maintain": 0}
                categories_data = {}
                normalized_differences = []
                
                for result in results:
                    action = result["prediction"]["action"]
                    category = result["japfa_product"].get("category_name", "Unknown")
                    prediction = result["prediction"]
                    
                    # Count actions
                    actions_count[action] += 1
                    
                    # Categorize by product category
                    if category not in categories_data:
                        categories_data[category] = {"increase": 0, "decrease": 0, "maintain": 0}
                    categories_data[category][action] += 1
                    
                    # Collect normalized price differences for visualization
                    if prediction["normalization_type"] != "none":
                        jp_norm = prediction["normalized_japfa_price"]
                        lic_norm = prediction["normalized_licious_price"]
                        diff_pct = ((jp_norm - lic_norm) / lic_norm) * 100
                        normalized_differences.append({
                            "Product": result["japfa_product"]["title"],
                            "Difference": diff_pct,
                            "Category": category,
                            "Unit": prediction["normalization_unit"]
                        })
                
                # Action summary
                action_col1, action_col2, action_col3 = st.columns(3)
                with action_col1:
                    st.metric("Increase Price", actions_count["increase"])
                with action_col2:
                    st.metric("Decrease Price", actions_count["decrease"])
                with action_col3:
                    st.metric("Maintain Price", actions_count["maintain"])
                
                # Action distribution visualization
                fig_actions = px.pie(
                    names=list(actions_count.keys()),
                    values=list(actions_count.values()),
                    title="Price Action Distribution",
                    color=list(actions_count.keys()),
                    color_discrete_map={
                        "increase": "#28a745",
                        "decrease": "#dc3545",
                        "maintain": "#1976d2"
                    }
                )
                st.plotly_chart(fig_actions)
                
                # Price difference visualization (if there's data)
                if normalized_differences:
                    st.subheader("Price Difference from Licious (Normalized)")
                    diff_df = pd.DataFrame(normalized_differences)
                    diff_df = diff_df.sort_values("Difference")
                    
                    fig_diff = px.bar(
                        diff_df,
                        x="Product",
                        y="Difference",
                        color="Category",
                        title="Japfa Price Difference from Licious (%) - Normalized",
                        labels={"Difference": "Price Difference (%)", "Product": "Product", "Category": "Category"},
                        height=500
                    )
                    
                    # Add a horizontal line at 0% (equal prices)
                    fig_diff.add_shape(
                        type="line",
                        x0=-0.5, 
                        y0=0,
                        x1=len(diff_df)-0.5,
                        y1=0,
                        line=dict(color="red", width=2, dash="dash")
                    )
                    
                    # Make x-axis labels vertical for readability
                    fig_diff.update_layout(xaxis_tickangle=-90)
                    
                    st.plotly_chart(fig_diff, use_container_width=True)
                
                # Category distribution
                st.subheader("Recommendations by Category")
                
                # Prepare category data for visualization
                category_data = []
                for category, actions in categories_data.items():
                    for action, count in actions.items():
                        category_data.append({
                            "Category": category,
                            "Action": action.capitalize(),
                            "Count": count
                        })
                
                if category_data:
                    df_category = pd.DataFrame(category_data)
                    fig_category = px.bar(
                        df_category,
                        x="Category",
                        y="Count",
                        color="Action",
                        title="Price Actions by Category",
                        color_discrete_map={
                            "Increase": "#28a745",
                            "Decrease": "#dc3545",
                            "Maintain": "#1976d2"
                        }
                    )
                    st.plotly_chart(fig_category)
        else:
            st.warning("No products match the selected criteria. Try adjusting the filters.")
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Make sure all required data files are present in the directory.")

if __name__ == "__main__":
    main() 