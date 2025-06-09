import os
from typing import List, Dict, Union
from crawler import WebCrawler
from extractor import ContentExtractor

class RufusClient:
  def __init__(self, api_key: str = None):
    self.api_key = api_key or os.getenv('RUFUS_API_KEY')
    if not self.api_key or self.api_key != "loved_the_assignment":
        raise ValueError("API key is required.")
    
    self.crawler = WebCrawler()
    self.extractor = ContentExtractor()

  def scrape(self, url: str, instructions: str, max_depth: int = 3) -> Union[Dict, List[Dict]]:
    """
    Scrape and synthesize content from a website based on instructions.
    
    url: Starting URL to scrape
    instructions: User instructions for content extraction
    max_depth: Maximum depth for recursive crawling
    """
    try:
      print(f"\n🚀 STARTING RUFUS WEB SCRAPING")
      print(f"🎯 Target URL: {url}")
      print(f"📋 Instructions: {instructions}")
      print(f"🔍 Max Depth: {max_depth}")
      print(f"{'='*60}")
      
      # Crawl the website
      print(f"\n🕷️  STARTING WEB CRAWLING...")
      pages = self.crawler.crawl(url, max_depth=max_depth)
      print(f"✅ Crawling completed! Found {len(pages)} pages")
      
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
      
      # return in structured format
      return {
        'documents': extracted_content,
        'metadata': {
          'document_count': len(extracted_content),
          'sources': list(set(doc['url'] for doc in extracted_content))
        }
      }
        
    except Exception as e:
      print(f"❌ ERROR: Scraping failed - {str(e)}")
      raise RufusError(f"Scraping failed: {str(e)}")

class RufusError(Exception):
  """Custom exception class for Rufus-specific errors."""
  pass