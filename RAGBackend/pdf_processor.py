import os
from pathlib import Path
from typing import List, Optional
from PyPDF2 import PdfReader
from langchain_core.documents import Document  # Changed from langchain.schema
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from dotenv import load_dotenv

load_dotenv()

class PDFProcessor:
    """Process PDFs and add to vector store"""
    
    def __init__(
        self, 
        persist_directory: str = "db/chroma_db",
        docs_directory: str = "docs"
    ):
        self.persist_directory = persist_directory
        self.docs_directory = Path(docs_directory)
        self.docs_directory.mkdir(exist_ok=True)
        api_key = os.getenv("HF_TOKEN")
        self.embedding_function = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=api_key
        )
        
        # Load or create vector store
        if os.path.exists(persist_directory):
            self.db = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embedding_function,
                collection_metadata={"hnsw:space": "cosine"}
            )
        else:
            self.db = None
    
    def save_uploaded_pdf(
        self, 
        source_path: Path, 
        session_id: str,
        filename: str
    ) -> Path:
        """
        Save uploaded PDF to docs directory organized by session
        
        Args:
            source_path: Temporary upload path
            session_id: User session ID
            filename: Original filename
            
        Returns:
            Path where file was saved
        """
        # Create session subdirectory
        session_dir = self.docs_directory / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Destination path
        dest_path = session_dir / filename
        
        # Copy file
        import shutil
        shutil.copy2(source_path, dest_path)
        
        print(f"✅ PDF saved to docs: {dest_path}")
        return dest_path
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            reader = PdfReader(str(pdf_path))
            text = ""
            
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            
            print(f"✅ Extracted {len(text)} characters from {pdf_path.name} ({len(reader.pages)} pages)")
            return text
            
        except Exception as e:
            print(f"❌ Failed to extract text from PDF: {e}")
            return ""
    
    def create_documents(
        self, 
        text: str, 
        source: str, 
        session_id: str,
        filename: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Document]:
        """
        Split text into chunks and create Document objects
        
        Args:
            text: Text content
            source: Source file path
            session_id: User session ID
            filename: Original filename
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of Document objects
        """
        text_splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator="\n"
        )
        
        chunks = text_splitter.split_text(text)
        
        documents = [
            Document(
                page_content=chunk,
                metadata={
                    "source": source,
                    "filename": filename,
                    "session_id": session_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "type": "uploaded_pdf"
                }
            )
            for i, chunk in enumerate(chunks)
        ]
        
        print(f"✅ Created {len(documents)} document chunks from {filename}")
        return documents
    
    def add_to_vector_store(self, documents: List[Document]) -> int:
        """
        Add documents to vector store
        
        Args:
            documents: List of Document objects
            
        Returns:
            Number of documents added
        """
        try:
            if self.db is None:
                # Create new vector store
                self.db = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embedding_function,
                    persist_directory=self.persist_directory,
                    collection_metadata={"hnsw:space": "cosine"}
                )
            else:
                # Add to existing vector store
                self.db.add_documents(documents)
            
            print(f"✅ Added {len(documents)} documents to vector store")
            return len(documents)
            
        except Exception as e:
            print(f"❌ Failed to add documents to vector store: {e}")
            return 0
    
    def process_uploaded_pdf(
        self, 
        temp_path: Path,
        session_id: str,
        original_filename: str
    ) -> dict:
        """
        Complete PDF processing pipeline for uploaded files
        
        Args:
            temp_path: Temporary upload path
            session_id: User session ID
            original_filename: Original filename
            
        Returns:
            Dict with processing results
        """
        print(f"🔄 Processing uploaded PDF: {original_filename}")
        
        try:
            # 1. Save to docs directory
            saved_path = self.save_uploaded_pdf(
                source_path=temp_path,
                session_id=session_id,
                filename=original_filename
            )
            
            # 2. Extract text
            text = self.extract_text_from_pdf(saved_path)
            
            if not text:
                return {
                    "success": False,
                    "error": "Failed to extract text from PDF",
                    "chunks_created": 0
                }
            
            # 3. Create documents with metadata
            documents = self.create_documents(
                text=text,
                source=str(saved_path),
                session_id=session_id,
                filename=original_filename
            )
            
            # 4. Add to vector store
            chunks_added = self.add_to_vector_store(documents)
            
            if chunks_added > 0:
                print(f"✅ PDF processing complete: {original_filename}")
                return {
                    "success": True,
                    "saved_path": str(saved_path),
                    "chunks_created": chunks_added,
                    "text_length": len(text)
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to add to vector store",
                    "chunks_created": 0
                }
                
        except Exception as e:
            print(f"❌ Error processing PDF: {e}")
            return {
                "success": False,
                "error": str(e),
                "chunks_created": 0
            }
    
    def get_session_files(self, session_id: str) -> List[Path]:
        """
        Get all PDF files for a session
        
        Args:
            session_id: User session ID
            
        Returns:
            List of file paths
        """
        session_dir = self.docs_directory / session_id
        
        if not session_dir.exists():
            return []
        
        return list(session_dir.glob("*.pdf"))
    
    def delete_session_files(self, session_id: str) -> int:
        """
        Delete all files and embeddings for a session
        
        Args:
            session_id: User session ID
            
        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0
            
            # Delete files from docs directory
            session_dir = self.docs_directory / session_id
            if session_dir.exists():
                for file_path in session_dir.glob("*.pdf"):
                    file_path.unlink()
                    deleted_count += 1
                
                # Remove empty directory
                if not any(session_dir.iterdir()):
                    session_dir.rmdir()
            
            # Delete from vector store
            if self.db is not None:
                results = self.db.get(where={"session_id": session_id})
                
                if results and results['ids']:
                    self.db.delete(ids=results['ids'])
                    print(f"✅ Deleted {len(results['ids'])} embeddings for session {session_id}")
            
            print(f"✅ Deleted {deleted_count} files for session {session_id}")
            return deleted_count
            
        except Exception as e:
            print(f"❌ Failed to delete session files: {e}")
            return 0
    
    def get_session_stats(self, session_id: str) -> dict:
        """
        Get statistics for a session
        
        Args:
            session_id: User session ID
            
        Returns:
            Dict with session statistics
        """
        try:
            files = self.get_session_files(session_id)
            
            embeddings_count = 0
            if self.db is not None:
                results = self.db.get(where={"session_id": session_id})
                embeddings_count = len(results['ids']) if results and results['ids'] else 0
            
            return {
                "session_id": session_id,
                "files_count": len(files),
                "files": [f.name for f in files],
                "embeddings_count": embeddings_count
            }
        except Exception as e:
            print(f"❌ Error getting session stats: {e}")
            return {
                "session_id": session_id,
                "error": str(e)
            }