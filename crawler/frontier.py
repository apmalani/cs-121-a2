import os
import shelve
import threading
import time
from collections import Counter, defaultdict
from urllib.parse import urlparse

from threading import Thread, RLock
from queue import Queue, Empty

from utils import get_logger, get_urlhash, normalize, get_subdomain, process_content
from scraper import is_valid

class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.to_be_downloaded = list()
        self.frontier_lock = threading.RLock()
        self.visited_subdomains: dict[str, int] = {} # keep track of visited subdomains to prevent traps
        self.MAX_HITS: int = 1000 # maximum amount of hits a subdomain can have before we begin to ignore it 
        
        # Analysis and politeness functionality moved from analysis.py
        self.unique_urls = set()
        self.url_to_word_count = {}
        self.subdomain_counts = defaultdict(int)
        self.page_contents = {}
        self.word_counts = Counter()
        self.domain_last_request = {}
        self.politeness_delay = None
        self.politeness_lock = threading.Lock()
        # Removed data_lock - using frontier_lock for all operations
        
        if not os.path.exists(self.config.save_file) and not restart:
            # Save file does not exist, but request to load save.
            self.logger.info(
                f"Did not find save file {self.config.save_file}, "
                f"starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            # Save file does exists, but request to start from seed.
            self.logger.info(
                f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)
        # Load existing save file, or create one if it does not exist.
        self.save = shelve.open(self.config.save_file)
        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            # Set the frontier state with contents of save file.
            self._parse_save_file()
            self._load_analysis_data()  # Load analysis data from save file
            if not self.save:
                for url in self.config.seed_urls:
                    self.add_url(url)

        # Initialize subdomain counts for seed hosts to ensure they appear in report
        try:
            for seed_url in self.config.seed_urls:
                parsed_seed = urlparse(seed_url)
                host = parsed_seed.netloc.lower()
                if host and (host.endswith(".uci.edu") or host == "uci.edu"):
                    # Remove www. prefix if present to match normalization
                    if host.startswith("www."):
                        host = host[4:]
                    self.subdomain_counts[host] = self.subdomain_counts.get(host, 0)  # Initialize if not exists
        except Exception:
            pass

    def _parse_save_file(self):
        ''' This function can be overridden for alternate saving techniques. '''
        with self.frontier_lock:
            total_count = len(self.save)
            tbd_count = 0
            for url, completed in self.save.values():
                if not completed and is_valid(url) and self.can_add(url):   # Restores visited subdomains from saved run
                    self.to_be_downloaded.append(url)
                    tbd_count += 1
            self.logger.info(
                f"Found {tbd_count} urls to be downloaded from {total_count} "
                f"total urls discovered.")

    def _load_analysis_data(self):
        """Load analysis data from save file"""
        with self.frontier_lock:
            # Load unique URLs
            if 'unique_urls' in self.save:
                self.unique_urls = set(self.save['unique_urls'])
            
            # Load word counts
            if 'word_counts' in self.save:
                self.word_counts = Counter(self.save['word_counts'])
            
            # Load subdomain counts
            if 'subdomain_counts' in self.save:
                self.subdomain_counts = defaultdict(int, self.save['subdomain_counts'])
            
            # Load URL to word count mapping
            if 'url_to_word_count' in self.save:
                self.url_to_word_count = dict(self.save['url_to_word_count'])
            
            # Load page contents (optional, can be memory intensive)
            if 'page_contents' in self.save:
                self.page_contents = dict(self.save['page_contents'])
            
            self.logger.info(f"Loaded analysis data: {len(self.unique_urls)} unique URLs")

    def _save_analysis_data(self):
        """Save analysis data to save file"""
        with self.frontier_lock:
            self.save['unique_urls'] = list(self.unique_urls)
            self.save['word_counts'] = dict(self.word_counts)
            self.save['subdomain_counts'] = dict(self.subdomain_counts)
            self.save['url_to_word_count'] = self.url_to_word_count
            # Skip page_contents to save memory
            self.save.sync()

    def get_tbd_url(self):
        with self.frontier_lock:
            try:
                return self.to_be_downloaded.pop()
            except IndexError:
                return None

    # helper method used to check if we haven't visited a subdomain too many times
    def can_add(self, url) -> bool:
        ''' checks if subdomain can be visited (we havent reached max hits); returns True and updates class dict
            if haven't reached max, otherwise returns False
            this method is not lock safe; please only call it when nested in another locked
        '''
        url_subdomain: str = get_subdomain(url)
        if url_subdomain not in self.visited_subdomains:    # Haven't seen before
            self.visited_subdomains[url_subdomain] = 1
            return True
        elif url_subdomain in self.visited_subdomains and self.visited_subdomains[url_subdomain] < self.MAX_HITS:   # Seen but hasn't reached max hits
            self.visited_subdomains[url_subdomain] += 1
            return True
        else:
            return False 

    def add_url(self, url):
        with self.frontier_lock:
            if self.can_add(url):     # Check if we haven't visited subdomain too many times already
                normalized_url = normalize(url)
                urlhash = get_urlhash(normalized_url)  # Use normalized URL for hash
                if urlhash not in self.save:
                    self.save[urlhash] = (normalized_url, False)  # Store normalized URL
                    self.save.sync()
                    self.to_be_downloaded.append(normalized_url)  # Queue normalized URL

    def mark_url_complete(self, url):
        with self.frontier_lock:
            normalized_url = normalize(url)  # Normalize for consistency
            urlhash = get_urlhash(normalized_url)
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before.")

            self.save[urlhash] = (normalized_url, True)
            self.save.sync()
    
    # Politeness functionality moved from analysis.py
    def set_politeness_delay(self, delay):
        """Set the politeness delay for domain requests"""
        self.politeness_delay = delay
    
    def check_domain_politeness(self, url):
        """Check and enforce politeness delay for domain requests"""
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
    
    # Analysis functionality moved from analysis.py
    def add_page(self, normalized_url, content=None):
        """Add a page to the analysis data using pre-normalized URL"""
        with self.frontier_lock:
            if normalized_url not in self.unique_urls:
                self.unique_urls.add(normalized_url)
                
                parsed = urlparse(normalized_url)
                if parsed.netloc:
                    # Count by hostname (e.g., vision.ics.uci.edu), not scheme/path
                    host = parsed.netloc.lower()
                    self.subdomain_counts[host] += 1
                
                if content is not None:
                    self.page_contents[normalized_url] = content
                    
                    word_count, filtered_words = process_content(content)
                    
                    self.url_to_word_count[normalized_url] = word_count
                    
                    for word in filtered_words:
                        self.word_counts[word] += 1
                
                # Save analysis data periodically (every 100 pages)
                if len(self.unique_urls) % 100 == 0:
                    self._save_analysis_data()
    
    def get_unique_page_count(self):
        """Get the count of unique pages visited"""
        return len(self.unique_urls)
    
    def get_longest_page(self):
        """Get the URL and word count of the longest page"""
        if not self.url_to_word_count:
            return None, 0
        
        longest_url = max(self.url_to_word_count, key=self.url_to_word_count.get)
        return longest_url, self.url_to_word_count[longest_url]
    
    def get_most_common_words(self, n=50):
        """Get the most common words across all pages"""
        return self.word_counts.most_common(n)
    
    def get_subdomain_stats(self):
        """Get statistics for UCI subdomains as list[(host, count)] sorted alphabetically"""
        uci_subdomains = {}
        for host, count in self.subdomain_counts.items():
            if host.endswith(".uci.edu") or host == "uci.edu":
                uci_subdomains[host] = count
        # Return alphabetically sorted by hostname
        return sorted(uci_subdomains.items(), key=lambda item: item[0])
    
    def generate_report(self, output_file="crawler_report.txt"):
        """Generate a comprehensive crawler report"""
        # Save final analysis data
        self._save_analysis_data()
        
        report_lines = []
        
        report_lines.append(f"unique pages found: {self.get_unique_page_count()}")
        
        report_lines.append(f"longest page: {self.get_longest_page()[0]} {self.get_longest_page()[1]}")
        
        report_lines.append("50 most common words:")
        common_words = self.get_most_common_words(50)
        for i, (word, count) in enumerate(common_words, 1):
            report_lines.append(f"   {i:2d}. {word:<15} ({count} occurrences)")
        report_lines.append("")
        
        # Print subdomains in required format: "subdomain, number" sorted alphabetically
        report_lines.append("uci.edu subdomains:")
        for host, count in self.get_subdomain_stats():
            report_lines.append(f"{host}, {count}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
    
    def reset_analysis(self):
        """Reset all analysis data"""
        with self.frontier_lock:
            self.unique_urls.clear()
            self.url_to_word_count.clear()
            self.subdomain_counts.clear()
            self.page_contents.clear()
            self.word_counts.clear()
            self.domain_last_request.clear()
