from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import uuid
from pathlib import Path
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import tempfile
import os
from rag_chatbot import (
    get_chatbot,
    clear_session_history,
    delete_session,
    get_all_sessions,
    get_session_info,
    ingest_documents
)
from pdf_processor import PDFProcessor

app = FastAPI(title="RAG Chatbot API - Cloud Storage")

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PDF processor
pdf_processor = PDFProcessor(
    persist_directory="db/chroma_db",
    docs_directory="docs"
)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    k: int = 3
    verbose: bool = False


class ChatResponse(BaseModel):
    message: str
    answer: str
    session_id: str
    contextualized_question: Optional[str] = None
    sources: Optional[List] = None
    num_sources: Optional[int] = None


class UploadResponse(BaseModel):
    message: str
    filename: str
    session_id: str
    cloudinary_url: str
    cloudinary_public_id: str
    chunks_created: int
    text_length: int


class SessionFilesResponse(BaseModel):
    session_id: str
    files_count: int
    files: List[dict]
    embeddings_count: int


# ============================================================================
# CLOUDINARY HELPER FUNCTIONS
# ============================================================================

def upload_to_cloudinary(file_path: Path, session_id: str, original_filename: str) -> dict:
    """
    Upload PDF to Cloudinary as a public resource
    
    Args:
        file_path: Local path to the PDF file
        session_id: Session identifier
        original_filename: Original name of the file
    
    Returns:
        dict with cloudinary upload response
    """
    try:
        # Create a folder structure in Cloudinary: rag_pdfs/{session_id}/
        public_id = f"rag_pdfs/{session_id}/{Path(original_filename).stem}"
        
        result = cloudinary.uploader.upload(
            str(file_path),
            resource_type="raw",  # Use "raw" for non-image files like PDFs
            public_id=public_id,
            overwrite=True,
            invalidate=True,
            type="upload",  # Explicitly set type to "upload" (public)
            access_mode="public"  # Make the resource publicly accessible
        )
        
        print(f"✅ Cloudinary upload result: {result.get('secure_url')}")
        
        return {
            "success": True,
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "bytes": result["bytes"]
        }
    except Exception as e:
        print(f"❌ Cloudinary upload error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def delete_from_cloudinary(public_id: str) -> bool:
    """
    Delete a file from Cloudinary
    
    Args:
        public_id: The public ID of the file in Cloudinary
    
    Returns:
        bool indicating success
    """
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="raw")
        return result.get("result") == "ok"
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")
        return False


