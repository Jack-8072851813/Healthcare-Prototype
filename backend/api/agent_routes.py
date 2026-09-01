from fastapi import APIRouter, Query, HTTPException, File, Form, UploadFile
from pydantic import BaseModel
from typing import Optional, List
import sys
import os
import uuid

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent.agent_service as agent_service
import voice.voice_service as voice_service

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])

class AgentChatRequest(BaseModel):
    conversation_id: str
    patient_id: Optional[str] = None  # Could be patient code (e.g. 'P001') or null
    message: str
    language: Optional[str] = "ENGLISH"

class AgentChatResponse(BaseModel):
    success: bool
    conversation_id: str
    language: str
    intent: str
    response: str
    missing_information: List[str]
    tool_called: Optional[str] = None

@router.post("/chat", response_model=AgentChatResponse)
def agent_chat_endpoint(payload: AgentChatRequest):
    try:
        # If payload.patient_id is provided, check if it is a patient code or user ID
        # Pass payload.message and conversation_id to process_agent_message
        res = agent_service.process_agent_message(
            conversation_code=payload.conversation_id,
            patient_code=payload.patient_id,
            message_text=payload.message,
            language_override=payload.language
        )
        return AgentChatResponse(
            success=res["success"],
            conversation_id=res["conversation_id"],
            language=res["language"],
            intent=res["intent"],
            response=res["response"],
            missing_information=res["missing_information"],
            tool_called=res["tool_called"]
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class VoiceProcessResponse(BaseModel):
    success: bool
    transcript: str
    language: str
    response_text: str
    audio: str
    intent: str
    missing_information: List[str]
    tool_called: Optional[str] = None

@router.post("/voice/process", response_model=VoiceProcessResponse)
async def voice_process_endpoint(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    patient_code: Optional[str] = Form(None),
    language: Optional[str] = Form(None)
):
    # Validate MIME type (must be audio file)
    if audio.content_type and not audio.content_type.startswith("audio/") and not audio.filename.endswith((".wav", ".mp3", ".ogg", ".m4a", ".webm")):
        raise HTTPException(status_code=400, detail="Invalid file type. Only audio files are accepted.")
    
    # Write incoming stream to temp file in scratch directory
    scratch_dir = os.path.join(backend_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    # Save file with extension preserved
    ext = os.path.splitext(audio.filename)[1] or ".wav"
    temp_file_name = f"upload_{uuid.uuid4().hex}{ext}"
    temp_file_path = os.path.join(scratch_dir, temp_file_name)
    
    try:
        # Validate size: limit to 15MB
        size = 0
        with open(temp_file_path, "wb") as buffer:
            while chunk := await audio.read(1024 * 1024):  # 1MB chunks
                size += len(chunk)
                if size > 15 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="Audio file too large. Maximum size is 15MB.")
                buffer.write(chunk)
        
        # Run speech-to-text -> Agent -> text-to-speech workflow
        res = voice_service.process_voice_input(
            audio_file_path=temp_file_path,
            session_id=session_id,
            patient_code=patient_code,
            language_override=language
        )
        
        if not res["success"]:
            raise HTTPException(status_code=500, detail=res.get("error", "Voice processing failed"))
            
        return VoiceProcessResponse(
            success=True,
            transcript=res["transcript"],
            language=res["language"],
            response_text=res["response_text"],
            audio=res["audio"],
            intent=res["intent"],
            missing_information=res["missing_information"],
            tool_called=res["tool_called"]
        )
    except HTTPException:
        # Re-raise standard HTTP exceptions
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary upload file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass



# ─── Knowledge Base API ────────────────────────────────────────────────────────

class KnowledgeSearchRequest(BaseModel):
    query: str
    language: Optional[str] = "ENGLISH"
    category: Optional[str] = None   # e.g. "DEPARTMENT", "OPD_TIMING", "PRE_ADMISSION"
    top_k: Optional[int] = 3

class KnowledgeSearchResult(BaseModel):
    category: str
    title: str
    content: str
    score: float
    source: Optional[str] = None
    document_id: Optional[int] = None
    chunk_id: Optional[int] = None

class KnowledgeSearchResponse(BaseModel):
    success: bool
    query: str
    results: List[KnowledgeSearchResult]
    total: int

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

@knowledge_router.post("/search", response_model=KnowledgeSearchResponse)
def knowledge_search_endpoint(payload: KnowledgeSearchRequest):
    """
    Search the Meridian Hospital knowledge base.
    Returns relevant knowledge chunks ranked by relevance score.
    Internal API — not exposed to patient UI.
    """
    try:
        import knowledge.knowledge_retriever as knowledge_retriever
        results = knowledge_retriever.search(
            query=payload.query,
            language=payload.language or "ENGLISH",
            category_hint=payload.category,
            top_k=payload.top_k or 3
        )
        return KnowledgeSearchResponse(
            success=True,
            query=payload.query,
            results=[
                KnowledgeSearchResult(
                    category=r["category"],
                    title=r["title"],
                    content=r["content"],
                    score=r["score"],
                    source=r.get("source"),
                    document_id=r.get("document_id"),
                    chunk_id=r.get("chunk_id")
                )
                for r in results
            ],
            total=len(results)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
