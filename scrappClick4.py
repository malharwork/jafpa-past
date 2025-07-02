import re
import json
import csv
import datetime
import time
import pandas as pd
from playwright.sync_api import sync_playwright
import urllib.parse

def extract_image_url(product):
    try:
        # Look for image in carousel container first (works for both single and multiple images)
        carousel = product.query_selector("div.Carousel_carousel_container__q7kdq")
        if carousel:
            # Get the first carousel item image
            img = carousel.query_selector("img[alt^='carouselItem-']")
            if img:
                src = img.get_attribute('src')
                if src and src.startswith('/_next/image?url='):
                    # Extract and decode the actual URL from the _next/image URL
                    url_param = re.search(r'url=([^&]+)', src).group(1)
                    return urllib.parse.unquote(url_param)
                return src
        
        # Fallback: try to find any image in the product container
        img = product.query_selector("div.LargeProductCard_image_video_container__x92wg img")
        if img:
            src = img.get_attribute('src')
            if src and src.startswith('/_next/image?url='):
                url_param = re.search(r'url=([^&]+)', src).group(1)
                return urllib.parse.unquote(url_param)
            return src
    except Exception as e:
        print(f"Error extracting image URL: {e}")
    return ""

def scrape_licious_by_clicking_categories(output_filename="licious_data"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)  # set headless=True if you want
        page = browser.new_page()
        
        # Set longer default timeout
        page.set_default_timeout(60000)  # Increase to 60 seconds
        
        page.goto("https://www.licious.in/", timeout=60000)
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(5000)         
        
        # Set location to pune
        try:
            page.wait_for_selector("#LC_HEADER_LOCATION_SELECT")
            page.click("#LC_HEADER_LOCATION_SELECT")
            page.wait_for_selector('span.title_5', timeout=10000)
            page.click('span.title_5')
            input_box = page.locator("input#LC_HEADER_LOCATION_SEARCH")
            input_box.click(force=True)   
            input_box.fill("")           
            input_box.type("pune", delay=100)  
            page.wait_for_timeout(2000) 
            page.wait_for_function(
                """() => {
                    const first = document.querySelector('.LocationPopup_address_list__xB5ob div');
                    return first && first.innerText.toLowerCase().includes('pune');
                }""",
                timeout=10000
            )
            page.click(".LocationPopup_address_list__xB5ob div")
            page.wait_for_timeout(2000) 
        except Exception as e:
            print(f"Error setting location: {e}")
            return

        # Wait for categories to load
        try:
            page.wait_for_selector('span[data-testid^="category_grid"]', timeout=10000)
        except Exception as e:
            print(f"Error loading categories: {e}")
            return

        # Get all category elements
        category_elements = page.query_selector_all('span[data-testid^="category_grid"]')
        print(f"Found {len(category_elements)} categories")

        all_data = []

        for i in range(len(category_elements)):
            max_retries = 3  # Number of retries for each category
            success = False
            
            for retry in range(max_retries):
                try:
                    # Re-load homepage to reset
                    page.goto("https://www.licious.in/", timeout=60000)
                    page.wait_for_selector('span[data-testid^="category_grid"]', timeout=10000)

                    # Re-fetch category elements after reload
                    category_elements = page.query_selector_all('span[data-testid^="category_grid"]')

                    # Get category name
                    category_name = category_elements[i].query_selector("div[class*='CategoriesGrid_category_name_mobile']").inner_text()
                    print(f"Scraping {category_name} (Attempt {retry + 1}/{max_retries})")

                    # Click the category
                    category_elements[i].click()

                    # Wait for products to load with increased timeout
                    page.wait_for_selector("article[class*='LargeProductCard_large_product_card_container']", timeout=30000)

                    # Scroll to load all products
                    last_height = 0
                    max_scroll_attempts = 10
                    
                    for _ in range(max_scroll_attempts):
                        # Scroll down
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)  # Wait for content to load
                        
                        # Get new height
                        new_height = page.evaluate("document.body.scrollHeight")
                        
                        # Break if no more content loaded
                        if new_height == last_height:
                            break
                            
                        last_height = new_height

                    # Wait for any dynamic content to load
                    page.wait_for_timeout(3000)

                    success = True
                    break  # Break retry loop if successful

                except Exception as e:
                    print(f"Attempt {retry + 1} failed for category {i+1}: {e}")
                    if retry == max_retries - 1:  # If this was the last retry
                        print(f"Failed to load category {i+1} after {max_retries} attempts")
                        continue  # Skip to next category
                    page.wait_for_timeout(5000)  # Wait before retrying

            if not success:
                continue  # Skip to next category if all retries failed

            # Rest of the product scraping code remains the same
            products = page.query_selector_all("article[class*='LargeProductCard_large_product_card_container']")
            if not products:
                print(f"No products found in category {i+1}")
                continue

            print(f"Found {len(products)} products in {category_name}")

            for product in products:
                location="pune"
                try:
                    name = product.query_selector("span[class*='LargeProductCard_product_name']").inner_text().strip()
                except:
                    name = ""
                try:
                    desc = product.query_selector("span[class*='LargeProductCard_product_desc']").inner_text().strip()
                except:
                    desc = ""
                try:
                    weight_servings_text = product.query_selector("div[class*='LargeProductCard_product_weight_container']").inner_text().strip()
                    weight = ""
                    servings = ""
                    if '|' in weight_servings_text:
                        parts = weight_servings_text.split('|')
                        weight = parts[0].strip()
                        servings = ' | '.join([p.strip() for p in parts[1:]])
                    else:
                        weight = weight_servings_text
                except:
                    weight = servings = ""
                try:
                    price_text = product.query_selector("div[class*='LargeProductCard_product_pricing_cta']").inner_text().strip()
                    # Extract prices and discount separately
                    price_section = product.query_selector("section[class*='LargeProductCard_price_section']")
                    if price_section:
                        # Get current price
                        current_price = price_section.query_selector("span[class*='title_4']").inner_text().strip()
                        selling_price = re.search(r'₹(\d+\.?\d*)', current_price).group(1) if current_price else "0"
                        
                        # Get original price
                        original_price_elem = price_section.query_selector("span[class*='LargeProductCard_base_price']")
                        original_price = re.search(r'₹(\d+\.?\d*)', original_price_elem.inner_text().strip()).group(1) if original_price_elem else selling_price
                        
                        # Get discount percentage
                        discount_elem = price_section.query_selector("span[class*='green_text']")
                        discount_text = discount_elem.inner_text().strip() if discount_elem else "0% off"
                        discount_percent = re.search(r'(\d{1,2})%', discount_text).group(1) if discount_text else "0"
                    else:
                        original_price = selling_price = discount_percent = "0"
                except Exception as e:
                    print(f"Error extracting prices: {e}")
                    original_price = selling_price = discount_percent = "0"
                try:
                    delivery = product.query_selector("span[class*='LargeProductCard_delivery_messages_supportingText']").inner_text().strip()
                except:
                    delivery = ""

                # Extract image URL
                image_url = extract_image_url(product)

                all_data.append({
                    "licious_id": f"L{len(all_data) + 1}",
                    "title": name,
                    "description": desc,
                    "category_name": category_name,
                    "location": location,
                    "extraction_date": datetime.date.today().isoformat(),
                    "extraction_time": datetime.datetime.now().strftime("%H:%M:%S"),
                    "regular_price": original_price,
                    "discounted_price": selling_price,
                    "discount_percent": discount_percent,
                    "category_index": i + 1,
                    "weight": weight,
                    "servings": servings,
                    "delivery_info": delivery,
                    "image_url": image_url
                })

        # Generate timestamp for filenames
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        
        # Save as JSON
        json_file = f'{output_filename}_{location.lower().replace(" ", "_")}_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)

        print(f"Scraped {len(all_data)} products. JSON saved as {json_file}")

        # Clean all_data for CSV and Excel
        cleaned_data = []
        for item in all_data:
            cleaned_item = {k: (v if v is not None else ("0" if 'price' in k or 'discount' in k else "")) for k, v in item.items()}
            cleaned_data.append(cleaned_item)

        # Save as CSV
        csv_file = f'{output_filename}_{location.lower().replace(" ", "_")}_{timestamp}.csv'
        if cleaned_data:
            keys = cleaned_data[0].keys()
            with open(csv_file, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(cleaned_data)

            print(f"CSV file saved as {csv_file}")

        # Save as Excel
        excel_file = f'{output_filename}_{location.lower().replace(" ", "_")}_{timestamp}.xlsx'
        if cleaned_data:
            df = pd.DataFrame(cleaned_data)
            df.to_excel(excel_file, index=False)
            print(f"Excel file saved as {excel_file}")

        browser.close()

if __name__ == "__main__":
    # You can specify a custom filename here
    scrape_licious_by_clicking_categories("licious")
