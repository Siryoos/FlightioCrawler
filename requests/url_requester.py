import os
import re
import json
import time
import threading
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CrawlerSession:
    """Manages HTTP session with retry logic and connection pooling."""
    
    def __init__(self, user_agent: str = None, timeout: int = 30):
        self.session = requests.Session()
        self.timeout = timeout
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def get(self, url: str) -> requests.Response:
        return self.session.get(url, timeout=self.timeout, allow_redirects=True)


class URLCrawler:
    """Extracts comprehensive crawling information from URLs."""
    
    def __init__(self, save_dir: str = None):
        self.save_dir = save_dir or os.path.join(os.path.dirname(__file__), "pages")
        os.makedirs(self.save_dir, exist_ok=True)
        self.session = CrawlerSession()
    
    @staticmethod
    def sanitize_filename(url: str) -> str:
        """Create safe filename from URL."""
        # Remove protocol
        filename = re.sub(r'^https?://', '', url)
        # Replace special characters
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        # Limit length
        return filename[:200]
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract page metadata."""
        meta = {
            'title': '',
            'description': '',
            'keywords': [],
            'author': '',
            'robots': '',
            'canonical': '',
            'language': '',
            'og_data': {},
            'twitter_data': {},
            'json_ld': []
        }
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            meta['title'] = title_tag.get_text(strip=True)
        
        # Meta tags
        for tag in soup.find_all('meta'):
            name = tag.get('name', '').lower()
            property = tag.get('property', '').lower()
            content = tag.get('content', '')
            
            if name == 'description':
                meta['description'] = content
            elif name == 'keywords':
                meta['keywords'] = [k.strip() for k in content.split(',')]
            elif name == 'author':
                meta['author'] = content
            elif name == 'robots':
                meta['robots'] = content
            elif name in ['language', 'lang']:
                meta['language'] = content
            
            # Open Graph
            if property.startswith('og:'):
                meta['og_data'][property] = content
            
            # Twitter Card
            if name.startswith('twitter:') or property.startswith('twitter:'):
                key = name or property
                meta['twitter_data'][key] = content
        
        # Language from html tag
        html_tag = soup.find('html')
        if html_tag and not meta['language']:
            meta['language'] = html_tag.get('lang', '')
        
        # Canonical URL
        canonical = soup.find('link', {'rel': 'canonical'})
        if canonical:
            meta['canonical'] = canonical.get('href', '')
        
        # JSON-LD structured data
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                meta['json_ld'].append(data)
            except:
                pass
        
        return meta
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract and categorize links."""
        links = {
            'internal': [],
            'external': [],
            'mailto': [],
            'tel': [],
            'javascript': [],
            'anchors': []
        }
        
        base_domain = urlparse(base_url).netloc
        
        for tag in soup.find_all(['a', 'link']):
            href = tag.get('href', '').strip()
            if not href:
                continue
            
            # Categorize link
            if href.startswith('mailto:'):
                links['mailto'].append(href)
            elif href.startswith('tel:'):
                links['tel'].append(href)
            elif href.startswith('javascript:'):
                links['javascript'].append(href)
            elif href.startswith('#'):
                links['anchors'].append(href)
            else:
                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)
                link_domain = urlparse(absolute_url).netloc
                
                if link_domain == base_domain:
                    links['internal'].append(absolute_url)
                else:
                    links['external'].append(absolute_url)
        
        # Remove duplicates while preserving order
        for category in links:
            links[category] = list(dict.fromkeys(links[category]))
        
        return links
    
    def extract_resources(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract page resources."""
        resources = {
            'images': [],
            'scripts': [],
            'stylesheets': [],
            'videos': [],
            'audios': [],
            'iframes': []
        }
        
        # Images
        for img in soup.find_all(['img', 'picture']):
            src = img.get('src') or img.get('data-src')
            if src:
                resources['images'].append(urljoin(base_url, src))
        
        # Scripts
        for script in soup.find_all('script'):
            src = script.get('src')
            if src:
                resources['scripts'].append(urljoin(base_url, src))
        
        # Stylesheets
        for link in soup.find_all('link', {'rel': 'stylesheet'}):
            href = link.get('href')
            if href:
                resources['stylesheets'].append(urljoin(base_url, href))
        
        # Videos
        for video in soup.find_all(['video', 'source']):
            src = video.get('src')
            if src:
                resources['videos'].append(urljoin(base_url, src))
        
        # Audio
        for audio in soup.find_all('audio'):
            src = audio.get('src')
            if src:
                resources['audios'].append(urljoin(base_url, src))
        
        # Iframes
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src')
            if src:
                resources['iframes'].append(urljoin(base_url, src))
        
        # Remove duplicates
        for category in resources:
            resources[category] = list(dict.fromkeys(resources[category]))
        
        return resources
    
    def analyze_content(self, soup: BeautifulSoup) -> Dict:
        """Analyze page content structure."""
        analysis = {
            'headings': {'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': []},
            'forms': [],
            'tables': 0,
            'lists': {'ul': 0, 'ol': 0, 'dl': 0},
            'text_length': 0,
            'word_count': 0
        }
        
        # Headings
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                text = heading.get_text(strip=True)
                if text:
                    analysis['headings'][f'h{i}'].append(text)
        
        # Forms
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action', ''),
                'method': form.get('method', 'GET').upper(),
                'inputs': []
            }
            for input_tag in form.find_all(['input', 'select', 'textarea']):
                form_data['inputs'].append({
                    'type': input_tag.get('type', 'text'),
                    'name': input_tag.get('name', ''),
                    'id': input_tag.get('id', '')
                })
            analysis['forms'].append(form_data)
        
        # Tables
        analysis['tables'] = len(soup.find_all('table'))
        
        # Lists
        analysis['lists']['ul'] = len(soup.find_all('ul'))
        analysis['lists']['ol'] = len(soup.find_all('ol'))
        analysis['lists']['dl'] = len(soup.find_all('dl'))
        
        # Text analysis
        text = soup.get_text()
        analysis['text_length'] = len(text)
        analysis['word_count'] = len(text.split())
        
        return analysis
    
    def crawl(self, url: str, progress_callback=None) -> Tuple[bool, Dict, str]:
        """Crawl URL and extract comprehensive information."""
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback("Fetching URL...")
            
            # Fetch the page
            response = self.session.get(url)
            response.raise_for_status()
            
            if progress_callback:
                progress_callback("Parsing content...")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Collect crawl data
            crawl_data = {
                'url': url,
                'final_url': response.url,
                'timestamp': datetime.now().isoformat(),
                'response': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'encoding': response.encoding,
                    'response_time': response.elapsed.total_seconds(),
                    'content_length': len(response.content),
                    'redirects': [r.url for r in response.history]
                },
                'metadata': self.extract_metadata(soup, response.url),
                'links': self.extract_links(soup, response.url),
                'resources': self.extract_resources(soup, response.url),
                'content_analysis': self.analyze_content(soup),
                'crawl_time': time.time() - start_time
            }
            
            if progress_callback:
                progress_callback("Saving data...")
            
            # Save files
            base_filename = self.sanitize_filename(url)
            
            # Save HTML
            html_path = os.path.join(self.save_dir, f"{base_filename}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Save metadata
            json_path = os.path.join(self.save_dir, f"{base_filename}_metadata.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(crawl_data, f, indent=2, ensure_ascii=False)
            
            if progress_callback:
                progress_callback("Complete!")
            
            return True, crawl_data, f"Saved to:\n{html_path}\n{json_path}"
            
        except Exception as e:
            return False, {}, str(e)


class CrawlerGUI:
    """Enhanced GUI for URL crawling."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Advanced URL Crawler")
        self.root.geometry("900x700")
        
        self.crawler = URLCrawler()
        self.crawl_thread = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the GUI components."""
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # URL input section
        input_frame = ttk.LabelFrame(main_frame, text="URL Input", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(input_frame, text="URL:").grid(row=0, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(input_frame, width=70)
        self.url_entry.grid(row=0, column=1, padx=5)
        self.url_entry.bind('<Return>', lambda e: self.fetch_url())
        
        self.fetch_button = ttk.Button(input_frame, text="Crawl", command=self.fetch_url)
        self.fetch_button.grid(row=0, column=2, padx=5)
        
        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(input_frame, textvariable=self.progress_var).grid(row=1, column=0, columnspan=3, pady=5)
        
        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Crawl Results", padding="10")
        results_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Notebook for different result views
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Summary tab
        self.summary_text = scrolledtext.ScrolledText(self.notebook, height=20, width=80)
        self.notebook.add(self.summary_text, text="Summary")
        
        # Metadata tab
        self.metadata_text = scrolledtext.ScrolledText(self.notebook, height=20, width=80)
        self.notebook.add(self.metadata_text, text="Metadata")
        
        # Links tab
        self.links_text = scrolledtext.ScrolledText(self.notebook, height=20, width=80)
        self.notebook.add(self.links_text, text="Links")
        
        # Resources tab
        self.resources_text = scrolledtext.ScrolledText(self.notebook, height=20, width=80)
        self.notebook.add(self.resources_text, text="Resources")
        
        # Configure grid weights
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
        """Display crawl results in tabs."""
        # Summary
        summary = f"""URL: {crawl_data['url']}
