import httpx
import uuid
import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.database import get_connection, get_setting

GITHUB_API_URL = "https://api.github.com"

def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    if token is None:
        raw = get_setting("github_token", "").strip()
        if raw and (raw.startswith("ghp_") or raw.startswith("github_pat_") or raw.startswith("gho_")):
            token = raw
        else:
            token = ""

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitPost-LinkedIn-App"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

async def fetch_user_repositories() -> List[Dict[str, Any]]:
    """
    Busca os repositórios do usuário no GitHub e atualiza a base local.
    Se tiver token, busca repositórios autenticados (inclui privados e organizações).
    Caso contrário, busca pelos repositórios públicos do username configurado.
    """
    token = get_setting("github_token", "").strip()
    username = get_setting("github_username", "").strip()

    # Se o token não parecer um token GitHub
    use_token = bool(token and (token.startswith("ghp_") or token.startswith("github_pat_") or token.startswith("gho_")))

    if not use_token and not username:
        raise ValueError("Configure seu Nome de Usuário ou Personal Access Token do GitHub nas configurações.")

    headers = get_headers(token if use_token else None)
    url = f"{GITHUB_API_URL}/user/repos?per_page=100&sort=updated" if use_token else f"{GITHUB_API_URL}/users/{username}/repos?per_page=100&sort=updated"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 401 and username and use_token:
            print("[GitHub Service] Token retornou 401. Buscando repositórios públicos pelo nome de usuário...")
            public_headers = get_headers(None)
            response = await client.get(f"{GITHUB_API_URL}/users/{username}/repos?per_page=100&sort=updated", headers=public_headers)

        if response.status_code != 200:
            raise ValueError(f"Erro ao buscar repositórios no GitHub ({response.status_code}): {response.text}")
        
        repos_data = response.json()

    conn = get_connection()
    now_str = datetime.datetime.now().isoformat()

    synced_repos = []
    for r in repos_data:
        full_name = r.get("full_name")
        description = r.get("description") or ""
        is_private = 1 if r.get("private") else 0
        default_branch = r.get("default_branch") or "main"
        html_url = r.get("html_url")
        stars = r.get("stargazers_count", 0)
        language = r.get("language") or "Outro"


        existing = conn.execute("SELECT id, is_monitored, last_sha FROM monitored_repos WHERE repo_name = ?", (full_name,)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE monitored_repos 
                SET description = ?, is_private = ?, default_branch = ?, html_url = ?, stars = ?, language = ?, updated_at = ?
                WHERE id = ?
            """, (description, is_private, default_branch, html_url, stars, language, now_str, existing["id"]))
            is_mon = existing["is_monitored"]
            repo_id = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO monitored_repos 
                (repo_name, description, is_monitored, is_private, default_branch, html_url, stars, language, updated_at)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)
            """, (full_name, description, is_private, default_branch, html_url, stars, language, now_str))
            is_mon = 0
            repo_id = cur.lastrowid

        synced_repos.append({
            "id": repo_id,
            "repo_name": full_name,
            "description": description,
            "is_monitored": bool(is_mon),
            "is_private": bool(is_private),
            "default_branch": default_branch,
            "html_url": html_url,
            "stars": stars,
            "language": language
        })

    conn.commit()
    conn.close()
    return synced_repos

async def queue_new_repo_announcement(repo_dict: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
    """
    Gera automaticamente uma publicação na fila com foco em NOVIDADE / LANÇAMENTO
    para um repositório que foi adicionado ao monitoramento ou recém-criado.
    """
    from app.services.ai_service import generate_new_repo_post
    from app.services.email_service import send_approval_email

    repo_name = repo_dict.get("repo_name")
    html_url = repo_dict.get("html_url") or f"https://github.com/{repo_name}"
    description = repo_dict.get("description") or ""
    language = repo_dict.get("language") or ""
    clean_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name

    # Verifica se já existe um post desse repo na fila para não duplicar
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, status FROM posts_queue WHERE repo_name = ? AND commit_sha = 'new-repo'",
        (repo_name,)
    ).fetchone()
    
    if existing:
        conn.close()
        return False, f"Já existe uma publicação de novidade na fila para {repo_name} (Status: {existing['status']}).", existing["id"]

    print(f"\n[GitPost] Gerando publicação com IA sobre o novo repositório: {repo_name}...")
    post_text = await generate_new_repo_post(
        repo_name=repo_name,
        repo_url=html_url,
        repo_description=description,
        language=language
    )

    approval_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()

    cur = conn.execute("""
        INSERT INTO posts_queue 
        (repo_name, commit_sha, commit_message, commit_author, commit_url, post_content, status, approval_token, created_at)
        VALUES (?, 'new-repo', ?, 'GitHub', ?, ?, 'pending', ?, ?)
    """, (repo_name, f"🎉 Lançamento do Projeto: {clean_name}", html_url, post_text, approval_token, now_str))
    
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
        "approval_token": approval_token
    }

    try:
        await send_approval_email(post_data)
        print(f"[GitPost] E-mail de aprovação enviado para o post #{post_id} ({repo_name})!")
    except Exception as e:
        print(f"[Email Warning] Falha ao enviar email do novo repo: {e}")

    return True, f"Publicação de NOVIDADE criada para '{repo_name}' e adicionada à Fila!", post_id

