import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Set, Dict, List
import time

class WebCrawler:
    def __init__(self):
        """Initialize the web crawler with default configuration."""
        self.visited_urls: Set[str] = set()
        self.session = self._create_session()
        self.delay = 1  # Delay between requests in seconds

    def _create_session(self) -> requests.Session:
        """Create a requests session with basic configuration."""
        session = requests.Session()
        
        # Set user agent
        session.headers.update({
            'User-Agent': 'Rufus/1.0 (+https://github.com/yourusername/rufus)'
        })
        
        return session

    def crawl(self, start_url: str, max_depth: int = 3) -> List[Dict]:
        """
        Crawl website starting from given URL up to specified depth.
        
        Args:
            start_url: URL to start crawling from
            max_depth: Maximum depth of pages to crawl
            
        Returns:
            List of dictionaries containing page data
        """
        results = []
        self._crawl_recursive(start_url, 0, max_depth, results)
        return results

    def _crawl_recursive(
        self, 
        url: str, 
        current_depth: int, 
        max_depth: int, 
        results: List[Dict]
    ):
        """
        Recursively crawl pages up to max_depth.
        
        Args:
            url: Current URL to crawl
            current_depth: Current crawl depth
            max_depth: Maximum depth to crawl
            results: List to store crawled pages
        """
        if (current_depth > max_depth or 
            url in self.visited_urls or 
            not self._should_crawl(url)):
            return

        try:
            # Add delay between requests
            time.sleep(self.delay)
            
            # Mark URL as visited before making request
            self.visited_urls.add(url)
            
            # Make request
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch {url}: Status code {response.status_code}")
                return
            
            # Parse content
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
        
        Args:
            url: URL to check
            
        Returns:
            Boolean indicating if URL should be crawled
        """
        try:
            parsed_url = urlparse(url)
            
            # Check URL scheme
            if parsed_url.scheme not in ('http', 'https'):
                return False
                
            # Ignore common non-HTML extensions
            ignored_extensions = [
                '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', 
                '.docx', '.ppt', '.pptx', '.zip', '.tar', '.gz'
            ]
            if any(parsed_url.path.lower().endswith(ext) 
                   for ext in ignored_extensions):
                return False
            
            return True
            
        except Exception:
            return False