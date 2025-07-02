import streamlit as st
import json
import pandas as pd
import re
import os
from pathlib import Path
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="Price Comparison - Japfa-Licious Analysis",
    page_icon="💰",
    layout="wide"
)

# Initialize session state variables
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""
if 'last_search' not in st.session_state:
    st.session_state.last_search = ""
if 'selected_product_id' not in st.session_state:
    st.session_state.selected_product_id = None
if 'selected_city' not in st.session_state:
    st.session_state.selected_city = None

# Add custom CSS
st.markdown("""
    <style>
    .price-card {
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        background-color: white;
    }
    .price-comparison {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1976d2;
    }
    .price-better {
        color: #28a745;
    }
    .price-worse {
        color: #dc3545;
    }
    /* Search bar and reset button alignment */
    div[data-testid="column"] {
        padding: 0 !important;
    }
    div[data-testid="stButton"] {
        margin-top: 24px !important;
    }
    .stButton button {
        height: 46px !important;
    }
    /* Fix button width */
    .stButton > button {
        width: 100%;
    }
    .confidence-exact {
        color: #28a745;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #e8f5e9;
        border-radius: 4px;
        display: inline-block;
    }
    .confidence-best {
        color: #1976d2;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #e3f2fd;
        border-radius: 4px;
        display: inline-block;
    }
    .confidence-similar {
        color: #ffa000;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #fff3e0;
        border-radius: 4px;
        display: inline-block;
    }
    </style>
""", unsafe_allow_html=True)

def parse_datetime_from_filename(filename):
    """Extract datetime from filename format like brand_city_YYYY_MM_DD_HH_MM_SS"""
    try:
        # Extract date and time parts from filename
        parts = str(filename).split('_')
        date_time_parts = parts[-6:-1] + [parts[-1].split('.')[0]]  # Handle the last part with .json
        date_str = '_'.join(date_time_parts)
        return datetime.strptime(date_str, '%Y_%m_%d_%H_%M_%S')
    except (IndexError, ValueError):
        return None

def format_datetime(dt):
    """Format datetime in a readable way"""
    if dt:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return "Unknown date"

def get_json_files(directory, brand):
    """Get all JSON files for a specific brand from a directory."""
    path = Path(directory)
    files = []
    for file in path.glob(f"{brand}_*.json"):
        # Extract city from filename - handle hyphenated names
        parts = file.stem.split('_')
        # Find where the date part starts (looking for year)
        date_start_idx = next((i for i, part in enumerate(parts) if part.isdigit() and len(part) == 4), -1)
        if date_start_idx > 1:  # Ensure we have brand and city parts
            city = '_'.join(parts[1:date_start_idx])  # Join city parts if hyphenated
            dt = parse_datetime_from_filename(file.name)
            display_name = f"{format_datetime(dt)}"
            files.append((str(file), city, display_name))
    return files

def get_available_cities(japfa_files, licious_files):
    """Get list of cities that have data for both Japfa and Licious."""
    japfa_cities = set(city for _, city, _ in japfa_files)
    licious_cities = set(city for _, city, _ in licious_files)
    return sorted(japfa_cities.intersection(licious_cities))

def group_files_by_city(files):
    """Group files by city and sort by datetime."""
    grouped = {}
    for file_path, city, display_name in files:
        if city not in grouped:
            grouped[city] = []
        grouped[city].append((file_path, display_name))
    # Sort each city's files by datetime (newest first)
    for city in grouped:
        grouped[city].sort(key=lambda x: parse_datetime_from_filename(x[0]), reverse=True)
    return grouped

# Load the data
@st.cache_data
def load_data(japfa_file, licious_file):
    """Load data from selected files."""
    # Load product matches
    with open('product_matches_not_unique.json', 'r') as f:
        matches_data = json.load(f)
    
    # Load Japfa products
    with open(japfa_file, 'r') as f:
        japfa_data = json.load(f)
    
    # Load Licious products
    with open(licious_file, 'r') as f:
        licious_data = json.load(f)
    
    return matches_data, japfa_data, licious_data

def extract_weight_and_pieces(text):
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

