#load
#chunks
#embeeding
#Database

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

# load the file 
data = PyPDFLoader("book/SAD book.pdf")
docs = data.load()

# data or file split into chunks or Text spliter 
splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000,
    chunk_overlap = 200
)

chunks = splitter.split_documents(docs)

# Now Create A Embeeding Of Chunks using hugging face
embedding_model = HuggingFaceEmbeddings()

# step 4 --> Creating a Vector Database using Chroma

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embedding_model,
    collection_name="sad_book",
    persist_directory="chroma_db",
)
print("Actual chunks in database:", vectorstore._collection.count())
print("Database created successfully!")
print("Total chunks processed:", len(chunks))
