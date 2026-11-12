import os
import re
import numpy as np

from functools import lru_cache
from sentence_transformers import SentenceTransformer


KNOWLEDGE_FILE = os.path.join(
    "knowledge_base",
    "IT_FAQ.txt"
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.35


# Load the embedding model only once
@lru_cache(maxsize=1)
def load_model():
    return SentenceTransformer(MODEL_NAME)


# Read and split knowledge-base documents
def load_documents():

    if not os.path.exists(KNOWLEDGE_FILE):
        return []

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
        content = file.read()

    sections = re.split(
        r"(?m)(?=^[A-Z][A-Z ]+\s*$)",
        content
    )

    documents = []

    for section in sections:
        section = section.strip()

        if section:
            documents.append(section)

    return documents


# Generate embeddings for knowledge-base documents
@lru_cache(maxsize=1)
def get_document_embeddings():

    documents = load_documents()

    if not documents:
        return [], None

    model = load_model()

    embeddings = model.encode(
        documents,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return documents, embeddings


# Retrieve the top relevant documents with similarity scores
def retrieve_information(question, top_k=2):

    documents, document_embeddings = get_document_embeddings()

    if not documents:
        return {
            "found": False,
            "best_score": 0.0,
            "results": [],
            "context": "Knowledge base is empty."
        }

    model = load_model()

    question_embedding = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # Calculate cosine similarity scores (embeddings are normalized)
    scores = np.dot(
        document_embeddings,
        question_embedding[0]
    )

    # Sort indices from highest to lowest similarity
    ranked_indices = np.argsort(scores)[::-1]
    best_score = float(scores[ranked_indices[0]])

    # Filter matches above threshold
    matched_results = []
    for idx in ranked_indices[:top_k]:
        score = float(scores[idx])
        if score >= SIMILARITY_THRESHOLD:
            doc_text = documents[int(idx)]
            title = doc_text.splitlines()[0].strip()
            matched_results.append({
                "title": title,
                "score": round(score, 3),
                "content": doc_text
            })

    if not matched_results:
        return {
            "found": False,
            "best_score": round(best_score, 3),
            "results": [],
            "context": "No relevant information found in the knowledge base."
        }

    combined_context = "\n\n---\n\n".join(
        item["content"] for item in matched_results
    )

    return {
        "found": True,
        "best_score": round(best_score, 3),
        "results": matched_results,
        "context": combined_context
    }