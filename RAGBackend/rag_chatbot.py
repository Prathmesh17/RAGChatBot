import os
from typing import List, Dict, Optional
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from huggingface_hub import InferenceClient
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

class RAGConfig:
    """Configuration for RAG system"""
    DOCS_PATH = "docs"
    PERSISTENT_DIRECTORY = "db/chroma_db"
    LLM_MODEL_NAME = "gpt-4o-mini"
    HF_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_PROVIDER = "huggingface"
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 0
    DEFAULT_K = 3

client = InferenceClient(token=os.environ.get("HF_TOKEN"))

def get_embedding_function(provider: str = RAGConfig.EMBEDDING_PROVIDER):
    """
    Factory function to get the appropriate embedding function based on provider
    
    Args:
        provider: Embedding provider ("openai", "huggingface", or "cohere")
        
    Returns:
        Embedding function instance
    """
    provider = provider.lower()
    
    if provider == "huggingface":
        print(f"Using HuggingFace Embeddings: {RAGConfig.HF_EMBEDDING_MODEL}")
        
        api_key = os.getenv("HF_TOKEN")
        if not api_key:
            raise ValueError("HF_TOKEN not found in environment variables")
        
        return HuggingFaceEndpointEmbeddings(
            model=RAGConfig.HF_EMBEDDING_MODEL,
            huggingfacehub_api_token=api_key
        )
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            "Choose from: 'openai', 'huggingface', 'cohere'"
        )
# ============================================================================
# DOCUMENT INGESTION
# ============================================================================

def load_documents(docs_path: str = RAGConfig.DOCS_PATH) -> List:
    """
    Load all text files from the docs directory
    
    Args:
        docs_path: Path to documents directory
        
    Returns:
        List of loaded documents
    """
    print(f"Loading documents from {docs_path}...")
    
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"The directory {docs_path} does not exist.")
    
    loader = DirectoryLoader(
        path=docs_path,
        glob="*.txt",
        loader_cls=TextLoader
    )
    
    documents = loader.load()
    
    if len(documents) == 0:
        raise FileNotFoundError(f"No .txt files found in {docs_path}.")
    
    print(f"✅ Loaded {len(documents)} documents")
    return documents


def split_documents(
    documents: List, 
    chunk_size: int = RAGConfig.CHUNK_SIZE, 
    chunk_overlap: int = RAGConfig.CHUNK_OVERLAP
) -> List:
    """
    Split documents into smaller chunks
    
    Args:
        documents: List of documents to split
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of document chunks
    """
    print("Splitting documents into chunks...")
    
    text_splitter = CharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks")
    
    return chunks


def create_vector_store(
    chunks: List, 
    persist_directory: str = RAGConfig.PERSISTENT_DIRECTORY
) -> Chroma:
    """
    Create and persist ChromaDB vector store
    
    Args:
        chunks: List of document chunks
        persist_directory: Directory to persist the vector store
        
    Returns:
        ChromaDB vector store
    """
    print("Creating embeddings and storing in ChromaDB...")
    
    embedding_function = get_embedding_function(RAGConfig.EMBEDDING_PROVIDER)
    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_function,
        persist_directory=persist_directory, 
        collection_metadata={"hnsw:space": "cosine"}
    )
    
    print(f"✅ Vector store created and saved to {persist_directory}")
    return vectorstore


def ingest_documents(
    docs_path: str = RAGConfig.DOCS_PATH,
    persist_directory: str = RAGConfig.PERSISTENT_DIRECTORY,
    force_reingest: bool = False
) -> Chroma:
    """
    Complete document ingestion pipeline
    
    Args:
        docs_path: Path to documents directory
        persist_directory: Directory to persist the vector store
        force_reingest: If True, re-ingest even if vector store exists
        
    Returns:
        ChromaDB vector store
    """
    print("=== RAG Document Ingestion Pipeline ===\n")
    
    # Check if vector store already exists
    if os.path.exists(persist_directory) and not force_reingest:
        print("✅ Vector store already exists. Loading existing store...")
        
        embedding_function = get_embedding_function(RAGConfig.EMBEDDING_PROVIDER)
        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_function, 
            collection_metadata={"hnsw:space": "cosine"}
        )
        print(f"Loaded existing vector store with {vectorstore._collection.count()} documents")
        return vectorstore
    
    # Ingest documents
    print("Creating new vector store...\n")
    documents = load_documents(docs_path)
    chunks = split_documents(documents)
    vectorstore = create_vector_store(chunks, persist_directory)
    
    print("\n✅ Ingestion complete!")
    return vectorstore