def list_session_files_cloudinary(session_id: str) -> List[dict]:
    """
    List all files for a session in Cloudinary
    
    Args:
        session_id: Session identifier
    
    Returns:
        List of file information dictionaries
    """
    try:
        # Search for files in the session folder
        result = cloudinary.api.resources(
            type="upload",
            resource_type="raw",
            prefix=f"rag_pdfs/{session_id}/",
            max_results=500
        )
        
        files = []
        for resource in result.get("resources", []):
            files.append({
                "filename": Path(resource["public_id"]).name + ".pdf",
                "public_id": resource["public_id"],
                "url": resource["secure_url"],
                "size": resource["bytes"],
                "created_at": resource["created_at"]
            })
        
        return files
    except Exception as e:
        print(f"Error listing Cloudinary files: {e}")
        return []


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "RAG Chatbot API - Cloud Storage (Cloudinary)",
        "endpoints": {
            "POST /chat": "Send a message",
            "POST /upload": "Upload PDF to Cloudinary and process for RAG",
            "GET /files/{session_id}": "List uploaded PDFs for session",
            "DELETE /files/{session_id}": "Delete all files for session",
            "POST /chat/clear/{session_id}": "Clear session history",
            "DELETE /chat/session/{session_id}": "Delete session",
            "GET /health": "Health check"
        }
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the RAG bot"""
    try:
        session_id = request.session_id if request.session_id else str(uuid.uuid4())
        
        chatbot = get_chatbot(session_id)
        response = chatbot.chat(
            message=request.message,
            k=request.k,
            verbose=request.verbose
        )
        
        response["session_id"] = session_id
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Upload a PDF file to Cloudinary and process for RAG
    
    OPTIMIZED: Process the file BEFORE uploading to avoid download issues
    """
    temp_path = None
    
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Create temporary file
        temp_path = Path(tempfile.mktemp(suffix=".pdf"))
        
        with temp_path.open("wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)
        
        print(f"📁 PDF received: {file.filename}")
        
        # STEP 1: Process PDF FIRST (while we have the file locally)
        print(f"🔄 Processing PDF for embeddings...")
        result = pdf_processor.process_uploaded_pdf(
            temp_path=temp_path,
            session_id=session_id,
            original_filename=file.filename
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to process PDF")
            )
        
        print(f"✅ PDF processed: {result['chunks_created']} chunks created")
        
        # STEP 2: Upload to Cloudinary for storage (after processing)
        print(f"☁️ Uploading to Cloudinary...")
        cloudinary_result = upload_to_cloudinary(
            temp_path, 
            session_id, 
            file.filename
        )
        
        if not cloudinary_result["success"]:
            # Processing succeeded but upload failed - that's okay, we have embeddings
            print(f"⚠️ Warning: Cloudinary upload failed but embeddings were created")
            return {
                "message": "PDF processed successfully (cloud backup failed)",
                "filename": file.filename,
                "session_id": session_id,
                "cloudinary_url": "",
                "cloudinary_public_id": "",
                "chunks_created": result["chunks_created"],
                "text_length": result["text_length"]
            }
        
        print(f"☁️ Uploaded to Cloudinary: {cloudinary_result['url']}")
        
        # Clean up temp file
        if temp_path and temp_path.exists():
            temp_path.unlink()
        
        return {
            "message": "PDF uploaded and processed successfully",
            "filename": file.filename,
            "session_id": session_id,
            "cloudinary_url": cloudinary_result["url"],
            "cloudinary_public_id": cloudinary_result["public_id"],
            "chunks_created": result["chunks_created"],
            "text_length": result["text_length"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if temp_path and temp_path.exists():
            temp_path.unlink()
        
        print(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{session_id}", response_model=SessionFilesResponse)
async def list_session_files(session_id: str):
    """List all uploaded PDFs and their embeddings for a session"""
    try:
        # Get files from Cloudinary
        cloudinary_files = list_session_files_cloudinary(session_id)
        
        # Get embedding stats from vector store
        stats = pdf_processor.get_session_stats(session_id)
        
        return {
            "session_id": session_id,
            "files_count": len(cloudinary_files),
            "files": cloudinary_files,
            "embeddings_count": stats.get("embeddings_count", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files/{session_id}")
async def delete_session_files(session_id: str):
    """Delete all files and embeddings for a session"""
    try:
        # Get all files from Cloudinary
        cloudinary_files = list_session_files_cloudinary(session_id)
        
        # Delete from Cloudinary
        deleted_count = 0
        for file_info in cloudinary_files:
            if delete_from_cloudinary(file_info["public_id"]):
                deleted_count += 1
        
        # Delete embeddings from vector store
        pdf_processor.delete_session_files(session_id)
        
        return {
            "message": f"Deleted all files for session {session_id}",
            "files_deleted": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/clear/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a specific session"""
    success = clear_session_history(session_id)
    if success:
        return {"message": f"History cleared for session {session_id}"}
    return {"message": f"Session {session_id} not found"}


@app.delete("/chat/session/{session_id}")
async def remove_session(session_id: str):
    """Delete a conversation session and all its files"""
    try:
        # Delete chat session
        chat_deleted = delete_session(session_id)
        
        # Get all files from Cloudinary
        cloudinary_files = list_session_files_cloudinary(session_id)
        
        # Delete from Cloudinary
        files_deleted = 0
        for file_info in cloudinary_files:
            if delete_from_cloudinary(file_info["public_id"]):
                files_deleted += 1
        
        # Delete embeddings
        pdf_processor.delete_session_files(session_id)
        
        if chat_deleted or files_deleted > 0:
            return {
                "message": f"Session {session_id} deleted",
                "files_deleted": files_deleted
            }
        
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "RAG Chatbot API is running",
        "storage": "Cloudinary",
        "active_sessions": len(get_all_sessions())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)