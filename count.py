import json
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from urllib.parse import urlparse

def analyze_domain_by_depth(json_file_path: str, target_domain: str) -> Tuple[Dict[int, int], Dict[int, int], Dict[int, int]]:
    """
    Analyze a specific domain by counting:
    1. Total URLs at each depth (all domains)
    2. URLs that belong to the target domain at each depth
    3. Links to the target domain found in content_links at each depth
    
    Args:
        json_file_path: Path to the JSON file containing crawled data
        target_domain: The domain to analyze (e.g., 'askus-resource-center.unitedspinal.org')
        
    Returns:
        Tuple of (total_url_counts_by_depth, domain_url_counts_by_depth, content_links_counts_by_depth)
    """
    try:
        print(f"📂 Loading data from: {json_file_path}")
        
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        print(f"✅ Successfully loaded {len(data)} entries")
        
        # Track all URLs by depth
        total_url_depths = []
        total_url_count = 0
        
        # Track URLs from the target domain
        domain_url_depths = []
        domain_url_count = 0
        
        # Track content links pointing to the target domain
        content_link_depths = []
        content_link_count = 0
        
        for entry in data:
            if not isinstance(entry, dict) or 'depth' not in entry:
                continue
                
            entry_depth = entry['depth']
            
            # Count all URLs at this depth
            if 'url' in entry:
                total_url_depths.append(entry_depth)
                total_url_count += 1
                
                # Check if this entry's URL is from the target domain
                url = entry['url']
                try:
                    parsed_url = urlparse(url)
                    entry_domain = parsed_url.netloc.lower()
                    
                    if target_domain.lower() in entry_domain:
                        domain_url_depths.append(entry_depth)
                        domain_url_count += 1
                except Exception as e:
                    print(f"⚠️  Warning: Could not parse URL '{url}': {e}")
            
            # Check content_links for links to the target domain
            if 'content_links' in entry and isinstance(entry['content_links'], list):
                for link in entry['content_links']:
                    if isinstance(link, dict) and 'url' in link:
                        link_url = link['url']
                        try:
                            parsed_link_url = urlparse(link_url)
                            link_domain = parsed_link_url.netloc.lower()
                            
                            if target_domain.lower() in link_domain:
                                content_link_depths.append(entry_depth)
                                content_link_count += 1
                        except Exception as e:
                            print(f"⚠️  Warning: Could not parse content link URL '{link_url}': {e}")
        
        print(f"📊 Total URLs across all domains: {total_url_count}")
        print(f"📊 URLs from domain '{target_domain}': {domain_url_count}")
        print(f"🔗 Content links pointing to domain '{target_domain}': {content_link_count}")
        
        # Count by depth
        total_url_depth_counts = dict(sorted(Counter(total_url_depths).items()))
        domain_url_depth_counts = dict(sorted(Counter(domain_url_depths).items()))
        content_link_depth_counts = dict(sorted(Counter(content_link_depths).items()))
        
        return total_url_depth_counts, domain_url_depth_counts, content_link_depth_counts
        
    except FileNotFoundError:
        print(f"❌ Error: File '{json_file_path}' not found")
        return {}, {}, {}
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format - {e}")
        return {}, {}, {}
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {}, {}, {}

