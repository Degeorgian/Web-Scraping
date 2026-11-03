# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass


@dataclass
class WebScraperItem:
    # define the fields for your item here like:
    # name: str | None = None
    pass

# web_scraper/web_scraper/items.py
import re
import scrapy
from itemloaders.processors import MapCompose, TakeFirst, Join

def clean_price(value):
    """Strips currency symbols (£) and converts to float."""
    if value:
        return float(re.sub(r'[^\d.]', '', value))
    return 0.0

def parse_stock(value):
    """Extracts integer stock count from 'In stock (22 available)'."""
    if value:
        match = re.search(r'\d+', value)
        return int(match.group()) if match else 0
    return 0

def convert_rating(value):
    """Converts CSS class 'star-rating Three' into integer 3."""
    rating_map = {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5}
    if value:
        parts = value.split()
        return rating_map.get(parts[-1], 0)
    return 0


class BookItem(scrapy.Item):
    # Identifiers & Metadata
    upc = scrapy.Field(output_processor=TakeFirst())
    title = scrapy.Field(output_processor=TakeFirst())
    category = scrapy.Field(output_processor=TakeFirst())
    product_type = scrapy.Field(output_processor=TakeFirst())
    url = scrapy.Field(output_processor=TakeFirst())
    
    # Financials & Inventory (Cleaned via MapCompose)
    price_excl_tax = scrapy.Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    price_incl_tax = scrapy.Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    tax = scrapy.Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    availability = scrapy.Field(
        input_processor=MapCompose(str.strip, parse_stock),
        output_processor=TakeFirst()
    )
    
    # Content & Reviews
    star_rating = scrapy.Field(
        input_processor=MapCompose(convert_rating),
        output_processor=TakeFirst()
    )
    num_reviews = scrapy.Field(
        input_processor=MapCompose(int),
        output_processor=TakeFirst()
    )
    description = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=Join(" ")
    )

    # Scrapy ImagesPipeline Hooks (Must remain lists!)
    image_urls = scrapy.Field()
    images = scrapy.Field()
    crawl_depth = scrapy.Field()
    crawl_timestamp = scrapy.Field()
    original_status = scrapy.Field()


class WikimediaMediaItem(scrapy.Item):
    # Metadata
    title = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    page_url = scrapy.Field(output_processor=TakeFirst())
    media_type = scrapy.Field(output_processor=TakeFirst())  # 'video' or 'image'
    file_extension = scrapy.Field(output_processor=TakeFirst())
    author_or_source = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=Join(" ")
    )
    license_info = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst()
    )
    categories = scrapy.Field()  # Kept as a list of category tags

    # Scrapy FilesPipeline & ImagesPipeline Hooks (Must remain lists!)
    file_urls = scrapy.Field()   # Used for Video/Audio streams
    files = scrapy.Field()
    image_urls = scrapy.Field()  # Used for Photo assets
    images = scrapy.Field()
    crawl_depth = scrapy.Field()
    crawl_timestamp = scrapy.Field()
    original_status = scrapy.Field()