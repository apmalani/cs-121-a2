from threading import Event
from utils import get_logger
from crawler.frontier import Frontier
from crawler.worker import Worker
from analysis import analyzer

class Crawler(object):
    def __init__(self, config, restart, frontier_factory=Frontier, worker_factory=Worker):
        self.config = config
        self.logger = get_logger("CRAWLER")
        self.frontier = frontier_factory(config, restart)
        self.workers = list()
        self.worker_factory = worker_factory
        self.stop_event = Event()

        if restart:
            analyzer.reset()

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
        # Wait for all workers to finish
        for worker in self.workers:
            worker.join()
        
        # Generate report once after all workers are done
        self.logger.info("All workers finished. Generating final report...")
        analyzer.generate_report()
