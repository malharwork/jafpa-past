from playwright.sync_api import sync_playwright
import json
import time
import os
from datetime import datetime

def set_location(page, location):
    """Set delivery location"""
    try:
        # Wait for location popup
        page.wait_for_selector('.locationContainerBox')
        
        # Find and click the search input
        search_input = page.query_selector('.searchLocationBox input[type="text"]')
        if search_input:
            # Clear any existing text and type the location
            search_input.click()
            search_input.fill(location)
            time.sleep(2)  # Wait for suggestions to load
            
            # Try to find and click the first location suggestion
            try:
                # Wait for the location list to appear
                page.wait_for_selector('.locationList', timeout=5000)
                
                # Get the first location item from the list
                first_location = page.query_selector('.locationList li:first-child')
                if first_location:
                    first_location.click()
                    time.sleep(2)
                    
                    # Verify if location was set (popup should disappear)
                    if not page.query_selector('.locationContainerBox'):
                        print("Location set successfully!")
                        return True
                    
            except Exception as e:
                print(f"Error selecting first location suggestion: {e}")
                
                # Try clicking "Use Current Location" as fallback
                try:
                    current_location_btn = page.query_selector('.getLocationButton')
                    if current_location_btn:
                        current_location_btn.click()
                        time.sleep(2)
                        return True
                except Exception as e:
                    print(f"Failed to use current location: {e}")
                    
        return False
    except Exception as e:
        print(f"Error setting location: {e}")
        return False

def save_storage_state(context, location):
    """Save browser storage state to file"""
    state_file = f'storage_state_{location.lower().replace(" ", "_")}.json'
    context.storage_state(path=state_file)
    return state_file

def load_storage_state(location):
    """Load browser storage state from file"""
    state_file = f'storage_state_{location.lower().replace(" ", "_")}.json'
    return state_file if os.path.exists(state_file) else None

def scrape_product_details(page, product_data, location):
    """Scrape details for a single product"""
    try:
        # Get current date and time
        current_datetime = datetime.now()
        extraction_date = current_datetime.strftime('%Y-%m-%d')
        extraction_time = current_datetime.strftime('%H:%M:%S')
        
        # Add timestamp and location to product data
        product_data['location'] = location
        product_data['extraction_date'] = extraction_date
        product_data['extraction_time'] = extraction_time
        product_data['description'] = ''
        
        # Get product ID from image URL and navigate to details page
        if product_data['image_url'] and 'prod/' in product_data['image_url']:
            try:
                product_id = product_data['image_url'].split('prod/')[1].split('/')[0]
                
                # Navigate to product details page
                details_url = f"https://japfabest.in/product-details/{product_id}"
                page.goto(details_url)
                
                # Wait for the product details section to load
                page.wait_for_selector('.productDetails', timeout=10000)
                
                # Try multiple possible selectors for the description
                description_selectors = [
                    '.productDetails .text-left.text-base.font-normal.leading-5',  # Original selector
                    'p.text-left.text-base.font-normal.leading-5',  # New selector for SUB type products
                    '.mt-4 p.text-left.text-base.font-normal.leading-5'  # More specific selector
                ]
                
                description = ''
                for selector in description_selectors:
                    about_section = page.query_selector(selector)
                    if about_section:
                        description = about_section.inner_text().strip()
                        if description:  # If we found a non-empty description
                            break
                            
                if description:
                    product_data['description'] = description
                    print(f"Successfully extracted description for: {product_data['title']} (ID: {product_id})")
                else:
                    print(f"Could not find description for product: {product_data['title']} (ID: {product_id})")
                
                # Go back to category page
                page.go_back()
                # Wait for category page to load
                page.wait_for_selector('.product-card', timeout=10000)
                time.sleep(1)
            except Exception as e:
                print(f"Error extracting description for {product_data['title']}: {e}")
                # Try to go back to category page if there was an error
                try:
                    page.go_back()
                    page.wait_for_selector('.product-card', timeout=10000)
                    time.sleep(1)
                except:
                    pass
        
        return product_data
    except Exception as e:
        print(f"Error scraping product: {e}")
        return None

