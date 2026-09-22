"""Terminal test for the Q&A agent.

    python scripts/ask.py "What is a replay attack?"
    python scripts/ask.py --no-web "What is a replay attack?"
"""

import argparse
import time

from cipher.qa_agent import ask

ap = argparse.ArgumentParser()
ap.add_argument("question", nargs="+")
ap.add_argument("--no-web", action="store_true", help="skip internet lookup even if enabled in .env")
ap.add_argument("-k", type=int, default=5, help="chunks to retrieve")
args = ap.parse_args()

q = " ".join(args.question)
t0 = time.perf_counter()
a = ask(q, k=args.k, web=False if args.no_web else None)
dt = time.perf_counter() - t0

print(f"\nQ: {q}\n")
print(a.answer)
print(f"\n--- grounded={a.grounded}  partial={a.partial}  {dt:.1f}s")
if a.sources:
    print("Sources:")
    for c in a.sources:
        print(f"  - {c.citation}")
if a.web_sources:
    print("Web references:")
    for w in a.web_sources:
        print(f"  - {w.title}\n    {w.url}")
