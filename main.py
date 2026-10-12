from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
load_dotenv()


embeeding = HuggingFaceEmbeddings()

vectorstore = Chroma(
    collection_name="sad_book",
    embedding_function=embeeding,
    persist_directory="chroma_db",
)

retriever = vectorstore.as_retriever(
    search_type = "mmr",
    search_kwargs = {"k":4,
                    "fetch_k":10,
                    "lambda_mult":0.5
                    }
    
)
llm = ChatGroq(
    model = "openai/gpt-oss-120b"
)


prompt = ChatPromptTemplate.from_messages([
    ("system",
    """You are an AI Book Assistant.
Answer questions using only the provided book context.
Explain concepts in simple English.
If the answer is not in the context, say you couldn't find it in the book.

Book Context:
{context}
    """
    ),
    
    ("human",
    """Question: {question}

Answer the question based on the provided book context.
    """
    )
])







print("Total chunks:", vectorstore._collection.count())
while True:
    query = input("You : ")
    
    if query == "0":
        break
    
    docs = retriever.invoke(query)

    
    context = "\n\n".join(
    [doc.page_content for doc in docs]
    )
    
    final_prompt = prompt.format_messages(
    question=query,
    context=context
    )
    
    response = llm.invoke(final_prompt)
    
    print("\n")
    
    print("AI : ",response.content)
    
    print("\n")    
    
    
