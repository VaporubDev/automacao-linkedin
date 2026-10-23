from fastapi import APIRouter, Request, HTTPException
import uuid
import datetime
from app.database import get_connection
from app.services.ai_service import generate_linkedin_post
from app.services.email_service import send_approval_email

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

@router.post("/github")
async def github_webhook_receiver(request: Request):
    """
    Endpoint de Webhook do GitHub.
    Recebe eventos 'push' e 'release' em tempo real.
    """
    event_type = request.headers.get("X-GitHub-Event", "push")
    payload = await request.json()

    repository = payload.get("repository", {})
    repo_name = repository.get("full_name")
    html_url = repository.get("html_url")
    description = repository.get("description") or ""

    if not repo_name:
        return {"ignored": True, "reason": "Sem repositório no payload"}

    # Verificação de repositórios monitorados
    conn = get_connection()
    repo_row = conn.execute("SELECT * FROM monitored_repos WHERE repo_name = ? AND is_monitored = 1", (repo_name,)).fetchone()
    
    if not repo_row:
        conn.close()
        return {"ignored": True, "reason": f"Repositório '{repo_name}' não está marcado como monitorado no painel."}

    now_str = datetime.datetime.now().isoformat()
    created_posts = []

    if event_type == "push":
        commits = payload.get("commits", [])
        for c in commits:
            sha = c.get("id")
            message = c.get("message", "").strip()
            author = c.get("author", {}).get("name", "Desenvolvedor")
            commit_url = c.get("url", f"{html_url}/commit/{sha}")

            already_processed = conn.execute("SELECT 1 FROM processed_commits WHERE sha = ?", (sha,)).fetchone()
            if already_processed:
                continue

            conn.execute("INSERT INTO processed_commits (sha, repo_name, processed_at) VALUES (?, ?, ?)",
                         (sha, repo_name, now_str))

            # Gera texto com IA
            post_text = await generate_linkedin_post(
                repo_name=repo_name,
                repo_url=html_url,
                repo_description=description,
                commit_message=message,
                commit_author=author
            )

            token = str(uuid.uuid4())
            cur = conn.execute("""
                INSERT INTO posts_queue 
                (repo_name, commit_sha, commit_message, commit_author, commit_url, post_content, status, approval_token, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (repo_name, sha, message, author, commit_url, post_text, token, now_str))
            
            post_id = cur.lastrowid
            post_data = {
                "id": post_id,
                "repo_name": repo_name,
                "commit_sha": sha,
                "commit_message": message,
                "commit_author": author,
                "commit_url": commit_url,
                "post_content": post_text,
                "approval_token": token
            }
            created_posts.append(post_id)

            # Dispara email
            try:
                await send_approval_email(post_data)
            except Exception as e:
                print(f"[Webhook Email Error] {e}")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "event": event_type,
        "repo": repo_name,
        "posts_created": len(created_posts)
    }