def extract_product_data(product):
    """Extract basic product data from a product element"""
    try:
        name_elem = product.query_selector('.product-name')
        regular_price = product.query_selector('.regularPrice')
        regular_price_red = product.query_selector('.regularPriceRed')
        discounted_price = product.query_selector('.discountedPrice')
        final_regular_price = regular_price_red if regular_price_red else regular_price
        discount_label = product.query_selector('.product-discount-label')
        weight = product.query_selector('.product-weight')
        image = product.query_selector('.product-image')
        delivery = product.query_selector('.text-green')
        
        # Get the product ID from image URL
        product_id = None
        if image:
            image_url = image.get_attribute('src')
            if 'prod/' in image_url:
                product_id = image_url.split('prod/')[1].split('/')[0]
        
        return {
            'title': name_elem.inner_text() if name_elem else '',
            'regular_price': final_regular_price.inner_text() if final_regular_price else '',
            'discounted_price': discounted_price.inner_text() if discounted_price else '',
            'discount': discount_label.inner_text() if discount_label else '',
            'weight': weight.inner_text() if weight else '',
            'image_url': image.get_attribute('src') if image else '',
            'delivery_time': delivery.inner_text() if delivery else '',
            'product_id': product_id
        }
    except Exception as e:
        print(f"Error extracting basic product details: {e}")
        return None

def get_product_description(page, product_id):
    """Get product description from product details page"""
    try:
        # Check if it's a SUB type product
        is_sub_product = product_id.startswith('SUB-')
        
        # Choose URL based on product type
        url = f"https://japfabest.in/{'products' if is_sub_product else 'product'}-details/{product_id}"
        
        try:
            # Navigate to product details page
            page.goto(url)
            
            if is_sub_product:
                # For SUB type products
                try:
                    # Wait for the about section to load
                    page.wait_for_selector('.hidden.md\\:block', timeout=10000)
                    time.sleep(2)  # Additional wait for dynamic content
                    
                    # Try to get description
                    about_section = page.query_selector('.hidden.md\\:block p.text-left.text-base.font-normal.leading-5')
                    if about_section:
                        description = about_section.inner_text().strip()
                        if description:
                            return description
                except Exception as e:
                    print(f"Error extracting SUB product description: {e}")
            else:
                # For regular products
                try:
                    # Wait for product details section
                    page.wait_for_selector('.productDetails', timeout=10000)
                    time.sleep(2)  # Additional wait for dynamic content
                    
                    # Try to get description
                    about_section = page.query_selector('.productDetails .text-left.text-base.font-normal.leading-5')
                    if about_section:
                        description = about_section.inner_text().strip()
                        if description:
                            return description
                except Exception as e:
                    print(f"Error extracting regular product description: {e}")
            
            # If we haven't returned yet, try a generic selector as fallback
            try:
                generic_selector = 'p.text-left.text-base.font-normal.leading-5'
                about_section = page.query_selector(generic_selector)
                if about_section:
                    description = about_section.inner_text().strip()
                    if description:
                        return description
            except Exception:
                pass
                
        except Exception as e:
            print(f"Failed to load URL {url}: {e}")
            
        return ''  # Return empty string if no description found
        
    except Exception as e:
        print(f"Error getting description for product {product_id}: {e}")
        return ''

def ensure_all_products_loaded(page):
    """Ensure all products are loaded by scrolling to the bottom"""
    try:
        # Initial product count
        initial_count = len(page.query_selector_all('.product-card'))
        
        # Scroll to bottom and wait for potential new products
        for _ in range(3):  # Try scrolling up to 3 times
            # Scroll to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)  # Wait for potential loading
            
            # Get new count
            new_count = len(page.query_selector_all('.product-card'))
            
            # If no new products loaded, we're done
            if new_count == initial_count:
                break
                
            initial_count = new_count
            
        # Final wait to ensure all content is stable
        time.sleep(2)
        
    except Exception as e:
        print(f"Error while ensuring products loaded: {e}")

