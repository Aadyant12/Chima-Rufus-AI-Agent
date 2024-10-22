import json
import csv
from typing import List, Dict, Union
import io

class DocumentSynthesizer:
    def synthesize(
        self, 
        content: List[Dict],
        format: str = "json"
    ) -> Union[Dict, List[Dict]]:
        """
        Synthesize extracted content into structured documents.
        
        Args:
            content: List of extracted content
            format: Output format ("json" or "csv")
            
        Returns:
            Structured data in specified format
        """
        if format == "json":
            return self._synthesize_json(content)
        elif format == "csv":
            return self._synthesize_csv(content)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _synthesize_json(self, content: List[Dict]) -> Dict:
        """Convert content to JSON structure."""
        return {
            'documents': content,
            'metadata': {
                'document_count': len(content),
                'sources': list(set(doc['url'] for doc in content))
            }
        }

    def _synthesize_csv(self, content: List[Dict]) -> str:
        """Convert content to CSV format."""
        output = io.StringIO()
        writer = csv.DictWriter(
            output, 
            fieldnames=['url', 'content', 'title', 'depth']
        )
        
        writer.writeheader()
        for doc in content:
            writer.writerow({
                'url': doc['url'],
                'content': doc['content'],
                'title': doc['metadata']['title'],
                'depth': doc['metadata']['depth']
            })
        
        return output.getvalue()