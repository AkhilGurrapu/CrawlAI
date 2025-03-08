import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import time
import random
from requests.exceptions import RequestException
import os
import json
import ssl
import urllib.request

# Make imports conditional to avoid breaking when only using the crawler part
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    
try:
    from langdetect import detect, LangDetectException
except ImportError:
    detect = None
    LangDetectException = Exception

# Configuration
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
]
REQUEST_DELAY = (2, 5)  # Random delay between 2-5 seconds
MAX_DEPTH = 2
CONTENT_DIR = "crawled_content"

# Create directory for saving content
os.makedirs(CONTENT_DIR, exist_ok=True)

# Import DocumentHistory
from document_history import DocumentHistory

class SafeCrawler:
    def __init__(self):
        self.visited = set()
        self.session = requests.Session()
        # Disable SSL verification to handle certificate issues
        self.session.verify = False
        # Suppress only the InsecureRequestWarning
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.content_store = {}  # Store URL -> page content
        self.max_links = 20  # Default max links to crawl
        self.keyword = None
        self.doc_history = DocumentHistory()  # Initialize document history tracking  # Optional keyword filter

    def get_random_user_agent(self):
        return random.choice(USER_AGENTS)

    def check_robots_txt(self, base_url):
        rp = RobotFileParser()
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            # Create a custom SSL context that doesn't verify certificates
            ssl_context = ssl._create_unverified_context()
            
            # Use urllib.request with the custom SSL context
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            urllib.request.install_opener(opener)
            
            rp.set_url(robots_url)
            rp.read()
            return rp
        except Exception as e:
            print(f"Couldn't read robots.txt: {e}")
            # Create a permissive RobotFileParser that allows all URLs
            permissive_rp = RobotFileParser()
            permissive_rp.parse(['User-agent: *', 'Allow: /'])
            return permissive_rp

    def extract_main_content(self, soup):
        """Extract main content from the page, removing navigation, headers, footers etc."""
        # Find and remove navigation, headers, footers, and other non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        # Try to find main content containers
        main_content_tags = soup.find_all(['main', 'article', 'div', 'section'], 
                                        class_=lambda c: c and any(x in str(c).lower() for x in ['content', 'main', 'article', 'body']))
        
        # If we found specific content containers, use them
        if main_content_tags:
            content = ''
            for tag in main_content_tags:
                content += tag.get_text(separator='\n', strip=True) + '\n\n'
            text = content
        else:
            # Otherwise get all text
            text = soup.get_text(separator='\n', strip=True)

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text
        
    def detect_language(self, text):
        """Detect the language of the text."""
        try:
            # Use a sample of text for faster detection
            sample = text[:1000] if len(text) > 1000 else text
            # If detect function is not available, default to English
            if detect is None:
                return 'en'
            lang = detect(sample)
            return lang
        except Exception:
            # If detection fails for any reason, default to English to be safe
            return 'en'

    def crawl(self, start_url, max_depth=MAX_DEPTH, keyword=None, max_links=20, progress_callback=None):
        # Reset state for new crawl
        self.visited = set()
        self.content_store = {}
        self.keyword = keyword
        self.max_links = min(max_links, 20)  # Cap at 20 links
        self.progress_callback = progress_callback
        self.links_crawled = 0
        self.total_links_to_crawl = max_links
        
        print(f"Starting crawl at {start_url} with max depth {max_depth}, max links {self.max_links}")
        if keyword:
            print(f"Filtering links containing keyword: '{keyword}'")
            
        rp = self.check_robots_txt(start_url)
        if not rp.can_fetch("*", start_url):
            print(f"robots.txt forbids crawling: {start_url}")
            return {}

        self._crawl_recursive(start_url, max_depth, rp)

        # Save the content store to disk
        with open(os.path.join(CONTENT_DIR, 'content_store.json'), 'w') as f:
            json.dump(self.content_store, f)

        print(f"Crawl completed. Visited {len(self.visited)} pages.")
        return self.content_store

    def _crawl_recursive(self, url, depth, rp):
        # Stop if we've reached max links or depth limit
        if len(self.visited) >= self.max_links or depth <= 0:
            return

        # Skip if we've already visited this URL
        if url in self.visited:
            return

        # Skip URLs that are disallowed by robots.txt
        if not rp.can_fetch("*", url):
            print(f"robots.txt disallows: {url}")
            return

        try:
            print(f"Crawling: {url} (depth: {depth})")
            
            # Update progress via callback if provided
            self.links_crawled += 1
            if self.progress_callback:
                self.progress_callback(url, self.links_crawled, self.total_links_to_crawl)
            
            # Add to visited set
            self.visited.add(url)
            
            # Random delay and user-agent
            time.sleep(random.uniform(*REQUEST_DELAY))
            headers = {"User-Agent": self.get_random_user_agent()}

            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"HTTP {response.status_code} for {url}")
                return

            if "captcha" in response.text.lower():
                print(f"CAPTCHA detected at {url} - stopping crawl!")
                return

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract main content
            main_content = self.extract_main_content(soup)
            
            # Detect language
            lang = self.detect_language(main_content)
            
            # Skip non-English content or force English URLs
            if 'en' not in url.lower() and lang != 'en':
                print(f"Skipping non-English content: {url} (detected: {lang})")
                return
                
            # For URLs with language codes, only process English
            url_parts = urlparse(url)
            path_parts = url_parts.path.split('/')
            if len(path_parts) > 1 and path_parts[1] in ['de', 'fr', 'ja', 'ko', 'pt'] and lang != 'en':
                print(f"Skipping non-English language path: {url}")
                return

            # Store the content
            page_title = soup.title.string if soup.title else "No title"
            self.content_store[url] = {
                "title": page_title,
                "content": main_content,
                "language": lang
            }

            # Track document in history
            self.doc_history.track_document(url, page_title, main_content, lang)

            # Save individual page content to file
            page_filename = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')
            with open(os.path.join(CONTENT_DIR, f"{page_filename}.txt"), 'w', encoding='utf-8') as f:
                f.write(f"Title: {page_title}\n\n")
                f.write(main_content)

            # Stop if we've reached the max links
            if len(self.visited) >= self.max_links:
                print(f"Reached maximum links limit ({self.max_links})")
                return

            links = soup.find_all('a')
            filtered_links = []

            for link in links:
                href = link.get('href')
                if href:
                    absolute_url = urljoin(url, href)
                    parsed_url = urlparse(absolute_url)
                    
                    # Apply keyword filter if specified
                    if self.keyword and self.keyword.lower() not in absolute_url.lower():
                        continue

                    # Same domain check and robots.txt compliance
                    if (parsed_url.netloc == urlparse(url).netloc and
                        rp.can_fetch("*", absolute_url)):
                        filtered_links.append(absolute_url)
            
            # Process filtered links
            for absolute_url in filtered_links:
                if len(self.visited) < self.max_links:
                    self._crawl_recursive(absolute_url, depth-1, rp)

        except RequestException as e:
            print(f"Request failed for {url}: {e}")
        except Exception as e:
            print(f"Error processing {url}: {e}")


