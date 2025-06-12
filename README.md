# Rufus - Intelligent Web Crawling for RAG Pipelines

Rufus is a sophisticated web crawling and content extraction library specifically designed for RAG (Retrieval-Augmented Generation) pipelines. It combines intelligent web crawling capabilities with semantic content extraction to gather relevant information based on specific user instructions.

## 🌟 Key Features

- **Smart Web Crawling**: Recursively crawls websites with configurable depth and domain restrictions
- **Semantic Content Extraction**: Uses transformer models to extract relevant content based on user instructions
- **PDF Support**: Optional PDF parsing and content extraction
- **Intelligent Caching**: Built-in caching system for both crawled pages and extracted content
- **Navigation Path Tracking**: Maintains complete navigation paths for extracted content
- **Content Filtering**: Sophisticated filtering of boilerplate content, ads, and irrelevant sections
- **Domain Control**: Flexible domain control with strict and relaxed modes

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/Aadyant12/Chima-Rufus-AI-Agent.git

# Install required dependencies
pip install beautifulsoup4 requests sentence-transformers torch

# Optional: Install PDF parsing support
pip install PyPDF2
```

## 🚀 Quick Start

```python
from client import RufusClient

# Initialize the client
client = RufusClient(
    chunk_size=1024,           # Size of content chunks for processing
    similarity_threshold=0.6,   # Threshold for content relevance
    parse_pdfs=False,          # Enable/disable PDF parsing
    max_depth=3,               # Maximum crawling depth
    strict_domain=False        # Enable/disable strict domain mode
)

# Scrape content based on instructions
documents = client.scrape(
    url="https://example.com",
    instructions="Find information about product features and pricing"
)

# Access the extracted content
for doc in documents['documents']:
    print(f"URL: {doc['url']}")
    print(f"Title: {doc['title']}")
    print(f"Content: {doc['content']}")
    print(f"Relevance Score: {doc['relevance_score']}")
```

## 🔧 Configuration Options

### RufusClient Parameters

- `chunk_size` (int, default=1024): Size of text chunks for semantic analysis
- `similarity_threshold` (float, default=0.6): Minimum similarity score for content relevance
- `parse_pdfs` (bool, default=False): Enable PDF parsing and extraction
- `max_depth` (int, default=3): Maximum depth for recursive crawling
- `strict_domain` (bool, default=False): Restrict crawling to exact domain match

### Scraping Parameters

- `url` (str): Starting URL for crawling
- `instructions` (str): Natural language instructions for content extraction

## 🧠 Content Extraction

Rufus uses the `sentence-transformers/all-MiniLM-L6-v2` model for semantic content extraction. The process involves:

1. Splitting content into manageable chunks
2. Generating embeddings for instructions and content
3. Computing similarity scores
4. Filtering relevant content based on threshold
5. Sorting results by relevance

## 🌐 Web Crawling Features

- **Smart URL Filtering**: Automatically filters out social media, asset files, and non-content URLs
- **Rate Limiting**: Built-in delay between requests to prevent overwhelming servers
- **External Link Handling**: Configurable handling of external domain links
- **Content Cleaning**: Removes boilerplate content, ads, navigation elements, etc.
- **PDF Processing**: Optional PDF text extraction and cleaning

## 💾 Caching System

Rufus implements a two-level caching system:

1. **Crawl Cache**: Stores raw crawled pages
2. **Extraction Cache**: Stores processed and extracted content

Access cache information:
```python
cache_info = client.get_cache_info()
print(cache_info)

# Clear caches if needed
client.clear_cache()
```

## 🗺️ Navigation Path Tracking

Each extracted content piece includes its complete navigation path, showing how the crawler reached that content:

```python
for doc in documents['documents']:
    print("Navigation Path:")
    for node in doc['navigation_path']:
        print(f"-> {node['title']}")
```

## ⚠️ Limitations

- PDF parsing requires additional `PyPDF2` installation
- Maximum crawling depth affects processing time
- Rate limiting may slow down large-scale crawling
- Some websites may block automated crawling

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for improvements and bug fixes.

