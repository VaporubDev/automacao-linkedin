from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import get_connection
from app.services.github_service import fetch_user_repositories, queue_new_repo_announcement

router = APIRouter(prefix="/api/repos", tags=["repos"])

class BranchUpdate(BaseModel):
    branch: str

@router.get("")
async def list_repositories():
    conn = get_connection()
    repos = conn.execute("SELECT * FROM monitored_repos ORDER BY is_monitored DESC, updated_at DESC").fetchall()
    conn.close()

    items = [dict(r) for r in repos]
    monitored_count = sum(1 for r in items if r["is_monitored"])
    return {
        "total": len(items),
        "monitored_count": monitored_count,
        "repositories": items
    }

@router.post("/sync")
async def sync_github_repositories():
    try:
        repos = await fetch_user_repositories()
        return {
            "success": True,
            "message": f"{len(repos)} repositórios sincronizados com sucesso do GitHub!",
            "total": len(repos)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset")
async def reset_repositories():
    """Limpa a lista de repositórios monitorados para refazer o reconhecimento do zero."""
    conn = get_connection()
    conn.execute("DELETE FROM monitored_repos")
    conn.execute("DELETE FROM processed_commits")
    conn.commit()
    conn.close()
    return {
        "success": True,
        "message": "Lista de repositórios reiniciada! Agora você pode sincronizar do zero."
    }

@router.post("/{repo_id}/toggle")
async def toggle_repository_monitoring(repo_id: int):
    conn = get_connection()
    repo = conn.execute("SELECT * FROM monitored_repos WHERE id = ?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    repo_dict = dict(repo)
    new_state = 0 if repo_dict["is_monitored"] else 1
    conn.execute("UPDATE monitored_repos SET is_monitored = ? WHERE id = ?", (new_state, repo_id))
    conn.commit()
    conn.close()

    queued_msg = ""
    post_id = None
    if new_state == 1:
        # QUANDO ADICIONA O REPOSITORIO, GERA AUTOMATICAMENTE O POST DE NOVIDADE!
        success, msg, post_id = await queue_new_repo_announcement(repo_dict)
        if success:
            queued_msg = f" 🎉 Post de NOVIDADE criado na fila (Post #{post_id}) e notificação enviada por e-mail!"
        else:
            queued_msg = f" ({msg})"

    status_str = "agora está sendo monitorado!" if new_state else "não está mais sendo monitorado."
    return {
        "success": True,
        "repo_id": repo_id,
        "is_monitored": bool(new_state),
        "post_id": post_id,
        "message": f"'{repo_dict['repo_name']}' {status_str}{queued_msg}"
    }

@router.post("/{repo_id}/announce")
async def announce_repository(repo_id: int):
    """Gera manualmente um post de novidade/lançamento para o repositório selecionado."""
    conn = get_connection()
    repo = conn.execute("SELECT * FROM monitored_repos WHERE id = ?", (repo_id,)).fetchone()
    conn.close()
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    repo_dict = dict(repo)
    success, msg, post_id = await queue_new_repo_announcement(repo_dict)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "post_id": post_id,
        "message": f"Post de novidade sobre '{repo_dict['repo_name']}' gerado e adicionado à Fila de Publicações!"
    }

@router.post("/{repo_id}/branch")
async def update_monitored_branch(repo_id: int, payload: BranchUpdate):
    conn = get_connection()
    conn.execute("UPDATE monitored_repos SET default_branch = ? WHERE id = ?", (payload.branch, repo_id))
    conn.commit()
    conn.close()
    return {"success": True, "branch": payload.branch}
