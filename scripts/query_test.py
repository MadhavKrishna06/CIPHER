"""Quick retrieval sanity check: python scripts/query_test.py "your question" """

import sys

from cipher.ingest import get_vectorstore

question = " ".join(sys.argv[1:]) or "What are the goals of network security?"
store = get_vectorstore()
print("total chunks:", store._collection.count())
print("query:", question, "\n")
for doc, score in store.similarity_search_with_score(question, k=3):
    m = doc.metadata
    print(f"[{m['source']} p{m['page']}] score={score:.3f}")
    print("   ", doc.page_content[:200].replace("\n", " "), "...\n")