async def check_repo_updates(repo: Any = None, repo_dict: Dict[str, Any] = None):
    """
    Verifica se há novos commits em um repositório monitorado.
    Dispara IA e cria item na fila para aprovação por email se encontrar novo commit.
    """
    from app.services.ai_service import generate_linkedin_post
    from app.services.email_service import send_approval_email

    r_id = repo_dict["id"]
    repo_name = repo_dict["repo_name"]
    default_branch = repo_dict.get("default_branch") or "main"
    html_url = repo_dict.get("html_url")
    description = repo_dict.get("description") or ""

    token = get_setting("github_token")
    headers = get_headers(token)

    url = f"{GITHUB_API_URL}/repos/{repo_name}/commits?sha={default_branch}&per_page=5"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"[GitHub] Erro ao buscar commits de {repo_name}: {resp.status_code}")
                return []
            commits = resp.json()
    except Exception as e:
        print(f"[GitHub] Falha de conexão ao checar {repo_name}: {e}")
        return []

    if not isinstance(commits, list) or len(commits) == 0:
        return []

    conn = get_connection()
    now_str = datetime.datetime.now().isoformat()
    new_pending_posts = []


    last_known_sha = repo_dict.get("last_sha")
    is_initial_check = not bool(last_known_sha)

    commits_to_process = [commits[0]] if is_initial_check else commits

    for c in reversed(commits_to_process):
        sha = c.get("sha")
        commit_info = c.get("commit", {})
        message = commit_info.get("message", "").strip()
        author_name = commit_info.get("author", {}).get("name", "Desenvolvedor")
        commit_url = c.get("html_url", f"{html_url}/commit/{sha}")

        if message.startswith("Merge branch") or message.startswith("Merge pull request"):
            continue

        already_processed = conn.execute("SELECT 1 FROM processed_commits WHERE sha = ?", (sha,)).fetchone()
        if already_processed:
            continue

        conn.execute("INSERT INTO processed_commits (sha, repo_name, processed_at) VALUES (?, ?, ?)",
                     (sha, repo_name, now_str))

        if is_initial_check:
            continue

        post_text = await generate_linkedin_post(
            repo_name=repo_name,
            repo_url=html_url,
            repo_description=description,
            commit_message=message,
            commit_author=author_name
        )

        approval_token = str(uuid.uuid4())

        cur = conn.execute("""
            INSERT INTO posts_queue 
            (repo_name, commit_sha, commit_message, commit_author, commit_url, post_content, status, approval_token, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (repo_name, sha, message, author_name, commit_url, post_text, approval_token, now_str))
        
        post_id = cur.lastrowid

        post_data = {
            "id": post_id,
            "repo_name": repo_name,
            "commit_sha": sha,
            "commit_message": message,
            "commit_author": author_name,
            "commit_url": commit_url,
            "post_content": post_text,
            "approval_token": approval_token
        }
        new_pending_posts.append(post_data)

        # Dispara o email
        try:
            await send_approval_email(post_data)
        except Exception as err:
            print(f"[Email] Erro ao enviar email para post #{post_id}: {err}")

    latest_sha = commits[0].get("sha")
    conn.execute("UPDATE monitored_repos SET last_sha = ?, last_checked_at = ? WHERE id = ?",
                 (latest_sha, now_str, r_id))
    conn.commit()
    conn.close()

    return new_pending_posts

async def check_all_monitored_repositories() -> int:
    """Verifica todos os repositórios que estão marcados como monitorados."""
    conn = get_connection()
    repos = conn.execute("SELECT * FROM monitored_repos WHERE is_monitored = 1").fetchall()
    conn.close()

    total_new_events = 0
    for r in repos:
        r_dict = dict(r)
        new_posts = await check_repo_updates(repo_dict=r_dict)
        total_new_events += len(new_posts)

    return total_new_events
