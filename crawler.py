import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Set, Dict, List
import time
import hashlib
import io

# PDF parsing imports
try:
    import PyPDF2
    PDF_PARSING_AVAILABLE = True
except ImportError:
    PDF_PARSING_AVAILABLE = False
    print("⚠️  PyPDF2 not found. Install with: pip install PyPDF2")

class WebCrawler:
  def __init__(self, allowed_domains: Set[str] = None, parse_pdfs: bool = False):
    self.visited_urls: Set[str] = set()
    self.session = requests.Session()
    self.delay = 1  # Delay between requests in seconds
    self.allowed_domains = allowed_domains or set()
    self.strict_domain = False
    self.parse_pdfs = parse_pdfs
    
    # Validate PDF parsing capability
    if self.parse_pdfs and not PDF_PARSING_AVAILABLE:
      raise ValueError("PDF parsing requested but PyPDF2 is not installed. Install with: pip install PyPDF2")
    
    # Add page-level cache
    self.page_cache: Dict[str, Dict] = {}

  def _get_page_cache_key(self, url: str) -> str:
    """Generate a cache key for individual pages."""
    return hashlib.md5(url.encode()).hexdigest()

  def _extract_pdf_text(self, pdf_content: bytes) -> str:
    """Extract text from PDF content."""
    if not PDF_PARSING_AVAILABLE:
      return ""
    
    try:
      pdf_file = io.BytesIO(pdf_content)
      pdf_reader = PyPDF2.PdfReader(pdf_file)
      
      text = ""
      for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() + "\n"
      
      return text.strip()
    except Exception as e:
      print(f"❌ Error extracting PDF text: {str(e)}")
      return ""

  def _is_pdf_url(self, url: str) -> bool:
    """Check if URL points to a PDF file."""
    parsed_url = urlparse(url)
    return parsed_url.path.lower().endswith('.pdf')

  def _extract_main_content(self, soup: BeautifulSoup, url: str) -> str:
    """
    Extract main content from HTML, filtering out headers, footers, navigation, ads, etc.
    """
    print(f"🧹 Filtering HTML content for: {url}")
    
    # Strategy 1: Remove unwanted elements by tag and class/id patterns
    unwanted_selectors = [
        # Navigation elements
        'nav', 'header', 'footer', '.nav', '.navigation', '.navbar', 
        '#navigation', '#nav', '.menu', '.main-menu',
        
        # Ads and promotional content
        '.ad', '.ads', '.advertisement', '.promo', '.promotion', 
        '.banner', '.sidebar-ads', '[class*="ad-"]', '[id*="ad-"]',
        '.google-ad', '.adsense', '.adsbygoogle',
        
        # Social media and sharing
        '.social', '.share', '.sharing', '.social-media', '.social-share',
        '.twitter', '.facebook', '.linkedin', '.instagram',
        
        # Comments sections (optional - remove if you want comments)
        '.comments', '.comment', '.user-comments', '#comments',
        
        # Other common non-content elements
        '.sidebar', '.side-bar', '.widget', '.widgets',
        '.breadcrumb', '.breadcrumbs', '.pagination',
        '.newsletter', '.subscription', '.subscribe',
        '.popup', '.modal', '.overlay',
        '.cookie', '.cookie-notice', '.cookie-banner',
        
        # Generic utility classes
        '.hidden', '.hide', '.invisible', '[style*="display:none"]',
        '.sr-only', '.screen-reader-text'
    ]
    
    # Remove unwanted elements
    removed_count = 0
    for selector in unwanted_selectors:
        elements = soup.select(selector)
        for element in elements:
            element.decompose()  # Completely remove from DOM
            removed_count += 1
    
    print(f"🗑️  Removed {removed_count} unwanted HTML elements")
    
    # Strategy 2: Try to identify main content area
    main_content = self._find_main_content_area(soup)
    
    if main_content:
        print(f"✅ Found main content area")
        content_text = main_content.get_text(separator=' ', strip=True)
    else:
        print(f"⚠️  No main content area found, using body")
        # Fallback: use body but with additional filtering
        body = soup.find('body')
        if body:
            content_text = body.get_text(separator=' ', strip=True)
        else:
            content_text = soup.get_text(separator=' ', strip=True)
    
    # Strategy 3: Clean up the extracted text
    content_text = self._clean_extracted_text(content_text)
    
    print(f"📏 Final HTML content length: {len(content_text)} characters")
    return content_text

  def _find_main_content_area(self, soup):
    """
    Try to identify the main content area using common patterns.
    """
    # Common selectors for main content areas (in order of preference)
    main_content_selectors = [
        'main',
        'article', 
        '.main-content',
        '.content',
        '.post-content',
        '.entry-content',
        '.article-content',
        '.page-content',
        '#main-content',
        '#content',
        '#main',
        '.container .content',
        '.wrapper .content'
    ]
    
    for selector in main_content_selectors:
        element = soup.select_one(selector)
        if element:
            # Check if this element has substantial content
            text_length = len(element.get_text(strip=True))
            if text_length > 200:  # Minimum content threshold
                print(f"🎯 Found main content using selector: {selector}")
                return element
    
    # If no main content area found, try to find the largest text block
    return self._find_largest_content_block(soup)

  def _find_largest_content_block(self, soup):
    """
    Find the HTML element with the most text content (likely the main content).
    """
    candidates = soup.find_all(['div', 'section', 'article', 'main'])
    
    best_candidate = None
    best_score = 0
    
    for candidate in candidates:
        # Calculate content score based on text length and structure
        text_length = len(candidate.get_text(strip=True))
        
        # Bonus for semantic HTML elements
        tag_bonus = 0
        if candidate.name in ['article', 'main', 'section']:
            tag_bonus = 100
        
        # Penalty for likely non-content areas
        class_penalty = 0
        classes = ' '.join(candidate.get('class', []))
        if any(word in classes.lower() for word in ['sidebar', 'nav', 'header', 'footer', 'ad']):
            class_penalty = 500
        
        score = text_length + tag_bonus - class_penalty
        
        if score > best_score and text_length > 200:
            best_score = score
            best_candidate = candidate
    
    if best_candidate:
        print(f"🔍 Found largest content block with score: {best_score}")
    
    return best_candidate

  def _clean_extracted_text(self, text: str) -> str:
    """
    Clean and normalize the extracted text content (works for both HTML and PDF).
    """
    import re
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common navigational text patterns
    nav_patterns = [
        r'Home\s*>\s*',
        r'Skip to (?:main )?content',
        r'Menu\s*Toggle',
        r'Search\s*for:',
        r'Categories?\s*:',
        r'Tags?\s*:',
        r'Share\s*this\s*(?:post|article|page)',
        r'Follow\s*us\s*on',
        r'Subscribe\s*to\s*our',
        r'Cookie\s*(?:Policy|Notice)',
        r'Privacy\s*Policy',
        r'Terms\s*(?:of\s*(?:Service|Use))?',
        r'Copyright\s*©',
        r'All\s*rights\s*reserved'
    ]
    
    for pattern in nav_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Final cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

  def _clean_pdf_text(self, pdf_text: str, url: str) -> str:
    """
    Clean and filter PDF text content to remove headers, footers, page numbers, etc.
    """
    import re
    
    print(f"🧹 Filtering PDF content for: {url}")
    
    # Split into lines for processing
    lines = pdf_text.split('\n')
    cleaned_lines = []
    
    # Common PDF artifacts to remove
    pdf_artifacts = [
        # Page numbers (various formats)
        r'^\s*\d+\s*$',  # Just a number
        r'^\s*Page\s+\d+\s*$',  # "Page 1"
        r'^\s*\d+\s+of\s+\d+\s*$',  # "1 of 10"
        r'^\s*-\s*\d+\s*-\s*$',  # "- 1 -"
        
        # Headers/footers that repeat
        r'^\s*(?:confidential|proprietary|draft|internal)\s*$',
        
        # URLs at top/bottom of pages
        r'^(?:https?://|www\.)',
        
        # Email addresses in headers/footers
        r'^\s*[\w\.-]+@[\w\.-]+\.\w+\s*$',
        
        # Copyright notices
        r'^\s*©.*\d{4}',
        r'^\s*Copyright.*\d{4}',
        
        # Common footer text
        r'^\s*All rights reserved\s*$',
        r'^\s*Confidential and Proprietary\s*$',
    ]
    
    removed_lines = 0
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Check if line matches any artifact pattern
        is_artifact = False
        for pattern in pdf_artifacts:
            if re.match(pattern, line, re.IGNORECASE):
                is_artifact = True
                removed_lines += 1
                break
        
        # Skip very short lines (likely artifacts) unless they contain meaningful punctuation
        if len(line) < 3 and not any(punct in line for punct in ['.', '!', '?', ':']):
            is_artifact = True
            removed_lines += 1
        
        if not is_artifact:
            cleaned_lines.append(line)
    
    print(f"🗑️  Removed {removed_lines} PDF artifact lines")
    
    # Rejoin lines
    cleaned_text = ' '.join(cleaned_lines)
    
    # Apply general text cleaning
    cleaned_text = self._clean_extracted_text(cleaned_text)
    
    # Additional PDF-specific cleaning
    # Remove repeated headers/footers (text that appears multiple times)
    cleaned_text = self._remove_repeated_content(cleaned_text)
    
    print(f"📏 Final PDF content length: {len(cleaned_text)} characters")
    return cleaned_text

  def _remove_repeated_content(self, text: str) -> str:
    """
    Remove content that appears to be repeated headers/footers in PDFs.
    """
    import re
    
    # Split into sentences for analysis
    sentences = re.split(r'[.!?]+', text)
    sentence_counts = {}
    
    # Count occurrences of each sentence
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:  # Only count substantial sentences
            sentence_counts[sentence] = sentence_counts.get(sentence, 0) + 1
    
    # Find sentences that appear too frequently (likely headers/footers)
    repeated_sentences = []
    for sentence, count in sentence_counts.items():
        if count > 2 and len(sentence) < 100:  # Short sentences repeated many times
            repeated_sentences.append(sentence)
    
    # Remove repeated sentences
    for repeated in repeated_sentences:
        text = text.replace(repeated, '')
    
    if repeated_sentences:
        print(f"🔄 Removed {len(repeated_sentences)} repeated content patterns")
    
    return text

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
    # Start with empty path for root URL and no parent URL for the starting URL
    self._crawl_recursive(start_url, 0, max_depth, results, [], None)
    return results

  def _crawl_recursive(self, url: str, current_depth: int, max_depth: int, results: List[Dict], path: List[Dict], parent_url: str = None):
    # Recursively crawl pages up to max_depth.
    if (current_depth > max_depth or 
      url in self.visited_urls or 
      not self._should_crawl(url, parent_url)):
      return

    try:
      # Check if page is cached
      cache_key = self._get_page_cache_key(url)
      if cache_key in self.page_cache:
        print(f"💾 Cache hit for [Depth {current_depth}]: {url}")
        cached_page = self.page_cache[cache_key].copy()
        cached_page['depth'] = current_depth  # Update depth for current context
        cached_page['navigation_path'] = path.copy()  # Add navigation path
        results.append(cached_page)
        self.visited_urls.add(url)
        
        # Continue crawling links from cached page if not at max depth and not a PDF
        if current_depth < max_depth and not self._is_pdf_url(url):
          soup = BeautifulSoup(cached_page['html'], 'html.parser')
          current_page_info = {'url': url, 'title': cached_page['title']}
          self._crawl_links_from_soup(soup, url, current_depth, max_depth, results, path + [current_page_info])
        return

      print(f"🌐 Crawling [Depth {current_depth}]: {url}")
      time.sleep(self.delay)
      self.visited_urls.add(url)
      
      # Handle PDF files differently
      if self._is_pdf_url(url):
        print(f"🔍 PDF DETECTED: {url}")
        print(f"📄 Starting PDF scraping process...")
        self._process_pdf(url, current_depth, results)
        return
      
      # Make request for HTML content
      response = self.session.get(url, timeout=15)
      if response.status_code != 200:
        print(f"❌ Failed to fetch {url}: Status code {response.status_code}")
        return
      
      soup = BeautifulSoup(response.text, 'html.parser')
      page_title = soup.title.string if soup.title else 'No Title'
      
      print(f"✅ Successfully scraped: {page_title}")
      
      # Extract main content with filtering
      clean_text = self._extract_main_content(soup, url)
      
      # Create page data
      page_data = {
        'url': url,
        'title': page_title,
        'html': response.text,
        'text': clean_text,  # Use filtered content instead of soup.get_text()
        'depth': current_depth,
        'content_type': 'html',
        'navigation_path': path.copy()
      }
      
      # Cache the page (without depth and path since they can vary)
      cache_data = page_data.copy()
      del cache_data['depth']
      del cache_data['navigation_path']
      self.page_cache[cache_key] = cache_data
      
      # Store page data
      results.append(page_data)
      
      # Only continue if we haven't reached max depth
      if current_depth < max_depth:
        current_page_info = {'url': url, 'title': page_title}
        self._crawl_links_from_soup(soup, url, current_depth, max_depth, results, path + [current_page_info])
                
    except Exception as e:
      print(f"❌ Error crawling {url}: {str(e)}")

  def _process_pdf(self, url: str, current_depth: int, results: List[Dict]):
    """Process a PDF file."""
    try:
      print(f"📄 Processing PDF [Depth {current_depth}]: {url}")
      
      # Download PDF content
      response = self.session.get(url, timeout=30)
      if response.status_code != 200:
        print(f"❌ Failed to download PDF {url}: Status code {response.status_code}")
        return
      
      # Extract text from PDF
      pdf_text = self._extract_pdf_text(response.content)
      
      if not pdf_text:
        print(f"⚠️  No text extracted from PDF: {url}")
        return
      
      # Clean and filter PDF text
      clean_pdf_text = self._clean_pdf_text(pdf_text, url)
      
      # Get PDF title from URL or content
      pdf_title = url.split('/')[-1].replace('.pdf', '') or 'PDF Document'
      
      print(f"✅ Successfully extracted text from PDF: {pdf_title}")
      print(f"📊 Extracted {len(clean_pdf_text)} characters from {url}")
      
      # Create page data for PDF
      page_data = {
        'url': url,
        'title': pdf_title,
        'html': '',  # PDFs don't have HTML
        'text': clean_pdf_text,  # Use cleaned PDF text
        'depth': current_depth,
        'content_type': 'pdf',
        'navigation_path': path.copy()  # Add navigation path for PDFs too
      }
      
      # Cache the PDF data
      cache_key = self._get_page_cache_key(url)
      cache_data = page_data.copy()
      del cache_data['depth']
      self.page_cache[cache_key] = cache_data
      
      # Store PDF data
      results.append(page_data)
      
    except Exception as e:
      print(f"❌ Error processing PDF {url}: {str(e)}")

  def _should_crawl(self, url: str, current_url: str = None) -> bool:
    """
    Determine if URL should be crawled based on various rules.
    Now includes domain filtering with external link allowance.
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Check URL scheme
        if parsed_url.scheme not in ('http', 'https'):
            return False
        
        # Domain filtering logic
        if self.allowed_domains:
            is_internal_domain = self._is_internal_domain(domain)
            
            if is_internal_domain:
                # Always allow internal domains
                pass
            else:
                # External domain - only allow if we're coming from an internal domain
                if current_url:
                    current_parsed = urlparse(current_url)
                    current_domain = current_parsed.netloc.lower()
                    is_current_internal = self._is_internal_domain(current_domain)
                    
                    if not is_current_internal:
                        # We're on an external domain, don't crawl more external links
                        return False
                else:
                    # No current URL context, block external domains
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
        
        # Handle PDF files
        if parsed_url.path.lower().endswith('.pdf'):
            return self.parse_pdfs  # Only allow PDFs if PDF parsing is enabled
            
        # Ignore common non-HTML extensions (excluding PDF when PDF parsing is enabled)
        ignored_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.doc', 
            '.docx', '.ppt', '.pptx', '.zip', '.tar', '.gz',
            '.mp4', '.avi', '.mov', '.mp3', '.wav', '.exe'
        ]
        
        # Add PDF to ignored extensions only if PDF parsing is disabled
        if not self.parse_pdfs:
            ignored_extensions.append('.pdf')
        
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

  def _is_internal_domain(self, domain: str) -> bool:
    """Check if a domain is considered internal (allowed)."""
    if self.strict_domain:
        # In strict mode, domain must match exactly
        return domain in self.allowed_domains
    else:
        # Original behavior - allow subdomains
        for allowed_domain in self.allowed_domains:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                return True
        return False

  def _crawl_links_from_soup(self, soup: BeautifulSoup, url: str, current_depth: int, max_depth: int, results: List[Dict], path: List[Dict]):
    """Extract and crawl links from a BeautifulSoup object."""
    print(f"🔗 Looking for links on: {url}")
    
    # Check if current page is external
    parsed_current = urlparse(url)
    current_domain = parsed_current.netloc.lower()
    is_current_internal = self._is_internal_domain(current_domain)
    
    if not is_current_internal:
        print(f"🚫 On external domain {current_domain} - will not crawl any links from this page")
        return
    
    # Find all links
    links_found = 0
    external_links_found = 0
    
    for link in soup.find_all('a', href=True):
        next_url = urljoin(url, link['href'])
        
        # Check if this link is external
        parsed_next = urlparse(next_url)
        next_domain = parsed_next.netloc.lower()
        is_next_internal = self._is_internal_domain(next_domain)
        
        # Recursively crawl each valid link
        if self._should_crawl(next_url, url):  # Pass current URL for context
            links_found += 1
            if not is_next_internal:
                external_links_found += 1
                print(f"🌍 Following external link: {next_url}")
            
            self._crawl_recursive(
                next_url, 
                current_depth + 1, 
                max_depth, 
                results,
                path,  # Pass the current path
                url    # Pass current URL as parent_url
            )
    
    print(f"📊 Found {links_found} valid links to crawl from {url} ({external_links_found} external)")

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