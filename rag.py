from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import response

# Initialize the embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

def pathToPaper(filePath):
    """
    Read the PDF using the given file path.
    """
    reader = PdfReader(filePath)
    return reader

def readingPages(reader: PdfReader):
    """
    Extract and split text from all pages in the PDF.
    """
    num_pages = len(reader.pages)
    text = []
    for x in range(num_pages):
        page = reader.pages[x]
        page_text = page.extract_text()
        if page_text:
            sentences = page_text.split('. ')
            text.extend(sentences)
    return text

def store_embeddings_in_faiss(text):
    """
    Compute embeddings for the text chunks and store them in a FAISS index.
    """
    embeddings = model.encode(text, convert_to_tensor=False)
    embeddings_array = np.array(embeddings).astype("float32")
    dimension = embeddings_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_array)
    faiss.write_index(index, "research_index.faiss")
    print(f"Stored {len(text)} text chunks in FAISS.")
    return index, text, embeddings_array

def query_faiss(user_query, text_chunks, model, top_k=3):
    """
    Build a FAISS index on the fly, query it with the user query,
    and return the top matching text chunks.
    """
    index, _, _ = store_embeddings_in_faiss(text_chunks)
    query_embeddings = model.encode([user_query], convert_to_tensor=False).astype("float32")
    distances, indices = index.search(query_embeddings, top_k)
    retrieved_chunks = [text_chunks[i] for i in indices[0]]
    return retrieved_chunks, distances[0]

def ask(user_query, file_path):
    """
    Process the uploaded file and generate an answer using the RAG method.
    """

    pdf_reader = pathToPaper(file_path)
    text_chunks = readingPages(pdf_reader)
    if not pdf_reader or text_chunks:
        print('error with pdf reader or text chunks')

    results, distances = query_faiss(
        user_query=user_query,
        text_chunks=text_chunks,
        model=model,
        top_k=3
    )
    response1 = response.generateResponse(user_query=user_query, retrieved_chunks=results)

    if not response1:
        print('error with response')
    return response1
