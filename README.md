# Advanced Scrapy Architecture: Books & Wikimedia

A production-grade web scraping project demonstrating advanced Scrapy features, including custom middlewares, media processing, asynchronous database orchestration, and proxy rotation. This repository contains two specialized spiders designed to handle distinct scraping paradigms: static product catalogs and deep-linked media repositories.

## Overview

*   **Books Spider (`books.toscrape.com`):** Utilizes standard Scrapy request structures and `ItemLoader` processors to extract structured product data, financial metrics, and high-resolution book covers.
*   **Wiki Spider (`commons.wikimedia.org`):** Utilizes Scrapy's `CrawlSpider` with `Rule` and `LinkExtractor` components to traverse categorical directories, extracting open-source video streams (`.webm`, `.ogv`) and high-resolution images.

## Key Features

*   **Asynchronous Dual-Database Persistence:** Implements a lightweight local SQLite database for rapid testing and a non-blocking PostgreSQL pipeline via Twisted's `adbapi` for production-grade `UPSERT` operations.
*   **Custom Media Pipelines:** Extends Scrapy's native `ImagesPipeline` and `FilesPipeline` to abandon default SHA1 hash naming, dynamically routing and labeling downloaded files based on scraped item metadata.
*   **Smart Network Middleware:** Custom `RetryMiddleware` subclass that intercepts `429 Too Many Requests` errors to trigger exponential backoff, while logging slow proxy response times.
*   **Provenance & Validation Middleware:** Intercepts spider outputs to validate data integrity (dropping items missing primary URLs) and injects crawl depth, HTTP status, and UTC timestamps before pipeline processing.
*   **Anti-Ban Mechanisms:** Integrates `scrapy-rotating-proxies` and `scrapy-fake-useragent` to distribute traffic across proxy pools and prevent browser fingerprinting.

## Prerequisites

*   Python 3.10+
*   PostgreSQL (Local or Remote)
*   Git

## Installation & Setup

1. **Clone the repository and create a virtual environment:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install scrapy scrapy-rotating-proxies scrapy-fake-useragent Pillow psycopg2-binary twisted python-dotenv
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory (at the same level as `scrapy.cfg`) to securely store your database credentials. 
   ```env
   POSTGRES_HOST=localhost
   POSTGRES_DB=scraper_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_password
   POSTGRES_PORT=5432
   ```
   *Note: Do not commit the `.env` file to version control. It is already included in the `.gitignore`.*

## Architecture & Data Flow

1. **Extraction (Spiders):** Network responses are parsed via XPaths and CSS selectors. Data is passed into `ItemLoader` classes where input/output processors (like `MapCompose` and `TakeFirst`) instantly clean strings, cast floats, and extract regex patterns.
2. **Spider Middleware:** Intercepts the cleaned items, verifies the presence of required fields, and tags the payload with crawl metadata.
3. **Pipelines:**
   *   `DataCleaningPipeline`: Tracks duplicate UPCs and URLs, dropping redundancies.
   *   `CustomImagesPipeline` / `CustomFilesPipeline`: Intercepts media URLs, downloads the assets asynchronously, and writes them to local disk with human-readable filenames.
   *   `SQLitePipeline`: Writes structured data to a local `.db` file.
   *   `PostgreSQLPipeline`: Executes asynchronous, non-blocking inserts and updates to the production database pool.

## Usage

**Run the Books Spider:**
```bash
scrapy crawl books
```

**Run the Wikimedia Spider:**
```bash
scrapy crawl wiki
```

**Testing & Debugging:**
To limit the scrape during testing, use the `CLOSESPIDER_ITEMCOUNT` flag, which safely terminates the spider after retrieving a specified number of items:
```bash
scrapy crawl books -s CLOSESPIDER_ITEMCOUNT=10 -O output_test.json
```