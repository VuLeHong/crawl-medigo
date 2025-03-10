import asyncio
import json
import random
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Initialize WebDriver for Selenium
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

async def scrape_pharmacy_products():
    driver = init_driver()  # No need for `await` since this is synchronous
    scraped_products = []  

    try:
        pharmacy_id = 258
        url = f"https://www.medigoapp.com/product/bang-ca-nhan-vai-do-dinh-cao-urgo-durable-hop-102-mieng.html?pharmacyId=258"
        driver.get(url)
        
        time.sleep(random.uniform(5, 10))  # Replace `await asyncio.sleep()`
        
        product_soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract product image
        product_image_div = product_soup.find('div', class_='d-none d-md-flex d-lg-flex')
        product_info_div = product_soup.find('table')

        # Extract medicine information
        medicine_info = {}
        if product_info_div:
            for row in product_info_div.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    medicine_info[key] = value

        # Extract JSON Data from `__NEXT_DATA__`
        script_tag = product_soup.find('script', id="__NEXT_DATA__")
        if not script_tag:
            raise ValueError("Could not find __NEXT_DATA__ script")

        parsed_data = json.loads(script_tag.text)
        json_div = json.loads(parsed_data["props"]["pageProps"]["product"])
        product_id = json_div.get("mId")

        if not product_id:
            raise ValueError("Could not extract product ID")

        # API request to fetch price & package details
        api_url = "https://production-api.medigoapp.com/es/pharmacy-inventory/item"
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://www.medigoapp.com",
            "referer": "https://www.medigoapp.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }
        data = {
            "pharmacyId": pharmacy_id,
            "productId": product_id,
            "location": {"lat": 10.79426667238426, "lon": 106.6988930691023}
        }

        response = requests.post(api_url, headers=headers, json=data)

        if response.status_code != 200:
            raise ValueError(f"API request failed with status {response.status_code}: {response.text}")

        info = response.json()
        package_info = info['_source']['mProduct']['dong_goi']
        money_info = info['_source']['mData']
        money_info_map = {item["mPackageId"]: item["mPrice"] for item in money_info}

        # Extract price and package details
        price_package = [
            {
                "name": f"{package['loai_dong_goi']['name'].capitalize()} {package['so_luong']} {package['don_vi']['name']}",
                "price": f"{money_info_map[package['id']]:,} đ".replace(",", ".")
            }
            for package in package_info if package["id"] in money_info_map
        ]

        # Extract ratings
        rating_div = product_soup.find('div', class_='d-flex flex-wrap mt-4 w-100')
        star_rating = {}
        if rating_div:
            average_div = rating_div.find('div', class_='d-flex flex-column mr-4')
            average = average_div.find('p').text if average_div else "N/A"
            stars_div = rating_div.find('div', class_='w-100')

            if stars_div:
                star_div = stars_div.find_all('div', class_='d-flex align-items-center mb-3')
                star_rating['average'] = average
                for i, star in enumerate(star_div[::-1], start=1):
                    star_rating[f"{i} star"] = star.find('b').text

        # Final product information
        product = {
            "images": [img.get('src') for img in product_image_div.find_all('img')] if product_image_div else [],
            "medicine_info": medicine_info,
            "medicine_description": str(product_soup.find('div', class_='col-sm-12 entry-content py-0')),
            "price_package": price_package,
            "star_rating": star_rating
        }

        scraped_products.append(product)
        print(json.dumps(product, indent=4, ensure_ascii=False))
        print('-' * 60)

    except Exception as e:
        print(f"Error scraping: {e}")

    finally:
        driver.quit()

    return scraped_products

# Run the async program properly
if __name__ == "__main__":
    asyncio.run(scrape_pharmacy_products())
