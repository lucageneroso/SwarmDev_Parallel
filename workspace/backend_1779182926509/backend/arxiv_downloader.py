import requests
import csv
import datetime

class ArXivDownloader:
    def __init__(self, author, title, category, recent_days, max_results=10):
        self.author = author
        self.title = title
        self.category = category
        self.recent_days = recent_days
        self.max_results = max_results

    def _build_query(self):
        today = datetime.datetime.now()
        recent_date = (today - datetime.timedelta(days=self.recent_days)).strftime('%Y-%m-%d')
        query = f'\search?query=all:{self.title} AND all:{self.author} AND cat:{self.category} AND submittedDate:[{recent_date} TO *]&max_results={self.max_results}'
        return query

    def download(self):
        query = self._build_query()
        url = f'https://export.arxiv.org/api{query}'
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f'Error during requests to {url}: {str(e)}')
            return

        return response.json()

    def save_to_csv(self, data, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['author', 'title', 'published', 'abstract', 'link']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow({
                    'author': item['author'],
                    'title': item['title'],
                    'published': item['published'],
                    'abstract': item['abstract'],
                    'link': item['link']
                })

    def process_results(self):
        data = self.download()
        if not data:
            print('No results found.')
            return
        # Assuming 'data' contains a list of items with the relevant fields.
        self.save_to_csv(data, 'arxiv_papers.csv')

# Example usage:
# downloader = ArXivDownloader(author='John Doe', title='Quantum Computing', category='quant-ph', recent_days=30)
# downloader.process_results()