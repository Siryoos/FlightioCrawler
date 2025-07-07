import os
import re
import json
import time
import random
import threading
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from utils.file_utils import sanitize_filename


class AdvancedCrawler:
    """Enhanced crawler with JavaScript support and anti-detection."""

    def __init__(self, save_dir: str = None, use_selenium: bool = True):
        self.save_dir = save_dir or os.path.join(os.path.dirname(__file__), "pages")
        os.makedirs(self.save_dir, exist_ok=True)
        self.use_selenium = use_selenium
        self.driver = None

    def setup_driver(self):
        """Setup Selenium driver with anti-detection measures."""
        try:
            # Use undetected-chromedriver for better anti-bot evasion
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # Additional options
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

            # Random user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            ]
            options.add_argument(f"user-agent={random.choice(user_agents)}")

            self.driver = uc.Chrome(options=options)

            # Execute anti-detection scripts
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({state: 'granted'})
                        })
                    });
                """
                },
            )

        except Exception as e:
            # Fallback to standard Chrome
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            self.driver = webdriver.Chrome(options=options)

    def human_like_delay(self):
        """Add random delay to mimic human behavior."""
        time.sleep(random.uniform(0.5, 2.0))

    def extract_with_selenium(self, url: str) -> Tuple[str, Dict]:
        """Extract content using Selenium for JavaScript-heavy sites."""
        if not self.driver:
            self.setup_driver()

        try:
            # Navigate to URL
            self.driver.get(url)

            # Random mouse movements and scrolls
            self.human_like_delay()

            # Wait for dynamic content
            wait = WebDriverWait(self.driver, 20)

            # Scroll to trigger lazy loading
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            while True:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(2)
                new_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                if new_height == last_height:
                    break
                last_height = new_height

            # Get page source after JavaScript execution
            html = self.driver.page_source

            # Collect performance and network data
            performance_data = self.driver.execute_script(
                """
                return {
                    timing: performance.timing,
                    resources: performance.getEntriesByType('resource').map(r => ({
                        name: r.name,
                        type: r.initiatorType,
                        duration: r.duration
                    }))
                };
            """
            )

            # Get console logs
            console_logs = self.driver.get_log("browser")

            # Get cookies
            cookies = self.driver.get_cookies()

            # Extract AJAX/XHR endpoints
            xhr_endpoints = self.driver.execute_script(
                """
                return Array.from(performance.getEntriesByType('resource'))
                    .filter(r => r.initiatorType === 'xmlhttprequest' || r.initiatorType === 'fetch')
                    .map(r => r.name);
            """
            )

            selenium_data = {
                "final_url": self.driver.current_url,
                "performance": performance_data,
                "console_logs": console_logs,
                "cookies": cookies,
                "xhr_endpoints": xhr_endpoints,
                "javascript_enabled": True,
            }

            return html, selenium_data

        except Exception as e:
            raise Exception(f"Selenium extraction failed: {str(e)}")

    def close_driver(self):
        """Close the Selenium driver if it's running."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing driver: {e}")
            finally:
                self.driver = None

    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract comprehensive page metadata."""
        meta = {
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
        }

        # Title
        title_tag = soup.find("title")
        if title_tag:
            meta["title"] = title_tag.get_text(strip=True)

        # Meta tags
        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            property = tag.get("property", "").lower()
            content = tag.get("content", "")

            if name == "description":
                meta["description"] = content
            elif name == "keywords":
                meta["keywords"] = [k.strip() for k in content.split(",")]
            elif name == "author":
                meta["author"] = content
            elif name == "robots":
                meta["robots"] = content
            elif name in ["language", "lang"]:
                meta["language"] = content

            # Open Graph
            if property.startswith("og:"):
                meta["og_data"][property] = content

            # Twitter Card
            if name.startswith("twitter:") or property.startswith("twitter:"):
                key = name or property
                meta["twitter_data"][key] = content

        # Language detection
        html_tag = soup.find("html")
        if html_tag and not meta["language"]:
            meta["language"] = html_tag.get("lang", "")

        # Canonical URL
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical:
            meta["canonical"] = canonical.get("href", "")

        # JSON-LD and Schema.org
        for script in soup.find_all(
            "script", {"type": ["application/ld+json", "application/json"]}
        ):
            try:
                data = json.loads(script.string)
                if "@context" in str(data):
                    meta["schema_org"].append(data)
                else:
                    meta["json_ld"].append(data)
            except:
                pass

        return meta

    def extract_ajax_data(self, soup: BeautifulSoup) -> Dict:
        """Extract AJAX endpoints and API calls from JavaScript."""
        ajax_data = {"api_endpoints": [], "websocket_urls": [], "data_attributes": {}}

        # Find API endpoints in scripts
        for script in soup.find_all("script"):
            if script.string:
                # Common API patterns
                api_patterns = [
                    r'(?:fetch|axios|ajax)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                    r'api[Uu]rl\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                    r'endpoint\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
                    r'[\'"](?:GET|POST|PUT|DELETE)[\'"],\s*[\'"]([^\'"]+)[\'"]',
                ]

                for pattern in api_patterns:
                    matches = re.findall(pattern, script.string)
                    ajax_data["api_endpoints"].extend(matches)

                # WebSocket URLs
                ws_pattern = r'wss?://[^\s\'"]+'
                ws_matches = re.findall(ws_pattern, script.string)
                ajax_data["websocket_urls"].extend(ws_matches)

        # Data attributes that might contain API info
        for element in soup.find_all(attrs={"data-api": True}):
            ajax_data["data_attributes"][element.name] = element.get("data-api")

        # Remove duplicates
        ajax_data["api_endpoints"] = list(set(ajax_data["api_endpoints"]))
        ajax_data["websocket_urls"] = list(set(ajax_data["websocket_urls"]))

        return ajax_data

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract and categorize all links."""
        links = {
            "internal": [],
            "external": [],
            "mailto": [],
            "tel": [],
            "javascript": [],
            "anchors": [],
            "files": {"pdf": [], "doc": [], "xls": [], "other": []},
        }

        base_domain = urlparse(base_url).netloc

        # Extract from various sources
        link_sources = [
            ("a", "href"),
            ("area", "href"),
            ("link", "href"),
            ("base", "href"),
        ]

        for tag_name, attr_name in link_sources:
            for tag in soup.find_all(tag_name):
                href = tag.get(attr_name, "").strip()
                if not href:
                    continue

                # Categorize
                if href.startswith("mailto:"):
                    links["mailto"].append(href)
                elif href.startswith("tel:"):
                    links["tel"].append(href)
                elif href.startswith("javascript:"):
                    links["javascript"].append(href)
                elif href.startswith("#"):
                    links["anchors"].append(href)
                else:
                    absolute_url = urljoin(base_url, href)
                    link_domain = urlparse(absolute_url).netloc

                    # Check for files
                    if href.lower().endswith(".pdf"):
                        links["files"]["pdf"].append(absolute_url)
                    elif href.lower().endswith((".doc", ".docx")):
                        links["files"]["doc"].append(absolute_url)
                    elif href.lower().endswith((".xls", ".xlsx")):
                        links["files"]["xls"].append(absolute_url)
                    elif re.search(r"\.(zip|rar|7z|tar|gz)$", href.lower()):
                        links["files"]["other"].append(absolute_url)
                    elif link_domain == base_domain:
                        links["internal"].append(absolute_url)
                    else:
                        links["external"].append(absolute_url)

        # Remove duplicates
        for category in links:
            if isinstance(links[category], list):
                links[category] = list(dict.fromkeys(links[category]))
            else:
                for subcat in links[category]:
                    links[category][subcat] = list(
                        dict.fromkeys(links[category][subcat])
                    )

        return links

    def extract_resources(
        self, soup: BeautifulSoup, base_url: str
    ) -> Dict[str, List[str]]:
        """Extract all page resources."""
        resources = {
            "images": [],
            "scripts": [],
            "stylesheets": [],
            "videos": [],
            "audios": [],
            "iframes": [],
            "fonts": [],
            "icons": [],
        }

        # Images - check multiple attributes
        for img in soup.find_all(["img", "picture", "source"]):
            for attr in ["src", "data-src", "data-lazy-src", "srcset"]:
                value = img.get(attr)
                if value:
                    if "srcset" in attr:
                        # Parse srcset
                        urls = re.findall(r"([^\s]+)\s+\d+[wx]", value)
                        resources["images"].extend([urljoin(base_url, u) for u in urls])
                    else:
                        resources["images"].append(urljoin(base_url, value))

        # Scripts
        for script in soup.find_all("script"):
            src = script.get("src")
            if src:
                resources["scripts"].append(urljoin(base_url, src))

        # Stylesheets
        for link in soup.find_all("link"):
            if link.get("rel") and "stylesheet" in link.get("rel"):
                href = link.get("href")
                if href:
                    resources["stylesheets"].append(urljoin(base_url, href))

        # Videos
        for video in soup.find_all(["video", "source"]):
            src = video.get("src") or video.get("data-src")
            if src:
                resources["videos"].append(urljoin(base_url, src))

        # Audio
        for audio in soup.find_all("audio"):
            src = audio.get("src")
            if src:
                resources["audios"].append(urljoin(base_url, src))

        # Iframes
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src")
            if src:
                resources["iframes"].append(urljoin(base_url, src))

        # Fonts
        for link in soup.find_all("link"):
            if link.get("rel") and "font" in str(link.get("rel")):
                href = link.get("href")
                if href:
                    resources["fonts"].append(urljoin(base_url, href))

        # Icons/Favicons
        for link in soup.find_all("link"):
            rel = link.get("rel", [])
            if isinstance(rel, list):
                rel = " ".join(rel)
            if "icon" in str(rel):
                href = link.get("href")
                if href:
                    resources["icons"].append(urljoin(base_url, href))

        # Remove duplicates
        for category in resources:
            resources[category] = list(dict.fromkeys(resources[category]))

        return resources

    def analyze_content(self, soup: BeautifulSoup) -> Dict:
        """Analyze page content structure."""
        analysis = {
            "headings": {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
            "forms": [],
            "tables": [],
            "lists": {"ul": 0, "ol": 0, "dl": 0},
            "text_stats": {
                "total_length": 0,
                "word_count": 0,
                "paragraph_count": 0,
                "average_paragraph_length": 0,
            },
            "interactive_elements": {
                "buttons": 0,
                "inputs": 0,
                "selects": 0,
                "textareas": 0,
                "links": 0,
            },
            "semantic_elements": {
                "nav": 0,
                "article": 0,
                "section": 0,
                "aside": 0,
                "header": 0,
                "footer": 0,
                "main": 0,
            },
        }

        # Headings
        for i in range(1, 7):
            for heading in soup.find_all(f"h{i}"):
                text = heading.get_text(strip=True)
                if text:
                    analysis["headings"][f"h{i}"].append(text)

        # Forms
        for form in soup.find_all("form"):
            form_data = {
                "action": form.get("action", ""),
                "method": form.get("method", "GET").upper(),
                "id": form.get("id", ""),
                "name": form.get("name", ""),
                "inputs": [],
            }

            for input_tag in form.find_all(["input", "select", "textarea", "button"]):
                input_data = {
                    "tag": input_tag.name,
                    "type": input_tag.get("type", "text"),
                    "name": input_tag.get("name", ""),
                    "id": input_tag.get("id", ""),
                    "required": input_tag.get("required") is not None,
                    "placeholder": input_tag.get("placeholder", ""),
                }
                form_data["inputs"].append(input_data)

            analysis["forms"].append(form_data)

        # Tables
        for table in soup.find_all("table"):
            table_data = {
                "id": table.get("id", ""),
                "class": " ".join(table.get("class", [])),
                "rows": len(table.find_all("tr")),
                "headers": [th.get_text(strip=True) for th in table.find_all("th")],
            }
            analysis["tables"].append(table_data)

        # Lists
        analysis["lists"]["ul"] = len(soup.find_all("ul"))
        analysis["lists"]["ol"] = len(soup.find_all("ol"))
        analysis["lists"]["dl"] = len(soup.find_all("dl"))

        # Text analysis
        paragraphs = soup.find_all("p")
        text = soup.get_text()
        analysis["text_stats"]["total_length"] = len(text)
        analysis["text_stats"]["word_count"] = len(text.split())
        analysis["text_stats"]["paragraph_count"] = len(paragraphs)

        if paragraphs:
            avg_length = sum(len(p.get_text()) for p in paragraphs) / len(paragraphs)
            analysis["text_stats"]["average_paragraph_length"] = round(avg_length, 2)

        # Interactive elements
        analysis["interactive_elements"]["buttons"] = len(soup.find_all("button"))
        analysis["interactive_elements"]["inputs"] = len(soup.find_all("input"))
        analysis["interactive_elements"]["selects"] = len(soup.find_all("select"))
        analysis["interactive_elements"]["textareas"] = len(soup.find_all("textarea"))
        analysis["interactive_elements"]["links"] = len(soup.find_all("a"))

        # Semantic HTML5 elements
        for elem in ["nav", "article", "section", "aside", "header", "footer", "main"]:
            analysis["semantic_elements"][elem] = len(soup.find_all(elem))

        return analysis

    def crawl(self, url: str, progress_callback=None) -> Tuple[bool, Dict, str]:
        """Crawl URL with JavaScript support."""
        start_time = time.time()

        try:
            if progress_callback:
                progress_callback("Initializing crawler...")

            # Try Selenium first for JavaScript content
            html = None
            selenium_data = {}

            if self.use_selenium:
                try:
                    if progress_callback:
                        progress_callback("Loading page with JavaScript...")
                    html, selenium_data = self.extract_with_selenium(url)
                except Exception as e:
                    if progress_callback:
                        progress_callback(
                            f"Selenium failed, falling back to requests: {str(e)}"
                        )
                    self.use_selenium = False

            # Fallback to requests
            if not html:
                if progress_callback:
                    progress_callback("Fetching page...")
                response = requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                response.raise_for_status()
                html = response.text
                selenium_data = {
                    "final_url": response.url,
                    "javascript_enabled": False,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                }

            if progress_callback:
                progress_callback("Parsing content...")

            # Parse HTML
            soup = BeautifulSoup(html, "html.parser")

            # Extract AJAX data
            ajax_data = self.extract_ajax_data(soup)

            # Compile crawl data
            crawl_data = {
                "url": url,
                "final_url": selenium_data.get("final_url", url),
                "timestamp": datetime.now().isoformat(),
                "crawler_info": {
                    "javascript_enabled": selenium_data.get(
                        "javascript_enabled", False
                    ),
                    "selenium_used": self.use_selenium,
                    "crawl_time": time.time() - start_time,
                },
                "response": selenium_data,
                "metadata": self.extract_metadata(
                    soup, selenium_data.get("final_url", url)
                ),
                "links": self.extract_links(soup, selenium_data.get("final_url", url)),
                "resources": self.extract_resources(
                    soup, selenium_data.get("final_url", url)
                ),
                "content_analysis": self.analyze_content(soup),
                "ajax_data": ajax_data,
            }

            if progress_callback:
                progress_callback("Saving data...")

            # Save files
            base_filename = sanitize_filename(url)

            # Save HTML
            html_path = os.path.join(self.save_dir, f"{base_filename}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            # Save metadata
            json_path = os.path.join(self.save_dir, f"{base_filename}_metadata.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(crawl_data, f, indent=2, ensure_ascii=False)

            if progress_callback:
                progress_callback("Complete!")

            return True, crawl_data, f"Saved to:\n{html_path}\n{json_path}"

        except Exception as e:
            return False, {}, f"Crawl failed: {str(e)}"

        finally:
            # Clean up driver
            self.close_driver()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_driver()


class CrawlerGUI:
    """GUI for the advanced crawler."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Advanced URL Crawler")
        self.root.geometry("1000x750")

        self.crawler = None
        self.crawl_thread = None

        self.setup_ui()

    def setup_ui(self):
        """Setup GUI components."""
        style = ttk.Style()
        style.theme_use("clam")

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # URL input section
        input_frame = ttk.LabelFrame(main_frame, text="URL Input", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(input_frame, text="URL:").grid(row=0, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(input_frame, width=60)
        self.url_entry.grid(row=0, column=1, padx=5)
        self.url_entry.bind("<Return>", lambda e: self.fetch_url())

        # JavaScript checkbox
        self.js_var = tk.BooleanVar(value=True)
        self.js_check = ttk.Checkbutton(
            input_frame, text="Enable JavaScript", variable=self.js_var
        )
        self.js_check.grid(row=0, column=2, padx=5)

        self.fetch_button = ttk.Button(
            input_frame, text="Crawl", command=self.fetch_url
        )
        self.fetch_button.grid(row=0, column=3, padx=5)

        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(input_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=1, column=0, columnspan=4, pady=5)

        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Crawl Results", padding="10")
        results_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5
        )

        # Notebook
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create tabs
        self.summary_text = scrolledtext.ScrolledText(
            self.notebook, height=25, width=90
        )
        self.notebook.add(self.summary_text, text="Summary")

        self.metadata_text = scrolledtext.ScrolledText(
            self.notebook, height=25, width=90
        )
        self.notebook.add(self.metadata_text, text="Metadata")

        self.links_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.links_text, text="Links")

        self.resources_text = scrolledtext.ScrolledText(
            self.notebook, height=25, width=90
        )
        self.notebook.add(self.resources_text, text="Resources")

        self.ajax_text = scrolledtext.ScrolledText(self.notebook, height=25, width=90)
        self.notebook.add(self.ajax_text, text="AJAX/API")

        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

    def update_progress(self, message: str):
        """Update progress message."""
        self.progress_var.set(message)
        self.root.update_idletasks()

    def display_results(self, crawl_data: Dict):
        """Display crawl results."""
        # Summary
        js_status = (
            "Enabled"
            if crawl_data["crawler_info"]["javascript_enabled"]
            else "Disabled"
        )
        summary = f"""URL: {crawl_data['url']}
Final URL: {crawl_data['final_url']}
JavaScript: {js_status}
Crawl Time: {crawl_data['crawler_info']['crawl_time']:.2f}s

Title: {crawl_data['metadata']['title']}
Description: {crawl_data['metadata']['description']}
Language: {crawl_data['metadata']['language']}

Content Analysis:
- Word Count: {crawl_data['content_analysis']['text_stats']['word_count']:,}
- Paragraphs: {crawl_data['content_analysis']['text_stats']['paragraph_count']}
- Tables: {len(crawl_data['content_analysis']['tables'])}
- Forms: {len(crawl_data['content_analysis']['forms'])}
- H1 Tags: {len(crawl_data['content_analysis']['headings']['h1'])}
- H2 Tags: {len(crawl_data['content_analysis']['headings']['h2'])}
- Buttons: {crawl_data['content_analysis']['interactive_elements']['buttons']}
- Input Fields: {crawl_data['content_analysis']['interactive_elements']['inputs']}

Links Summary:
- Internal: {len(crawl_data['links']['internal'])}
- External: {len(crawl_data['links']['external'])}
- Mailto: {len(crawl_data['links']['mailto'])}
- PDF Files: {len(crawl_data['links']['files']['pdf'])}

Resources:
- Images: {len(crawl_data['resources']['images'])}
- Scripts: {len(crawl_data['resources']['scripts'])}
- Stylesheets: {len(crawl_data['resources']['stylesheets'])}
- Iframes: {len(crawl_data['resources']['iframes'])}"""

        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, summary)

        # Metadata
        meta_display = json.dumps(crawl_data["metadata"], indent=2)
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(1.0, meta_display)

        # Links
        links_display = ""
        for category, urls in crawl_data["links"].items():
            if isinstance(urls, dict):
                for subcat, suburls in urls.items():
                    if suburls:
                        links_display += f"\n{category.upper()} - {subcat.upper()} ({len(suburls)}):\n"
                        for url in suburls[:20]:
                            links_display += f"  {url}\n"
            elif urls:
                links_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:20]:
                    links_display += f"  {url}\n"

        self.links_text.delete(1.0, tk.END)
        self.links_text.insert(1.0, links_display)

        # Resources
        resources_display = ""
        for category, urls in crawl_data["resources"].items():
            if urls:
                resources_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:30]:
                    resources_display += f"  {url}\n"

        self.resources_text.delete(1.0, tk.END)
        self.resources_text.insert(1.0, resources_display)

        # AJAX/API
        ajax_display = json.dumps(crawl_data["ajax_data"], indent=2)
        self.ajax_text.delete(1.0, tk.END)
        self.ajax_text.insert(1.0, ajax_display)

    def crawl_worker(self, url: str, use_js: bool):
        """Worker thread for crawling."""
        self.crawler = AdvancedCrawler(use_selenium=use_js)
        try:
            success, data, error = self.crawler.crawl(
                url, progress_callback=self.update_progress
            )
            if success:
                self.display_results(data)
            else:
                messagebox.showerror("Error", error)
        except Exception as e:
            messagebox.showerror("Fatal Error", str(e))
        finally:
            self.crawler.close_driver()
            self.enable_controls()

    def fetch_url(self):
        """Start crawling."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, url)

        # Disable controls
        self.fetch_button.config(state="disabled")
        self.url_entry.config(state="disabled")
        self.js_check.config(state="disabled")

        # Clear results
        for widget in [
            self.summary_text,
            self.metadata_text,
            self.links_text,
            self.resources_text,
            self.ajax_text,
        ]:
            widget.delete(1.0, tk.END)

        # Start crawling
        use_js = self.js_var.get()
        self.crawl_thread = threading.Thread(
            target=self.crawl_worker, args=(url, use_js)
        )
        self.crawl_thread.daemon = True
        self.crawl_thread.start()

    def enable_controls(self):
        """Re-enable controls."""
        self.fetch_button.config(state="normal")
        self.url_entry.config(state="normal")
        self.js_check.config(state="normal")
        self.progress_var.set("Ready")

    def run(self):
        """Start GUI."""
        self.root.mainloop()


if __name__ == "__main__":
    # Note: Requires installation of:
    # pip install selenium beautifulsoup4 requests undetected-chromedriver
    app = CrawlerGUI()
    app.run()