def calculate_normalized_prices(price, weight_grams, pieces):
    result = {}
    
    if weight_grams:
        # Calculate price per 500g
        price_per_500g = (price / weight_grams) * 500
        result['per_500g'] = price_per_500g
    
    if pieces:
        # Calculate price per piece
        price_per_piece = price / pieces
        result['per_piece'] = price_per_piece
    
    return result

def safe_price_to_float(price_str):
    if not price_str or price_str.strip() == '':
        return 0.0
    try:
        # Remove '₹' symbol and any whitespace, then convert to float
        cleaned_price = price_str.replace('₹', '').strip()
        if cleaned_price == '':
            return 0.0
        return float(cleaned_price)
    except (ValueError, AttributeError):
        return 0.0

def get_product_price(product):
    # First try to get the discounted price
    price = safe_price_to_float(product.get('discounted_price', '0'))
    # If discounted price is 0, use the regular price
    if price == 0:
        price = safe_price_to_float(product.get('regular_price', '0'))
    return price

def get_confidence_label_and_class(confidence_str):
    confidence = float(confidence_str.strip('%'))
    if confidence > 95:
        return "Exact Match", "confidence-exact"
    elif confidence >= 90:
        return "Best Match", "confidence-best"
    else:
        return "Similar Product", "confidence-similar"

