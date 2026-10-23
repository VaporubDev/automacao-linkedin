from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.database import get_all_settings, update_settings, get_setting
from app.services.email_service import send_test_email
from app.services.ai_service import generate_linkedin_post
from app.services.scheduler import update_scheduler_interval

router = APIRouter(prefix="/api/settings", tags=["settings"])

class TestEmailPayload(BaseModel):
    to_email: str

class TestAIPayload(BaseModel):
    prompt_sample: Optional[str] = "Adicionei suporte a cache Redis e reduzi a latência em 40%"

@router.get("")
async def get_settings_endpoint():
    settings = get_all_settings()
    return {"settings": settings}

@router.post("")
async def save_settings_endpoint(payload: Dict[str, Any]):
    try:
        update_settings(payload)

        if "check_interval_minutes" in payload and payload["check_interval_minutes"]:
            try:
                update_scheduler_interval(int(payload["check_interval_minutes"]))
            except Exception:
                pass
        return {"success": True, "message": "Configurações salvas com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-email")
async def test_email_endpoint(payload: TestEmailPayload):
    try:
        await send_test_email(payload.to_email)
        return {"success": True, "message": f"Email de teste enviado com sucesso para {payload.to_email}!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao enviar email: {str(e)}")

@router.post("/test-ai")
async def test_ai_endpoint(payload: TestAIPayload):
    try:
        sample_text = await generate_linkedin_post(
            repo_name="meu-usuario/projeto-incrivel",
            repo_url="https://github.com/meu-usuario/projeto-incrivel",
            repo_description="Sistema de alta performance para processamento assíncrono",
            commit_message=payload.prompt_sample or "Otimização de performance com Redis",
            commit_author="Você"
        )
        return {"success": True, "generated_post": sample_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro na IA: {str(e)}")
