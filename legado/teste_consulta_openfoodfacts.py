# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 21:36:03 2026

@author: Bruno
"""

import requests

ean = "7894900700015"
url2 = "https://world.openfoodfacts.net/api/v3.6/product"


url = f"{url2}/{ean}.json"

try:
    print(f"buscando {ean} na Open Food Facts na url {url}...")
    response = requests.get(url, timeout=22)
    print(f"status: {response.status_code}")
    print(response)
    response.raise_for_status()
except requests.RequestException:
    print("deu ruim")
    
response.json()
