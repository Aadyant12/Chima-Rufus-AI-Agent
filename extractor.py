from typing import List, Dict
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from transformers import pipeline
import re

class ContentExtractor:
  def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    self.sentence_transformer = SentenceTransformer(model_name)
    
    # Load summarization model for content summarization
    self.summarizer = pipeline(
      "summarization",
      model="facebook/bart-large-cnn",
      device=0 if torch.cuda.is_available() else -1
    )

  def extract(self, pages: List[Dict], instructions: str) -> List[Dict]:
    """
    Extract relevant content from crawled pages based on instructions.
    """
    # Get user instruction embeddings
    instruction_embedding = self.sentence_transformer.encode(
      instructions,
      convert_to_tensor=True
    )
    
    extracted_content = []
    
    for page in pages:
        # Split content into chunks for processing
        chunks = self._split_into_chunks(page['text'])
        
        # Get embeddings for all chunks
        chunk_embeddings = self.sentence_transformer.encode(
          chunks,
          convert_to_tensor=True
        )
        
        # Calculate similarity scores
        similarities = torch.cosine_similarity(
          instruction_embedding.unsqueeze(0),
          chunk_embeddings
        )
        
        # Filter relevant chunks (similarity > 0.3)
        relevant_chunks = [
          chunks[i] for i in range(len(chunks))
          if similarities[i] > 0.3
        ]
        
        if relevant_chunks:
          # Combine relevant chunks
          combined_text = " ".join(relevant_chunks)
          
          # Summarize the relevant content
          try:
            summary = self.summarizer(
              combined_text,
              max_length=150,
              min_length=30,
              do_sample=False
            )[0]['summary_text']
          except Exception as e:
            print(f"Summarization failed for {page['url']}: {str(e)}")
            summary = combined_text[:500] + "..."
          
          extracted_content.append({
            'url': page['url'],
            'content': combined_text,
            'summary': summary,
            'title': page['title'],
            'depth': page['depth'],
            'relevance_score': float(max(similarities))
          })
    
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