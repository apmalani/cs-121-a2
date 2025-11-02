from threading import Event
from utils import get_logger
from crawler.frontier import Frontier
from crawler.worker import Worker

class Crawler(object):
    def __init__(self, config, restart, frontier_factory=Frontier, worker_factory=Worker):
        self.config = config
        self.logger = get_logger("CRAWLER")
        self.frontier = frontier_factory(config, restart)
        self.workers = list()
        self.worker_factory = worker_factory
        self.stop_event = Event()

        if restart:
            self.frontier.reset_analysis()

    def start_async(self):
        self.workers = [
            self.worker_factory(worker_id, self.config, self.frontier, self.stop_event)
            for worker_id in range(self.config.threads_count)]
        for worker in self.workers:
            worker.start()

    def start(self):
        self.start_async()
        self.join()

    def join(self):
        for worker in self.workers:
            worker.join()
        
        self.logger.info("All workers finished. Generating final report...")
        self.frontier.generate_report()
