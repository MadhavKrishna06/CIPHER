"""Ingest course documents into the local Chroma vector database.

Pipeline per file:
  1. SHA-256 hash, compare against data/manifest.json (integrity check)
  2. load pages/slides
  3. split into ~500-word chunks with overlap
  4. embed with the local Ollama embedding model
  5. upsert into Chroma with {source, page, chunk} metadata for citations

Nothing here touches the network except localhost:11434 (Ollama).

Usage:
    python -m cipher.ingest                 # ingest new files, refuse changed ones
    python -m cipher.ingest --accept-changes  # re-ingest files whose hash changed
    python -m cipher.ingest --verify        # integrity report only, no writes
    python -m cipher.ingest --reset         # wipe the vector DB and re-ingest all
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import integrity
from .config import (
    CHROMA_DIR,
    CHUNK_OVERLAP_WORDS,
    CHUNK_WORDS,
    COLLECTION_NAME,
    EMBED_MODEL,
    OLLAMA_HOST,
    RAW_DIR,
)
from .loaders import load_document

# Rough English average: 1 word ~ 6 characters including the space.
_CHARS_PER_WORD = 6


def get_vectorstore() -> Chroma:
    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_HOST)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


def chunk_file(path: Path, raw_dir: Path) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_WORDS * _CHARS_PER_WORD,
        chunk_overlap=CHUNK_OVERLAP_WORDS * _CHARS_PER_WORD,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    rel = path.relative_to(raw_dir).as_posix()
    docs: list[Document] = []
    for page in load_document(path):
        for j, text in enumerate(splitter.split_text(page.text)):
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": page.source,
                        "rel_path": rel,
                        "page": page.page,
                        "chunk": j,
                    },
                    id=f"{rel}::p{page.page}::c{j}",
                )
            )
    return docs


def delete_file_chunks(store: Chroma, rel_path: str) -> None:
    existing = store.get(where={"rel_path": rel_path}, include=[])
    if existing["ids"]:
        store.delete(ids=existing["ids"])


def ingest(paths: list[Path], store: Chroma, raw_dir: Path = RAW_DIR) -> int:
    total = 0
    for path in paths:
        rel = path.relative_to(raw_dir).as_posix()
        delete_file_chunks(store, rel)  # idempotent re-ingest
        docs = chunk_file(path, raw_dir)
        if not docs:
            print(f"  skip  {rel}: no extractable text")
            continue
        store.add_documents(docs, ids=[d.id for d in docs])
        total += len(docs)
        print(f"  ok    {rel}: {len(docs)} chunks")
    return total


def print_report(r: integrity.VerifyResult, raw_dir: Path) -> None:
    def rel(p: Path) -> str:
        return p.relative_to(raw_dir).as_posix()

    print(f"Integrity check against {integrity.MANIFEST_PATH.name}:")
    for p in r.ok:
        print(f"  VERIFIED  {rel(p)}")
    for p in r.new:
        print(f"  NEW       {rel(p)}")
    for p in r.changed:
        print(f"  CHANGED   {rel(p)}  <-- hash mismatch")
    for name in r.missing:
        print(f"  MISSING   {name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="report only, write nothing")
    ap.add_argument("--accept-changes", action="store_true", help="re-ingest files whose hash changed")
    ap.add_argument("--reset", action="store_true", help="delete the vector DB and ingest everything")
    args = ap.parse_args(argv)

    if not RAW_DIR.exists():
        print(f"no such directory: {RAW_DIR}", file=sys.stderr)
        return 1

    if args.reset and not args.verify:
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)
        manifest = {"files": {}}
        print("Reset: vector DB and manifest cleared.")
    else:
        manifest = integrity.load_manifest()

    report = integrity.verify(RAW_DIR, manifest)
    print_report(report, RAW_DIR)

    if args.verify:
        return 1 if report.changed else 0

    to_ingest = list(report.new)
    if report.changed:
        if args.accept_changes:
            print("Accepting changed files (hash will be updated).")
            to_ingest += report.changed
        else:
            print("Refusing to ingest CHANGED files. Re-run with --accept-changes if this was intentional.")

    if not to_ingest:
        print("Nothing to ingest.")
        return 1 if report.changed else 0

    print(f"Embedding with {EMBED_MODEL} via {OLLAMA_HOST} ...")
    store = get_vectorstore()
    n = ingest(to_ingest, store, RAW_DIR)

    manifest = integrity.record(to_ingest, RAW_DIR, manifest)
    for name in report.missing:
        manifest["files"].pop(name, None)
        delete_file_chunks(store, name)
    integrity.save_manifest(manifest)

    print(f"Done: {n} chunks from {len(to_ingest)} file(s). Manifest written to {integrity.MANIFEST_PATH}")
    return 1 if (report.changed and not args.accept_changes) else 0


if __name__ == "__main__":
    sys.exit(main())
