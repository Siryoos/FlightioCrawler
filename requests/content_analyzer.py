"""
Content Analyzer for comprehensive web page content analysis.
"""

from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import re


class ContentAnalyzer:
    """
    Advanced content analyzer for web pages.
    
    Features:
    - Structure analysis (headings, forms, tables)
    - Text statistics and readability
    - Interactive elements detection
    - Semantic HTML5 analysis
    - Content quality assessment
    """
    
    def __init__(self):
        """Initialize the content analyzer."""
        self.semantic_elements = [
            "nav", "article", "section", "aside", 
            "header", "footer", "main", "figure", 
            "figcaption", "time", "mark"
        ]
        
        self.interactive_elements = [
            "button", "input", "select", "textarea", 
            "a", "area", "details", "summary"
        ]
    
    def analyze_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Perform comprehensive content analysis.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            
        Returns:
            Dictionary containing detailed content analysis
        """
        analysis = {
            "headings": self._analyze_headings(soup),
            "forms": self._analyze_forms(soup),
            "tables": self._analyze_tables(soup),
            "lists": self._analyze_lists(soup),
            "text_stats": self._analyze_text_statistics(soup),
            "interactive_elements": self._analyze_interactive_elements(soup),
            "semantic_elements": self._analyze_semantic_elements(soup),
            "content_quality": self._assess_content_quality(soup),
            "readability": self._calculate_readability(soup),
            "media_elements": self._analyze_media_elements(soup),
        }
        
        return analysis
    
    def _analyze_headings(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Analyze heading structure and hierarchy."""
        headings = {f"h{i}": [] for i in range(1, 7)}
        
        for i in range(1, 7):
            for heading in soup.find_all(f"h{i}"):
                text = heading.get_text(strip=True)
                if text:
                    headings[f"h{i}"].append(text)
        
        return headings
    
    def _analyze_forms(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyze forms and form elements."""
        forms = []
        
        for form in soup.find_all("form"):
            form_data = {
                "action": form.get("action", ""),
                "method": form.get("method", "GET").upper(),
                "id": form.get("id", ""),
                "name": form.get("name", ""),
                "enctype": form.get("enctype", ""),
                "inputs": [],
                "validation": {
                    "has_required_fields": False,
                    "has_validation": False,
                    "has_csrf_protection": False,
                }
            }
            
            # Analyze form inputs
            for input_tag in form.find_all(["input", "select", "textarea", "button"]):
                input_data = {
                    "tag": input_tag.name,
                    "type": input_tag.get("type", "text"),
                    "name": input_tag.get("name", ""),
                    "id": input_tag.get("id", ""),
                    "required": input_tag.get("required") is not None,
                    "placeholder": input_tag.get("placeholder", ""),
                    "pattern": input_tag.get("pattern", ""),
                    "maxlength": input_tag.get("maxlength", ""),
                    "minlength": input_tag.get("minlength", ""),
                }
                form_data["inputs"].append(input_data)
                
                # Check for validation
                if input_data["required"] or input_data["pattern"]:
                    form_data["validation"]["has_required_fields"] = True
                    form_data["validation"]["has_validation"] = True
            
            # Check for CSRF protection
            csrf_inputs = form.find_all("input", {"name": re.compile(r"csrf|token", re.I)})
            if csrf_inputs:
                form_data["validation"]["has_csrf_protection"] = True
            
            forms.append(form_data)
        
        return forms
    
    def _analyze_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Analyze table structure and accessibility."""
        tables = []
        
        for table in soup.find_all("table"):
            table_data = {
                "id": table.get("id", ""),
                "class": " ".join(table.get("class", [])),
                "caption": "",
                "rows": len(table.find_all("tr")),
                "columns": 0,
                "headers": [],
                "accessibility": {
                    "has_caption": False,
                    "has_headers": False,
                    "has_scope": False,
                    "has_summary": False,
                }
            }
            
            # Caption
            caption = table.find("caption")
            if caption:
                table_data["caption"] = caption.get_text(strip=True)
                table_data["accessibility"]["has_caption"] = True
            
            # Headers
            headers = table.find_all("th")
            if headers:
                table_data["headers"] = [th.get_text(strip=True) for th in headers]
                table_data["accessibility"]["has_headers"] = True
                
                # Check for scope attributes
                for th in headers:
                    if th.get("scope"):
                        table_data["accessibility"]["has_scope"] = True
                        break
            
            # Column count (from first row)
            first_row = table.find("tr")
            if first_row:
                cells = first_row.find_all(["td", "th"])
                table_data["columns"] = len(cells)
            
            # Summary attribute (deprecated but still used)
            if table.get("summary"):
                table_data["accessibility"]["has_summary"] = True
            
            tables.append(table_data)
        
        return tables
    
    def _analyze_lists(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Analyze list elements."""
        return {
            "unordered": len(soup.find_all("ul")),
            "ordered": len(soup.find_all("ol")),
            "definition": len(soup.find_all("dl")),
        }
    
    def _analyze_text_statistics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze text content and statistics."""
        # Get all text content
        text = soup.get_text()
        paragraphs = soup.find_all("p")
        
        # Basic statistics
        stats = {
            "total_length": len(text),
            "total_characters_no_spaces": len(text.replace(" ", "")),
            "word_count": len(text.split()),
            "sentence_count": len(re.split(r'[.!?]+', text)),
            "paragraph_count": len(paragraphs),
            "average_paragraph_length": 0,
            "average_sentence_length": 0,
            "average_word_length": 0,
        }
        
        # Calculate averages
        if paragraphs:
            avg_para_length = sum(len(p.get_text()) for p in paragraphs) / len(paragraphs)
            stats["average_paragraph_length"] = round(avg_para_length, 2)
        
        if stats["sentence_count"] > 0:
            stats["average_sentence_length"] = round(stats["word_count"] / stats["sentence_count"], 2)
        
        words = text.split()
        if words:
            avg_word_length = sum(len(word.strip('.,!?;:"()[]{}')) for word in words) / len(words)
            stats["average_word_length"] = round(avg_word_length, 2)
        
        return stats
    
    def _analyze_interactive_elements(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Analyze interactive elements count."""
        elements = {}
        
        for element_type in self.interactive_elements:
            elements[element_type] = len(soup.find_all(element_type))
        
        # Special cases
        elements["clickable_areas"] = len(soup.find_all("area"))
        elements["form_controls"] = (
            elements.get("input", 0) + 
            elements.get("select", 0) + 
            elements.get("textarea", 0)
        )
        
        return elements
    
    def _analyze_semantic_elements(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Analyze semantic HTML5 elements."""
        elements = {}
        
        for element_type in self.semantic_elements:
            elements[element_type] = len(soup.find_all(element_type))
        
        return elements
    
    def _assess_content_quality(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Assess overall content quality."""
        quality = {
            "has_main_content": len(soup.find_all("main")) > 0,
            "has_navigation": len(soup.find_all("nav")) > 0,
            "has_footer": len(soup.find_all("footer")) > 0,
            "has_header": len(soup.find_all("header")) > 0,
            "content_to_code_ratio": 0,
            "heading_structure_score": 0,
            "semantic_score": 0,
        }
        
        # Content to code ratio
        text_length = len(soup.get_text())
        html_length = len(str(soup))
        if html_length > 0:
            quality["content_to_code_ratio"] = round((text_length / html_length) * 100, 2)
        
        # Heading structure score (simplified)
        h1_count = len(soup.find_all("h1"))
        has_proper_hierarchy = h1_count == 1  # Should have exactly one H1
        
        if has_proper_hierarchy:
            quality["heading_structure_score"] = 100
        elif h1_count == 0:
            quality["heading_structure_score"] = 0
        else:
            quality["heading_structure_score"] = 50  # Multiple H1s
        
        # Semantic score
        semantic_count = sum(len(soup.find_all(elem)) for elem in self.semantic_elements)
        if semantic_count >= 5:
            quality["semantic_score"] = 100
        elif semantic_count >= 3:
            quality["semantic_score"] = 75
        elif semantic_count >= 1:
            quality["semantic_score"] = 50
        else:
            quality["semantic_score"] = 0
        
        return quality
    
    def _calculate_readability(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Calculate basic readability metrics."""
        text = soup.get_text()
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        
        readability = {
            "flesch_reading_ease": 0,
            "flesch_kincaid_grade": 0,
            "automated_readability_index": 0,
            "difficulty_level": "unknown",
        }
        
        if len(words) > 0 and len(sentences) > 1:
            # Calculate syllables (simplified - count vowel groups)
            total_syllables = 0
            for word in words:
                word = word.lower().strip('.,!?;:"()[]{}')
                syllables = len(re.findall(r'[aeiouy]+', word))
                total_syllables += max(1, syllables)  # At least 1 syllable per word
            
            # Flesch Reading Ease
            avg_sentence_length = len(words) / len(sentences)
            avg_syllables_per_word = total_syllables / len(words)
            
            flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            readability["flesch_reading_ease"] = round(flesch_score, 2)
            
            # Flesch-Kincaid Grade Level
            fk_grade = (0.39 * avg_sentence_length) + (11.8 * avg_syllables_per_word) - 15.59
            readability["flesch_kincaid_grade"] = round(fk_grade, 2)
            
            # Automated Readability Index
            characters = sum(len(word.strip('.,!?;:"()[]{}')) for word in words)
            ari = (4.71 * (characters / len(words))) + (0.5 * (len(words) / len(sentences))) - 21.43
            readability["automated_readability_index"] = round(ari, 2)
            
            # Difficulty level based on Flesch score
            if flesch_score >= 90:
                readability["difficulty_level"] = "very_easy"
            elif flesch_score >= 80:
                readability["difficulty_level"] = "easy"
            elif flesch_score >= 70:
                readability["difficulty_level"] = "fairly_easy"
            elif flesch_score >= 60:
                readability["difficulty_level"] = "standard"
            elif flesch_score >= 50:
                readability["difficulty_level"] = "fairly_difficult"
            elif flesch_score >= 30:
                readability["difficulty_level"] = "difficult"
            else:
                readability["difficulty_level"] = "very_difficult"
        
        return readability
    
    def _analyze_media_elements(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze media elements (images, videos, audio)."""
        media = {
            "images": {
                "total": 0,
                "with_alt": 0,
                "without_alt": 0,
                "decorative": 0,
                "formats": {},
            },
            "videos": {
                "total": 0,
                "with_controls": 0,
                "autoplay": 0,
                "with_captions": 0,
            },
            "audio": {
                "total": 0,
                "with_controls": 0,
                "autoplay": 0,
            },
        }
        
        # Analyze images
        images = soup.find_all("img")
        media["images"]["total"] = len(images)
        
        for img in images:
            alt = img.get("alt")
            if alt is not None:
                media["images"]["with_alt"] += 1
                if alt == "":
                    media["images"]["decorative"] += 1
            else:
                media["images"]["without_alt"] += 1
            
            # Check image format from src
            src = img.get("src", "")
            if src:
                ext = src.split('.')[-1].lower()
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                    media["images"]["formats"][ext] = media["images"]["formats"].get(ext, 0) + 1
        
        # Analyze videos
        videos = soup.find_all("video")
        media["videos"]["total"] = len(videos)
        
        for video in videos:
            if video.get("controls"):
                media["videos"]["with_controls"] += 1
            if video.get("autoplay"):
                media["videos"]["autoplay"] += 1
            if video.find("track", {"kind": "captions"}):
                media["videos"]["with_captions"] += 1
        
        # Analyze audio
        audios = soup.find_all("audio")
        media["audio"]["total"] = len(audios)
        
        for audio in audios:
            if audio.get("controls"):
                media["audio"]["with_controls"] += 1
            if audio.get("autoplay"):
                media["audio"]["autoplay"] += 1
        
        return media
    
    def get_content_summary(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of content analysis."""
        summary = {
            "total_headings": sum(len(headings) for headings in analysis["headings"].values()),
            "total_forms": len(analysis["forms"]),
            "total_tables": len(analysis["tables"]),
            "total_lists": sum(analysis["lists"].values()),
            "word_count": analysis["text_stats"]["word_count"],
            "paragraph_count": analysis["text_stats"]["paragraph_count"],
            "interactive_elements_count": sum(analysis["interactive_elements"].values()),
            "semantic_elements_count": sum(analysis["semantic_elements"].values()),
            "content_quality_score": self._calculate_overall_quality_score(analysis),
            "readability_level": analysis["readability"]["difficulty_level"],
            "media_elements_count": (
                analysis["media_elements"]["images"]["total"] +
                analysis["media_elements"]["videos"]["total"] +
                analysis["media_elements"]["audio"]["total"]
            ),
        }
        
        return summary
    
    def _calculate_overall_quality_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate an overall content quality score."""
        scores = []
        
        # Content structure score
        quality_data = analysis["content_quality"]
        structure_score = (
            (100 if quality_data["has_main_content"] else 0) +
            (100 if quality_data["has_navigation"] else 0) +
            (100 if quality_data["has_header"] else 0) +
            (100 if quality_data["has_footer"] else 0)
        ) / 4
        scores.append(structure_score)
        
        # Heading structure score
        scores.append(quality_data["heading_structure_score"])
        
        # Semantic score
        scores.append(quality_data["semantic_score"])
        
        # Accessibility score (simplified)
        images_data = analysis["media_elements"]["images"]
        if images_data["total"] > 0:
            accessibility_score = (images_data["with_alt"] / images_data["total"]) * 100
        else:
            accessibility_score = 100  # No images to check
        scores.append(accessibility_score)
        
        return round(sum(scores) / len(scores), 2) 