Final URL: {crawl_data['final_url']}
Status: {crawl_data['response']['status_code']}
Response Time: {crawl_data['response']['response_time']:.2f}s
Content Length: {crawl_data['response']['content_length']:,} bytes
Encoding: {crawl_data['response']['encoding']}
Redirects: {len(crawl_data['response']['redirects'])}

Title: {crawl_data['metadata']['title']}
Description: {crawl_data['metadata']['description']}
Language: {crawl_data['metadata']['language']}

Content Analysis:
- Word Count: {crawl_data['content_analysis']['word_count']:,}
- Tables: {crawl_data['content_analysis']['tables']}
- Forms: {len(crawl_data['content_analysis']['forms'])}
- H1 Tags: {len(crawl_data['content_analysis']['headings']['h1'])}
- H2 Tags: {len(crawl_data['content_analysis']['headings']['h2'])}

Links Summary:
- Internal: {len(crawl_data['links']['internal'])}
- External: {len(crawl_data['links']['external'])}
- Mailto: {len(crawl_data['links']['mailto'])}
- Tel: {len(crawl_data['links']['tel'])}

Resources:
- Images: {len(crawl_data['resources']['images'])}
- Scripts: {len(crawl_data['resources']['scripts'])}
- Stylesheets: {len(crawl_data['resources']['stylesheets'])}
- Iframes: {len(crawl_data['resources']['iframes'])}"""
        
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, summary)
        
        # Metadata
        meta_display = json.dumps(crawl_data['metadata'], indent=2)
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(1.0, meta_display)
        
        # Links
        links_display = ""
        for category, urls in crawl_data['links'].items():
            if urls:
                links_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:50]:  # Limit display
                    links_display += f"  {url}\n"
                if len(urls) > 50:
                    links_display += f"  ... and {len(urls) - 50} more\n"
        
        self.links_text.delete(1.0, tk.END)
        self.links_text.insert(1.0, links_display)
        
        # Resources
        resources_display = ""
        for category, urls in crawl_data['resources'].items():
            if urls:
                resources_display += f"\n{category.upper()} ({len(urls)}):\n"
                for url in urls[:50]:  # Limit display
                    resources_display += f"  {url}\n"
                if len(urls) > 50:
                    resources_display += f"  ... and {len(urls) - 50} more\n"
        
        self.resources_text.delete(1.0, tk.END)
        self.resources_text.insert(1.0, resources_display)
    
    def crawl_worker(self, url: str):
        """Worker thread for crawling."""
        success, data, message = self.crawler.crawl(url, self.update_progress)
        
        if success:
            self.root.after(0, self.display_results, data)
            self.root.after(0, messagebox.showinfo, "Success", message)
        else:
            self.root.after(0, messagebox.showerror, "Error", message)
        
        self.root.after(0, self.enable_controls)
    
    def fetch_url(self):
        """Start crawling process."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, url)
        
        # Disable controls
        self.fetch_button.config(state='disabled')
        self.url_entry.config(state='disabled')
        
        # Clear previous results
        for text_widget in [self.summary_text, self.metadata_text, self.links_text, self.resources_text]:
            text_widget.delete(1.0, tk.END)
        
        # Start crawling in thread
        self.crawl_thread = threading.Thread(target=self.crawl_worker, args=(url,))
        self.crawl_thread.daemon = True
        self.crawl_thread.start()
    
    def enable_controls(self):
        """Re-enable controls after crawling."""
        self.fetch_button.config(state='normal')
        self.url_entry.config(state='normal')
        self.progress_var.set("Ready")
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = CrawlerGUI()
    app.run()