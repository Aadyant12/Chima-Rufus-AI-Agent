import os
from typing import List, Dict, Union
import hashlib
import json
from crawler import WebCrawler
from urllib.parse import urlparse, urlunparse

class RufusClient:
  def __init__(self, parse_pdfs: bool = False, max_depth: int = 3, strict_domain: bool = False):
    self.parse_pdfs = parse_pdfs
    self.max_depth = max_depth
    self.strict_domain = strict_domain
    self.crawler = WebCrawler(parse_pdfs=parse_pdfs)
    
    # Initialize cache for storing scraped results
    self.crawl_cache = {}  # Cache for raw crawled pages
    
    if parse_pdfs:
      print("📄 PDF parsing enabled - PDFs will be processed during crawling")

  def _generate_cache_key(self, url: str, max_depth: int, strict_domain: bool) -> str:
    """Generate a unique cache key for crawl parameters."""
    # Normalize URL before generating cache key
    normalized_url = self._normalize_url(url)
    cache_data = {
      'url': normalized_url,  # Use normalized URL
      'max_depth': max_depth,
      'strict_domain': strict_domain,
      'parse_pdfs': self.parse_pdfs
    }
    cache_string = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_string.encode()).hexdigest()

  def scrape(self, url: str, max_depth: int = None, strict_domain: bool = None) -> List[Dict]:
    """
    Scrape all content from a website up to the specified depth.
    
    url: Starting URL to scrape
    max_depth: Maximum depth for recursive crawling (overrides instance value if provided)
    strict_domain: If True, only crawl within the exact subdomain of the starting URL (overrides instance value if provided)
    
    Returns: List of all scraped pages with their content and links
    """
    try:
      # Use instance values if method parameters are not provided
      max_depth = max_depth if max_depth is not None else self.max_depth
      strict_domain = strict_domain if strict_domain is not None else self.strict_domain

      print(f"\n🚀 STARTING RUFUS WEB SCRAPING")
      print(f"🎯 Target URL: {url}")
      print(f"🔍 Max Depth: {max_depth}")
      print(f"🔒 Strict Domain Mode: {'ON' if strict_domain else 'OFF'}")
      print(f"📄 PDF Parsing: {'ON' if self.parse_pdfs else 'OFF'}")
      print(f"{'='*60}")
      
      # Generate cache key
      crawl_cache_key = self._generate_cache_key(url, max_depth, strict_domain)
      
      # Check if we have cached crawl results
      if crawl_cache_key in self.crawl_cache:
        print(f"💾 CACHE HIT! Using cached crawl results")
        pages = self.crawl_cache[crawl_cache_key]
        # Ensure HTML is removed from cached results too
        pages = self._remove_html_from_results(pages)
        print(f"✅ Retrieved {len(pages)} cached pages")
        print(f"🌐 From {len(set(page['url'] for page in pages))} unique sources")
        print(f"{'='*60}")
        return pages
      
      # Crawl the website and cache results
      print(f"\n🕷️  STARTING WEB CRAWLING...")
      pages = self.crawler.crawl(url, max_depth=max_depth, strict_domain=strict_domain)
      print(f"✅ Crawling completed! Found {len(pages)} pages")
      
      # REMOVE HTML FROM ALL RESULTS - Ensure HTML is never returned
      pages = self._remove_html_from_results(pages)
      
      # Cache the crawl results (store cleaned results)
      self.crawl_cache[crawl_cache_key] = pages
      print(f"💾 Cached {len(pages)} pages for future use")
      
      print(f"\n📈 SCRAPING SUMMARY:")
      print(f"📄 Total pages scraped: {len(pages)}")
      print(f"🌐 Unique sources: {len(set(page['url'] for page in pages))}")
      
      # Count content types
      html_pages = sum(1 for page in pages if page.get('content_type', 'html') == 'html')
      pdf_pages = sum(1 for page in pages if page.get('content_type', 'html') == 'pdf')
      print(f"📝 HTML pages: {html_pages}")
      print(f"📄 PDF pages: {pdf_pages}")
      
      # Calculate total content length
      total_content_length = sum(len(page.get('text', '')) for page in pages)
      print(f"📏 Total content length: {total_content_length:,} characters")
      
      # Calculate total content links
      total_content_links = sum(len(page.get('content_links', [])) for page in pages)
      if total_content_links > 0:
        print(f"🔗 Total content links extracted: {total_content_links}")
        # Count internal vs external links
        all_links = []
        for page in pages:
          all_links.extend(page.get('content_links', []))
        internal_links = sum(1 for link in all_links if link.get('type', '').startswith('internal'))
        external_links = len(all_links) - internal_links
        print(f"   📊 {internal_links} internal, {external_links} external links")
      
      print(f"{'='*60}")
      
      return pages
        
    except Exception as e:
      print(f"❌ ERROR: Scraping failed - {str(e)}")
      raise RufusError(f"Scraping failed: {str(e)}")
  
  def get_cache_info(self) -> Dict:
    """Get information about the current cache state."""
    crawler_info = self.crawler.get_cache_info()
    return {
      'crawl_cache_entries': len(self.crawl_cache),
      'total_cached_pages': sum(len(pages) for pages in self.crawl_cache.values()),
      'crawler_cached_pages': crawler_info['cached_pages'],
      'crawler_visited_urls': crawler_info['visited_urls']
    }
  
  def clear_cache(self):
    """Clear all cached data."""
    self.crawl_cache.clear()
    self.crawler.clear_cache()  # Also clear crawler's page cache
    print("🗑️  All caches cleared successfully")

  def _remove_html_from_results(self, pages: List[Dict]) -> List[Dict]:
    """Remove HTML from all pages in results to prevent it from being returned."""
    cleaned_pages = []
    for page in pages:
      # Create a copy of the page without HTML
      cleaned_page = {k: v for k, v in page.items() if k != 'html'}
      cleaned_pages.append(cleaned_page)
    return cleaned_pages

  def _normalize_url(self, url: str) -> str:
    """
    Normalize URL to avoid duplicates from:
    - Fragment identifiers (#section)
    - Trailing slashes
    - Common index files (index.php, index.html)
    - Case differences in domain
    """
    parsed = urlparse(url)
    
    # Convert domain to lowercase
    netloc = parsed.netloc.lower()
    
    # Remove fragment
    fragment = ''
    
    # Normalize path
    path = parsed.path
    
    # Remove trailing slash unless it's the root path
    if path.endswith('/') and len(path) > 1:
        path = path.rstrip('/')
    
    # Handle common index files
    index_files = ['/index.php', '/index.html', '/index.htm']
    for index_file in index_files:
        if path.endswith(index_file):
            # Remove index file, but keep the directory path
            path = path[:-len(index_file)]
            # If path is empty, make it root
            if not path:
                path = '/'
            break
    
    # If path is empty, make it root
    if not path:
        path = '/'
    
    # Reconstruct URL without fragment
    normalized = urlunparse((
        parsed.scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        fragment
    ))
    
    return normalized

class RufusError(Exception):
  """Custom exception class for Rufus-specific errors."""
  pass