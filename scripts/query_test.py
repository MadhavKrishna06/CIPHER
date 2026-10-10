"""Quick retrieval sanity check: python scripts/query_test.py "your question" """

import sys

from cipher.ingest import get_vectorstore

# **Get the question from command-line arguments or use a default question.**
question = " ".join(sys.argv[1:]) or "What are the goals of network security?"
# **Load the vector store containing the indexed document chunks.**
store = get_vectorstore()
# **Display the total number of stored chunks and the question being tested.**
print("total chunks:", store._collection.count())
print("query:", question, "\n")
# **Retrieve the three most similar document chunks and display their scores and content.**
for doc, score in store.similarity_search_with_score(question, k=3):
    m = doc.metadata
    print(f"[{m['source']} p{m['page']}] score={score:.3f}")
    print("   ", doc.page_content[:200].replace("\n", " "), "...\n")
