The chakin project is designed to streamline the process of downloading pre-trained word vectors, which are essential components in natural language processing (NLP) tasks. The ease of access to various word vectors allows researchers and developers to enhance language models effectively.

Background
chakin addresses the challenge of accessing diverse pre-trained word vectors from multiple sources. It simplifies the retrieval process, eliminating the need for manual searches and downloads, thereby saving time and reducing complexity.

Goals
The primary goal of chakin is to provide an efficient, user-friendly tool to download pre-trained word vectors. It aims to support NLP applications by making a wide range of word vectors easily accessible.

Data Model
The only data source is a static local file located in ./chakin/datasets.csv. The data model must reflect exactly the 9 columns of this file: Name, Dimension, Corpus, VocabularySize, Method, Language, Paper, Author, and URL. Data will be loaded and filtered in memory exclusively using the pandas library.

APIs
No external third-party APIs will be used for searching. The function chakin.search(lang) will simply filter the loaded CSV file with pandas. The only network interaction will occur in chakin.download(number, save_dir), which will download the file pointed to by the URL column of the CSV. Standard Python modules for HTTP requests will suffice.

Edge Cases
1. Invalid user input (e.g., entering a language not present in the CSV or an incorrect numeric index for download).
2. Network interruptions: efficient error handling is required to manage disconnections or interrupted downloads without crashing the script.
3. Memory efficiency: since word vectors are large files, downloads must be managed efficiently (e.g., in chunks), and progress must be visually tracked using the progressbar2 library. Ensure that the six library is among the dependencies.