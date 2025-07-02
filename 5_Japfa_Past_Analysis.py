import streamlit as st
import json
import pandas as pd
import glob
import os
import plotly.express as px
from datetime import datetime
from collections import defaultdict

# Set page title
st.title("Japfa Price Analysis Over Time")

# Define the directory path for data files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'japfa_past')

def extract_datetime_from_filename(filename):
    # Extract date and time parts from filename (format: japfa_city_2025_04_14_17_09_46.json)
    filename = os.path.basename(filename).replace('.json', '')
    parts = filename.split('_')
    # Find the first part that looks like a year (2025)
    year_index = next(i for i, part in enumerate(parts) if part.isdigit() and len(part) == 4)
    year = int(parts[year_index])
    month = int(parts[year_index + 1])
    day = int(parts[year_index + 2])
    hour = int(parts[year_index + 3])
    minute = int(parts[year_index + 4])
    second = int(parts[year_index + 5])
    return datetime(year, month, day, hour, minute, second)

def extract_city_from_filename(filename):
    # Extract city name from filename (format: japfa_city_YYYY_MM_DD_HH_MM_SS.json)
    filename = os.path.basename(filename)
    parts = filename.split('_')
    # Find the first part that looks like a year (2025)
    year_index = next(i for i, part in enumerate(parts) if part.isdigit() and len(part) == 4)
    # City name is between 'japfa' and the year
    return '_'.join(parts[1:year_index])

