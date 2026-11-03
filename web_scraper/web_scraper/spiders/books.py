import scrapy
from scrapy.loader import ItemLoader
from web_scraper.items import BookItem


class BooksSpider(scrapy.Spider):
    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com"]
    custom_settings = {
        'ROTATING_PROXY_LIST': [
            # Add your proxy list here
        ],
    }

    def parse(self, response):
        """Tier 1 Callback: Extracts book links and handles pagination."""
        book_cards = response.css("article.product_pod")
        
        for card in book_cards:
            detail_rel_url = card.css("h3 a::attr(href)").get()
            yield response.follow(
                detail_rel_url,
                callback=self.parse_book_detail
            )

        # Follow pagination link
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_book_detail(self, response):
        """Tier 2 Callback: Uses ItemLoader to populate BookItem from detail page."""
        loader = ItemLoader(item=BookItem(), response=response)

        loader.add_value("url", response.url)
        loader.add_css("title", "div.product_main h1::text")
        loader.add_xpath(
            "category", 
            "//ul[@class='breadcrumb']/li[position()=3]/a/text()"
        )
        loader.add_css("star_rating", "p.star-rating::attr(class)")
        loader.add_xpath(
            "description", 
            "//div[@id='product_description']/following-sibling::p/text()"
        )

        # Product Information Table extraction via XPath
        loader.add_xpath("upc", "//th[text()='UPC']/following-sibling::td/text()")
        loader.add_xpath("product_type", "//th[text()='Product Type']/following-sibling::td/text()")
        loader.add_xpath("price_excl_tax", "//th[text()='Price (excl. tax)']/following-sibling::td/text()")
        loader.add_xpath("price_incl_tax", "//th[text()='Price (incl. tax)']/following-sibling::td/text()")
        loader.add_xpath("tax", "//th[text()='Tax']/following-sibling::td/text()")
        loader.add_xpath("availability", "//th[text()='Availability']/following-sibling::td/text()")
        loader.add_xpath("num_reviews", "//th[text()='Number of reviews']/following-sibling::td/text()")

        # Media extraction: Convert relative image URL to absolute URL for ImagesPipeline
        rel_img_url = response.css("div.item.active img::attr(src)").get()
        if rel_img_url:
            loader.add_value("image_urls", [response.urljoin(rel_img_url)])

        yield loader.load_item()