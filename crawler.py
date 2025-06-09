import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Set, Dict, List
import time
import hashlib

class WebCrawler:
  def __init__(self, allowed_domains: Set[str] = None):
    self.visited_urls: Set[str] = set()
    self.session = requests.Session()
    self.delay = 1  # Delay between requests in seconds
    self.allowed_domains = allowed_domains or set()
    self.strict_domain = False
    
    # Add page-level cache
    self.page_cache: Dict[str, Dict] = {}

  def _get_page_cache_key(self, url: str) -> str:
    """Generate a cache key for individual pages."""
    return hashlib.md5(url.encode()).hexdigest()

  def crawl(self, start_url: str, max_depth: int = 3, strict_domain: bool = False) -> List[Dict]:
    """
    Crawl website starting from given URL up to specified depth.
    
    Args:
      start_url: URL to start crawling from
      max_depth: Maximum depth of pages to crawl
      strict_domain: If True, only crawl within the exact subdomain of the starting URL
        
    Returns: List of dictionaries containing page data
    """
    self.strict_domain = strict_domain
    
    # Reset visited URLs for each new crawl operation
    self.visited_urls.clear()
    
    # Extract base domain from start URL and add to allowed domains
    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc.lower()
    
    if strict_domain:
      # In strict mode, only allow the exact subdomain
      print(f"🔒 STRICT DOMAIN MODE: Only crawling {base_domain} and its sub-paths")
      self.allowed_domains = {base_domain}
    else:
      # Original behavior - allow domain variations
      self.allowed_domains = set()  # Reset allowed domains
      self.allowed_domains.add(base_domain)
      
      # Also allow the main domain without subdomain
      if base_domain.startswith('www.'):
        self.allowed_domains.add(base_domain[4:])
      elif not base_domain.startswith('www.'):
        self.allowed_domains.add(f'www.{base_domain}')
      
      # For unitedspinal.org, allow all subdomains
      if 'unitedspinal.org' in base_domain:
        self.allowed_domains.add('unitedspinal.org')
        self.allowed_domains.add('www.unitedspinal.org')
    
    results = []
    self._crawl_recursive(start_url, 0, max_depth, results)
    return results

  def _crawl_recursive(self, url: str, current_depth: int, max_depth: int, results: List[Dict]):
    # Recursively crawl pages up to max_depth.
    if (current_depth > max_depth or 
      url in self.visited_urls or 
      not self._should_crawl(url)):
      return

    try:
      # Check if page is cached
      cache_key = self._get_page_cache_key(url)
      if cache_key in self.page_cache:
        print(f"💾 Cache hit for [Depth {current_depth}]: {url}")
        cached_page = self.page_cache[cache_key].copy()
        cached_page['depth'] = current_depth  # Update depth for current context
        results.append(cached_page)
        self.visited_urls.add(url)
        
        # Continue crawling links from cached page if not at max depth
        if current_depth < max_depth:
          soup = BeautifulSoup(cached_page['html'], 'html.parser')
          self._crawl_links_from_soup(soup, url, current_depth, max_depth, results)
        return

      print(f"🌐 Crawling [Depth {current_depth}]: {url}")
      time.sleep(self.delay)
      self.visited_urls.add(url)
      
      # Make request
      response = self.session.get(url, timeout=15)
      if response.status_code != 200:
        print(f"❌ Failed to fetch {url}: Status code {response.status_code}")
        return
      
      soup = BeautifulSoup(response.text, 'html.parser')
      page_title = soup.title.string if soup.title else 'No Title'
      
      print(f"✅ Successfully scraped: {page_title}")
      
      # Create page data
      page_data = {
        'url': url,
        'title': page_title,
        'html': response.text,
        'text': soup.get_text(separator=' ', strip=True),
        'depth': current_depth
      }
      
      # Cache the page (without depth since depth can vary)
      cache_data = page_data.copy()
      del cache_data['depth']
      self.page_cache[cache_key] = cache_data
      
      # Store page data
      results.append(page_data)
      
      # Only continue if we haven't reached max depth
      if current_depth < max_depth:
        self._crawl_links_from_soup(soup, url, current_depth, max_depth, results)
                
    except Exception as e:
      print(f"❌ Error crawling {url}: {str(e)}")

  def _crawl_links_from_soup(self, soup: BeautifulSoup, url: str, current_depth: int, max_depth: int, results: List[Dict]):
    """Extract and crawl links from a BeautifulSoup object."""
    print(f"🔗 Looking for links on: {url}")
    
    # Find all links
    links_found = 0
    for link in soup.find_all('a', href=True):
      next_url = urljoin(url, link['href'])

      # Recursively crawl each valid link
      if self._should_crawl(next_url):
        links_found += 1
        self._crawl_recursive(
          next_url, 
          current_depth + 1, 
          max_depth, 
          results
        )
    
    print(f"📊 Found {links_found} valid links to crawl from {url}")

  def _should_crawl(self, url: str) -> bool:
    """
    Determine if URL should be crawled based on various rules.
    Now includes domain filtering to stay within allowed domains.
    """
    try:
      parsed_url = urlparse(url)
      domain = parsed_url.netloc.lower()
      
      # Check URL scheme
      if parsed_url.scheme not in ('http', 'https'):
        return False
      
      # Domain filtering - only crawl allowed domains
      if self.allowed_domains:
        domain_allowed = False
        
        if self.strict_domain:
          # In strict mode, domain must match exactly
          domain_allowed = domain in self.allowed_domains
        else:
          # Original behavior - allow subdomains
          for allowed_domain in self.allowed_domains:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
              domain_allowed = True
              break
        
        if not domain_allowed:
          return False
      
      # Exclude common social media and external platforms
      excluded_domains = [
        'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
        'youtube.com', 'tiktok.com', 'snapchat.com', 'pinterest.com',
        'reddit.com', 'tumblr.com', 'flickr.com', 'vimeo.com',
        'google.com', 'bing.com', 'yahoo.com', 'amazon.com',
        'apple.com', 'microsoft.com', 'adobe.com', 'paypal.com'
      ]
      
      for excluded in excluded_domains:
        if domain == excluded or domain.endswith('.' + excluded):
          return False
          
      # Ignore common non-HTML extensions
      ignored_extensions = [
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', 
        '.docx', '.ppt', '.pptx', '.zip', '.tar', '.gz',
        '.mp4', '.avi', '.mov', '.mp3', '.wav', '.exe'
      ]
      if any(parsed_url.path.lower().endswith(ext) for ext in ignored_extensions):
        return False
      
      # Skip common non-content paths
      ignored_paths = [
        '/api/', '/admin/', '/login/', '/logout/', '/register/',
        '/wp-admin/', '/wp-content/', '/node_modules/', '/assets/'
      ]
      if any(ignored_path in parsed_url.path.lower() for ignored_path in ignored_paths):
        return False
      
      return True
        
    except Exception:
      return False

  def get_cache_info(self) -> Dict:
    """Get information about the page cache."""
    return {
      'cached_pages': len(self.page_cache),
      'visited_urls': len(self.visited_urls)
    }
  
  def clear_cache(self):
    """Clear the page cache."""
    self.page_cache.clear()
    print("🗑️  WebCrawler cache cleared")