from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent.agent_service as agent_service

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
