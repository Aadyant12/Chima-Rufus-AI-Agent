# Rufus Documentation
Rufus is a powerful web crawling and content extraction library designed for RAG pipelines.
It combines intelligent web crawling with semantic content extraction to gather relevant
information based on specific user instructions.
## Overview
Rufus consists of three main components:
1. WebCrawler: Recursively crawls websites to gather content
2. ContentExtractor: Processes and extracts relevant information using semantic
similarity
3. RufusClient: Main interface that orchestrates crawling and extraction
Installation and Running
```
git clone https://github.com/Aadyant12/Chima-Rufus-AI-Agent.git
# Required dependencies
pip install beautifulsoup4 requests sentence-transformers torch
from client import RufusClient
client = RufusClient(api_key="loved_the_assignment")
documents = client.scrape(
url="https://www.withchima.com/",
instructions="Find information about product features and pricing",
max_depth=2,
)
documents
