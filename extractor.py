from typing import List, Dict
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from transformers import pipeline
import re

class ContentExtractor:
  def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    self.sentence_transformer = SentenceTransformer(model_name)
    
    # Remove summarization model since we're not using it anymore
    # self.summarizer = pipeline(
    #   "summarization",
    #   model="facebook/bart-large-cnn",
    #   device=0 if torch.cuda.is_available() else -1
    # )

  def extract(self, pages: List[Dict], instructions: str) -> List[Dict]:
    """
    Extract relevant content from crawled pages based on instructions.
    Returns individual relevant chunks instead of combined summaries.
    """
    print(f"🧠 Processing instructions: '{instructions}'")
    print(f"📚 Generating instruction embeddings...")
    
    # Get user instruction embeddings
    instruction_embedding = self.sentence_transformer.encode(
      instructions,
      convert_to_tensor=True
    )
    
    extracted_content = []
    
    for page_num, page in enumerate(pages, 1):
        print(f"\n📄 Processing page {page_num}/{len(pages)}: {page['title']}")
        print(f"🔗 URL: {page['url']}")
        
        # Split content into chunks for processing
        chunks = self._split_into_chunks(page['text'])
        print(f"✂️  Split into {len(chunks)} chunks for analysis")
        
        if len(chunks) == 0:
            print(f"⚠️  No content chunks found on this page")
            continue
        
        # Get embeddings for all chunks
        print(f"🧮 Generating embeddings for {len(chunks)} chunks...")
        chunk_embeddings = self.sentence_transformer.encode(
          chunks,
          convert_to_tensor=True
        )
        
        # Calculate similarity scores
        similarities = torch.cosine_similarity(
          instruction_embedding.unsqueeze(0),
          chunk_embeddings
        )
        
        # Print similarity scores for all chunks
        print(f"📊 Cosine similarity scores for all chunks:")
        for i, chunk in enumerate(chunks):
          similarity_score = float(similarities[i])
          print(f"  Chunk {i+1}: {similarity_score:.3f} - {chunk[:100]}{'...' if len(chunk) > 100 else ''}")
        
        relevant_chunks_found = 0
        # Filter relevant chunks (similarity > 0.6) and return each individually
        for i, chunk in enumerate(chunks):
          if similarities[i] > 0.6:
            relevant_chunks_found += 1
            # Print relevant chunk as soon as it's found
            print(f"\n🔍 RELEVANT CHUNK FOUND!")
            print(f"📄 Source: {page['title']} ({page['url']})")
            print(f"📊 Relevance Score: {float(similarities[i]):.3f}")
            print(f"📝 Content Preview: {chunk[:200]}{'...' if len(chunk) > 200 else ''}")
            print(f"{'='*60}")
            
            extracted_content.append({
              'url': page['url'],
              'content': chunk,  # Individual chunk instead of combined text
              'title': page['title'],
              'depth': page['depth'],
              'relevance_score': float(similarities[i]),
              'chunk_index': i  # Add chunk index for reference
            })
        
        print(f"📊 Page summary: {relevant_chunks_found}/{len(chunks)} chunks were relevant")
    
    print(f"\n🔄 Sorting {len(extracted_content)} relevant chunks by relevance score...")
    # Sort by relevance score
    extracted_content.sort(
      key=lambda x: x['relevance_score'],
      reverse=True
    )
    
    return extracted_content

  def _split_into_chunks(self, text: str, chunk_size: int = 512) -> List[str]:
    """
    Split text into chunks for processing.
    """
    # Clean text
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Split into sentences (rough approximation)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
      sentence_length = len(sentence)
      
      if current_length + sentence_length > chunk_size:
        if current_chunk:
          chunks.append(' '.join(current_chunk))
        current_chunk = [sentence]
        current_length = sentence_length

      else:
        current_chunk.append(sentence)
        current_length += sentence_length
    
    if current_chunk:
      chunks.append(' '.join(current_chunk))
    
    return chunks