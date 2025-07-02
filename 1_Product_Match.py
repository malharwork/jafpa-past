import streamlit as st
import json
import pandas as pd

# Set page config
st.set_page_config(
    page_title="Product Match - Japfa-Licious Analysis",
    page_icon="🍔",
    layout="wide"
)

# Initialize session state variables
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""
if 'last_search' not in st.session_state:
    st.session_state.last_search = ""
if 'selected_product_id' not in st.session_state:
    st.session_state.selected_product_id = None

# Add custom CSS
st.markdown("""
    <style>
    .product-card {
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        background-color: white;
    }
    .confidence-high {
        color: #28a745;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #e8f5e9;
        border-radius: 4px;
        display: inline-block;
    }
    .confidence-medium {
        color: #ffa000;
        font-weight: 600;
        padding: 4px 8px;
        background-color: #fff3e0;
        border-radius: 4px;
        display: inline-block;
    }
    /* Search bar and reset button alignment */
    div[data-testid="column"] {
        padding: 0 !important;
    }
    div[data-testid="stButton"] {
        margin-top: 8px !important;
        margin-bottom: 16px !important;
    }
    .stButton button {
        height: 46px !important;
        width: auto !important;
    }
    /* Fix button width */
    .stButton > button {
        width: 100%;
    }
    .source-product {
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        background-color: #f8f9fa;
        text-align: center;
    }
    .no-matches {
        color: #721c24;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .stats-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .company-label {
        color: #666;
        font-size: 0.9em;
        margin-bottom: 0.5rem;
    }
    /* Search results styles */
    .search-results {
        max-height: 200px;
        overflow-y: auto;
        background-color: #2D2D2D;
        border-radius: 4px;
        margin-top: 0.5rem;
    }
    .search-result-item {
        padding: 8px 12px;
        color: #ffffff;
        border-left: 4px solid transparent;
    }
    .search-result-item:hover {
        background-color: rgba(74, 74, 74, 0.2);
        border-left-color: #ffa000;
    }
    .search-result-item.selected {
        background-color: rgba(74, 74, 74, 0.4);
        border-left-color: #28a745;
    }
    .search-highlight {
        background-color: #4A4A4A;
        padding: 2px;
        border-radius: 2px;
    }
    .confidence-tag {
        font-size: 0.8em;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: bold;
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

# Load the data
@st.cache_data
def load_data():
    # Load product matches
    with open('product_matches_not_unique.json', 'r') as f:
        matches_data = json.load(f)
    
    # Load Japfa products
    with open('japfa_past/japfa_pune_2025_04_14_17_49_23.json', 'r') as f:
        japfa_data = json.load(f)
    
    # Load Licious products
    with open('licious_past/licious_pune_2025_04_14_17_09_46.json', 'r') as f:
        licious_data = json.load(f)
    
    return matches_data, japfa_data, licious_data

# Create image URL lookup dictionaries
def create_image_lookups(japfa_data, licious_data):
    japfa_images = {item['title']: item['image_url'] for item in japfa_data}
    licious_images = {item['title']: item['image_url'] for item in licious_data}
    return japfa_images, licious_images

def get_confidence_class(confidence, threshold):
    confidence_val = float(confidence.strip('%'))
    if confidence_val >= threshold + 10:  # High confidence is 10% above threshold
        return "confidence-high"
    else:
        return "confidence-medium"

def filter_matches(matches, min_confidence):
    return [match for match in matches 
            if float(match['confidence'].strip('%')) >= min_confidence]

def categorize_products(matches_data, threshold):
    products_with_matches = []
    products_without_matches = []
    
    for product_id, product_data in matches_data['weighted_matches'].items():
        japfa_product = product_data['japfa_product']
        if any(float(match['confidence'].strip('%')) >= threshold for match in product_data['matches']):
            products_with_matches.append((product_id, japfa_product))
        else:
            products_without_matches.append((product_id, japfa_product))
    
    return products_with_matches, products_without_matches

def get_match_distribution(matches_data, threshold):
    distribution = {0: 0, 1: 0, 2: 0, 3: 0}
    total_products = len(matches_data['weighted_matches'])
    
    for product_id, product_data in matches_data['weighted_matches'].items():
        match_count = len([m for m in product_data['matches'] if float(m['confidence'].strip('%')) >= threshold])
        if match_count > 3:
            match_count = 3  # Group all products with 3 or more matches
        distribution[match_count] += 1
    
    return distribution, total_products

def get_confidence_color(confidence):
    confidence_val = float(confidence.strip('%'))
    if confidence_val >= 90:
        return "#28a745", "#e8f5e9"  # Green text, light green background
    elif confidence_val >= 80:
        return "#5cb85c", "#edf7ed"  # Light green text, lighter green background
    elif confidence_val >= 70:
        return "#ffa000", "#fff3e0"  # Orange text, light orange background
    elif confidence_val >= 60:
        return "#ff9800", "#fff3e6"  # Light orange text, lighter orange background
    else:
        return "#dc3545", "#fbeaec"  # Red text, light red background

def get_confidence_label_and_class(confidence_str):
    confidence = float(confidence_str.strip('%'))
    if confidence > 95:
        return "Exact Match", "confidence-exact"
    elif confidence >= 90:
        return "Best Match", "confidence-best"
    else:
        return "Similar Product", "confidence-similar"

# Main page content
st.title("🍔 Japfa-Licious Product Match Analysis")

try:
    # Load data
    matches_data, japfa_data, licious_data = load_data()
    
    # Create image lookups
    japfa_images, licious_images = create_image_lookups(japfa_data, licious_data)
    
    # Add confidence threshold slider to sidebar
    confidence_threshold = st.sidebar.slider(
        "Minimum Confidence Threshold (%)",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
        help="Only show matches with confidence score greater than or equal to this value"
    )
    
    # Display match distribution statistics
    match_distribution, total_products = get_match_distribution(matches_data, confidence_threshold)
    
    st.markdown("<div class='stats-card'>", unsafe_allow_html=True)
    st.subheader(f"Match Distribution at {confidence_threshold}% Confidence Threshold")
    
    stat_cols = st.columns(5)
    with stat_cols[0]:
        st.metric("Total Japfa Products", total_products)
    with stat_cols[1]:
        st.metric("No Licious Matches", match_distribution[0])
    with stat_cols[2]:
        st.metric("1 Licious Match", match_distribution[1])
    with stat_cols[3]:
        st.metric("2 Licious Matches", match_distribution[2])
    with stat_cols[4]:
        st.metric("3 Licious Matches", match_distribution[3])
    
    st.markdown("### Match Distribution Analysis")
    for matches, count in match_distribution.items():
        percentage = (count / total_products) * 100
        match_label = "3 Licious matches" if matches == 3 else f"{matches} Licious match{'es' if matches != 1 else ''}"
        st.progress(percentage / 100)
        st.markdown(f"**{match_label}**: {percentage:.1f}% ({count} Japfa products)")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Categorize products based on threshold
    products_with_matches, products_without_matches = categorize_products(matches_data, confidence_threshold)
    
    # Add search box for Japfa products with autocomplete
    st.sidebar.markdown("### Japfa Product Selection")
    
    # Radio button to switch between products with and without matches
    view_option = st.sidebar.radio(
        "View Products",
        ["Products with Licious matches", "Products without Licious matches"],
        index=0
    )
    
    # Handle reset button first
    if st.sidebar.button("Reset", key="reset_search"):
        st.session_state.product_search = ""  # Clear the text input widget's state directly
        st.session_state.search_term = ""
        st.session_state.last_search = ""
        st.session_state.selected_product_id = None
        st.rerun()
    
    # Search input after reset
    search_term = st.sidebar.text_input(
        "🔍 Search Japfa products",
        key="product_search",  # This key matches what we clear in reset
        label_visibility="visible"
    ).lower()
    
    # Determine available products based on view option
    available_products = products_with_matches if view_option == "Products with Licious matches" else products_without_matches
    
    # Filter and display search results
    if search_term:
        filtered_products = [(pid, prod) for pid, prod in available_products 
                           if search_term in prod['title'].lower()]
    else:
        filtered_products = available_products
    
    # Create product options for dropdown
    product_options = []
    product_titles = []
    for pid, prod in filtered_products:
        title = prod['title']
        category = prod.get('category_name', 'N/A')
        display_text = f"{title} ({category})"
        product_options.append((pid, prod))
        product_titles.append(display_text)
    
    if product_options:
        # Find index of currently selected product
        selected_index = 0
        if st.session_state.selected_product_id:
            for i, (pid, _) in enumerate(product_options):
                if pid == st.session_state.selected_product_id:
                    selected_index = i
                    break
        
        # Display dropdown for product selection
        selected_title = st.sidebar.selectbox(
            f"Select Japfa Product (with matches ≥ {confidence_threshold}%)" if view_option == "Products with Licious matches"
            else f"Select Japfa Product (no matches ≥ {confidence_threshold}%)",
            product_titles,
            index=selected_index
        )
        
        # Get selected product from the selected title
        selected_index = product_titles.index(selected_title)
        selected_product_id, selected_product = product_options[selected_index]
        
        # Update session state when product is selected
        if selected_product_id != st.session_state.selected_product_id:
            st.session_state.selected_product_id = selected_product_id
        
        # Display search results count
        if search_term:
            st.sidebar.info(f"Found {len(filtered_products)} matching products")
        
        # Display selected product details
        st.header(f"Japfa Product: {selected_product['title']}")
        st.subheader(f"Category: {selected_product.get('category_name', 'N/A')}")
        
        source_image = japfa_images.get(selected_product['title'])
        if source_image:
            st.markdown("<div class='source-product'>", unsafe_allow_html=True)
            st.markdown("<div class='company-label'>Japfa Product</div>", unsafe_allow_html=True)
            st.image(source_image, caption=selected_product['title'], width=450)
            st.markdown("</div>", unsafe_allow_html=True)
        
        product_matches = matches_data['weighted_matches'][selected_product_id]
        
        if view_option == "Products with Licious matches":
            st.subheader("Matching Licious Products")
            filtered_matches = [match for match in product_matches['matches'] 
                              if float(match['confidence'].strip('%')) >= confidence_threshold]
            
            if filtered_matches:
                cols = st.columns(len(filtered_matches))
                
                for idx, match in enumerate(filtered_matches):
                    with cols[idx]:
                        st.markdown(f"<div class='product-card'>", unsafe_allow_html=True)
                        st.markdown("<div class='company-label'>Licious Product</div>", unsafe_allow_html=True)
                        
                        matched_image = licious_images.get(match['title'])
                        if matched_image:
                            st.image(matched_image, width=450)
                        
                        st.markdown(f"**{match['title']}**")
                        st.markdown(f"Category: {match.get('category_name', 'N/A')}")
                        label, class_name = get_confidence_label_and_class(match['confidence'])
                        st.markdown(f"<span class='{class_name}'>{label}</span>", 
                                  unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                
                # Add metrics
                st.subheader("Match Statistics")
                metrics_cols = st.columns(3)
                
                # Count matches by category
                exact_matches = sum(1 for m in filtered_matches if float(m['confidence'].strip('%')) > 95)
                best_matches = sum(1 for m in filtered_matches if 90 <= float(m['confidence'].strip('%')) <= 95)
                similar_matches = sum(1 for m in filtered_matches if float(m['confidence'].strip('%')) < 90)
                
                with metrics_cols[0]:
                    st.metric("Exact Matches", exact_matches)
                with metrics_cols[1]:
                    st.metric("Best Matches", best_matches)
                with metrics_cols[2]:
                    st.metric("Similar Products", similar_matches)
            else:
                st.warning("No matches found above the confidence threshold.")
        else:
            st.markdown("<div class='no-matches'>", unsafe_allow_html=True)
            st.markdown(f"### Licious Products Below {confidence_threshold}% Confidence Threshold:")
            for match in product_matches['matches']:
                confidence = float(match['confidence'].strip('%'))
                label, _ = get_confidence_label_and_class(match['confidence'])
                st.markdown(f"- **{match['title']}** (Category: {match.get('category_name', 'N/A')}, Match Type: {label})")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("No products available with the current filters.")

except FileNotFoundError as e:
    st.error("Error: Required data files not found. Please ensure all JSON files are present in the directory.")
except Exception as e:
    st.error(f"An error occurred: {str(e)}") 