from bs4 import BeautifulSoup
import requests
import pandas as pd
import numpy as np  
import re
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import time
from langchain_experimental.text_splitter import SemanticChunker
from langchain.embeddings.openai import OpenAIEmbeddings  # Correct import

def clean_string(text):
    text = text.replace("\r\n", "\n")  # Replace \r\n with \n
    text = re.sub(r'\n+', '\n', text)  # Replace multiple newlines with a single \n
    text = re.sub(r' +', ' ', text)  # Replace multiple spaces with a single space
    text = "\n".join(line.strip() for line in text.split("\n"))  # Trim spaces around each line
    return text.strip()  # Trim leading/trailing spaces and newlines
pharmacy_list = []
for i in range(1, 19):
    if i == 1:
        url = 'https://www.medigoapp.com/danh-sach-nha-thuoc/tat-ca'
    else:
        url = 'https://www.medigoapp.com/danh-sach-nha-thuoc/tat-ca?page=' + str(i)
    res = requests.get(url)

    soup = BeautifulSoup(res.text, 'html')
    pharmacies_div = soup.find_all('p', class_='pharmacy-name mb-3 pt-2 align-items-center')
    output = []
    for pharmacy_div in pharmacies_div:
        pharmacy_link = pharmacy_div.find('a').get('href')
        pharmacy_name = pharmacy_div.find('b').text
        count = 0
        pharmacy_list.append({"pharmacy_name": pharmacy_name, "pharmacy_link": pharmacy_link})
        for i in range(0, 100):
            num = 20 * i
            driver = webdriver.Chrome()
            if i == 0:
                driver.get("https://www.medigoapp.com" + pharmacy_link)
            else:
                driver.get("https://www.medigoapp.com" + pharmacy_link + "?from=" + str(num))
            WebDriverWait(driver, 10)
            time.sleep(5)
            pharmacy_soup = BeautifulSoup(driver.page_source, 'html')
            driver.quit()
            pharmacy_item = pharmacy_soup.find_all('div', class_='grid-products-item cursor-pointer px-1 pb-2 pb-md-0 px-md-2')
            if len(pharmacy_item) == 0:
                break
            else:
                for item in pharmacy_item:
                    product = {}
                    product['pharmacy_name'] = pharmacy_name
                    product_div = item.find('a') 
                    product_link = product_div.get('href')
                    match = re.search(r'pharmacyId=(\d+)', product_link)
                    pharmacy_id = int(match.group(1))
                    medicine_name = product_div.text
                    driver = webdriver.Chrome()
                    driver.get("https://www.medigoapp.com" + product_link)
                    WebDriverWait(driver, 10)
                    time.sleep(5)
                    product_soup = BeautifulSoup(driver.page_source, 'html')
                    driver.quit()
                    product_image_div = product_soup.find('div', class_='d-none d-md-flex d-lg-flex')
                    images = []
                    print(medicine_name)
                    product['medicine_name'] = medicine_name
                    images_div = product_image_div.find_all('img') 
                    for image in images_div:
                        images.append(image.get('src'))
                    product_info_div = product_soup.find('table')
                    product_infos = product_info_div.find_all('tr')
                    medicine_info = {}
                    for product_info in product_infos:
                        product_info_cate = product_info.find_all('td')
                        product_info_key = product_info_cate[0].text
                        product_info_value = product_info_cate[1].text    
                        medicine_info[product_info_key] = product_info_value
                    medicine_description = product_soup.find('div', class_='col-sm-12 entry-content py-0')
                    script = product_soup.find('script', id="__NEXT_DATA__").text
                    parsed_data = json.loads(script)
                    json_div = json.loads(parsed_data["props"]["pageProps"]["product"])
                    product_id = json_div["mId"]
                    url = "https://production-api.medigoapp.com/es/pharmacy-inventory/item"
                    headers = {
                        "accept": "application/json, text/plain, */*",
                        "accept-language": "en-US,en;q=0.6",
                        "content-type": "application/json",
                        "origin": "https://www.medigoapp.com",
                        "priority": "u=1, i",
                        "referer": "https://www.medigoapp.com/",
                        "sec-ch-ua": '"Not(A:Brand";v="99", "Brave";v="133", "Chromium";v="133")',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "same-site",
                        "sec-gpc": "1",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
                    }

                    data = {
                        "pharmacyId": pharmacy_id,
                        "productId": product_id,
                        "location": {
                            "lat": 10.79426667238426,
                            "lon": 106.6988930691023
                        }
                    }
                    response = requests.post(url, headers=headers, json=data)
                    if(response.status_code != 200):
                        print("Error")
                    else:
                        info = response.json()
                        package_info = info['_source']['mProduct']['dong_goi']
                        money_info = info['_source']['mData']
                        money_info_map = {item["mPackageId"]: item["mPrice"] for item in money_info}
                        price_package = []
                        for package in package_info:
                            package_id = package["id"]
                            if package_id in money_info_map:
                                price = f"{money_info_map[package_id]:,} đ".replace(",", ".")
                                name = f"{package['loai_dong_goi']['name'].capitalize()} {package['so_luong']} {package['don_vi']['name']}"
                                price_package.append({"name": name, "price": price})
                        rating_div = product_soup.find('div', class_='d-flex flex-wrap mt-4 w-100')
                        star_rating = {}
                        if rating_div != None:
                            average_div = rating_div.find('div', class_='d-flex flex-column mr-4')
                            average = average_div.find('p').text
                            stars_div = rating_div.find('div', class_='w-100')
                            star_div = stars_div.find_all('div', class_='d-flex align-items-center mb-3')
                            star_rating['average'] = average
                            s = 5
                            for star in star_div:
                                star_number = star.find('b').text
                                star_rating[str(s)+' star'] = star_number
                                s -= 1
                        pharmacy_address = info['_source']['mPharmacy']['mPharmacyAddress']['mAddress']
                        product['images'] = images
                        product['medicine_info'] = medicine_info
                        product['medicine_description'] = medicine_description
                        product['price_package'] = price_package
                        product['star_rating'] = star_rating
                        product['pharmacy_address'] = pharmacy_address
                        count += 1
                        print(num)
                        print(count)
                        print(product)
                        print('-----------------------------------')
                        output.append(product)
        
        
output_file = "medigo_product.json"    
output_file1 = "medigo_pharmacy.json"
with open(output_file1, "w", encoding="utf-8") as f:
    json.dump(pharmacy_list, f, ensure_ascii=False, indent=4)                
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)