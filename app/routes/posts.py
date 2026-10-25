from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import datetime
import uuid
import os
import shutil
from typing import Optional
from app.database import get_connection
from app.services.linkedin_service import approve_and_publish_post, reject_post
from app.services.github_service import check_all_monitored_repositories
from app.services.ai_service import generate_linkedin_post
from app.services.email_service import send_approval_email
from app.services.media_helper import MEDIA_UPLOAD_DIR, get_media_type_from_filename, generate_website_screenshot_url

router = APIRouter(prefix="/api/posts", tags=["posts"])

class PostContentUpdate(BaseModel):
    post_content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = "image"
    media_title: Optional[str] = None

class SimulateCommitPayload(BaseModel):
    repo_name: Optional[str] = "usuario/meu-projeto-exemplo"
    commit_message: Optional[str] = "Implementação da nova API de autenticação e otimização de consultas"
    homepage_url: Optional[str] = "https://meu-projeto-demo.vercel.app"
    media_url: Optional[str] = None

@router.get("")
async def get_posts_queue(status: Optional[str] = None):
    conn = get_connection()
    if status:
        posts = conn.execute("SELECT * FROM posts_queue WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
    else:
        posts = conn.execute("SELECT * FROM posts_queue ORDER BY id DESC").fetchall()
    
    counts_raw = conn.execute("SELECT status, count(*) as total FROM posts_queue GROUP BY status").fetchall()
    conn.close()

    counts = {r["status"]: r["total"] for r in counts_raw}
    counts.setdefault("pending", 0)
    counts.setdefault("published", 0)
    counts.setdefault("rejected", 0)

    return {
        "counts": counts,
        "posts": [dict(p) for p in posts]
    }

@router.post("/{post_id}/approve")
async def approve_post_endpoint(post_id: int):
    success, message = await approve_and_publish_post(post_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}

@router.post("/{post_id}/reject")
async def reject_post_endpoint(post_id: int):
    success, message = await reject_post(post_id)
    return {"success": True, "message": message}

@router.delete("/{post_id}")
async def delete_post_endpoint(post_id: int):
    """Exclui permanentemente um post da fila (lixeira)."""
    conn = get_connection()
    post = conn.execute("SELECT id FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        raise HTTPException(status_code=404, detail="Post não encontrado")
    
    conn.execute("DELETE FROM posts_queue WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Post #{post_id} excluído com sucesso!"}

@router.post("/clear-answered")
async def clear_answered_posts_endpoint():
    """Remove da fila todos os posts que já foram respondidos (publicados, rejeitados ou falhos)."""
    conn = get_connection()
    cur = conn.execute("DELETE FROM posts_queue WHERE status != 'pending'")
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"{deleted_count} post(s) já respondido(s) limpo(s) com sucesso!"
    }

@router.put("/{post_id}")
async def update_post_content(post_id: int, payload: PostContentUpdate):
    conn = get_connection()
    conn.execute("""
        UPDATE posts_queue 
        SET post_content = ?, media_url = ?, media_type = ?, media_title = ? 
        WHERE id = ?
    """, (payload.post_content, payload.media_url, payload.media_type or "image", payload.media_title or "", post_id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Conteúdo e mídia do post atualizados com sucesso!"}

@router.post("/{post_id}/upload-media")
async def upload_post_media_file(post_id: int, file: UploadFile = File(...)):
    """Faz upload de uma imagem ou vídeo para associar ao post."""
    conn = get_connection()
    post = conn.execute("SELECT id FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        raise HTTPException(status_code=404, detail="Post não encontrado")

    ext = os.path.splitext(file.filename)[1].lower()
    media_type = get_media_type_from_filename(file.filename)
    unique_filename = f"post_{post_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(MEDIA_UPLOAD_DIR, unique_filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    media_relative_url = f"/static/uploads/{unique_filename}"
    conn.execute("""
        UPDATE posts_queue 
        SET media_url = ?, media_type = ?, media_title = ?
        WHERE id = ?
    """, (media_relative_url, media_type, file.filename, post_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "media_url": media_relative_url,
        "media_type": media_type,
        "media_title": file.filename,
        "message": "Mídia enviada e anexada ao post com sucesso!"
    }

@router.post("/{post_id}/fetch-screenshot")
async def fetch_screenshot_for_post(post_id: int, website_url: str):
    """Gera captura automática de tela do site informado e anexa ao post."""
    conn = get_connection()
    post = conn.execute("SELECT id FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        raise HTTPException(status_code=404, detail="Post não encontrado")

    screenshot_url = generate_website_screenshot_url(website_url)
    if not screenshot_url:
        conn.close()
        raise HTTPException(status_code=400, detail="URL inválida para captura de tela.")

    conn.execute("""
        UPDATE posts_queue 
        SET media_url = ?, media_type = 'image', media_title = ?
        WHERE id = ?
    """, (screenshot_url, f"Preview de {website_url}", post_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "media_url": screenshot_url,
        "media_type": "image",
        "message": "Screenshot da homepage gerada e anexada ao post!"
    }

@router.post("/manual-check")
async def trigger_manual_check():
    """Dispara imediatamente a verificação de todos os repositórios monitorados."""
    try:
        new_events = await check_all_monitored_repositories()
        return {
            "success": True,
            "new_events": new_events,
            "message": f"Verificação concluída! {new_events} nova(s) atualização(ões) encontrada(s)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate-commit")
async def simulate_commit_event(payload: SimulateCommitPayload):
    """
    Cria uma atualização de teste com IA, incluindo mídia do site/demo, e envia email de aprovação.
    """
    repo_name = payload.repo_name or "usuario/projeto-teste"
    commit_msg = payload.commit_message or "Nova funcionalidade implementada"
    homepage = payload.homepage_url or "https://meu-projeto-demo.vercel.app"
    author = "Desenvolvedor"
    sha = f"sim-{uuid.uuid4().hex[:7]}"
    now_str = datetime.datetime.now().isoformat()

    media_url = payload.media_url or generate_website_screenshot_url(homepage)
    media_type = get_media_type_from_filename(media_url) if media_url else "image"
    media_title = f"Interface ao vivo de {homepage}" if homepage else "Demonstração do Projeto"

    # Gera texto com IA
    post_text = await generate_linkedin_post(
        repo_name=repo_name,
        repo_url=f"https://github.com/{repo_name}",
        repo_description="Repositório de teste para validação de automação",
        commit_message=commit_msg,
        commit_author=author,
        homepage_url=homepage,
        has_media=bool(media_url)
    )

    approval_token = str(uuid.uuid4())

    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO posts_queue 
        (repo_name, commit_sha, commit_message, commit_author, commit_url, post_content, media_url, media_type, media_title, status, approval_token, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (repo_name, sha, commit_msg, author, f"https://github.com/{repo_name}", post_text, media_url, media_type, media_title, approval_token, now_str))
    
    post_id = cur.lastrowid
    conn.commit()
    conn.close()

    post_data = {
        "id": post_id,
        "repo_name": repo_name,
        "commit_sha": sha,
        "commit_message": commit_msg,
        "commit_author": author,
        "commit_url": f"https://github.com/{repo_name}",
        "post_content": post_text,
        "media_url": media_url,
        "media_type": media_type,
        "media_title": media_title,
        "approval_token": approval_token
    }

    email_sent = False
    try:
        email_sent = await send_approval_email(post_data)
    except Exception as err:
        print(f"[Simulation] Aviso de email: {err}")

    return {
        "success": True,
        "post_id": post_id,
        "email_sent": email_sent,
        "media_url": media_url,
        "message": "Atualização simulada criada com sucesso e adicionada à fila!",
        "post_content": post_text
    }

@router.post("/simulate-new-repo")
async def simulate_new_repo_event(payload: Optional[SimulateCommitPayload] = None):
    """
    Simula a criação de um novo repositório com texto de NOVIDADE gerado pela IA e anexo visual.
    """
    repo_name = (payload.repo_name if payload else None) or "VaporubDev/App-Inovador"
    description = "Sistema inovador de automação e produtividade com Python e IA"
    language = "Python"
    homepage = (payload.homepage_url if payload else None) or "https://vaporubdev.vercel.app"
    clean_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    html_url = f"https://github.com/{repo_name}"
    now_str = datetime.datetime.now().isoformat()

    media_url = (payload.media_url if payload else None) or generate_website_screenshot_url(homepage)
    media_type = get_media_type_from_filename(media_url) if media_url else "image"
    media_title = f"Screenshot do projeto {clean_name}"

    from app.services.ai_service import generate_new_repo_post
    post_text = await generate_new_repo_post(
        repo_name=repo_name,
        repo_url=html_url,
        repo_description=description,
        language=language,
        homepage_url=homepage,
        has_media=bool(media_url)
    )

    approval_token = str(uuid.uuid4())
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO posts_queue 
        (repo_name, commit_sha, commit_message, commit_author, commit_url, post_content, media_url, media_type, media_title, status, approval_token, created_at)
        VALUES (?, 'new-repo', ?, 'GitHub', ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (repo_name, f"🎉 Lançamento do Projeto: {clean_name}", html_url, post_text, media_url, media_type, media_title, approval_token, now_str))
    
    post_id = cur.lastrowid
    conn.commit()
    conn.close()

    post_data = {
        "id": post_id,
        "repo_name": repo_name,
        "commit_sha": "new-repo",
        "commit_message": f"🎉 Lançamento do Projeto: {clean_name}",
        "commit_author": "GitHub",
        "commit_url": html_url,
        "post_content": post_text,
        "media_url": media_url,
        "media_type": media_type,
        "media_title": media_title,
        "approval_token": approval_token
    }

    email_sent = False
    try:
        email_sent = await send_approval_email(post_data)
    except Exception as err:
        print(f"[Simulation] Aviso de email: {err}")

    return {
        "success": True,
        "post_id": post_id,
        "email_sent": email_sent,
        "media_url": media_url,
        "message": f"Post de NOVIDADE sobre '{repo_name}' gerado com mídia e adicionado à fila!",
        "post_content": post_text
    }
