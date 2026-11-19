"""Read a PDF, cut it into chunks, turn each chunk into numbers (an embedding), save to Postgres."""
import hashlib
import os
import uuid
from datetime import date

os.environ["TOKENIZERS_PARALLELISM"] = "false"

DB_CONN = "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel"
MODEL_NAME = "all-MiniLM-L6-v2"   # turns text into 384 numbers
CHUNK_SIZE = 1000                 # characters per chunk
CHUNK_OVERLAP = 150               # characters repeated between neighbouring chunks


# STEP 1: read the PDF, one page at a time
def read_pdf_pages(filepath):
    from pypdf import PdfReader

    reader = PdfReader(filepath)
    pages = []                                   # a list of small dictionaries
    page_number = 1
    for page in reader.pages:
        text = page.extract_text()
        if text is None:                         # some pages have no text at all
            text = ""
        text = text.strip()
        if text != "":
            pages.append({"page": page_number, "text": text})
        page_number = page_number + 1

    if len(pages) == 0:
        print("WARNING: no text found. The PDF is probably a scan. Run OCR first (ocrmypdf).")
    return pages


# STEP 2: cut every page into smaller chunks
def split_into_chunks(pages):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = []
    for page in pages:
        pieces = splitter.split_text(page["text"])
        for piece in pieces:
            chunks.append({"page": page["page"], "text": piece})
    return chunks


# A fingerprint of the chunk. Same chunk -> same fingerprint, so we never save it twice.
def make_fingerprint(doc_name, page, text):
    raw = doc_name + "|" + str(page) + "|" + text
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# STEP 3 and 4: embed the chunks and save them
def ingest_pdf(filepath, doc_name, pub_date, source_url):
    import psycopg
    from pgvector.psycopg import register_vector
    from sentence_transformers import SentenceTransformer

    pages = read_pdf_pages(filepath)
    chunks = split_into_chunks(pages)
    print("Pages with text:", len(pages), "| Chunks:", len(chunks))
    if len(chunks) == 0:
        return

    # Make a plain list of the chunk texts, then embed ALL of them in one go (much faster)
    texts = []
    for chunk in chunks:
        texts.append(chunk["text"])

    print("Loading model ...")
    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, normalize_embeddings=True)   # one row of 384 numbers per chunk

    inserted = 0
    DB_CONN = "postgresql://sentinel:sentinel_dev@db:5432/sentinel"
    with psycopg.connect(DB_CONN) as conn:        # leaving this block saves (commits) everything once
        register_vector(conn)                     # teaches psycopg what a "vector" is
        cur = conn.cursor()

        for i in range(len(chunks)):
            chunk = chunks[i]
            embedding = embeddings[i]             # keep as is; do NOT call .tolist()
            fingerprint = make_fingerprint(doc_name, chunk["page"], chunk["text"])

            cur.execute(
                """
                INSERT INTO knowledge_chunk
                    (chunk_id, document_name, section, page_number, published_date,
                     source_url, text, content_hash, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (content_hash) DO NOTHING
                """,
                [str(uuid.uuid4()), doc_name, "p." + str(chunk["page"]), chunk["page"],
                 pub_date, source_url, chunk["text"], fingerprint, embedding],
            )
            inserted = inserted + cur.rowcount    # 1 if saved, 0 if it already existed

    print("Saved", inserted, "new chunks.", len(chunks) - inserted, "already existed.")


if __name__ == "__main__":
    pdf_path = "knowledge/pdfs/rbi-tat-circular.pdf"
    if os.path.exists(pdf_path):
        ingest_pdf(
            pdf_path,
            "RBI/2019-20/67 Harmonisation of TAT and customer compensation for failed transactions",
            date(2019, 9, 20),
            "https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=11693&Mode=0",
        )
    else:
        print("Download the PDF first and put it at", pdf_path)