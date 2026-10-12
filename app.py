import os, json, uuid
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
BOOKS_FILE = os.path.join(BASE, "books.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

embedding = HuggingFaceEmbeddings()
vectorstore = Chroma(
    collection_name="library",          # new collection: every chunk carries book_id
    embedding_function=embedding,
    persist_directory=os.path.join(BASE, "chroma_db"),
)
llm = ChatGroq(model="openai/gpt-oss-120b")
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

prompt = ChatPromptTemplate.from_messages([
    ("system",
    """You are an AI Book Assistant.
Answer questions using only the provided book context.
Explain concepts in simple English.
The context comes from {book_count} book(s); each passage is labelled with its book title.
Do not use markdown headings (#).
If there is only ONE book, answer directly in a few short paragraphs. Do not repeat the
book title as a heading and do not add a summary section.
If there are SEVERAL books, write each book's answer under its title on a bold line
(like **Book title**), then add a short combined summary only if it adds something useful.
If a book has nothing about the question, say you couldn't find it in that book.
If none of the context helps, say you couldn't find it in the books.

Book Context:
{context}"""),
    ("human", "Question: {question}"),
])


def load_books():
    if os.path.exists(BOOKS_FILE):
        with open(BOOKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_books(books):
    with open(BOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/books", methods=["GET"])
def list_books():
    return jsonify(load_books())


@app.route("/api/upload", methods=["POST"])
def upload():
    books, added, errors = load_books(), [], []
    for file in request.files.getlist("files"):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".pdf", ".txt"):
            errors.append(f"{file.filename}: only PDF or TXT files are supported")
            continue
        book_id = uuid.uuid4().hex[:10]
        path = os.path.join(UPLOAD_DIR, f"{book_id}{ext}")
        file.save(path)
        try:
            loader = PyPDFLoader(path) if ext == ".pdf" else TextLoader(path, encoding="utf-8")
            chunks = splitter.split_documents(loader.load())
            name = os.path.splitext(file.filename)[0]
            for c in chunks:
                c.metadata = {"book_id": book_id, "book_name": name,
                            "page": int(c.metadata.get("page", 0)) + 1}
            if not chunks:
                raise ValueError("no readable text found (scanned PDF?)")
            vectorstore.add_documents(chunks)
            book = {"id": book_id, "name": name, "chunks": len(chunks), "file": path}
            books.append(book)
            added.append(book)
        except Exception as e:
            os.remove(path)
            errors.append(f"{file.filename}: {e}")
    save_books(books)
    return jsonify({"added": added, "errors": errors})


@app.route("/api/books/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    books = load_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404
    vectorstore._collection.delete(where={"book_id": book_id})
    if os.path.exists(book["file"]):
        os.remove(book["file"])
    save_books([b for b in books if b["id"] != book_id])
    return jsonify({"ok": True})


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = (data.get("question") or "").strip()
    books = load_books()
    selected = data.get("book_ids") or [b["id"] for b in books]
    if not question:
        return jsonify({"error": "Please type a question."}), 400
    if not selected:
        return jsonify({"error": "Add at least one book first."}), 400

    names = {b["id"]: b["name"] for b in books}
    blocks, sources = [], []
    for bid in selected:                       # retrieve from EVERY selected book
        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5,
                        "filter": {"book_id": bid}},
        )
        docs = retriever.invoke(question)
        if not docs:
            continue
        pages = sorted({d.metadata.get("page", 0) for d in docs})
        sources.append({"book": names.get(bid, "Unknown"), "pages": pages})
        text = "\n\n".join(d.page_content for d in docs)
        blocks.append(f"### Book: {names.get(bid, 'Unknown')}\n{text}")

    if not blocks:
        return jsonify({"answer": "I couldn't find that in the selected books.", "sources": []})

    msgs = prompt.format_messages(question=question, context="\n\n".join(blocks),
                                book_count=len(blocks))
    response = llm.invoke(msgs)
    return jsonify({"answer": response.content, "sources": sources})


if __name__ == "__main__":
    app.run(debug=True, port=5000)