def load_and_process_file(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['product_identifier'] = df['title'] + ' - ' + df['category_name']
    
    # Convert price columns to numeric
    df['regular_price'] = pd.to_numeric(df['regular_price'].str.replace('₹', '').str.strip(), errors='coerce')
    df['discounted_price'] = pd.to_numeric(df['discounted_price'].str.replace('₹', '').str.strip(), errors='coerce')
    
    return df

try:
    # Create directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Find all Japfa JSON files in the specified directory
    files = glob.glob(os.path.join(DATA_DIR, 'japfa_*_*.json'))
    
    if not files:
        st.error(f"No Japfa data files found in the directory: {DATA_DIR}")
        st.info("Please ensure your data files are placed in the 'japfa_past' directory and follow the naming convention: japfa_city_YYYY_MM_DD_HH_MM_SS.json")
        st.stop()
    
    # Get available cities
    cities = sorted(set(extract_city_from_filename(f) for f in files))
    
    # City selection
    selected_city = st.selectbox(
        "Select City",
        cities,
        format_func=lambda x: x.replace('-', ' ').title()
    )
    
    # Filter files for selected city
    city_files = [f for f in files if extract_city_from_filename(f) == selected_city]
    
    # Group files by date for the selected city
    files_by_date = defaultdict(list)
    for file in city_files:
        dt = extract_datetime_from_filename(file)
        date_key = dt.date()
        files_by_date[date_key].append((dt, file))
    
    # Sort dates and files within each date
    sorted_dates = sorted(files_by_date.keys())
    for date_key in files_by_date:
        files_by_date[date_key].sort()  # Sort by datetime
    
    if len(sorted_dates) < 2:
        st.error(f"Insufficient data for {selected_city.replace('-', ' ').title()}. Need at least 2 different dates for comparison.")
        st.stop()
    
    # Display date selection
    st.header(f"Select Analysis Period for {selected_city.replace('-', ' ').title()}")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.selectbox(
            "Start Date",
            sorted_dates,
            format_func=lambda x: x.strftime('%B %d, %Y')
        )
    with col2:
        end_date = st.selectbox(
            "End Date",
            [d for d in sorted_dates if d >= start_date],
            index=len([d for d in sorted_dates if d >= start_date])-1,
            format_func=lambda x: x.strftime('%B %d, %Y')
        )
    
    # For each date, allow selection of specific time if multiple files exist
    start_datetime = None
    end_datetime = None
    
    if len(files_by_date[start_date]) > 1:
        start_datetime = st.selectbox(
            "Select Start Time",
            [dt for dt, _ in files_by_date[start_date]],
            format_func=lambda x: x.strftime('%I:%M %p')
        )
    else:
        start_datetime = files_by_date[start_date][0][0]
    
    if len(files_by_date[end_date]) > 1:
        end_datetime = st.selectbox(
            "Select End Time",
            [dt for dt, _ in files_by_date[end_date]],
            index=len(files_by_date[end_date])-1,
            format_func=lambda x: x.strftime('%I:%M %p')
        )
    else:
        end_datetime = files_by_date[end_date][-1][0]
    
    # Get the corresponding filenames
    start_file = next(f for dt, f in files_by_date[start_date] if dt == start_datetime)
    end_file = next(f for dt, f in files_by_date[end_date] if dt == end_datetime)
    
    # Display selected period
    st.info(f"Analyzing price changes in {selected_city.replace('-', ' ').title()} from {start_datetime.strftime('%B %d, %Y at %I:%M %p')} to {end_datetime.strftime('%B %d, %Y at %I:%M %p')}")
    time_diff = end_datetime - start_datetime
    st.caption(f"Time period analyzed: {time_diff.days} days, {time_diff.seconds//3600} hours")
    
    # Load and process the data
    df_old = load_and_process_file(start_file)
    df_new = load_and_process_file(end_file)
    
    # Merge the dataframes
    df_merged = pd.merge(
        df_old[['product_identifier', 'regular_price', 'discounted_price', 'title', 'category_name']],
        df_new[['product_identifier', 'regular_price', 'discounted_price']],
        on='product_identifier',
        suffixes=('_old', '_new')
    )
    
    # Calculate price differences
    df_merged['regular_price_diff'] = df_merged['regular_price_new'] - df_merged['regular_price_old']
    df_merged['discounted_price_diff'] = df_merged['discounted_price_new'] - df_merged['discounted_price_old']
    
    # Filter products with price changes
    price_changed_products = df_merged[
        (df_merged['regular_price_diff'] != 0) | 
        (df_merged['discounted_price_diff'] != 0)
    ].copy()
    
    # Calculate percentage changes
    price_changed_products['regular_price_change_percent'] = (
        price_changed_products['regular_price_diff'] / price_changed_products['regular_price_old'] * 100
    )
    price_changed_products['discounted_price_change_percent'] = (
        price_changed_products['discounted_price_diff'] / price_changed_products['discounted_price_old'] * 100
    )
    
    # Load all files between start and end date for price trend analysis
    all_dates = []
    all_files = []
    for date in sorted_dates:
        if start_date <= date <= end_date:
            for dt, file in files_by_date[date]:
                all_dates.append(dt)
                all_files.append(file)
    
    # Create price trend data for products with changes
    if price_changed_products.empty:
        st.warning(f"No products with price changes found in {selected_city.replace('-', ' ').title()} for the selected period.")
    else:
        st.header(f"Price Trends for Changed Products in {selected_city.replace('-', ' ').title()}")
        
        # Get all product data across time
        product_price_data = []
        changed_product_ids = set(price_changed_products['product_identifier'])
        
        for dt, file in zip(all_dates, all_files):
            df = load_and_process_file(file)
            df = df[df['product_identifier'].isin(changed_product_ids)]
            
            for _, row in df.iterrows():
                product_price_data.append({
                    'datetime': dt,
                    'product_identifier': row['product_identifier'],
                    'title': row['title'],
                    'category_name': row['category_name'],
                    'regular_price': row['regular_price'],
                    'discounted_price': row['discounted_price']
                })
        
        trend_df = pd.DataFrame(product_price_data)
        
        # Add product selection for detailed view
        selected_product = st.selectbox(
            "Select Product to View Price Trend",
            options=sorted(price_changed_products['product_identifier'].unique()),
            format_func=lambda x: x.split(' - ')[0]  # Show only title part
        )
        
        # Filter data for selected product
        product_data = trend_df[trend_df['product_identifier'] == selected_product]
        
        # Create line chart using plotly
        fig = px.line(
            product_data,
            x='datetime',
            y=['regular_price', 'discounted_price'],
            title=f"Price Trend for {selected_product.split(' - ')[0]} in {selected_city.replace('-', ' ').title()}",
            labels={
                'datetime': 'Date',
                'value': 'Price (₹)',
                'variable': 'Price Type'
            }
        )
        
        # Update line colors and names
        fig.update_traces(
            name='Regular Price',
            line=dict(color='#1f77b4', width=2),  # Blue color
            mode='lines+markers',
            marker=dict(size=8, color='#1f77b4', symbol='circle'),
            selector=dict(name='regular_price')
        )
        fig.update_traces(
            name='Discounted Price',
            line=dict(color='#ff69b4', width=2),  # Pink color
            mode='lines+markers',
            marker=dict(size=8, color='#ff69b4', symbol='circle'),
            selector=dict(name='discounted_price')
        )
        
        # Customize layout
        fig.update_layout(
            xaxis_title='Month',
            yaxis_title='Price (₹)',
            hovermode='x unified',
            legend_title='Price Type',
            plot_bgcolor='white',
            title_font=dict(size=24, color='#484848'),
            font=dict(color='#484848'),
            xaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='#E5E5E5',
                tickfont=dict(size=12),
                tickangle=0,
                showline=True,
                linewidth=1,
                linecolor='#E5E5E5'
            ),
            yaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='#E5E5E5',
                tickfont=dict(size=12),
                tickprefix='₹',
                showline=True,
                linewidth=1,
                linecolor='#E5E5E5',
                zeroline=True,
                zerolinewidth=1,
                zerolinecolor='#E5E5E5'
            ),
            margin=dict(t=100, l=50, r=50, b=50),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255, 255, 255, 0.8)'
            )
        )
        
        # Display the plot
        st.plotly_chart(fig, use_container_width=True)
        
        # Display price change summary for selected product
        product_summary = price_changed_products[price_changed_products['product_identifier'] == selected_product].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Regular Price Change",
                f"₹{product_summary['regular_price_diff']:.2f}",
                f"{product_summary['regular_price_change_percent']:.1f}%"
            )
        with col2:
            st.metric(
                "Discounted Price Change",
                f"₹{product_summary['discounted_price_diff']:.2f}",
                f"{product_summary['discounted_price_change_percent']:.1f}%"
            )
        
        # Display summary statistics
        st.header(f"Summary Statistics for {selected_city.replace('-', ' ').title()}")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Total Products Analyzed",
                len(df_merged)
            )
        with col2:
            st.metric(
                "Products with Price Changes",
                len(price_changed_products)
            )
        with col3:
            avg_price_change = price_changed_products['regular_price_diff'].mean()
            st.metric(
                "Average Regular Price Change",
                f"₹{avg_price_change:.2f}"
            )
        
        # Category-wise analysis
        st.subheader(f"Category-wise Price Changes in {selected_city.replace('-', ' ').title()}")
        category_stats = price_changed_products.groupby('category_name').agg({
            'regular_price_diff': ['count', 'mean'],
            'discounted_price_diff': 'mean'
        }).round(2)
        category_stats.columns = ['Number of Changes', 'Avg Regular Price Change', 'Avg Discounted Price Change']
        st.dataframe(category_stats)
        
        # Display detailed analysis
        st.header("Detailed Price Changes")
        
        # Add price change filters
        col1, col2, col3 = st.columns(3)
        with col1:
            min_price_change = st.number_input(
                "Minimum Price Change (₹)",
                value=0.0,
                step=1.0
            )
        with col2:
            price_change_type = st.selectbox(
                "Price Change Type",
                ["All Changes", "Price Increases", "Price Decreases"]
            )
        with col3:
            selected_category = st.selectbox(
                "Filter by Category",
                ["All Categories"] + sorted(price_changed_products['category_name'].unique().tolist())
            )
        
        # Filter based on user selection
        filtered_df = price_changed_products.copy()
        
        if price_change_type == "Price Increases":
            filtered_df = filtered_df[filtered_df['regular_price_diff'] > min_price_change]
        elif price_change_type == "Price Decreases":
            filtered_df = filtered_df[filtered_df['regular_price_diff'] < -min_price_change]
        else:
            filtered_df = filtered_df[abs(filtered_df['regular_price_diff']) > min_price_change]
        
        if selected_category != "All Categories":
            filtered_df = filtered_df[filtered_df['category_name'] == selected_category]
        
        # Sort by absolute price change
        filtered_df = filtered_df.sort_values(by='regular_price_diff', key=abs, ascending=False)
        
        # Display the results in a table
        if not filtered_df.empty:
            display_columns = [
                'title', 'category_name',
                'regular_price_old', 'regular_price_new', 'regular_price_diff', 'regular_price_change_percent',
                'discounted_price_old', 'discounted_price_new', 'discounted_price_diff', 'discounted_price_change_percent'
            ]
            
            st.dataframe(
                filtered_df[display_columns].style.format({
                    'regular_price_old': '₹{:.2f}',
                    'regular_price_new': '₹{:.2f}',
                    'regular_price_diff': '₹{:.2f}',
                    'regular_price_change_percent': '{:.1f}%',
                    'discounted_price_old': '₹{:.2f}',
                    'discounted_price_new': '₹{:.2f}',
                    'discounted_price_diff': '₹{:.2f}',
                    'discounted_price_change_percent': '{:.1f}%'
                }),
                use_container_width=True
            )
        else:
            st.info("No products found matching the selected criteria.")
        
        # Add download button for the filtered data
        if not filtered_df.empty:
            # Prepare data for CSV export
            export_df = filtered_df[display_columns].copy()
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download Price Changes Data",
                data=csv,
                file_name=f"japfa_{selected_city}_price_changes_{start_datetime.strftime('%Y%m%d')}_to_{end_datetime.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

except Exception as e:
    st.error(f"Error loading or processing data: {str(e)}")
    st.error("Please ensure all required data files are present in the correct location.") 