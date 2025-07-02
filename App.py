import streamlit as st

# Set page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="Japfa-Licious Product Analysis",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Japfa-Licious Product Analysis\nA tool for analyzing product matches between Japfa and Licious."
    }
)

# Add custom CSS - Only for app-wide and sidebar styling
st.markdown("""
    <style>
    /* App-wide styles */
    .stApp {
        max-width: 100%;
    }
    .main {
        padding: 0;
    }
    
    /* Sidebar specific styles */
    section[data-testid="stSidebar"] {
        background-color: #1E1E1E;
        width: 250px;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }
    section[data-testid="stSidebar"] .element-container {
        margin-bottom: 1rem;
    }
    section[data-testid="stSidebar"] h1 {
        color: #FFFFFF;
        font-size: 1.5rem;
        padding: 0 1rem;
        margin-bottom: 1.5rem;
    }
    section[data-testid="stSidebar"] .stRadio label {
        color: #FFFFFF;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        background-color: #2D2D2D;
        border-radius: 4px;
        padding: 0.5rem;
    }
    section[data-testid="stSidebar"] .stRadio div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF;
    }
    </style>
""", unsafe_allow_html=True)

# Main page content
st.title("🍔 Welcome to Japfa-Licious Product Analysis")
st.markdown("""
This tool helps analyze product matches between Japfa and Licious catalogs.

### Available Pages:
1. **Product Match**: View and analyze product matches between Japfa and Licious
2. **Unmatched Products**: Explore Licious products that don't have matches in Japfa catalog

Use the sidebar navigation to switch between pages.
""")

# Display some overall statistics if needed
try:
    import json
    with open('product_matches_not_unique.json', 'r') as f:
        matches_data = json.load(f)
    
    with open('japfa_pune_2025_04_14_17_49_23_revised_description.json', 'r') as f:
        japfa_data = json.load(f)
    
    with open('licious_pune_2025_04_14_17_09_46_revised_description.json', 'r') as f:
        licious_data = json.load(f)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Japfa Products", len(matches_data['weighted_matches']))
    with col2:
        st.metric("Total Licious Products", len(licious_data))
    with col3:
        total_matches = sum(len(product_data['matches']) for product_data in matches_data['weighted_matches'].values())
        st.metric("Total Product Matches", total_matches)
        
except Exception as e:
    st.error("Could not load data files. Please ensure all required files are present.")
