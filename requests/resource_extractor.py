"""
Resource Extractor for extracting resources and links from web pages.
"""

import re
from typing import Dict, List, Set, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class ResourceExtractor:
    """
    Advanced resource and link extractor for web pages.
    
    Features:
    - Extract all page resources (images, scripts, stylesheets, etc.)
    - Categorize and analyze links
    - Support for lazy loading and responsive images
    - Resource optimization analysis
    - Security and performance insights
    """
    
    def __init__(self):
        """Initialize the resource extractor."""
        self.resource_types = {
            "images": ["img", "picture", "source"],
            "scripts": ["script"],
            "stylesheets": ["link"],
            "videos": ["video", "source"],
            "audios": ["audio"],
            "iframes": ["iframe"],
            "fonts": ["link"],
            "icons": ["link"],
        }
        
        self.link_attributes = [
            ("a", "href"),
            ("area", "href"),
            ("link", "href"),
            ("base", "href"),
        ]
        
        self.file_extensions = {
            "images": ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"],
            "documents": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"],
            "archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
            "videos": ["mp4", "avi", "mov", "wmv", "flv", "webm"],
            "audios": ["mp3", "wav", "ogg", "aac", "flac"],
        }
    
    def extract_all_resources(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """
        Extract all resources and links from the page.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Dictionary containing all extracted resources and analysis
        """
        return {
            "resources": self.extract_resources(soup, base_url),
            "links": self.extract_links(soup, base_url),
            "analysis": self._analyze_resources(soup, base_url),
            "optimization": self._analyze_optimization(soup),
            "security": self._analyze_security(soup, base_url),
        }
    
    def extract_resources(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """
        Extract all page resources.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            base_url: Base URL for resolving relative URLs
            
        Returns:
            Dictionary categorizing all extracted resources
        """
        resources = {
            "images": [],
            "scripts": [],
            "stylesheets": [],
            "videos": [],
            "audios": [],
            "iframes": [],
            "fonts": [],
            "icons": [],
            "preload": [],
            "prefetch": [],
        }
        
        # Extract images with multiple source attributes
        resources["images"] = self._extract_images(soup, base_url)
        
        # Extract scripts
        resources["scripts"] = self._extract_scripts(soup, base_url)
        
        # Extract stylesheets
        resources["stylesheets"] = self._extract_stylesheets(soup, base_url)
        
        # Extract videos
        resources["videos"] = self._extract_videos(soup, base_url)
        
        # Extract audios
        resources["audios"] = self._extract_audios(soup, base_url)
        
        # Extract iframes
        resources["iframes"] = self._extract_iframes(soup, base_url)
        
        # Extract fonts
        resources["fonts"] = self._extract_fonts(soup, base_url)
        
        # Extract icons
        resources["icons"] = self._extract_icons(soup, base_url)
        
        # Extract preload and prefetch resources
        resources["preload"] = self._extract_preload_resources(soup, base_url)
        resources["prefetch"] = self._extract_prefetch_resources(soup, base_url)
        
        # Remove duplicates
        for category in resources:
            resources[category] = list(dict.fromkeys(resources[category]))
        
        return resources
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """
        Extract and categorize all links.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            base_url: Base URL for categorizing internal/external links
            
        Returns:
            Dictionary with categorized links
        """
        links = {
            "internal": [],
            "external": [],
            "mailto": [],
            "tel": [],
            "javascript": [],
            "anchors": [],
            "files": {
                "pdf": [],
                "doc": [],
                "xls": [],
                "images": [],
                "videos": [],
                "audios": [],
                "archives": [],
                "other": []
            },
            "social": [],
            "navigation": [],
        }
        
        base_domain = urlparse(base_url).netloc
        
        # Extract from various link sources
        for tag_name, attr_name in self.link_attributes:
            for tag in soup.find_all(tag_name):
                href = tag.get(attr_name, "").strip()
                if not href:
                    continue
                
                # Categorize the link
                self._categorize_link(href, links, base_url, base_domain, tag)
        
        # Extract navigation links specifically
        links["navigation"] = self._extract_navigation_links(soup, base_url)
        
        # Extract social media links
        links["social"] = self._extract_social_links(soup, base_url)
        
        # Remove duplicates from all categories
        self._remove_duplicates_from_links(links)
        
        return links
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract image resources including lazy-loaded and responsive images."""
        images = []
        
        for img in soup.find_all(["img", "picture", "source"]):
            # Check multiple attributes for image sources
            for attr in ["src", "data-src", "data-lazy-src", "data-original", "srcset"]:
                value = img.get(attr)
                if value:
                    if "srcset" in attr:
                        # Parse srcset for responsive images
                        urls = re.findall(r"([^\s,]+)(?:\s+\d+[wx])?", value)
                        images.extend([urljoin(base_url, url.strip()) for url in urls])
                    else:
                        images.append(urljoin(base_url, value))
        
        return images
    
    def _extract_scripts(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract JavaScript resources."""
        scripts = []
        
        for script in soup.find_all("script"):
            src = script.get("src")
            if src:
                scripts.append(urljoin(base_url, src))
        
        return scripts
    
    def _extract_stylesheets(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract CSS resources."""
        stylesheets = []
        
        for link in soup.find_all("link"):
            rel = link.get("rel", [])
            if isinstance(rel, list):
                rel = " ".join(rel)
            
            if "stylesheet" in str(rel).lower():
                href = link.get("href")
                if href:
                    stylesheets.append(urljoin(base_url, href))
        
        return stylesheets
    
    def _extract_videos(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract video resources."""
        videos = []
        
        for video in soup.find_all(["video", "source"]):
            # Check multiple source attributes
            for attr in ["src", "data-src"]:
                src = video.get(attr)
                if src:
                    videos.append(urljoin(base_url, src))
        
        return videos
    
    def _extract_audios(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract audio resources."""
        audios = []
        
        for audio in soup.find_all("audio"):
            src = audio.get("src")
            if src:
                audios.append(urljoin(base_url, src))
        
        return audios
    
    def _extract_iframes(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract iframe sources."""
        iframes = []
        
        for iframe in soup.find_all("iframe"):
            for attr in ["src", "data-src"]:
                src = iframe.get(attr)
                if src:
                    iframes.append(urljoin(base_url, src))
        
        return iframes
    
    def _extract_fonts(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract font resources."""
        fonts = []
        
        for link in soup.find_all("link"):
            rel = link.get("rel", [])
            if isinstance(rel, list):
                rel = " ".join(rel)
            
            if "font" in str(rel).lower() or "preload" in str(rel).lower():
                href = link.get("href")
                as_attr = link.get("as", "")
                
                if href and ("font" in str(rel).lower() or as_attr == "font"):
                    fonts.append(urljoin(base_url, href))
        
        return fonts
    
    def _extract_icons(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract icon and favicon resources."""
        icons = []
        
        for link in soup.find_all("link"):
            rel = link.get("rel", [])
            if isinstance(rel, list):
                rel = " ".join(rel)
            
            if "icon" in str(rel).lower():
                href = link.get("href")
                if href:
                    icons.append(urljoin(base_url, href))
        
        return icons
    
    def _extract_preload_resources(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract preloaded resources."""
        preload = []
        
        for link in soup.find_all("link", {"rel": "preload"}):
            href = link.get("href")
            if href:
                preload.append(urljoin(base_url, href))
        
        return preload
    
    def _extract_prefetch_resources(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract prefetched resources."""
        prefetch = []
        
        for link in soup.find_all("link", {"rel": ["prefetch", "dns-prefetch", "preconnect"]}):
            href = link.get("href")
            if href:
                prefetch.append(urljoin(base_url, href))
        
        return prefetch
    
    def _categorize_link(self, href: str, links: Dict, base_url: str, base_domain: str, tag) -> None:
        """Categorize a single link."""
        # Protocol-based categorization
        if href.startswith("mailto:"):
            links["mailto"].append(href)
        elif href.startswith("tel:"):
            links["tel"].append(href)
        elif href.startswith("javascript:"):
            links["javascript"].append(href)
        elif href.startswith("#"):
            links["anchors"].append(href)
        else:
            # Resolve to absolute URL
            absolute_url = urljoin(base_url, href)
            link_domain = urlparse(absolute_url).netloc
            
            # Check for file downloads
            if self._is_file_link(href):
                file_type = self._get_file_type(href)
                links["files"][file_type].append(absolute_url)
            elif link_domain == base_domain:
                links["internal"].append(absolute_url)
            else:
                links["external"].append(absolute_url)
    
    def _is_file_link(self, href: str) -> bool:
        """Check if link points to a downloadable file."""
        href_lower = href.lower()
        for file_types in self.file_extensions.values():
            for ext in file_types:
                if href_lower.endswith(f".{ext}"):
                    return True
        return False
    
    def _get_file_type(self, href: str) -> str:
        """Determine file type category."""
        href_lower = href.lower()
        
        for category, extensions in self.file_extensions.items():
            for ext in extensions:
                if href_lower.endswith(f".{ext}"):
                    if category == "documents":
                        if ext in ["pdf"]:
                            return "pdf"
                        elif ext in ["doc", "docx"]:
                            return "doc"
                        elif ext in ["xls", "xlsx"]:
                            return "xls"
                    elif category == "images":
                        return "images"
                    elif category == "videos":
                        return "videos"
                    elif category == "audios":
                        return "audios"
                    elif category == "archives":
                        return "archives"
        
        return "other"
    
    def _extract_navigation_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract navigation-specific links."""
        nav_links = []
        
        # Links within nav elements
        for nav in soup.find_all("nav"):
            for link in nav.find_all("a", href=True):
                href = link.get("href")
                if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    nav_links.append(urljoin(base_url, href))
        
        # Links with navigation-related classes
        nav_classes = ["nav", "menu", "navigation", "navbar", "breadcrumb"]
        for class_name in nav_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                for link in element.find_all("a", href=True):
                    href = link.get("href")
                    if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        nav_links.append(urljoin(base_url, href))
        
        return list(set(nav_links))
    
    def _extract_social_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract social media links."""
        social_domains = [
            "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
            "youtube.com", "tiktok.com", "pinterest.com", "snapchat.com",
            "telegram.org", "whatsapp.com", "github.com"
        ]
        
        social_links = []
        
        for link in soup.find_all("a", href=True):
            href = link.get("href")
            if href:
                absolute_url = urljoin(base_url, href)
                domain = urlparse(absolute_url).netloc.lower()
                
                # Check if it's a social media domain
                for social_domain in social_domains:
                    if social_domain in domain:
                        social_links.append(absolute_url)
                        break
        
        return list(set(social_links))
    
    def _remove_duplicates_from_links(self, links: Dict) -> None:
        """Remove duplicates from all link categories."""
        for category in links:
            if isinstance(links[category], list):
                links[category] = list(dict.fromkeys(links[category]))
            elif isinstance(links[category], dict):
                for subcat in links[category]:
                    links[category][subcat] = list(dict.fromkeys(links[category][subcat]))
    
    def _analyze_resources(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """Analyze resource usage and patterns."""
        analysis = {
            "total_resources": 0,
            "external_resources": 0,
            "resource_domains": set(),
            "largest_category": "",
            "has_lazy_loading": False,
            "has_responsive_images": False,
            "cdn_usage": [],
        }
        
        # Analyze all resources
        resources = self.extract_resources(soup, base_url)
        base_domain = urlparse(base_url).netloc
        
        resource_counts = {}
        
        for category, resource_list in resources.items():
            count = len(resource_list)
            resource_counts[category] = count
            analysis["total_resources"] += count
            
            # Check for external resources and CDNs
            for resource_url in resource_list:
                resource_domain = urlparse(resource_url).netloc
                analysis["resource_domains"].add(resource_domain)
                
                if resource_domain != base_domain:
                    analysis["external_resources"] += 1
                    
                    # Check for common CDNs
                    if self._is_cdn_domain(resource_domain):
                        analysis["cdn_usage"].append(resource_domain)
        
        # Find largest category
        if resource_counts:
            analysis["largest_category"] = max(resource_counts, key=resource_counts.get)
        
        # Check for lazy loading
        analysis["has_lazy_loading"] = self._check_lazy_loading(soup)
        
        # Check for responsive images
        analysis["has_responsive_images"] = self._check_responsive_images(soup)
        
        # Convert set to list for JSON serialization
        analysis["resource_domains"] = list(analysis["resource_domains"])
        analysis["cdn_usage"] = list(set(analysis["cdn_usage"]))
        
        return analysis
    
    def _analyze_optimization(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze optimization techniques used."""
        optimization = {
            "has_minified_resources": False,
            "has_compression": False,
            "has_preload": False,
            "has_prefetch": False,
            "has_async_scripts": False,
            "has_defer_scripts": False,
            "critical_css_inline": False,
        }
        
        # Check for preload/prefetch
        optimization["has_preload"] = bool(soup.find("link", {"rel": "preload"}))
        optimization["has_prefetch"] = bool(soup.find("link", {"rel": ["prefetch", "dns-prefetch"]}))
        
        # Check script loading strategies
        scripts = soup.find_all("script", src=True)
        optimization["has_async_scripts"] = any(script.get("async") for script in scripts)
        optimization["has_defer_scripts"] = any(script.get("defer") for script in scripts)
        
        # Check for inline CSS (potential critical CSS)
        style_tags = soup.find_all("style")
        optimization["critical_css_inline"] = len(style_tags) > 0
        
        # Check for minified resources (simplified check)
        for script in scripts:
            src = script.get("src", "")
            if ".min." in src or "minified" in src:
                optimization["has_minified_resources"] = True
                break
        
        return optimization
    
    def _analyze_security(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """Analyze security-related aspects of resources."""
        security = {
            "external_scripts": 0,
            "external_stylesheets": 0,
            "has_sri": False,
            "mixed_content": [],
            "suspicious_domains": [],
        }
        
        base_domain = urlparse(base_url).netloc
        is_https = urlparse(base_url).scheme == "https"
        
        # Check external scripts and SRI
        for script in soup.find_all("script", src=True):
            src = script.get("src")
            if src:
                script_domain = urlparse(urljoin(base_url, src)).netloc
                if script_domain != base_domain:
                    security["external_scripts"] += 1
                
                # Check for Subresource Integrity
                if script.get("integrity"):
                    security["has_sri"] = True
                
                # Check for mixed content
                if is_https and src.startswith("http://"):
                    security["mixed_content"].append(src)
        
        # Check external stylesheets
        for link in soup.find_all("link", {"rel": "stylesheet"}):
            href = link.get("href")
            if href:
                link_domain = urlparse(urljoin(base_url, href)).netloc
                if link_domain != base_domain:
                    security["external_stylesheets"] += 1
                
                # Check for mixed content
                if is_https and href.startswith("http://"):
                    security["mixed_content"].append(href)
        
        return security
    
    def _is_cdn_domain(self, domain: str) -> bool:
        """Check if domain is a known CDN."""
        cdn_patterns = [
            "cdn", "cloudfront", "cloudflare", "jsdelivr", "unpkg",
            "googleapis", "gstatic", "bootstrapcdn", "cdnjs"
        ]
        
        return any(pattern in domain.lower() for pattern in cdn_patterns)
    
    def _check_lazy_loading(self, soup: BeautifulSoup) -> bool:
        """Check if lazy loading is implemented."""
        lazy_attributes = ["data-src", "data-lazy-src", "loading"]
        
        for img in soup.find_all("img"):
            for attr in lazy_attributes:
                if img.get(attr):
                    return True
        
        return False
    
    def _check_responsive_images(self, soup: BeautifulSoup) -> bool:
        """Check if responsive images are used."""
        # Check for srcset or picture elements
        return bool(
            soup.find("img", srcset=True) or 
            soup.find("picture") or 
            soup.find("source")
        )
    
    def get_resource_summary(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of extracted resources."""
        resource_data = resources.get("resources", {})
        analysis_data = resources.get("analysis", {})
        
        summary = {
            "total_resources": analysis_data.get("total_resources", 0),
            "external_resources": analysis_data.get("external_resources", 0),
            "images_count": len(resource_data.get("images", [])),
            "scripts_count": len(resource_data.get("scripts", [])),
            "stylesheets_count": len(resource_data.get("stylesheets", [])),
            "largest_category": analysis_data.get("largest_category", ""),
            "uses_cdn": len(analysis_data.get("cdn_usage", [])) > 0,
            "has_optimization": any(resources.get("optimization", {}).values()),
            "security_score": self._calculate_security_score(resources.get("security", {})),
        }
        
        return summary
    
    def _calculate_security_score(self, security_data: Dict[str, Any]) -> float:
        """Calculate a basic security score."""
        score = 100.0
        
        # Deduct points for security issues
        if security_data.get("external_scripts", 0) > 0 and not security_data.get("has_sri", False):
            score -= 20  # External scripts without SRI
        
        if security_data.get("mixed_content", []):
            score -= 30  # Mixed content issues
        
        if security_data.get("suspicious_domains", []):
            score -= 25  # Suspicious domains
        
        return max(0, score) 