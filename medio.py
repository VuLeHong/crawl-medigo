import asyncio
import nest_asyncio
import aiohttp
import json
import re
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Initialize WebDriver for Selenium
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=1")
    service = Service(executable_path='/usr/local/bin/chromedriver')  # No need to specify the path
    return webdriver.Chrome(service=service, options=options)

# Function to clean text
def clean_string(text):
    text = text.replace("\r\n", "\n")
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()

# Load existing product data
def load_existing_products():
    try:
        with open("medigo_product.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Save products to JSON
def append_to_json(product):
    try:
        with open("medigo_product.json", "r", encoding="utf-8") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        products = []
    
    products.append(product)
    
    with open("medigo_product.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=4)

# Asynchronous function to fetch page content
async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

# Asynchronous function to scrape pharmacy list
async def scrape_pharmacy_list():
    pharmacy_list = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, f'https://www.medigoapp.com/danh-sach-nha-thuoc/tat-ca?page={i}') for i in range(1, 19)]
        pages = await asyncio.gather(*tasks)

        for page in pages:
            soup = BeautifulSoup(page, 'html.parser')
            pharmacies_div = soup.find_all('p', class_='pharmacy-name mb-3 pt-2 align-items-center')

            for pharmacy_div in pharmacies_div:
                pharmacy_link = pharmacy_div.find('a').get('href')
                pharmacy_name = pharmacy_div.find('b').text
                pharmacy_list.append({"pharmacy_name": pharmacy_name, "pharmacy_link": pharmacy_link})

    return pharmacy_list

# Function to scrape products using Selenium
async def scrape_pharmacy_products(pharmacy, existing_products):
    pharmacy_name = pharmacy["pharmacy_name"]
    pharmacy_link = pharmacy["pharmacy_link"]
    driver = await asyncio.to_thread(init_driver)
    scraped_products = []  # Store new scraped products
    count = 0
    try:
        for i in range(0, 100):  # Scrape multiple pages
            num = 20 * i
            page_url = f"https://www.medigoapp.com{pharmacy_link}?from={num}" if i > 0 else f"https://www.medigoapp.com{pharmacy_link}"
            driver.get(page_url)
            await asyncio.sleep(5)  # Wait for content to load
            pharmacy_soup = BeautifulSoup(driver.page_source, 'html.parser')

            pharmacy_items = pharmacy_soup.find_all('div', class_='grid-products-item cursor-pointer px-1 pb-2 pb-md-0 px-md-2')
            if not pharmacy_items:
                break  # Stop when there are no more products

            for item in pharmacy_items:
                product_div = item.find('a')
                product_link = product_div.get('href')
                if not product_link:
                    continue

                medicine_name = product_div.text.strip()
                # Skip if product already exists
                if any(p["medicine_name"] == medicine_name and p["pharmacy_name"] == pharmacy_name for p in existing_products):
                    print(f"Skipping already scraped product: {medicine_name}")
                    continue

                driver.get(f"https://www.medigoapp.com{product_link}")
                await asyncio.sleep(5)  # Wait for product page to load
                product_soup = BeautifulSoup(driver.page_source, 'html.parser')
                product_image_div = product_soup.find('div', class_='d-none d-md-flex d-lg-flex')
                product_info_div = product_soup.find('table')
                medicine_info = {}
                if product_info_div != None:
                    product_infos = product_info_div.find_all('tr')
                    if product_infos:                   
                        for product_info in product_infos:
                            product_info_cate = product_info.find_all('td')
                            product_info_key = product_info_cate[0].text.strip()
                            product_info_value = product_info_cate[1].text.strip()
                            medicine_info[product_info_key] = product_info_value
                # Extract product information
                product = {
                    "pharmacy_name": pharmacy_name,
                    "medicine_name": medicine_name,
                    "images": [img.get('src') for img in product_image_div.find_all('img') ],
                    "medicine_info": medicine_info,
                    "medicine_description": str(product_soup.find('div', class_='col-sm-12 entry-content py-0'))
                }
                # Append new product
                append_to_json(product)
                count += 1
                print(num)
                print(count)
                print(f"Scraped: {medicine_name}")
                print(product)
                print('-------------------------------------------------')

    except Exception as e:
        print(f"Error scraping {pharmacy_name}: {e}")
    finally:
        driver.quit()

    return scraped_products

# Asynchronous main function
async def main():
    # Load existing product data
    existing_products = load_existing_products()
    
    # Step 1: Scrape pharmacy list
    print("Scraping pharmacy list...")
    pharmacy_list = await scrape_pharmacy_list()
    
    # Save pharmacy list to JSON
    with open("medigo_pharmacy.json", "w", encoding="utf-8") as f:
        json.dump(pharmacy_list, f, ensure_ascii=False, indent=4)

    # Step 2: Scrape product details in batches of 3 pharmacies
    print("Scraping pharmacy products in batches of 20...")

    batch_size = 20
    for i in range(0, len(pharmacy_list), batch_size):
        batch = pharmacy_list[i:i + batch_size]
        tasks = [scrape_pharmacy_products(pharmacy, existing_products) for pharmacy in batch]
        results = await asyncio.gather(*tasks)

    

# Run the async program
if __name__ == "__main__":
    asyncio.run(main())