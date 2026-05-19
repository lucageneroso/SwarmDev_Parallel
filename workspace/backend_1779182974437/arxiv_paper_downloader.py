import requests
import csv
from datetime import datetime, timedelta

class ArxivPaperDownloader:
    def __init__(self, author, title, category, recent_days, max_results=10):
        self.author = author
        self.title = title
        self.category = category
        self.recent_days = recent_days
        self.max_results = max_results
        self.base_url = "http://export.arxiv.org/api/query"

    def _construct_query(self):
        start_date = (datetime.now() - timedelta(days=self.recent_days)).strftime('%Y-%m-%d')
        query = f"search_query=au:{self.author}+AND+ti:{self.title}+AND+cat:{self.category}+AND+recent_date:>{start_date}"
        query += f"&start=0&max_results={self.max_results}"
        return query

    def download_papers(self):
        try:
            url = self.base_url + "?" + self._construct_query()
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f'Error during network operation: {e}')
            return None

    def parse_papers(self, data):
        papers = []  # placeholder for parsed papers
        # Parsing logic would go here (not implemented for brevity)
        return papers

    def save_to_csv(self, papers, filename='papers.csv'):
        if not papers:
            print('No papers found.')
            return
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['author', 'title', 'category', 'published', 'abstract', 'link']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for paper in papers:
                writer.writerow(paper)
        print(f'Saved papers to {filename}')

    def run(self):
        data = self.download_papers()
        if data:
            papers = self.parse_papers(data)
            self.save_to_csv(papers)

# Example usage:
# downloader = ArxivPaperDownloader(author='John Doe', title='Quantum Computing', category='quant-ph', recent_days=30)
# downloader.run()