def display_comprehensive_domain_statistics(total_url_counts: Dict[int, int], domain_url_counts: Dict[int, int], content_link_counts: Dict[int, int], domain: str) -> None:
    """
    Display comprehensive statistics about total URL counts, domain URL counts, and content link counts by depth.
    
    Args:
        total_url_counts: Dictionary with depth as key and count of all URLs as value
        domain_url_counts: Dictionary with depth as key and count of domain URLs as value
        content_link_counts: Dictionary with depth as key and count of content links as value
        domain: The domain being analyzed
    """
    print(f"\n🌐 Comprehensive Analysis for Domain: {domain}")
    print(f"{'='*100}")
    
    # Get all depths from all dictionaries
    all_depths = sorted(set(list(total_url_counts.keys()) + list(domain_url_counts.keys()) + list(content_link_counts.keys())))
    
    if not all_depths:
        print(f"📊 No data found")
        return
    
    total_all_urls = sum(total_url_counts.values())
    total_domain_urls = sum(domain_url_counts.values())
    total_content_links = sum(content_link_counts.values())
    
    print(f"📈 Total URLs (all domains): {total_all_urls:,}")
    print(f"📍 URLs from target domain: {total_domain_urls:,}")
    print(f"🔗 Content links to target domain: {total_content_links:,}")
    print(f"📊 Domain penetration: {(total_domain_urls/total_all_urls*100):,.1f}% of all URLs")
    print(f"🔢 Depth range: {min(all_depths)} - {max(all_depths)}")
    print(f"{'='*100}")
    
    # Display detailed breakdown by depth
    print(f"{'Depth':<6} {'Total URLs':<12} {'Domain URLs':<12} {'Content Links':<15} {'Domain %':<10} {'Distribution'}")
    print(f"{'-'*6} {'-'*12} {'-'*12} {'-'*15} {'-'*10} {'-'*20}")
    
    for depth in all_depths:
        total_count = total_url_counts.get(depth, 0)
        domain_count = domain_url_counts.get(depth, 0)
        content_count = content_link_counts.get(depth, 0)
        
        # Calculate domain percentage at this depth
        if total_count > 0:
            domain_percentage = (domain_count / total_count) * 100
        else:
            domain_percentage = 0
            
        # Calculate percentage of total for visual bar (based on total URLs)
        if total_all_urls > 0:
            bar_percentage = (total_count / total_all_urls) * 100
        else:
            bar_percentage = 0
            
        # Create visual bar
        bar_length = int(bar_percentage / 5)  # Scale bar to fit display
        bar = "█" * bar_length + "░" * (20 - bar_length)
        
        print(f"{depth:<6} {total_count:<12,} {domain_count:<12,} {content_count:<15,} {domain_percentage:<9.1f}% {bar}")
    
    print(f"{'='*100}")
    
    # Additional statistics
    print(f"\n📊 Additional Statistics:")
    
    print(f"   🌍 Overall Statistics:")
    print(f"     • Total unique depths: {len(all_depths)}")
    print(f"     • Average URLs per depth: {total_all_urls / len(all_depths):,.1f}")
    print(f"     • Depth with most URLs: {max(total_url_counts, key=total_url_counts.get)} ({max(total_url_counts.values()):,} URLs)")
    
    if domain_url_counts:
        print(f"   📍 Domain URL Statistics:")
        print(f"     • Depth with most domain URLs: {max(domain_url_counts, key=domain_url_counts.get)} ({max(domain_url_counts.values()):,} URLs)")
        print(f"     • Depth with fewest domain URLs: {min(domain_url_counts, key=domain_url_counts.get)} ({min(domain_url_counts.values()):,} URLs)")
        print(f"     • Average domain URLs per depth: {total_domain_urls / len(domain_url_counts):,.1f}")
    
    if content_link_counts:
        print(f"   🔗 Content Link Statistics:")
        print(f"     • Depth with most content links: {max(content_link_counts, key=content_link_counts.get)} ({max(content_link_counts.values()):,} links)")
        print(f"     • Depth with fewest content links: {min(content_link_counts, key=content_link_counts.get)} ({min(content_link_counts.values()):,} links)")
        print(f"     • Average content links per depth: {total_content_links / len(content_link_counts):,.1f}")
    
    # Domain penetration by depth
    print(f"   📈 Domain Penetration by Depth:")
    for depth in sorted(all_depths):
        total_at_depth = total_url_counts.get(depth, 0)
        domain_at_depth = domain_url_counts.get(depth, 0)
        if total_at_depth > 0:
            penetration = (domain_at_depth / total_at_depth) * 100
            print(f"     • Depth {depth}: {penetration:.1f}% ({domain_at_depth:,}/{total_at_depth:,})")

def main():
    """
    Main function to analyze URL and content link distribution for a specific domain.
    """
    print("🚀 Comprehensive Domain Analysis Tool")
    print("=" * 60)
    
    # Default JSON file path
    json_file = "data(depth4-breadth).json"
    
    # Target domain to analyze
    target_domain = "askus-resource-center.unitedspinal.org"
    
    print(f"🎯 Analyzing domain: {target_domain}")
    print(f"📁 Data source: {json_file}")
    
    # Analyze URLs and content links by depth for the specific domain
    total_url_counts, domain_url_counts, content_link_counts = analyze_domain_by_depth(json_file, target_domain)
    
    if total_url_counts or domain_url_counts or content_link_counts:
        # Display comprehensive statistics
        display_comprehensive_domain_statistics(total_url_counts, domain_url_counts, content_link_counts, target_domain)
        
        # Return the data for potential further use
        return total_url_counts, domain_url_counts, content_link_counts
    else:
        print("❌ No valid data found or error occurred")
        return {}, {}, {}

if __name__ == "__main__":
    main()