class GeminiAgent:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.content_store = {}

    def load_content(self, content_path=None):
        """Load content from disk or use content_store dict directly"""
        if content_path:
            try:
                with open(content_path, 'r') as f:
                    self.content_store = json.load(f)
                print(f"Loaded content from {content_path} with {len(self.content_store)} pages")
            except Exception as e:
                print(f"Error loading content: {e}")
                self.content_store = {}

    def set_content(self, content_store):
        """Set content store directly from crawler"""
        self.content_store = content_store
        print(f"Content store set with {len(self.content_store)} pages")

    def search_relevant_content(self, query, max_results=5):
        """Find most relevant pages for the query"""
        # Simple keyword search
        results = []
        for url, page_data in self.content_store.items():
            content = page_data["content"]
            title = page_data["title"]

            # Calculate relevance score (very basic implementation)
            query_terms = query.lower().split()
            relevance = sum(1 for term in query_terms if term in content.lower())

            if relevance > 0:
                results.append((url, title, content, relevance))

        # Sort by relevance
        results.sort(key=lambda x: x[3], reverse=True)
        return results[:max_results]

    def answer_question(self, query: str) -> str:
        """Answer a question using the crawled content"""
        if not self.content_store:
            return "No content has been loaded. Please crawl a website first."

        relevant_pages = self.search_relevant_content(query)

        if not relevant_pages:
            return f"I couldn't find relevant information about '{query}' in the crawled content."

        # Prepare context for the LLM
        context = "I'll answer based on the following information:\n\n"

        for i, (url, title, content, _) in enumerate(relevant_pages):
            # Truncate content if it's too long
            max_content_length = 8000 // len(relevant_pages)  # Distribute token budget
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."

            context += f"Source {i+1}: {title} (URL: {url})\n{content}\n\n"

        # Prepare prompt
        prompt = f"""
{context}

Based only on the information provided above, answer this question: {query}
If the answer is not in the provided information, say "I don't have enough information to answer that question."
Include relevant source URLs in your answer.
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating response: {e}"


def main():
    # Replace with your Google API key
    API_KEY = "AIzaSyDpwDUu1cyhiKdDv3WAc7a5MvPwv33f7Z4"

    # Set up the crawler and agent
    crawler = SafeCrawler()
    agent = GeminiAgent(API_KEY)

    # Get user input for crawling parameters
    print("\n==== Website Knowledge Agent Configuration ====")
    start_url = input("Enter the URL to crawl: ")
    max_depth = int(input("Enter maximum crawl depth (1-3): ") or "2")
    max_depth = max(1, min(3, max_depth))  # Limit between 1-3
    
    keyword = input("Enter keyword to filter links (optional): ") or None
    
    max_links = input("Enter maximum number of links to crawl (max 20): ") or "20"
    max_links = min(20, max(1, int(max_links)))
    
    # 1. Crawl the website with user parameters
    content_store = crawler.crawl(start_url, max_depth=max_depth, keyword=keyword, max_links=max_links)

    # 2. Load content into the agent
    agent.set_content(content_store)

    # 3. Interactive question answering
    print("\n==== Website Knowledge Agent ====")
    print(f"Loaded information from {len(content_store)} pages at {start_url}")

    while True:
        query = input("\nAsk a question (or type 'exit' to quit): ")
        if query.lower() in ['exit', 'quit', 'q']:
            break

        answer = agent.answer_question(query)
        print("\nAnswer:")
        print(answer)
        print("\n" + "-"*50)

if __name__ == "__main__":
    main()
