import os
import re
import json
import sqlite3
import logging
from twisted.enterprise import adbapi
from scrapy.exceptions import DropItem
from scrapy.pipelines.images import ImagesPipeline
from scrapy.pipelines.files import FilesPipeline
from scrapy.http import Request

logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """Removes invalid characters for safe OS file saving."""
    if not name:
        return "unknown"
    return re.sub(r'[^\w\-_\. ]', '_', name)

class DataCleaningPipeline:
    """Drops duplicates and ensures required fields are present."""
    
    def __init__(self):
        self.seen_upcs = set()
        self.seen_urls = set()

    def process_item(self, item, spider):
        # Books deduplication and validation
        if spider.name == 'books':
            upc = item.get('upc')
            if not upc:
                raise DropItem(f"Missing UPC in item: {item.get('url')}")
            if upc in self.seen_upcs:
                raise DropItem(f"Duplicate book dropped: {upc}")
            self.seen_upcs.add(upc)

        # Wikimedia deduplication and validation
        elif spider.name == 'wiki':
            url = item.get('page_url')
            if not url:
                raise DropItem("Missing page URL.")
            if url in self.seen_urls:
                raise DropItem(f"Duplicate media dropped: {url}")
            self.seen_urls.add(url)
            
            # Ensure at least one download link exists
            if not item.get('file_urls') and not item.get('image_urls'):
                raise DropItem(f"No media links found for {url}")

        return item


class CustomImagesPipeline(ImagesPipeline):
    """Downloads images and dynamically renames them based on item data."""
    
    def get_media_requests(self, item, info):
        # Pass the item inside the request meta so it can be accessed in file_path
        for image_url in item.get('image_urls', []):
            yield Request(image_url, meta={'item': item})

    def file_path(self, request, response=None, info=None, *, item=None):
        # Retrieve item from kwargs (Scrapy >= 2.4) or request meta
        item = item or request.meta.get('item')
        spider_name = getattr(info.spider, 'name', None)
        
        if spider_name == 'books':
            title = sanitize_filename(item.get('title'))
            upc = item.get('upc', 'no_upc')
            return f'book_covers/full/{upc}_{title}.jpg'
            
        elif spider_name == 'wiki':
            title = sanitize_filename(item.get('title'))
            ext = item.get('file_extension', '.jpg')
            return f'wikimedia_assets/images/{title}{ext}'
            
        # Fallback to default behavior
        return super().file_path(request, response, info, item=item)


class CustomFilesPipeline(FilesPipeline):
    """Downloads videos/audio and dynamically renames them."""
    
    def get_media_requests(self, item, info):
        for file_url in item.get('file_urls', []):
            yield Request(file_url, meta={'item': item})

    def file_path(self, request, response=None, info=None, *, item=None):
        item = item or request.meta.get('item')
        spider_name = getattr(info.spider, 'name', None)
        
        if spider_name == 'wiki' and item.get('media_type') == 'video':
            title = sanitize_filename(item.get('title'))
            ext = item.get('file_extension', '.webm')
            return f'wikimedia_assets/videos/{title}{ext}'
            
        return super().file_path(request, response, info, item=item)

class SQLitePipeline:
    """Lightweight local persistence for testing and GitHub showcases."""
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(sqlite_file=crawler.settings.get('SQLITE_FILE', 'data/wikimedia_books.db'))

    def __init__(self, sqlite_file):
        self.sqlite_file = sqlite_file

    def open_spider(self, spider):
        os.makedirs(os.path.dirname(self.sqlite_file), exist_ok=True)
        self.conn = sqlite3.connect(self.sqlite_file)
        self.cur = self.conn.cursor()
        
        # Create Tables
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                upc TEXT PRIMARY KEY, title TEXT, category TEXT, url TEXT,
                price_excl_tax REAL, availability INTEGER, star_rating INTEGER
            )
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS wiki_media (
                page_url TEXT PRIMARY KEY, title TEXT, media_type TEXT,
                file_extension TEXT, license_info TEXT, categories TEXT
            )
        """)
        self.conn.commit()

    def close_spider(self, spider):
        self.conn.close()

    def process_item(self, item, spider):
        if spider.name == 'books':
            self.cur.execute("""
                INSERT OR REPLACE INTO books (upc, title, category, url, price_excl_tax, availability, star_rating)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get('upc'), item.get('title'), item.get('category'), item.get('url'),
                item.get('price_excl_tax'), item.get('availability'), item.get('star_rating')
            ))
        elif spider.name == 'wiki':
            self.cur.execute("""
                INSERT OR REPLACE INTO wiki_media (page_url, title, media_type, file_extension, license_info, categories)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item.get('page_url'), item.get('title'), item.get('media_type'),
                item.get('file_extension'), item.get('license_info'), json.dumps(item.get('categories', []))
            ))
        self.conn.commit()
        return item


class PostgreSQLPipeline:
    """Production-grade asynchronous database insertion using Twisted adbapi."""
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(db_settings=crawler.settings.get('POSTGRES_DB_SETTINGS'))

    def __init__(self, db_settings):
        self.db_settings = db_settings

    def open_spider(self, spider):
        # Creates a non-blocking connection pool
        self.dbpool = adbapi.ConnectionPool('psycopg2', **self.db_settings)
        self.dbpool.runInteraction(self._create_tables)

    def _create_tables(self, tx):
        tx.execute("""
            CREATE TABLE IF NOT EXISTS books (
                upc TEXT PRIMARY KEY, title TEXT, category TEXT, url TEXT,
                price_excl_tax REAL, availability INTEGER, star_rating INTEGER
            )
        """)
        tx.execute("""
            CREATE TABLE IF NOT EXISTS wiki_media (
                page_url TEXT PRIMARY KEY, title TEXT, media_type TEXT,
                file_extension TEXT, license_info TEXT, categories TEXT
            )
        """)

    def close_spider(self, spider):
        self.dbpool.close()

    def process_item(self, item, spider):
        # Run DB query in a separate thread so it doesn't block Scrapy
        query = self.dbpool.runInteraction(self._insert_item, item, spider)
        query.addErrback(self._handle_error, item, spider)
        return item

    def _insert_item(self, tx, item, spider):
        if spider.name == 'books':
            tx.execute("""
                INSERT INTO books (upc, title, category, url, price_excl_tax, availability, star_rating)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (upc) DO UPDATE SET 
                    price_excl_tax = EXCLUDED.price_excl_tax,
                    availability = EXCLUDED.availability;
            """, (
                item.get('upc'), item.get('title'), item.get('category'), item.get('url'),
                item.get('price_excl_tax'), item.get('availability'), item.get('star_rating')
            ))
        elif spider.name == 'wiki':
            tx.execute("""
                INSERT INTO wiki_media (page_url, title, media_type, file_extension, license_info, categories)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (page_url) DO NOTHING;
            """, (
                item.get('page_url'), item.get('title'), item.get('media_type'),
                item.get('file_extension'), item.get('license_info'), json.dumps(item.get('categories', []))
            ))

    def _handle_error(self, failure, item, spider):
        logger.error(f"PostgreSQL insertion error: {failure}")   