from threading import Thread, Event

from inspect import getsource
from utils.download import download
from utils import get_logger
import scraper
import time
from analysis import analyzer


class Worker(Thread):
    def __init__(self, worker_id, config, frontier, stop_event=None):
        self.logger = get_logger(f"Worker-{worker_id}", "Worker")
        self.config = config
        self.frontier = frontier
        self.stop_event = stop_event
        # basic check for requests in scraper
        assert {getsource(scraper).find(req) for req in {"from requests import", "import requests"}} == {-1}, "Do not use requests in scraper.py"
        assert {getsource(scraper).find(req) for req in {"from urllib.request import", "import urllib.request"}} == {-1}, "Do not use urllib.request in scraper.py"
        
        # Set politeness delay from config
        analyzer.set_politeness_delay(config.time_delay)
        
        super().__init__(daemon=True)
        
    def run(self):
        while not self.stop_event.is_set():
            tbd_url = self.frontier.get_tbd_url()
            if not tbd_url:
                self.logger.info("Frontier is empty. Worker stopping.")
                break
            
            analyzer.check_domain_politeness(tbd_url)
            
            resp = download(tbd_url, self.config, self.logger)
            
            self.logger.info(
                f"Downloaded {tbd_url}, status <{resp.status}>, "
                f"using cache {self.config.cache_server}.")
            scraped_urls = scraper.scraper(tbd_url, resp)
            for scraped_url in scraped_urls:
                self.frontier.add_url(scraped_url)
            self.frontier.mark_url_complete(tbd_url)
