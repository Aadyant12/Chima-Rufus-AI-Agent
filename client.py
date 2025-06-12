import os
from typing import List, Dict, Union
import hashlib
import json
from crawler import WebCrawler
from extractor import ContentExtractor
from urllib.parse import urlparse, urlunparse

class RufusClient:
  def __init__(self, chunk_size: int = 1024, similarity_threshold: float = 0.6, parse_pdfs: bool = False, max_depth: int = 3, strict_domain: bool = False):
    self.parse_pdfs = parse_pdfs
    self.max_depth = max_depth
    self.strict_domain = strict_domain
    self.crawler = WebCrawler(parse_pdfs=parse_pdfs)
    self.extractor = ContentExtractor(chunk_size=chunk_size, similarity_threshold=similarity_threshold)
    
    # Initialize cache for storing scraped results
    self.crawl_cache = {}  # Cache for raw crawled pages
    self.extraction_cache = {}  # Cache for processed extraction results
    
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
  
  def _generate_extraction_cache_key(self, crawl_cache_key: str, instructions: str) -> str:
    """Generate a unique cache key for extraction parameters."""
    cache_data = {
      'crawl_key': crawl_cache_key,
      'instructions': instructions.lower().strip()
    }
    cache_string = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_string.encode()).hexdigest()

  def scrape(self, url: str, instructions: str, max_depth: int = None, strict_domain: bool = None) -> Union[Dict, List[Dict]]:
    """
    Scrape and synthesize content from a website based on instructions.
    
    url: Starting URL to scrape
    instructions: User instructions for content extraction
    max_depth: Maximum depth for recursive crawling (overrides instance value if provided)
    strict_domain: If True, only crawl within the exact subdomain of the starting URL (overrides instance value if provided)
    """
    try:
      # Use instance values if method parameters are not provided
      max_depth = max_depth if max_depth is not None else self.max_depth
      strict_domain = strict_domain if strict_domain is not None else self.strict_domain

      print(f"\n🚀 STARTING RUFUS WEB SCRAPING")
      print(f"🎯 Target URL: {url}")
      print(f"📋 Instructions: {instructions}")
      print(f"🔍 Max Depth: {max_depth}")
      print(f"🔒 Strict Domain Mode: {'ON' if strict_domain else 'OFF'}")
      print(f"{'='*60}")
      
      # Generate cache keys
      crawl_cache_key = self._generate_cache_key(url, max_depth, strict_domain)
      extraction_cache_key = self._generate_extraction_cache_key(crawl_cache_key, instructions)
      
      # Check if we have cached extraction results first
      if extraction_cache_key in self.extraction_cache:
        print(f"💾 CACHE HIT! Using cached extraction results")
        cached_result = self.extraction_cache[extraction_cache_key]
        print(f"✅ Retrieved {len(cached_result['documents'])} cached documents")
        print(f"🌐 From {len(cached_result['metadata']['sources'])} cached sources")
        print(f"{'='*60}")
        return cached_result
      
      # Check if we have cached crawl results
      if crawl_cache_key in self.crawl_cache:
        print(f"💾 PARTIAL CACHE HIT! Using cached crawl results")
        pages = self.crawl_cache[crawl_cache_key]
        print(f"✅ Retrieved {len(pages)} cached pages")
      else:
        # Crawl the website and cache results
        print(f"\n🕷️  STARTING WEB CRAWLING...")
        pages = self.crawler.crawl(url, max_depth=max_depth, strict_domain=strict_domain)
        print(f"✅ Crawling completed! Found {len(pages)} pages")
        
        # Cache the crawl results
        self.crawl_cache[crawl_cache_key] = pages
        print(f"💾 Cached {len(pages)} pages for future use")
      
      # Extract relevant content based on user instructions
      print(f"\n🧠 STARTING CONTENT EXTRACTION...")
      print(f"📊 Analyzing {len(pages)} pages for relevant content...")
      extracted_content = self.extractor.extract(
        pages=pages,
        instructions=instructions
      )
      
      print(f"\n📈 EXTRACTION SUMMARY:")
      print(f"✨ Found {len(extracted_content)} relevant chunks")
      print(f"🌐 From {len(set(doc['url'] for doc in extracted_content))} unique sources")
      print(f"{'='*60}")
      
      # Structure the result
      result = {
        'documents': extracted_content,
        'metadata': {
          'document_count': len(extracted_content),
          'sources': list(set(doc['url'] for doc in extracted_content))
        }
      }
      
      # Cache the extraction results
      self.extraction_cache[extraction_cache_key] = result
      print(f"💾 Cached extraction results for future use")
      
      return result
        
    except Exception as e:
      print(f"❌ ERROR: Scraping failed - {str(e)}")
      raise RufusError(f"Scraping failed: {str(e)}")
  
  def get_cache_info(self) -> Dict:
    """Get information about the current cache state."""
    crawler_info = self.crawler.get_cache_info()
    return {
      'crawl_cache_entries': len(self.crawl_cache),
      'extraction_cache_entries': len(self.extraction_cache),
      'total_cached_pages': sum(len(pages) for pages in self.crawl_cache.values()),
      'crawler_cached_pages': crawler_info['cached_pages'],
      'crawler_visited_urls': crawler_info['visited_urls']
    }
  
  def clear_cache(self):
    """Clear all cached data."""
    self.crawl_cache.clear()
    self.extraction_cache.clear()
    self.crawler.clear_cache()  # Also clear crawler's page cache
    print("🗑️  All caches cleared successfully")

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