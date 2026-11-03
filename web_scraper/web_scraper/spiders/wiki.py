import os
from urllib.parse import urlparse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.loader import ItemLoader
from web_scraper.items import WikimediaMediaItem


class WikiSpider(CrawlSpider):
    name = "wiki"
    allowed_domains = ["commons.wikimedia.org", "upload.wikimedia.org"]
    
    # Starting at both a Video category and an Image category
    start_urls = [
        "https://commons.wikimedia.org/wiki/Category:Videos_of_nature",
        "https://commons.wikimedia.org/wiki/Category:Featured_pictures_on_Wikimedia_Commons"
    ]

    custom_settings = {
        'ROTATING_PROXY_LIST': [
            # Add Wikimedia-specific proxies here
        ],
        # Prevent massive video files from timing out or getting dropped
        'DOWNLOAD_MAXSIZE': 104857600,  # 100 MB limit for learning/testing
        'DOWNLOAD_WARNSIZE': 52428800,  # 50 MB warning
    }

    # CrawlSpider Rules: Automatically extract and follow File pages and Subcategories
    rules = (
        # Rule 1: Visit individual media file pages and parse them
        Rule(
            LinkExtractor(
                allow=(r"/wiki/File:",),
                restrict_css=("#mw-category-media",)
            ),
            callback="parse_media_page",
            follow=False
        ),
        # Rule 2: Follow subcategory pagination up to depth limit (controlled in settings)
        Rule(
            LinkExtractor(
                allow=(r"/wiki/Category:",),
                restrict_css=("#mw-subcategories", "#mw-category-media")
            ),
            follow=True
        ),
    )

    def parse_media_page(self, response):
        """Extracts original high-res photo or video stream URL and metadata."""
        loader = ItemLoader(item=WikimediaMediaItem(), response=response)

        loader.add_value("page_url", response.url)
        loader.add_css("title", "h1#firstHeading span.mw-page-title-main::text")
        
        # Extract License & Author from the Commons metadata table
        loader.add_css(
            "author_or_source", 
            "td#fileinfotpl_aut + td ::text, td#fileinfotpl_src + td ::text"
        )
        loader.add_css(
            "license_info", 
            "span.licensetpl_short::text, div.layouttemplate a::text"
        )
        loader.add_css(
            "categories", 
            "div#mw-normal-catlinks ul li a::text"
        )

        # Locate the direct link to the original media file on upload.wikimedia.org
        original_media_url = (
            response.css("div.fullMedia a.internal::attr(href)").get()
            or response.css("div.fullImageLink a::attr(href)").get()
        )

        if original_media_url:
            full_media_url = response.urljoin(original_media_url)
            parsed_path = urlparse(full_media_url).path
            ext = os.path.splitext(parsed_path)[1].lower()
            loader.add_value("file_extension", ext)

            # Route videos (.webm, .ogv, .mpeg, .mp4) to FilesPipeline
            if ext in [".webm", ".ogv", ".ogg", ".mpeg", ".mpg", ".mp4"]:
                loader.add_value("media_type", "video")
                loader.add_value("file_urls", [full_media_url])
            # Route images (.jpg, .png, .svg, .tif) to ImagesPipeline
            elif ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"]:
                loader.add_value("media_type", "image")
                loader.add_value("image_urls", [full_media_url])

            yield loader.load_item()