# ============================================================================
# CONVERSATIONAL RAG (Always with History)
# ============================================================================

class RAGChatbot:
    """RAG Chatbot with conversation history support"""
    
    def __init__(
        self, 
        persist_directory: str = RAGConfig.PERSISTENT_DIRECTORY,
        auto_ingest: bool = True
    ):
        """
        Initialize RAG chatbot with conversation history
        
        Args:
            persist_directory: Directory where vector store is persisted
            auto_ingest: If True, automatically run ingestion if needed
        """
        self.persist_directory = persist_directory
        self.chat_history = []
        
        # Initialize embeddings
        api_key = os.getenv("HF_TOKEN")
        self.embedding_function = HuggingFaceEndpointEmbeddings(
            model=RAGConfig.HF_EMBEDDING_MODEL,
            huggingfacehub_api_token=api_key
        )
        
        # Load or create vector store
        if os.path.exists(persist_directory):
            self.db = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embedding_function,
                collection_metadata={"hnsw:space": "cosine"}
            )
        elif auto_ingest:
            print("Vector store not found. Running ingestion...")
            self.db = ingest_documents(persist_directory=persist_directory)
        else:
            raise FileNotFoundError(
                f"Vector store not found at {persist_directory}. "
                "Run ingestion first or set auto_ingest=True"
            )
        
        # Initialize LLM
        self.llm = ChatOpenAI(model=RAGConfig.LLM_MODEL_NAME,
        openai_api_key=os.getenv("OPENAI_API_KEY"))
    
    def _contextualize_question(self, user_question: str) -> str:
        """
        Convert a follow-up question into a standalone question using chat history
        
        Args:
            user_question: The new question from user
            
        Returns:
            Standalone, searchable question
        """
        if not self.chat_history:
            return user_question
        
        messages = [
            SystemMessage(
                content="Given the chat history, rewrite the new question to be "
                "standalone and searchable. Just return the rewritten question."
            ),
        ] + self.chat_history + [
            HumanMessage(content=f"New question: {user_question}")
        ]
        
        result = self.llm.invoke(messages)
        return result.content.strip()
    
    def chat(
        self, 
        message: str, 
        k: int = RAGConfig.DEFAULT_K, 
        verbose: bool = False
    ) -> Dict[str, any]:
        """
        Send a message and get a response with conversation history
        
        Args:
            message: User's message/question
            k: Number of documents to retrieve
            verbose: If True, include source documents and metadata
            
        Returns:
            Dictionary with answer and metadata
        """
        # Step 1: Contextualize the question using chat history
        search_question = self._contextualize_question(message)
        
        # Step 2: Retrieve relevant documents
        retriever = self.db.as_retriever(search_kwargs={"k": k})
        docs = retriever.invoke(search_question)
        
        # Step 3: Generate answer with context
        combined_input = f"""Based on the following documents, please answer this question: {message}

Documents:
{chr(10).join([f"- {doc.page_content}" for doc in docs])}

Please provide a clear, helpful answer using only the information from these documents. If you can't find the answer in the documents, say "I don't have enough information to answer that question based on the provided documents."
"""
        
        messages = [
            SystemMessage(
                content="You are a helpful assistant that answers questions based on "
                "provided documents and conversation history."
            ),
        ] + self.chat_history + [
            HumanMessage(content=combined_input)
        ]
        
        result = self.llm.invoke(messages)
        answer = result.content
        
        # Step 4: Update chat history
        self.chat_history.append(HumanMessage(content=message))
        self.chat_history.append(AIMessage(content=answer))
        
        # Step 5: Prepare response
        response = {
            "message": message,
            "answer": answer,
        }
        
        if verbose:
            response["contextualized_question"] = search_question if search_question != message else None
            response["sources"] = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {}
                }
                for doc in docs
            ]
            response["num_sources"] = len(docs)
        
        return response
    
    def clear_history(self):
        """Clear conversation history"""
        self.chat_history = []
        print("✅ Conversation history cleared")
    
    def get_history(self) -> List:
        """Get current conversation history"""
        return self.chat_history
    
    def get_history_length(self) -> int:
        """Get number of messages in history"""
        return len(self.chat_history)


