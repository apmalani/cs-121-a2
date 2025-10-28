import os
import shelve
import threading

from threading import Thread, RLock
from queue import Queue, Empty

from utils import get_logger, get_urlhash, normalize, get_subdomain
from scraper import is_valid

class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.to_be_downloaded = list()
        self.frontier_lock = threading.RLock()
        self.visited_subdomains: dict[str, int] = {} # keep track of visited subdomains to prevent traps
        self.MAX_HITS: int = 1000 # maximum amount of hits a subdomain can have before we begin to ignore it 
        
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
            if not self.save:
                for url in self.config.seed_urls:
                    self.add_url(url)

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
                url = normalize(url)
                urlhash = get_urlhash(url)
                if urlhash not in self.save:
                    self.save[urlhash] = (url, False)
                    self.save.sync()
                    self.to_be_downloaded.append(url)

    def mark_url_complete(self, url):
        with self.frontier_lock:
            urlhash = get_urlhash(url)
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before.")

            self.save[urlhash] = (url, True)
            self.save.sync()
