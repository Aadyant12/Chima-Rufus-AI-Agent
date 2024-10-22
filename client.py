import os
from typing import List, Dict, Union
from crawler import WebCrawler
from extractor import ContentExtractor
from synthesizer import DocumentSynthesizer

class RufusClient:
    def __init__(self, api_key: str = None):
        """Initialize Rufus client with API key."""
        self.api_key = api_key or os.getenv('RUFUS_API_KEY')
        if not self.api_key:
            raise ValueError("API key is required. Set it via constructor or RUFUS_API_KEY env variable.")
        
        self.crawler = WebCrawler()
        self.extractor = ContentExtractor()
        self.synthesizer = DocumentSynthesizer()

    def scrape(
        self, 
        url: str, 
        instructions: str,
        max_depth: int = 3,
        output_format: str = "json"
    ) -> Union[Dict, List[Dict]]:
        """
        Scrape and synthesize content from a website based on instructions.
        
        Args:
            url: Starting URL to scrape
            instructions: Natural language instructions for content extraction
            max_depth: Maximum depth for recursive crawling
            output_format: Desired output format ("json" or "csv")
            
        Returns:
            Structured data in the specified format
        """
        try:
            # Step 1: Crawl the website
            pages = self.crawler.crawl(url, max_depth=max_depth)
            
            # Step 2: Extract relevant content based on instructions
            extracted_content = self.extractor.extract(
                pages=pages,
                instructions=instructions
            )
            
            # Step 3: Synthesize into structured format
            documents = self.synthesizer.synthesize(
                content=extracted_content,
                format=output_format
            )
            
            return documents
            
        except Exception as e:
            raise RufusError(f"Scraping failed: {str(e)}")

class RufusError(Exception):
    """Custom exception class for Rufus-specific errors."""
    pass