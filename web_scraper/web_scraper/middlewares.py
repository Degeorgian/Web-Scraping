import time
import logging
from datetime import datetime, timezone
import scrapy
from scrapy.downloadermiddlewares.retry import RetryMiddleware

logger = logging.getLogger(__name__)

class SmartNetworkDownloaderMiddleware(RetryMiddleware):
    """Handles response timing, custom headers, and 429 exponential backoff."""
    
    def process_request(self, request, spider):
        # Inject custom tracking header for API identification
        request.headers['X-Scraper-Project'] = 'GitHub-Showcase-Scraper'
        # Mark start time for proxy performance tracking
        request.meta['start_time'] = time.time()
        return None

    def process_response(self, request, response, spider):
        # Calculate and log slow proxy responses (threshold: 3 seconds)
        start_time = request.meta.get('start_time')
        if start_time:
            duration = time.time() - start_time
            if duration > 3.0:
                proxy = request.meta.get('proxy', 'Local IP')
                logger.warning(f"Slow response ({duration:.2f}s) from proxy {proxy} on {request.url}")

        # Intercept 429 Too Many Requests and trigger exponential backoff
        if response.status == 429:
            retries = request.meta.get('retry_times', 0)
            backoff_time = 2 ** retries  # Exponential: 1s, 2s, 4s, 8s
            logger.warning(f"429 Too Many Requests on {request.url}. Backing off for {backoff_time}s.")
            time.sleep(backoff_time)
            # Re-queue the request using the inherited RetryMiddleware logic
            return self._retry(request, '429 Too Many Requests', spider) or response

        return super().process_response(request, response, spider)


class ProvenanceAndValidationSpiderMiddleware:
    """Tags items with extraction metadata and filters malformed outputs."""
    
    def process_spider_output(self, response, result, spider):
        for element in result:
            # Enrich extracted Items with runtime metadata
            if isinstance(element, (dict, scrapy.Item)):
                # Validation: Drop items missing a primary URL identifier
                url = element.get('url') or element.get('page_url')
                if not url:
                    logger.error("Dropped malformed item missing primary URL.")
                    continue
                
                element['crawl_depth'] = response.meta.get('depth', 0)
                element['crawl_timestamp'] = datetime.now(timezone.utc).isoformat()
                element['original_status'] = response.status
                
                yield element
            
            # Pass outgoing pagination/media requests through untouched
            elif isinstance(element, scrapy.Request):
                yield element