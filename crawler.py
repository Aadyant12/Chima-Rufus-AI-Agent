import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Set, Dict, List
import time
import hashlib
import io
import re
import copy
from collections import deque  # Add this import for the queue

# PDF parsing imports
# try:
import PyPDF2
PDF_PARSING_AVAILABLE = True
# except ImportError:
#     PDF_PARSING_AVAILABLE = False
#     print("⚠️  PyPDF2 not found. Install with: pip install PyPDF2")

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

  def _get_page_cache_key(self, url: str) -> str:
    """Generate a cache key for individual pages using normalized URL."""
    normalized_url = self._normalize_url(url)
    return hashlib.md5(normalized_url.encode()).hexdigest()

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

  def _extract_text_with_structure(self, element) -> str:
    """
    UNIVERSAL approach: Extract text with proper paragraph breaks from ANY HTML.
    The key is to treat every block-level element as a paragraph boundary.
    """
    if not hasattr(element, 'find_all'):
        return str(element).strip()
    
    # Block elements that should create paragraph breaks
    block_elements = {
        'p', 'div', 'section', 'article', 'header', 'footer', 'main',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
        'ul', 'ol', 'li', 'dl', 'dt', 'dd',
        'blockquote', 'pre', 'table', 'tr', 'td', 'th',
        'form', 'fieldset', 'legend', 'address'
    }
    
    def extract_recursive(elem):
        """Recursively extract text, adding breaks for block elements."""
        if not hasattr(elem, 'children'):
            # It's a text node
            text = str(elem).strip()
            return [text] if text else []
        
        result = []
        for child in elem.children:
            if hasattr(child, 'name'):
                # It's an HTML element
                if child.name in ['script', 'style']:
                    continue
                
                child_text = extract_recursive(child)
                if child_text:
                    if child.name in block_elements:
                        # Block element - wrap with paragraph breaks
                        result.extend(['', ''])  # Add blank lines before
                        result.extend(child_text)
                        result.extend(['', ''])  # Add blank lines after
                    else:
                        # Inline element - just add the text
                        result.extend(child_text)
            else:
                # It's a text node
                text = str(child).strip()
                if text:
                    result.append(text)
        
        return result
    
    # Extract all text parts
    text_parts = extract_recursive(element)
    
    # Join with single newlines, then clean up
    raw_text = '\n'.join(text_parts)
    
    # Clean up excessive newlines (convert 3+ newlines to exactly 2)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', raw_text)
    
    # Clean up spaces within lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
        cleaned_lines.append(cleaned_line)
    
    # Rejoin and final cleanup
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n\n\n+', '\n\n', result)  # Ensure max 2 consecutive newlines
    
    return result.strip()

  def _is_united_spinal_site(self, url: str) -> bool:
    """Check if the URL is from a United Spinal site that needs special handling."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    return 'unitedspinal.org' in domain

  def _extract_united_spinal_content(self, soup: BeautifulSoup, url: str) -> str:
    """Extract content from United Spinal sites using the universal method."""
    print(f"🏥 Extracting United Spinal content from: {url}")
    
    # Remove helper elements
    for element in soup.select('div.helpful, script, style'):
        element.decompose()
    
    # Find content div or fallback to body
    content_element = soup.select_one('div#content2col')
    if not content_element:
        content_element = soup.find('body')
    if not content_element:
        content_element = soup
    
    print(f"🎯 Using content element: {getattr(content_element, 'name', 'soup')}")
    
    # Use the universal extraction method
    content_text = self._extract_text_with_structure(content_element)
    
    # Apply standard cleaning
    content_text = self._clean_extracted_text_preserve_structure(content_text)
    
    print(f"📏 Final content length: {len(content_text)} characters")
    
    # Debug output - show paragraph structure
    paragraphs = content_text.split('\n\n')
    print(f"📝 Extracted {len(paragraphs)} paragraphs")
    for i, para in enumerate(paragraphs[:5]):  # Show first 5 paragraphs
        preview = para.replace('\n', ' ')[:100]
        print(f"  Para {i+1}: {preview}{'...' if len(preview) >= 100 else ''}")
    
    return content_text

  def _force_organization_breaks(self, text: str) -> str:
    """
    BRUTE FORCE: Add paragraph breaks before organization names.
    Look for specific patterns and force breaks.
    """
    # Common organization name patterns from the United Spinal example
    org_names = [
        'Ability Foundation',
        'All India Institute Of Physical Medicine',
        'Amar Jyoti Charitable Trust',
        'Association for People with Disability',
        'Association of Spine Surgeons of India',
        'Community Outreach Programme',
        'Helping Hand India',
        'Indian Spinal Injuries Centre',
        'Institute for the Physically Handicapped',
        'Mobility India',
        'National Centre for Promotion of Employment',
        'Pain & Stroke Rehab Center',
        'Samarthanam Trust for the Disabled',
        'Spinal Cord Society of West Bengal',
        'Spinal Injured Persons Association'
    ]
    
    # Add breaks before each organization name
    for org in org_names:
        # Use regex to add paragraph break before org name if it's not already there
        pattern = f'([a-z.])\s*({re.escape(org)})'
        replacement = r'\1\n\n\2'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Also add breaks before any text that looks like org names
    # Pattern: Word(s) + (Foundation|Institute|Trust|etc.)
    org_pattern = r'([a-z.])\s*([A-Z][^.]*(?:Foundation|Institute|Trust|Association|Centre|Center|Society|Hospital|Clinic|NGO))\b'
    text = re.sub(org_pattern, r'\1\n\n\2', text)
    
    return text

  def _extract_standard_content(self, soup: BeautifulSoup, url: str) -> str:
    """Updated standard content extraction with better paragraph handling."""
    main_content = self._find_main_content_area(soup, url)
    
    if main_content:
        content_text = self._extract_text_with_structure(main_content)
    else:
        # Fallback: use body
        body = soup.find('body')
        if body:
            content_text = self._extract_text_with_structure(body)
        else:
            content_text = self._extract_text_with_structure(soup)
    
    # Apply the same break-ensuring logic
    return self._clean_and_ensure_breaks(content_text)

  def _find_main_content_area(self, soup, url: str = None):
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

  def _remove_repeated_content(self, text: str) -> str:
    """Remove text that appears multiple times (likely headers/footers)."""
    # This method was missing - adding it to prevent errors
    return text

  def _clean_pdf_text(self, pdf_text: str, url: str) -> str:
    """
    Clean and filter PDF text content while preserving paragraph structure.
    """
    print(f"🧹 Filtering PDF content for: {url}")
    
    # FIRST: Extract URLs from the raw PDF text before cleaning removes them
    print(f"🔍 Raw PDF text length: {len(pdf_text)} characters")
    
    raw_urls = self._extract_urls_from_raw_text_improved(pdf_text)
    print(f"🔍 Found {len(raw_urls)} raw URLs before cleaning: {raw_urls}")
    
    # Split into lines for processing
    lines = pdf_text.split('\n')
    cleaned_lines = []
    
    # Common PDF artifacts to remove - IMPROVED to be less aggressive
    pdf_artifacts = [
        # Page numbers (various formats) - only match standalone page numbers
        r'^\s*\d+\s*$',  # Just a number on its own line
        r'^\s*Page\s+\d+\s*$',  # "Page 1"
        r'^\s*\d+\s+of\s+\d+\s*$',  # "1 of 10"
        r'^\s*-\s*\d+\s*-\s*$',  # "- 1 -"
        
        # Headers/footers that repeat - only very specific patterns
        r'^\s*(?:confidential|proprietary|draft|internal)\s*$',
        
        # Copyright notices - only if they're standalone
        r'^\s*©.*\d{4}\s*$',
        r'^\s*Copyright.*\d{4}\s*$',
        
        # Common footer text - only if standalone
        r'^\s*All rights reserved\s*$',
        r'^\s*Confidential and Proprietary\s*$',
    ]
    
    removed_lines = 0
    for line in lines:
        line_stripped = line.strip()
        
        # Check if line contains URLs - if so, ALWAYS keep it
        if self._line_contains_url(line_stripped):
            cleaned_lines.append(line_stripped)
            continue
            
        # Check if line matches any artifact pattern
        is_artifact = False
        for pattern in pdf_artifacts:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                is_artifact = True
                removed_lines += 1
                break
        
        # Only skip very short lines that don't contain URLs or meaningful punctuation
        if len(line_stripped) < 3 and not any(punct in line_stripped for punct in ['.', '!', '?', ':', '/', '@']):
            is_artifact = True
            removed_lines += 1
        
        if not is_artifact:
            cleaned_lines.append(line_stripped)
        elif not line_stripped:
            # Keep empty lines for paragraph structure
            cleaned_lines.append('')
    
    print(f"🗑️  Removed {removed_lines} PDF artifact lines")
    
    # Rejoin lines preserving paragraph structure
    cleaned_text = '\n'.join(cleaned_lines)
    print(f"🔍 Cleaned text length: {len(cleaned_text)} characters")
    
    # Apply general text cleaning - but preserve URLs and structure
    cleaned_text = self._clean_extracted_text_preserve_urls_and_structure(cleaned_text)
    
    # Re-inject URLs that were found in raw text if they're not already present
    cleaned_text = self._preserve_urls_in_cleaned_text_improved(cleaned_text, raw_urls)
    
    print(f"📏 Final PDF content length: {len(cleaned_text)} characters")
    return cleaned_text

  def _line_contains_url(self, line: str) -> bool:
    """Check if a line contains what looks like a URL.
    
    Uses high-recall/lower-precision patterns to identify potential URLs.
    We err on the side of keeping lines that might contain URLs, even if 
    this means occasionally keeping some non-URL text. This is preferable
    to accidentally removing valid URLs during PDF cleaning."""
    # Basic patterns to detect URLs in a line
    url_indicators = [
        r'https?://',
        r'www\.',
        r'\.[a-zA-Z]{2,6}/',  # domain with path
        r'\.pdf\b',  # PDF files
        r'\.html?\b',  # HTML files
        r'\.gov\b',  # Government domains
        r'\.org\b',  # Organization domains
        r'\.edu\b',  # Education domains
    ]
    
    for pattern in url_indicators:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False

  def _clean_extracted_text_preserve_urls_and_structure(self, text: str) -> str:
    """
    Clean and normalize the extracted text content while preserving URLs and paragraph structure.
    """
    # First normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Normalize spaces within lines (but preserve newlines)
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove excessive spaces within each line
        cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
        cleaned_lines.append(cleaned_line)
    
    text = '\n'.join(cleaned_lines)
    
    # Remove common navigational text patterns - but be careful not to remove URLs
    nav_patterns = [
        r'Skip to (?:main )?content',
        r'Menu\s*Toggle',
        r'Search\s*for:',
        r'Share\s*this\s*(?:post|article|page)(?!\S)',  # Don't match if followed by URL
        r'Follow\s*us\s*on(?!\S)',  # Don't match if followed by URL
        r'Subscribe\s*to\s*our(?!\S)',  # Don't match if followed by URL
        r'Cookie\s*(?:Policy|Notice)(?!\S)',
        r'Privacy\s*Policy(?!\S)',
        r'Terms\s*(?:of\s*(?:Service|Use))?(?!\S)',
        r'All\s*rights\s*reserved(?!\S)'
    ]
    
    for pattern in nav_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Clean up any resulting empty lines or excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
    text = text.strip()
    
    return text

  def _extract_urls_from_raw_text_improved(self, text: str) -> List[str]:
    """Extract URLs from raw text before cleaning - IMPROVED VERSION."""
    
    # More comprehensive URL patterns - FIXED
    url_patterns = [
        # Full HTTP/HTTPS URLs - more permissive
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        # www URLs - more permissive  
        r'www\.[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}[^\s<>"{}|\\^`\[\]]*',
        # FTP URLs
        r'ftp://[^\s<>"{}|\\^`\[\]]+',
        # Domain.extension patterns - FIXED bracket escaping for PDF links
        r'\b[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}[/\w\-._~:/?#\[\]@!$&\'()*+,;=%]*\.pdf\b',
        # Government and organization domains with paths - FIXED bracket escaping
        r'\b[a-zA-Z0-9][a-zA-Z0-9\-]*\.(?:gov|org|edu|com|net)[/\w\-._~:/?#\[\]@!$&\'()*+,;=%]*',
        # IP addresses - FIXED bracket escaping
        r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?[/\w\-._~:/?#\[\]@!$&\'()*+,;=%]*',
        # Email-like patterns that might be URLs
        r'\b[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}\b'
    ]
    
    found_urls = set()
    
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Clean trailing punctuation but be more careful
            url = re.sub(r'[.,;:!?)\]}]+$', '', match)
            
            # More lenient validation
            if (len(url) >= 4 and 
                url.count('.') >= 1 and 
                url.count('.') <= 15 and  # Increased limit
                not url.startswith('.') and
                not url.endswith('.') and
                not re.match(r'^\d+\.\d+(\.\d+)*$', url)):  # Skip version numbers
                
                found_urls.add(url)
    
    final_urls = list(found_urls)
    print(f"🔍 Found {len(final_urls)} URLs in raw text")
    return final_urls

  def _preserve_urls_in_cleaned_text_improved(self, cleaned_text: str, raw_urls: List[str]) -> str:
    """Re-inject URLs that may have been removed during cleaning - IMPROVED VERSION."""
    
    missing_urls = []
    for url in raw_urls:
        # Check if URL or a close variant is in cleaned text
        if (url not in cleaned_text and 
            url.replace('https://', '') not in cleaned_text and
            url.replace('http://', '') not in cleaned_text and
            url.replace('www.', '') not in cleaned_text):
            missing_urls.append(url)
    
    if missing_urls:
        print(f"🔗 Re-injecting {len(missing_urls)} URLs that were removed during cleaning")
        # Add missing URLs at the end with proper spacing
        cleaned_text += " " + " ".join(missing_urls)
    
    return cleaned_text

  def get_cache_info(self) -> Dict:
      """
      Get information about the page cache.
      
      Example:
          client.crawler.get_cache_info()
          # Returns: {'cached_pages': 10, 'visited_urls': 15}
      """
      return {
        'cached_pages': len(self.page_cache),
        'visited_urls': len(self.visited_urls)
      }
    
  def clear_cache(self):
      """
      Clear the page cache.
      
      Example:
          client.crawler.clear_cache()
          # Clears all cached pages and prints confirmation
      """
      self.page_cache.clear()
      print("🗑️  WebCrawler cache cleared")

  def _extract_content_links(self, soup: BeautifulSoup, url: str) -> List[Dict]:
    """
    Extract all links from the main content area of the page.
    
    Args:
        soup: BeautifulSoup object of the page
        url: Current page URL for resolving relative links
        
    Returns:
        List of dictionaries containing link information
    """
    print(f"🔗 Extracting links from main content area: {url}")
    
    # Find the main content area using the same logic as _extract_main_content
    main_content_element = None
    
    # Check if this is a United Spinal site that needs special handling
    if self._is_united_spinal_site(url):
        # Look for the specific content div
        main_content_element = soup.select_one('div#content2col')
    
    if not main_content_element:
        # Use the same main content finding logic
        main_content_element = self._find_main_content_area(soup, url)
    
    if not main_content_element:
        # Fallback to body
        main_content_element = soup.find('body')
    
    if not main_content_element:
        # Last resort - use the entire soup
        main_content_element = soup
    
    # Extract all links from the main content area
    content_links = []
    links_found = main_content_element.find_all('a', href=True)
    
    print(f"📊 Found {len(links_found)} links in main content area")
    
    for link in links_found:
        try:
            href = link.get('href', '').strip()
            if not href:
                continue
                
            # Resolve relative URLs
            absolute_url = urljoin(url, href)
            
            # Get link text
            link_text = link.get_text(strip=True)
            
            # Get any title attribute
            link_title = link.get('title', '').strip()
            
            # Parse the URL to get domain info
            parsed_link = urlparse(absolute_url)
            
            # Check if it's an internal or external link
            link_domain = parsed_link.netloc.lower()
            is_internal = self._is_internal_domain(link_domain)
            
            # Determine link type
            link_type = 'internal' if is_internal else 'external'
            
            # Check if it's a PDF
            if self._is_pdf_url(absolute_url):
                link_type += '_pdf'
            
            # Skip certain types of links (like javascript, mailto, etc.)
            if parsed_link.scheme in ['javascript', 'mailto', 'tel', 'ftp']:
                continue
                
            # Skip fragment-only links (anchors within the same page)
            if absolute_url.startswith('#') or (parsed_link.netloc == urlparse(url).netloc and 
                                              parsed_link.path == urlparse(url).path and 
                                              parsed_link.fragment and not parsed_link.query):
                continue
            
            link_info = {
                'url': absolute_url,
                'text': link_text,
                'title': link_title,
                'type': link_type,
                'domain': link_domain
            }
            
            content_links.append(link_info)
            
        except Exception as e:
            print(f"⚠️  Error processing link {href}: {str(e)}")
            continue
    
    # Remove duplicates based on URL
    unique_links = {}
    for link in content_links:
        url_key = link['url']
        if url_key not in unique_links:
            unique_links[url_key] = link
        else:
            # If we have a duplicate, keep the one with more text
            if len(link['text']) > len(unique_links[url_key]['text']):
                unique_links[url_key] = link
    
    final_links = list(unique_links.values())
    
    # Sort links by type (internal first) and then by text
    final_links.sort(key=lambda x: (x['type'] != 'internal', x['text'].lower()))
    
    print(f"✅ Extracted {len(final_links)} unique content links")
    if final_links:
        internal_count = sum(1 for link in final_links if link['type'].startswith('internal'))
        external_count = len(final_links) - internal_count
        print(f"   📊 {internal_count} internal, {external_count} external links")
    
    return final_links

  def _extract_urls_from_text(self, text: str, source_url: str) -> List[Dict]:
    """
    Extract URLs from plain text content (useful for PDFs and other text sources) - IMPROVED VERSION.
    """
    print(f"🔗 Extracting URLs from text content of: {source_url}")
    
    # Use the improved URL extraction method
    found_urls = self._extract_urls_from_raw_text_improved(text)
    
    # Convert to list and create link info dictionaries
    content_links = []
    for url in found_urls:
        try:
            # Add protocol if missing
            processed_url = url
            if not processed_url.startswith(('http://', 'https://', 'ftp://')):
                processed_url = 'https://' + processed_url
            
            parsed_link = urlparse(processed_url)
            
            # Skip if parsing failed
            if not parsed_link.netloc:
                continue
                
            link_domain = parsed_link.netloc.lower()
            
            # Check if it's an internal or external link
            is_internal = self._is_internal_domain(link_domain)
            
            # Determine link type
            link_type = 'internal' if is_internal else 'external'
            
            # Check if it's a PDF - improved detection
            if (processed_url.lower().endswith('.pdf') or 
                '.pdf' in processed_url.lower() or
                self._is_pdf_url(processed_url)):
                link_type += '_pdf'
            
            link_info = {
                'url': processed_url,
                'text': url,  # Keep original text as found
                'title': '',  # No title available from plain text
                'type': link_type,
                'domain': link_domain
            }
            
            content_links.append(link_info)
            
        except Exception as e:
            print(f"⚠️  Error processing extracted URL {url}: {str(e)}")
            continue
    
    # Sort links by type (internal first) and then by URL
    content_links.sort(key=lambda x: (x['type'] != 'internal', x['url'].lower()))
    
    print(f"✅ Extracted {len(content_links)} URLs from text content")
    if content_links:
        internal_count = sum(1 for link in content_links if link['type'].startswith('internal'))
        external_count = len(content_links) - internal_count
        pdf_count = sum(1 for link in content_links if 'pdf' in link['type'])
        print(f"   📊 {internal_count} internal, {external_count} external URLs")
        print(f"   📄 {pdf_count} PDF links detected")
    
    return content_links

  def _crawl_links_from_pdf(self, content_links: List[Dict], source_url: str, current_depth: int, max_depth: int, results: List[Dict], path: List[Dict]):
    """Extract and crawl links found in PDF text content."""
    print(f"🔗 Processing {len(content_links)} URLs found in PDF: {source_url}")
    
    # Check if current PDF is from external domain
    parsed_current = urlparse(source_url)
    current_domain = parsed_current.netloc.lower()
    is_current_internal = self._is_internal_domain(current_domain)
    
    if not is_current_internal:
        print(f"🚫 PDF is from external domain {current_domain} - will not crawl any URLs from this PDF")
        return
    
    # Find all links
    links_found = 0
    external_links_found = 0
    
    for link_info in content_links:
        next_url = link_info['url']
        
        # Check if this link is external
        parsed_next = urlparse(next_url)
        next_domain = parsed_next.netloc.lower()
        is_next_internal = self._is_internal_domain(next_domain)
        
        # Recursively crawl each valid link
        if self._should_crawl(next_url, source_url):  # Pass source PDF URL for context
            links_found += 1
            if not is_next_internal:
                external_links_found += 1
                print(f"🌍 Following external link from PDF: {next_url}")
            
            self._crawl_recursive(
                next_url, 
                current_depth + 1, 
                max_depth, 
                results,
                path,  # Pass the current path
                source_url    # Pass PDF URL as parent_url
            )
    
    print(f"📊 Crawled {links_found} valid URLs from PDF {source_url} ({external_links_found} external)")

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

  def crawl(self, start_url: str, max_depth: int = 3, strict_domain: bool = False) -> List[Dict]:
    """
    Crawl website starting from given URL up to specified depth using breadth-first traversal.
    
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
    
    # Initialize queue for breadth-first traversal
    # Queue items: (url, depth, path, parent_url)
    crawl_queue = deque([(start_url, 0, [], None)])
    
    print(f"🚀 Starting BREADTH-FIRST crawling from: {start_url}")
    print(f"📊 Max depth: {max_depth}")
    
    # Process queue until empty
    while crawl_queue:
      current_batch_size = len(crawl_queue)
      current_depth = crawl_queue[0][1] if crawl_queue else 0
      
      print(f"\n🔄 Processing depth {current_depth}: {current_batch_size} URLs in queue")
      
      # Process all URLs at current depth before moving to next depth
      depth_urls_processed = 0
      while crawl_queue and crawl_queue[0][1] == current_depth:
        url, depth, path, parent_url = crawl_queue.popleft()
        depth_urls_processed += 1
        
        print(f"  📍 [{depth_urls_processed}/{current_batch_size}] Processing: {url}")
        
        # Process this URL and collect any new URLs to add to queue
        new_urls = self._process_url_breadth_first(url, depth, max_depth, results, path, parent_url)
        
        # Add new URLs to queue for next depth level
        for new_url, new_path in new_urls:
          if depth + 1 <= max_depth:
            # Check for duplicates before adding to queue
            normalized_new_url = self._normalize_url(new_url)
            if normalized_new_url not in self.visited_urls:
              crawl_queue.append((new_url, depth + 1, new_path, url))
      
      print(f"✅ Completed depth {current_depth}: processed {depth_urls_processed} URLs")
    
    print(f"🏁 Breadth-first crawling completed! Total pages: {len(results)}")
    # Return list of crawled pages, each containing:
    # - url: str - The page URL
    # - title: str - Page title
    # - text: str - Extracted text content
    # - content_links: List[Dict] - Links found in content
    # - depth: int - Crawl depth
    # - content_type: str - 'html' or 'pdf'
    # - navigation_path: List[Dict] - Path taken to reach this page
    return results

  def _process_url_breadth_first(self, url: str, current_depth: int, max_depth: int, results: List[Dict], path: List[Dict], parent_url: str = None) -> List[tuple]:
    """
    Process a single URL and return list of new URLs to crawl.
    Returns: List of (url, path) tuples for URLs to add to queue
    """
    # Normalize URL for deduplication
    normalized_url = self._normalize_url(url)
    
    # Check if we should skip this URL
    if (normalized_url in self.visited_urls or 
        not self._should_crawl(url, parent_url)):
      return []

    new_urls = []  # URLs to add to crawl queue

    try:
      # Check if page is cached using normalized URL
      cache_key = self._get_page_cache_key(url)
      if cache_key in self.page_cache:
        print(f"    💾 Cache hit: {url}")
        # Remove HTML from cached data before copying
        if 'html' in self.page_cache[cache_key]:
          html_for_link_extraction = self.page_cache[cache_key]['html']
          # Create a copy without HTML for results
          cached_page = {k: v for k, v in self.page_cache[cache_key].items() if k != 'html'}
        else:
          cached_page = self.page_cache[cache_key].copy()
          html_for_link_extraction = None
        
        cached_page['depth'] = current_depth
        cached_page['navigation_path'] = path.copy()
        # Use original URL in results, not normalized
        cached_page['url'] = url
        
        results.append(cached_page)
        self.visited_urls.add(normalized_url)
        
        # Extract links for next depth level if not at max depth and not a PDF
        if current_depth < max_depth and cached_page.get('content_type', 'html') != 'pdf':
          if html_for_link_extraction:
            soup = BeautifulSoup(html_for_link_extraction, 'html.parser')
            current_page_info = {'url': url, 'title': cached_page['title']}
            new_urls = self._extract_urls_for_queue(soup, url, path + [current_page_info])
        
        return new_urls

      print(f"    🌐 Fetching: {url}")
      time.sleep(self.delay)
      self.visited_urls.add(normalized_url)
      
      # Handle PDF files detected by URL extension
      if self._is_pdf_url(url):
        print(f"    📄 PDF detected by URL: {url}")
        new_urls = self._process_pdf_breadth_first(url, current_depth, results, path)
        return new_urls
      
      # Make request to check content type
      response = self.session.get(url, timeout=15)
      if response.status_code != 200:
        print(f"    ❌ Failed to fetch {url}: Status code {response.status_code}")
        return []
      
      # Check if this is actually a PDF based on content type or content
      content_type = response.headers.get('content-type', '').lower()
      is_pdf_content = (content_type.startswith('application/pdf') or 
                       (response.content and response.content.startswith(b'%PDF-')))
      
      if is_pdf_content and self.parse_pdfs:
        print(f"    📄 PDF detected by content: {url}")
        new_urls = self._process_pdf_from_response_breadth_first(url, response, current_depth, results, path)
        return new_urls
      elif is_pdf_content and not self.parse_pdfs:
        print(f"    📄 PDF detected but parsing disabled: {url}")
        return []
      
      # Process as HTML
      soup = BeautifulSoup(response.text, 'html.parser')
      page_title = soup.title.string if soup.title else 'No Title'
      
      print(f"    ✅ Successfully scraped: {page_title}")
      
      # Extract main content with filtering
      clean_text = self._extract_standard_content(soup, url)
      
      # Extract links from main content area
      content_links = self._extract_content_links(soup, url)
      
      # Create page data (keep original URL for display purposes)
      page_data = {
        'url': url,
        'title': page_title,
        'text': clean_text,
        'content_links': content_links,
        'depth': current_depth,
        'content_type': 'html',
        'navigation_path': path.copy()
      }
      
      # Cache the page
      cache_data = copy.deepcopy(page_data)
      cache_data['html'] = response.text  # Store HTML only in cache for link crawling
      del cache_data['depth']
      del cache_data['navigation_path']
      self.page_cache[cache_key] = cache_data
      
      # Store page data
      results.append(page_data)
      
      # Extract URLs for next depth level
      if current_depth < max_depth:
        current_page_info = {'url': url, 'title': page_title}
        new_urls = self._extract_urls_for_queue(soup, url, path + [current_page_info])
      
      return new_urls
                
    except Exception as e:
      print(f"    ❌ Error crawling {url}: {str(e)}")
      return []

  def _extract_urls_for_queue(self, soup: BeautifulSoup, url: str, path: List[Dict]) -> List[tuple]:
    """Extract URLs from HTML and return them for adding to crawl queue."""
    # Check if current page is external
    parsed_current = urlparse(url)
    current_domain = parsed_current.netloc.lower()
    is_current_internal = self._is_internal_domain(current_domain)
    
    if not is_current_internal:
      print(f"    🚫 On external domain {current_domain} - will not crawl any links from this page")
      return []
    
    new_urls = []
    links_found = 0
    external_links_found = 0
    
    for link in soup.find_all('a', href=True):
      next_url = urljoin(url, link['href'])
      
      # Check if this link is external
      parsed_next = urlparse(next_url)
      next_domain = parsed_next.netloc.lower()
      is_next_internal = self._is_internal_domain(next_domain)
      
      # Add to queue if valid and not already visited
      if self._should_crawl(next_url, url):
        normalized_next_url = self._normalize_url(next_url)
        if normalized_next_url not in self.visited_urls:
          links_found += 1
          if not is_next_internal:
            external_links_found += 1
            print(f"    🌍 Adding external link to queue: {next_url}")
          
          new_urls.append((next_url, path.copy()))
    
    print(f"    📊 Found {links_found} valid links to add to queue ({external_links_found} external)")
    return new_urls

  def _process_pdf_breadth_first(self, url: str, current_depth: int, results: List[Dict], path: List[Dict]) -> List[tuple]:
    """Process a PDF file and return URLs found in it for the queue."""
    try:
      print(f"    📄 Processing PDF: {url}")
      
      # Download PDF content
      response = self.session.get(url, timeout=30)
      if response.status_code != 200:
        print(f"    ❌ Failed to download PDF {url}: Status code {response.status_code}")
        return []
      
      # Extract text from PDF
      pdf_text = self._extract_pdf_text(response.content)
      
      if not pdf_text:
        print(f"    ⚠️  No text extracted from PDF: {url}")
        return []
      
      # Clean and filter PDF text
      clean_pdf_text = self._clean_pdf_text(pdf_text, url)
      
      # Extract URLs from PDF text content
      content_links = self._extract_urls_from_text(clean_pdf_text, url)
      
      # Get PDF title from URL or content
      pdf_title = url.split('/')[-1].replace('.pdf', '') or 'PDF Document'
      
      print(f"    ✅ Successfully extracted text from PDF: {pdf_title}")
      
      # Create page data for PDF
      page_data = {
        'url': url,
        'title': pdf_title,
        'text': clean_pdf_text,
        'content_links': content_links,
        'depth': current_depth,
        'content_type': 'pdf',
        'navigation_path': path.copy()
      }
      
      # Cache the PDF data
      cache_key = self._get_page_cache_key(url)
      cache_data = page_data.copy()
      del cache_data['depth']
      del cache_data['navigation_path']
      self.page_cache[cache_key] = cache_data
      
      # Store PDF data
      results.append(page_data)
      
      # Extract URLs from PDF content for queue
      return self._extract_pdf_urls_for_queue(content_links, url, path)
      
    except Exception as e:
      print(f"    ❌ Error processing PDF {url}: {str(e)}")
      return []

  def _process_pdf_from_response_breadth_first(self, url: str, response, current_depth: int, results: List[Dict], path: List[Dict]) -> List[tuple]:
    """Process a PDF file from response and return URLs found in it for the queue."""
    try:
      print(f"    📄 Processing PDF from response: {url}")
      
      # Extract text from PDF
      pdf_text = self._extract_pdf_text(response.content)
      
      if not pdf_text:
        print(f"    ⚠️  No text extracted from PDF: {url}")
        return []
      
      # Clean and filter PDF text
      clean_pdf_text = self._clean_pdf_text(pdf_text, url)
      
      # Extract URLs from PDF text content
      content_links = self._extract_urls_from_text(clean_pdf_text, url)
      
      # Get PDF title from URL or content
      pdf_title = url.split('/')[-1].replace('.pdf', '') or 'PDF Document'
      
      print(f"    ✅ Successfully extracted text from PDF: {pdf_title}")
      
      # Create page data for PDF
      page_data = {
        'url': url,
        'title': pdf_title,
        'text': clean_pdf_text,
        'content_links': content_links,
        'depth': current_depth,
        'content_type': 'pdf',
        'navigation_path': path.copy()
      }
      
      # Cache the PDF data
      cache_key = self._get_page_cache_key(url)
      cache_data = page_data.copy()
      del cache_data['depth']
      del cache_data['navigation_path']
      self.page_cache[cache_key] = cache_data
      
      # Store PDF data
      results.append(page_data)
      
      # Extract URLs from PDF content for queue
      return self._extract_pdf_urls_for_queue(content_links, url, path)
      
    except Exception as e:
      print(f"    ❌ Error processing PDF from response {url}: {str(e)}")
      return []

  def _extract_pdf_urls_for_queue(self, content_links: List[Dict], source_url: str, path: List[Dict]) -> List[tuple]:
    """Extract URLs from PDF content and return them for adding to crawl queue."""
    # Check if current PDF is from external domain
    parsed_current = urlparse(source_url)
    current_domain = parsed_current.netloc.lower()
    is_current_internal = self._is_internal_domain(current_domain)
    
    if not is_current_internal:
      print(f"    🚫 PDF is from external domain {current_domain} - will not crawl any URLs from this PDF")
      return []
    
    new_urls = []
    links_found = 0
    external_links_found = 0
    
    for link_info in content_links:
      next_url = link_info['url']
      
      # Check if this link is external
      parsed_next = urlparse(next_url)
      next_domain = parsed_next.netloc.lower()
      is_next_internal = self._is_internal_domain(next_domain)
      
      # Add to queue if valid and not already visited
      if self._should_crawl(next_url, source_url):
        normalized_next_url = self._normalize_url(next_url)
        if normalized_next_url not in self.visited_urls:
          links_found += 1
          if not is_next_internal:
            external_links_found += 1
            print(f"    🌍 Adding external link from PDF to queue: {next_url}")
          
          new_urls.append((next_url, path.copy()))
    
    print(f"    📊 Found {links_found} valid URLs in PDF to add to queue ({external_links_found} external)")
    return new_urls

  def _remove_html_from_results(self, pages: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """Remove HTML from all pages in results to prevent it from being returned.
    
    Each page dict contains:
    - url: str - The page URL
    - title: str - Page title
    - text: str - Extracted text content
    - html: str - Raw HTML content (this key will be removed)
    - content_links: List[Dict] - Links found in content
    - depth: int - Crawl depth
    - content_type: str - 'html' or 'pdf'
    - navigation_path: List[Dict] - Path taken to reach this page
    """
    cleaned_pages = []
    for page in pages:
      # Create a copy of the page dict without the 'html' key to avoid returning raw HTML
      cleaned_page = {k: v for k, v in page.items() if k != 'html'}
      cleaned_pages.append(cleaned_page)
    return cleaned_pages