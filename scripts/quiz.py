"""Terminal test harness for the Quiz Agent.

Not the graded deliverable. The assignment requires a web UI, so this exists only
to exercise generate() and grade() before the FastAPI layer is written.

    python scripts/quiz.py                                  # 3 random questions
    python scripts/quiz.py --topic Kerberos --count 3
    python scripts/quiz.py --types mcq tf --count 4
    python scripts/quiz.py --show                           # print the key, do not prompt
"""

import argparse
import time

from cipher.quiz_agent import QTYPES, generate, grade

ap = argparse.ArgumentParser()
ap.add_argument("--topic", help="topic to quiz on; omitted means random passages")
ap.add_argument("--count", type=int, default=3, help="number of questions")
ap.add_argument("--types", nargs="+", default=list(QTYPES), choices=list(QTYPES))
ap.add_argument("--show", action="store_true", help="print answer keys instead of asking")
args = ap.parse_args()

mode = "topic" if args.topic else "random"

t0 = time.perf_counter()
questions = generate(mode=mode, topic=args.topic, count=args.count, types=tuple(args.types))
print(f"\nGenerated {len(questions)} question(s) in {time.perf_counter() - t0:.1f}s "
      f"(mode={mode}{', topic=' + args.topic if args.topic else ''})")

if not questions:
    raise SystemExit("No questions generated. Is Ollama running and the vector DB ingested?")

score = 0.0
for i, q in enumerate(questions, start=1):
    print(f"\n--- Q{i} [{q.qtype}]  ({q.citation})")
    print(q.prompt)
    if q.options:
        for key in sorted(q.options):
            print(f"  {key}. {q.options[key]}")

    if args.show:
        print(f"  key: {q.answer}")
        print(f"  why: {q.explanation}")
        continue

    student = input("\nYour answer: ")
    t1 = time.perf_counter()
    result = grade(q, student)
    score += result.score

    mark = "CORRECT" if result.correct else "INCORRECT"
    print(f"\n{mark}  score={result.score:.2f}  ({time.perf_counter() - t1:.1f}s)")
    if result.similarity is not None:
        print(f"embedding similarity to reference: {result.similarity:.3f}  "
              f"judge verdict: {result.judge_verdict}")
    print(result.feedback)
    print(f"Reference: {result.reference}")
    print(f"Source: {result.citation}")

if not args.show:
    print(f"\n=== Total: {score:.2f} / {len(questions)}  ({score / len(questions) * 100:.0f}%)")
