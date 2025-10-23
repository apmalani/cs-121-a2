import re
import json
import time
import threading
from collections import Counter, defaultdict
from urllib.parse import urlparse
from datetime import datetime

class CrawlerAnalyzer:
    def __init__(self):
        self.unique_urls = set()
        self.url_to_word_count = {}
        
        self.subdomain_counts = defaultdict(int)
        self.page_contents = {}
        
        self.word_counts = Counter()
        self.stopwords = self._load_stopwords()
        
        self.url_hashes = {}
        self.content_hashes = {}
        
        self.domain_last_request = {}
        self.politeness_delay = None
        self.politeness_lock = threading.Lock()
        
    def _load_stopwords(self):
        stopwords_text = "a about above after again against all am an and any are aren't as at be because been before being below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves"
        return set(stopwords_text.split())
    
    def normalize_url(self, url):
        try:
            parsed = urlparse(url)
            
            if '#' in url:
                url = url.split('#')[0]
                parsed = urlparse(url)
            
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path
            query = parsed.query
            
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            if path.endswith('/') and path != '/':
                path = path.rstrip('/')
            elif path == '':
                path = '/'
            
            if scheme in ('http', 'https'):
                scheme = 'https'
            
            normalized = f"{scheme}://{netloc}{path}"
            if query:
                normalized += f"?{query}"
            
            return normalized
            
        except Exception:
            return url.split('#')[0] if '#' in url else url
    
    def set_politeness_delay(self, delay):
        self.politeness_delay = delay
    
    def is_url_visited(self, url):
        normalized_url = self.normalize_url(url)
        return normalized_url in self.unique_urls
    
    def check_domain_politeness(self, url):
        try:
            if self.politeness_delay is None:
                return True
            
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            if not domain:
                return True
            
            with self.politeness_lock:
                current_time = time.time()
                last_request_time = self.domain_last_request.get(domain, 0)
                
                time_since_last = current_time - last_request_time
                
                if time_since_last < self.politeness_delay:
                    wait_time = self.politeness_delay - time_since_last
                    print(f"Domain politeness: waiting {wait_time:.3f}s before requesting {domain}")
                    time.sleep(wait_time)
                    current_time = time.time()
                
                self.domain_last_request[domain] = current_time
            
            return True
            
        except Exception as e:
            print(f"error checking domain politeness, {e}")
            return True
    
    def add_page(self, url, content=None):
        normalized_url = self.normalize_url(url)
        
        if normalized_url not in self.unique_urls:
            self.unique_urls.add(normalized_url)
            
            parsed = urlparse(normalized_url)
            if parsed.netloc:
                self.subdomain_counts[parsed.netloc] += 1
            
            if content is not None:
                self.page_contents[normalized_url] = content
                
                word_count, filtered_words = self.process_content(content)
                
                self.url_to_word_count[normalized_url] = word_count
                
                for word in filtered_words:
                    self.word_counts[word] += 1
    
    def process_content(self, content):
        clean_text = re.sub(r'<[^>]+>', ' ', content)
        words = re.findall(r'\b[a-zA-Z]+\b', clean_text.lower())
        filtered_words = [word for word in words if len(word) > 2 and word not in self.stopwords]
        return len(words), filtered_words
    
    def get_unique_page_count(self):
        return len(self.unique_urls)
    
    def get_longest_page(self):
        if not self.url_to_word_count:
            return None, 0
        
        longest_url = max(self.url_to_word_count, key=self.url_to_word_count.get)
        return longest_url, self.url_to_word_count[longest_url]
    
    def get_most_common_words(self, n=50):
        return self.word_counts.most_common(n)
    
    def get_subdomain_stats(self):
        uci_subdomains = {}
        for subdomain, count in self.subdomain_counts.items():
            if subdomain.endswith('.uci.edu'):
                uci_subdomains[subdomain] = count
        
        return sorted(uci_subdomains.items())
    
    def reset(self):
        self.unique_urls.clear()
        self.url_to_word_count.clear()
        self.subdomain_counts.clear()
        self.page_contents.clear()
        self.word_counts.clear()
        self.url_hashes.clear()
        self.content_hashes.clear()
        self.domain_last_request.clear()
    
    def generate_report(self, output_file="crawler_report.txt"):
        report_lines = []
        
        report_lines.append(f"unique pages found: {self.get_unique_page_count()}")
        
        report_lines.append(f"longest page: {self.get_longest_page()[0]} {self.get_longest_page()[1]}")
        
        report_lines.append("50 most common words:")
        common_words = self.get_most_common_words(50)
        for i, (word, count) in enumerate(common_words, 1):
            report_lines.append(f"   {i:2d}. {word:<15} ({count} occurrences)")
        report_lines.append("")
        
        report_lines.append(f"uci.edu subdomains: {self.get_subdomain_stats()}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

analyzer = CrawlerAnalyzer()