# ============================================================================
# SESSION MANAGEMENT FOR FASTAPI
# ============================================================================

# Global storage for conversation sessions
_conversation_sessions = {}


def get_chatbot(session_id: str) -> RAGChatbot:
    """
    Get or create a RAG chatbot instance for a session
    
    Args:
        session_id: Unique identifier for the conversation session
        
    Returns:
        RAGChatbot instance for this session
    """
    global _conversation_sessions
    
    if session_id not in _conversation_sessions:
        _conversation_sessions[session_id] = RAGChatbot(auto_ingest=True)
    
    return _conversation_sessions[session_id]


def clear_session_history(session_id: str) -> bool:
    """
    Clear conversation history for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if session exists and was cleared, False otherwise
    """
    if session_id in _conversation_sessions:
        _conversation_sessions[session_id].clear_history()
        return True
    return False


def delete_session(session_id: str) -> bool:
    """
    Delete a conversation session entirely
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if session was deleted, False if not found
    """
    if session_id in _conversation_sessions:
        del _conversation_sessions[session_id]
        return True
    return False


def get_all_sessions() -> List[str]:
    """Get list of all active session IDs"""
    return list(_conversation_sessions.keys())


def get_session_info(session_id: str) -> Optional[Dict]:
    """
    Get information about a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Dictionary with session info or None if not found
    """
    if session_id in _conversation_sessions:
        chatbot = _conversation_sessions[session_id]
        return {
            "session_id": session_id,
            "history_length": chatbot.get_history_length(),
            "active": True
        }
    return None


# ============================================================================
# TESTING / STANDALONE USAGE
# ============================================================================

def test_chatbot():
    """Test the RAG chatbot"""
    print("\n" + "="*60)
    print("TESTING RAG CHATBOT WITH HISTORY")
    print("="*60 + "\n")
    
    chatbot = RAGChatbot(auto_ingest=True)
    
    # First question
    print("Question 1: Tell me about Microsoft")
    response1 = chatbot.chat("Tell me about Microsoft", k=3, verbose=True)
    print(f"Answer: {response1['answer']}\n")
    print(f"Sources: {response1['num_sources']} documents\n")
    print("-" * 60)
    
    # Follow-up question (will use context from history)
    print("\nQuestion 2: What about their GitHub acquisition?")
    response2 = chatbot.chat("What about their GitHub acquisition?", k=3, verbose=True)
    print(f"Contextualized to: {response2['contextualized_question']}")
    print(f"Answer: {response2['answer']}\n")
    print(f"Sources: {response2['num_sources']} documents\n")
    print("-" * 60)
    
    # Another follow-up
    print("\nQuestion 3: How much did they pay?")
    response3 = chatbot.chat("How much did they pay?", k=3, verbose=True)
    print(f"Contextualized to: {response3['contextualized_question']}")
    print(f"Answer: {response3['answer']}\n")
    
    print(f"\nTotal messages in history: {chatbot.get_history_length()}")


def interactive_chat():
    """Interactive chat session"""
    print("\n" + "="*60)
    print("INTERACTIVE RAG CHATBOT")
    print("Commands: 'quit' to exit, 'clear' to clear history")
    print("="*60 + "\n")
    
    chatbot = RAGChatbot(auto_ingest=True)
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() == 'quit':
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() == 'clear':
            chatbot.clear_history()
            continue
        
        if not user_input:
            continue
        
        response = chatbot.chat(user_input, k=3)
        print(f"\nBot: {response['answer']}")
        print(f"(History: {chatbot.get_history_length()} messages)")


if __name__ == "__main__":
    # Run ingestion (if needed)
    # ingest_documents(force_reingest=True)
    
    # Test the chatbot
    # test_chatbot()
    
    # Interactive chat
    interactive_chat()