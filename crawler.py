import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Set, Dict, List
import time

class WebCrawler:
  def __init__(self, allowed_domains: Set[str] = None):
    self.visited_urls: Set[str] = set()
    self.session = requests.Session()
    self.delay = 1  # Delay between requests in seconds
    self.allowed_domains = allowed_domains or set()

  def crawl(self, start_url: str, max_depth: int = 3) -> List[Dict]:
    """
    Crawl website starting from given URL up to specified depth.
    
    Args:
      start_url: URL to start crawling from
      max_depth: Maximum depth of pages to crawl
        
    Returns: List of dictionaries containing page data
    """
    # Extract base domain from start URL and add to allowed domains
    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc.lower()
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
      time.sleep(self.delay)
      self.visited_urls.add(url)
      
      # Make request
      response = self.session.get(url, timeout=15)
      if response.status_code != 200:
        print(f"Failed to fetch {url}: Status code {response.status_code}")
        return
      
      soup = BeautifulSoup(response.text, 'html.parser')
      
      # Store page data
      results.append({
        'url': url,
        'title': soup.title.string if soup.title else '',
        'html': response.text,
        'text': soup.get_text(separator=' ', strip=True),
        'depth': current_depth
      })
      
      # Only continue if we haven't reached max depth
      if current_depth < max_depth:
        
        # Find all links
        for link in soup.find_all('a', href=True):
          next_url = urljoin(url, link['href'])

          # Recursively crawl each valid link
          if self._should_crawl(next_url):
            self._crawl_recursive(
              next_url, 
              current_depth + 1, 
              max_depth, 
              results
            )
                
    except Exception as e:
      print(f"Error crawling {url}: {str(e)}")

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