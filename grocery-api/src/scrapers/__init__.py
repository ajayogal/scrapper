"""
Grocery store scrapers module
"""

from .aldi_scrapper import fetch_aldi_products_with_discount, parse_price as aldi_parse_price
from .iga_scrapper import fetch_iga_products, parse_price as iga_parse_price

__all__ = [
    'fetch_aldi_products_with_discount',
    'aldi_parse_price',
    'fetch_iga_products', 
    'iga_parse_price'
]