def main():
    st.title("💰 Product Price Comparison by City")
    st.markdown("""
    Compare prices between Japfa and Licious products by city, normalized by weight/quantity.
    Prices are normalized to:
    - Price per 500g for weight-based products
    - Price per piece/unit for piece-based products
    """)
    
    # Get available files
    japfa_files = get_json_files("japfa_past", "japfa")
    licious_files = get_json_files("licious_past", "licious")
    
    # Group files by city
    japfa_files_by_city = group_files_by_city(japfa_files)
    licious_files_by_city = group_files_by_city(licious_files)
    
    # Get available cities
    available_cities = get_available_cities(japfa_files, licious_files)
    
    if not available_cities:
        st.error("No matching city data found for both Japfa and Licious.")
        return
    
    # City selection
    selected_city = st.selectbox(
        "Select a city to compare prices:",
        available_cities,
        index=0 if available_cities else None,
        key="city_selector"
    )
    
    if selected_city:
        st.session_state.selected_city = selected_city
        
        # File selection columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Japfa Data Selection")
            japfa_city_files = japfa_files_by_city.get(selected_city, [])
            if japfa_city_files:
                selected_japfa_file = st.selectbox(
                    "Select Japfa data file:",
                    japfa_city_files,
                    format_func=lambda x: x[1],  # Use display name
                    key="japfa_file_selector"
                )
                japfa_file = selected_japfa_file[0]
            else:
                st.error(f"No Japfa data files found for {selected_city}")
                return
        
        with col2:
            st.subheader("Licious Data Selection")
            licious_city_files = licious_files_by_city.get(selected_city, [])
            if licious_city_files:
                selected_licious_file = st.selectbox(
                    "Select Licious data file:",
                    licious_city_files,
                    format_func=lambda x: x[1],  # Use display name
                    key="licious_file_selector"
                )
                licious_file = selected_licious_file[0]
            else:
                st.error(f"No Licious data files found for {selected_city}")
                return
        
        # Display selected files
        with st.expander("Selected Data Files"):
            st.write(f"Japfa data: {Path(japfa_file).name}")
            st.write(f"Licious data: {Path(licious_file).name}")
        
        # Load data for selected files
        matches_data, japfa_data, licious_data = load_data(japfa_file, licious_file)
        
        # Create dictionaries for easy lookup
        japfa_dict = {item['title']: item for item in japfa_data}
        licious_dict = {item['title']: item for item in licious_data}
        
        # Add search box for products
        search_col1, search_col2 = st.columns([6, 1])
        
        # Handle reset button
        with search_col2:
            if st.button("Reset", key="price_reset_search", use_container_width=True):
                st.session_state.price_product_search = ""
                st.session_state.search_term = ""
                st.session_state.last_search = ""
                st.session_state.selected_product_id = None
                st.rerun()
        
        # Handle search input
        with search_col1:
            search_term = st.text_input(
                "🔍 Search products",
                key="price_product_search",
                label_visibility="visible"
            ).lower()
        
        # Update session state and handle search
        if search_term != st.session_state.last_search:
            st.session_state.search_term = search_term
            st.session_state.last_search = search_term
            st.session_state.selected_product_id = None
        
        # Create a list of all Japfa products with their titles
        all_japfa_products = []
        for product_id, product_data in matches_data['weighted_matches'].items():
            if isinstance(product_data, dict) and 'japfa_product' in product_data:
                japfa_title = product_data['japfa_product']['title']
                category = product_data['japfa_product'].get('category_name', 'Uncategorized')
                if japfa_title in japfa_dict:
                    display_text = f"{japfa_title} ({category})"
                    all_japfa_products.append((display_text, product_id))
        
        # Filter products based on search term
        if search_term:
            filtered_products = [(display, pid) for display, pid in all_japfa_products 
                               if search_term in display.lower()]
            if filtered_products:
                st.info(f"Found {len(filtered_products)} matching products")
        else:
            filtered_products = all_japfa_products
        
        # Sort products by title for better navigation
        filtered_products.sort(key=lambda x: x[0])
        
        # Product selection
        if filtered_products:
            # Find index of currently selected product
            selected_index = 0
            if st.session_state.selected_product_id:
                try:
                    selected_index = next(i for i, (_, pid) in enumerate(filtered_products) 
                                        if pid == st.session_state.selected_product_id)
                except StopIteration:
                    # If previously selected product is not in filtered results, reset selection
                    st.session_state.selected_product_id = None
                    selected_index = 0
            
            selected_display, selected_id = st.selectbox(
                "Select a Japfa product to compare:",
                filtered_products,
                format_func=lambda x: x[0],  # Use the display text for the dropdown
                index=selected_index
            )
            
            # Update session state when product is selected
            st.session_state.selected_product_id = selected_id
            
            product_data = matches_data['weighted_matches'][selected_id]
            japfa_title = product_data['japfa_product']['title']
            japfa_product = japfa_dict.get(japfa_title)
            
            if japfa_product:
                st.subheader("Japfa Product")
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if japfa_product.get('image_url'):
                        st.image(japfa_product['image_url'], width=200)
                
                with col2:
                    st.write(f"**{japfa_product['title']}**")
                    st.write(f"Category: {japfa_product.get('category_name', 'Uncategorized')}")
                    japfa_price = get_product_price(japfa_product)
                    st.write(f"Original Price: ₹{japfa_product.get('regular_price', '').replace('₹', '')}")
                    st.write(f"Discounted Price: ₹{japfa_price:.2f}")
                    st.write(f"Weight/Quantity: {japfa_product.get('weight', 'N/A')}")
                    
                    # Extract weight and pieces for Japfa product
                    japfa_weight, japfa_pieces = extract_weight_and_pieces(japfa_product.get('weight', ''))
                    japfa_normalized = calculate_normalized_prices(japfa_price, japfa_weight, japfa_pieces)
                    
                    with st.container():
                        st.markdown("<div class='price-details'>", unsafe_allow_html=True)
                        if 'per_500g' in japfa_normalized:
                            st.write(f"Price per 500g: ₹{japfa_normalized['per_500g']:.2f}")
                        if 'per_piece' in japfa_normalized:
                            st.write(f"Price per piece: ₹{japfa_normalized['per_piece']:.2f}")
                        st.markdown("</div>", unsafe_allow_html=True)
                
                st.subheader("Matching Licious Products")
                
                for match in product_data['matches']:
                    licious_title = match['title']
                    licious_product = licious_dict.get(licious_title)
                    if licious_product:
                        with st.container():
                            st.markdown("---")
                            cols = st.columns([1, 2, 1])
                            
                            with cols[0]:
                                if licious_product.get('image_url'):
                                    st.image(licious_product['image_url'], width=200)
                            
                            with cols[1]:
                                st.write(f"**{licious_product['title']}**")
                                st.write(f"Category: {licious_product.get('category_name', 'Uncategorized')}")
                                label, class_name = get_confidence_label_and_class(match['confidence'])
                                st.markdown(f"<span class='{class_name}'>{label}</span>", unsafe_allow_html=True)
                                licious_price = get_product_price(licious_product)
                                st.write(f"Original Price: ₹{licious_product.get('regular_price', '').replace('₹', '')}")
                                st.write(f"Discounted Price: ₹{licious_price:.2f}")
                                st.write(f"Weight/Quantity: {licious_product.get('weight', 'N/A')}")
                                
                                # Extract weight and pieces for Licious product
                                licious_weight, licious_pieces = extract_weight_and_pieces(licious_product.get('weight', ''))
                                licious_normalized = calculate_normalized_prices(licious_price, licious_weight, licious_pieces)
                                
                                with st.container():
                                    st.markdown("<div class='price-details'>", unsafe_allow_html=True)
                                    if 'per_500g' in licious_normalized:
                                        st.write(f"Price per 500g: ₹{licious_normalized['per_500g']:.2f}")
                                    if 'per_piece' in licious_normalized:
                                        st.write(f"Price per piece: ₹{licious_normalized['per_piece']:.2f}")
                                    st.markdown("</div>", unsafe_allow_html=True)
                            
                            with cols[2]:
                                comparison_made = False
                                price_diff_percent = None  # Initialize price_diff_percent as None
                                
                                # Check if products have different measurement types
                                japfa_has_weight = 'per_500g' in japfa_normalized
                                japfa_has_pieces = 'per_piece' in japfa_normalized
                                licious_has_weight = 'per_500g' in licious_normalized
                                licious_has_pieces = 'per_piece' in licious_normalized
                                
                                # Case where one product is by weight and other by pieces
                                if (japfa_has_weight and licious_has_pieces and not licious_has_weight) or \
                                   (japfa_has_pieces and licious_has_weight and not japfa_has_pieces):
                                    st.markdown("<div class='price-comparison'>Price comparison not possible - Different measurement units</div>", unsafe_allow_html=True)
                                    comparison_made = True
                                # Compare by weight if both have weight
                                elif japfa_has_weight and licious_has_weight:
                                    if japfa_normalized['per_500g'] > 0:  # Only calculate if Japfa price is non-zero
                                        price_diff_percent = ((licious_normalized['per_500g'] - japfa_normalized['per_500g']) / japfa_normalized['per_500g']) * 100
                                        comparison_made = True
                                    elif licious_normalized['per_500g'] > 0:  # If Japfa price is 0 but Licious price exists
                                        st.markdown("<div class='price-comparison price-worse'>Price comparison not available - Japfa price missing</div>", unsafe_allow_html=True)
                                        comparison_made = True
                                # Compare by pieces if both have pieces
                                elif japfa_has_pieces and licious_has_pieces:
                                    if japfa_normalized['per_piece'] > 0:  # Only calculate if Japfa price is non-zero
                                        price_diff_percent = ((licious_normalized['per_piece'] - japfa_normalized['per_piece']) / japfa_normalized['per_piece']) * 100
                                        comparison_made = True
                                    elif licious_normalized['per_piece'] > 0:  # If Japfa price is 0 but Licious price exists
                                        st.markdown("<div class='price-comparison price-worse'>Price comparison not available - Japfa price missing</div>", unsafe_allow_html=True)
                                        comparison_made = True
                                
                                # Only show price comparison if we have a valid price_diff_percent and haven't shown a "not possible" message
                                if comparison_made and price_diff_percent is not None:
                                    if price_diff_percent > 0:
                                        st.markdown(f"<div class='price-comparison price-better'>Japfa is {abs(price_diff_percent):.1f}% cheaper</div>", unsafe_allow_html=True)
                                    elif price_diff_percent < 0:
                                        st.markdown(f"<div class='price-comparison price-worse'>Licious is {abs(price_diff_percent):.1f}% cheaper</div>", unsafe_allow_html=True)
                                    else:
                                        st.markdown("<div class='price-comparison'>Same price</div>", unsafe_allow_html=True)
    else:
        st.error("No product matches found in the data. Please check the data files.")

if __name__ == "__main__":
    main() 