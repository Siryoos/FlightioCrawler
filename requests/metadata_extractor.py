"""
Metadata Extractor for comprehensive web page metadata extraction.
"""

import json
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class MetadataExtractor:
    """
    Advanced metadata extractor for web pages.
    
    Features:
    - Comprehensive metadata extraction
    - Open Graph and Twitter Card support
    - JSON-LD and Schema.org parsing
    - Language detection
    - SEO metadata extraction
    """
    
    def __init__(self):
        """Initialize the metadata extractor."""
        self.supported_schema_types = [
            "@context",
            "@type",
            "name",
            "description",
            "image",
            "url",
            "author",
            "datePublished",
            "dateModified"
        ]
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract comprehensive page metadata.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            url: Original URL of the page
            
        Returns:
            Dictionary containing extracted metadata
        """
        metadata = {
            "title": "",
            "description": "",
            "keywords": [],
            "author": "",
            "robots": "",
            "canonical": "",
            "language": "",
            "og_data": {},
            "twitter_data": {},
            "json_ld": [],
            "schema_org": [],
            "seo_data": {},
            "accessibility_data": {},
        }
        
        # Extract basic metadata
        metadata.update(self._extract_basic_metadata(soup))
        
        # Extract social media metadata
        metadata.update(self._extract_social_metadata(soup))
        
        # Extract structured data
        metadata.update(self._extract_structured_data(soup))
        
        # Extract SEO metadata
        metadata["seo_data"] = self._extract_seo_metadata(soup)
        
        # Extract accessibility metadata
        metadata["accessibility_data"] = self._extract_accessibility_metadata(soup)
        
        # Extract language information
        metadata["language"] = self._extract_language(soup)
        
        # Extract canonical URL
        metadata["canonical"] = self._extract_canonical_url(soup, url)
        
        return metadata
    
    def _extract_basic_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic HTML metadata."""
        metadata = {
            "title": "",
            "description": "",
            "keywords": [],
            "author": "",
            "robots": "",
        }
        
        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)
        
        # Meta tags
        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            content = tag.get("content", "")
            
            if name == "description":
                metadata["description"] = content
            elif name == "keywords":
                metadata["keywords"] = [k.strip() for k in content.split(",")]
            elif name == "author":
                metadata["author"] = content
            elif name == "robots":
                metadata["robots"] = content
        
        return metadata
    
    def _extract_social_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract social media metadata."""
        og_data = {}
        twitter_data = {}
        
        for tag in soup.find_all("meta"):
            property_attr = tag.get("property", "").lower()
            name_attr = tag.get("name", "").lower()
            content = tag.get("content", "")
            
            # Open Graph
            if property_attr.startswith("og:"):
                og_data[property_attr] = content
            
            # Twitter Card
            if name_attr.startswith("twitter:") or property_attr.startswith("twitter:"):
                key = name_attr or property_attr
                twitter_data[key] = content
        
        return {
            "og_data": og_data,
            "twitter_data": twitter_data
        }
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured data (JSON-LD, Schema.org)."""
        json_ld = []
        schema_org = []
        
        # Find JSON-LD and Schema.org scripts
        for script in soup.find_all("script", {"type": ["application/ld+json", "application/json"]}):
            if script.string:
                try:
                    data = json.loads(script.string)
                    if self._is_schema_org_data(data):
                        schema_org.append(data)
                    else:
                        json_ld.append(data)
                except json.JSONDecodeError:
                    continue
        
        # Extract microdata
        microdata = self._extract_microdata(soup)
        
        return {
            "json_ld": json_ld,
            "schema_org": schema_org,
            "microdata": microdata
        }
    
    def _extract_seo_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract SEO-related metadata."""
        seo_data = {
            "h1_tags": [],
            "h2_tags": [],
            "h3_tags": [],
            "meta_title_length": 0,
            "meta_description_length": 0,
            "alt_texts": [],
            "internal_links_count": 0,
            "external_links_count": 0,
        }
        
        # Heading tags
        for i in range(1, 4):
            tags = soup.find_all(f"h{i}")
            seo_data[f"h{i}_tags"] = [tag.get_text(strip=True) for tag in tags]
        
        # Meta title and description lengths
        title_tag = soup.find("title")
        if title_tag:
            seo_data["meta_title_length"] = len(title_tag.get_text(strip=True))
        
        desc_tag = soup.find("meta", {"name": "description"})
        if desc_tag:
            seo_data["meta_description_length"] = len(desc_tag.get("content", ""))
        
        # Alt texts
        for img in soup.find_all("img"):
            alt_text = img.get("alt", "")
            if alt_text:
                seo_data["alt_texts"].append(alt_text)
        
        # Link analysis
        links = soup.find_all("a", href=True)
        for link in links:
            href = link.get("href", "")
            if href.startswith("http"):
                seo_data["external_links_count"] += 1
            elif href.startswith("/") or not href.startswith(("mailto:", "tel:", "javascript:")):
                seo_data["internal_links_count"] += 1
        
        return seo_data
    
    def _extract_accessibility_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract accessibility-related metadata."""
        accessibility_data = {
            "has_alt_attributes": 0,
            "missing_alt_attributes": 0,
            "has_aria_labels": 0,
            "has_headings_structure": False,
            "has_skip_links": False,
        }
        
        # Alt attributes
        images = soup.find_all("img")
        for img in images:
            if img.get("alt"):
                accessibility_data["has_alt_attributes"] += 1
            else:
                accessibility_data["missing_alt_attributes"] += 1
        
        # ARIA labels
        aria_elements = soup.find_all(attrs={"aria-label": True})
        accessibility_data["has_aria_labels"] = len(aria_elements)
        
        # Headings structure
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        accessibility_data["has_headings_structure"] = len(headings) > 0
        
        # Skip links
        skip_links = soup.find_all("a", href=lambda x: x and x.startswith("#"))
        accessibility_data["has_skip_links"] = len(skip_links) > 0
        
        return accessibility_data
    
    def _extract_language(self, soup: BeautifulSoup) -> str:
        """Extract page language."""
        # Check HTML lang attribute
        html_tag = soup.find("html")
        if html_tag:
            lang = html_tag.get("lang", "")
            if lang:
                return lang
        
        # Check meta tags
        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            content = tag.get("content", "")
            
            if name in ["language", "lang"]:
                return content
        
        return ""
    
    def _extract_canonical_url(self, soup: BeautifulSoup, original_url: str) -> str:
        """Extract canonical URL."""
        canonical_tag = soup.find("link", {"rel": "canonical"})
        if canonical_tag:
            href = canonical_tag.get("href", "")
            if href:
                return urljoin(original_url, href)
        
        return ""
    
    def _is_schema_org_data(self, data: Any) -> bool:
        """Check if data contains Schema.org structured data."""
        if isinstance(data, dict):
            return "@context" in data and "schema.org" in str(data.get("@context", ""))
        elif isinstance(data, list):
            return any(self._is_schema_org_data(item) for item in data)
        return False
    
    def _extract_microdata(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract microdata from HTML."""
        microdata = []
        
        # Find elements with itemscope
        for element in soup.find_all(attrs={"itemscope": True}):
            item = {
                "type": element.get("itemtype", ""),
                "properties": {}
            }
            
            # Find child elements with itemprop
            for prop in element.find_all(attrs={"itemprop": True}):
                prop_name = prop.get("itemprop")
                prop_value = prop.get("content") or prop.get_text(strip=True)
                
                if prop_name:
                    if prop_name in item["properties"]:
                        # Convert to list if multiple values
                        if not isinstance(item["properties"][prop_name], list):
                            item["properties"][prop_name] = [item["properties"][prop_name]]
                        item["properties"][prop_name].append(prop_value)
                    else:
                        item["properties"][prop_name] = prop_value
            
            if item["properties"]:
                microdata.append(item)
        
        return microdata
    
    def extract_ajax_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract AJAX endpoints and API calls from JavaScript."""
        ajax_data = {
            "api_endpoints": [],
            "websocket_urls": [],
            "data_attributes": {},
            "javascript_apis": []
        }
        
        # Find API endpoints in scripts
        for script in soup.find_all("script"):
            if script.string:
                script_content = script.string
                
                # Common API patterns
                api_patterns = [
                    r'(?:fetch|axios|ajax)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                    r'api[Uu]rl\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                    r'endpoint\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                    r'[\'"](?:GET|POST|PUT|DELETE)[\'"],\s*[\'"]([^\'"]+)[\'"]',
                    r'url\s*[:=]\s*[\'"]([^\'"]+api[^\'"]*)[\'"]',
                ]
                
                for pattern in api_patterns:
                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                    ajax_data["api_endpoints"].extend(matches)
                
                # WebSocket URLs
                ws_patterns = [
                    r'wss?://[^\s\'"]+',
                    r'new\s+WebSocket\s*\(\s*[\'"]([^\'"]+)[\'"]',
                ]
                
                for pattern in ws_patterns:
                    matches = re.findall(pattern, script_content)
                    ajax_data["websocket_urls"].extend(matches)
                
                # JavaScript API calls
                js_api_patterns = [
                    r'\.ajax\s*\(',
                    r'\.get\s*\(',
                    r'\.post\s*\(',
                    r'fetch\s*\(',
                    r'axios\.',
                ]
                
                for pattern in js_api_patterns:
                    if re.search(pattern, script_content):
                        ajax_data["javascript_apis"].append(pattern.strip('\\.('))
        
        # Data attributes that might contain API info
        for element in soup.find_all(attrs=lambda x: x and any(attr.startswith('data-') for attr in x)):
            for attr_name, attr_value in element.attrs.items():
                if attr_name.startswith('data-') and ('api' in attr_name.lower() or 'url' in attr_name.lower()):
                    ajax_data["data_attributes"][attr_name] = attr_value
        
        # Remove duplicates
        ajax_data["api_endpoints"] = list(set(ajax_data["api_endpoints"]))
        ajax_data["websocket_urls"] = list(set(ajax_data["websocket_urls"]))
        ajax_data["javascript_apis"] = list(set(ajax_data["javascript_apis"]))
        
        return ajax_data
    
    def get_metadata_summary(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of extracted metadata."""
        summary = {
            "has_title": bool(metadata.get("title")),
            "has_description": bool(metadata.get("description")),
            "has_keywords": len(metadata.get("keywords", [])) > 0,
            "has_author": bool(metadata.get("author")),
            "has_canonical": bool(metadata.get("canonical")),
            "has_language": bool(metadata.get("language")),
            "has_open_graph": len(metadata.get("og_data", {})) > 0,
            "has_twitter_card": len(metadata.get("twitter_data", {})) > 0,
            "has_structured_data": len(metadata.get("json_ld", [])) > 0 or len(metadata.get("schema_org", [])) > 0,
            "seo_score": self._calculate_seo_score(metadata),
            "accessibility_score": self._calculate_accessibility_score(metadata),
        }
        
        return summary
    
    def _calculate_seo_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate a basic SEO score based on metadata."""
        score = 0.0
        max_score = 10.0
        
        # Title (2 points)
        if metadata.get("title"):
            score += 2.0
        
        # Description (2 points)
        if metadata.get("description"):
            score += 2.0
        
        # Keywords (1 point)
        if metadata.get("keywords"):
            score += 1.0
        
        # Open Graph (1 point)
        if metadata.get("og_data"):
            score += 1.0
        
        # Twitter Card (1 point)
        if metadata.get("twitter_data"):
            score += 1.0
        
        # Structured Data (1 point)
        if metadata.get("json_ld") or metadata.get("schema_org"):
            score += 1.0
        
        # Canonical URL (1 point)
        if metadata.get("canonical"):
            score += 1.0
        
        # Language (1 point)
        if metadata.get("language"):
            score += 1.0
        
        return (score / max_score) * 100
    
    def _calculate_accessibility_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate a basic accessibility score."""
        accessibility_data = metadata.get("accessibility_data", {})
        
        if not accessibility_data:
            return 0.0
        
        score = 0.0
        max_score = 5.0
        
        # Alt attributes
        total_images = accessibility_data.get("has_alt_attributes", 0) + accessibility_data.get("missing_alt_attributes", 0)
        if total_images > 0:
            alt_ratio = accessibility_data.get("has_alt_attributes", 0) / total_images
            score += alt_ratio * 2.0
        
        # ARIA labels
        if accessibility_data.get("has_aria_labels", 0) > 0:
            score += 1.0
        
        # Headings structure
        if accessibility_data.get("has_headings_structure", False):
            score += 1.0
        
        # Skip links
        if accessibility_data.get("has_skip_links", False):
            score += 1.0
        
        return (score / max_score) * 100 