def main(location="Pune"):
    with sync_playwright() as p:
        # Launch browser with viewport size
        browser = p.chromium.launch(headless=False)  # Set to False to see the browser while testing
        
        # Check if we have stored state for this location
        storage_state_path = load_storage_state(location)
        
        # Create context with stored state if available
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            storage_state=storage_state_path if storage_state_path else None
        )
        
        page = context.new_page()
        
        # Set longer default timeout
        page.set_default_timeout(30000)  # 30 seconds timeout
        
        # Navigate to the website
        print("Navigating to website...")
        page.goto('https://japfabest.in/')
        
        # Set delivery location if needed
        if not storage_state_path:
            print(f"Setting delivery location to: {location}")
            max_retries = 3
            location_set = False
            
            for attempt in range(max_retries):
                if set_location(page, location):
                    location_set = True
                    # Save the storage state after successful location set
                    save_storage_state(context, location)
                    break
                print(f"Attempt {attempt + 1} failed, retrying...")
                # Refresh page between attempts
                page.reload()
                time.sleep(2)
            
            if not location_set:
                print("Failed to set location after multiple attempts. Exiting...")
                browser.close()
                return
        
        # Wait for the categories section to load
        page.wait_for_selector('section h2:has-text("Browse by categories")')
        
        # Category IDs mapping
        category_ids = {
            'Curry in a Hurry': 'SPE-CAT-021',
            'Todays Deals': 'SPE-CAT-019',
            'Ready to Cook': 'SPE-CAT-018',
            'Bestsellers': 'SPE-CAT-002',
            'Chicken': 'SPE-CAT-011',
            'Mutton': 'SPE-CAT-012',
            'Sea Water Fish': 'SPE-CAT-014',
            'Fresh Water Fish': 'SPE-CAT-015',
            'Fillets and Steaks': 'SPE-CAT-008',
            'Speciality Cuts': 'SPE-CAT-009',
            'Eggs': 'SPE-CAT-013'
        }
        
        # Initialize a list to store all products
        all_products = []
        japfa_id_counter = 1
        
        # Process each category using the known IDs
        for category_name, category_id in category_ids.items():
            try:
                print(f"\nProcessing category: {category_name}")
                
                # Navigate to category page
                url = f'https://japfabest.in/productsCategories?id={category_id}'
                page.goto(url)
                
                # Check if location popup appears and handle it
                try:
                    location_popup = page.wait_for_selector('.locationContainerBox', timeout=5000)
                    if location_popup:
                        print("Location popup appeared, setting location again...")
                        if not set_location(page, location):
                            print(f"Failed to set location for category {category_name}, skipping...")
                            continue
                except:
                    pass  # No location popup found, continue normally
                
                # Wait for the title and products to load
                page.wait_for_selector('.text-stone-900.text-xl', timeout=10000)
                page.wait_for_selector('.product-card', timeout=10000)
                
                # Ensure all products are loaded
                ensure_all_products_loaded(page)
                
                # Get all products in this category
                products = page.query_selector_all('.product-card')
                print(f"Found {len(products)} product cards")
                
                # First collect basic data for all products
                category_products = []
                for idx, product in enumerate(products, 1):
                    print(f"Extracting basic data for product {idx} of {len(products)}")
                    product_data = extract_product_data(product)
                    if product_data:
                        # Add category name and japfa_id
                        product_data['category_name'] = category_name
                        product_data['japfa_id'] = f"J{japfa_id_counter}"
                        japfa_id_counter += 1
                        category_products.append(product_data)

                # Now get descriptions for all products
                for idx, product_data in enumerate(category_products, 1):
                    if product_data.get('product_id'):
                        print(f"Getting description for: {product_data['title']} ({idx} of {len(category_products)})")
                        description = get_product_description(page, product_data['product_id'])
                        product_data['description'] = description
                        
                        # Add timestamp and location
                        current_datetime = datetime.now()
                        product_data['extraction_date'] = current_datetime.strftime('%Y-%m-%d')
                        product_data['extraction_time'] = current_datetime.strftime('%H:%M:%S')
                        product_data['location'] = location
                        
                        # Return to category page
                        page.goto(url)
                        try:
                            page.wait_for_selector('.product-card', timeout=10000)
                            time.sleep(1)  # Short wait for page to stabilize
                            ensure_all_products_loaded(page)
                        except Exception as e:
                            print(f"Error returning to category page: {e}")
                            page.reload()
                            page.wait_for_selector('.product-card', timeout=10000)
                            ensure_all_products_loaded(page)
                    else:
                        print(f"No product ID found for: {product_data['title']}")
                        product_data['description'] = ''
                        # Add timestamp and location for consistency
                        current_datetime = datetime.now()
                        product_data['extraction_date'] = current_datetime.strftime('%Y-%m-%d')
                        product_data['extraction_time'] = current_datetime.strftime('%H:%M:%S')
                        product_data['location'] = location
                    
                    # Add product to the main list
                    all_products.append(product_data)
                    print(f"Successfully processed product {idx} of {len(category_products)} in {category_name}")
                
                print(f"Completed processing {len(category_products)} products in category: {category_name}")
                
            except Exception as e:
                print(f"Error processing category {category_name}: {e}")
                continue
        
        # Save data to JSON file
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        output_filename = f'japfa_{location.lower().replace(" ", "_")}_{timestamp}.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=4, ensure_ascii=False)
        
        print(f"\nScraping completed! Data saved to {output_filename}")
        browser.close()

if __name__ == "__main__":
    # main(location="Bangalore")
    main(location="Pune")
    # main(location="Pimpri-Chinchwad")