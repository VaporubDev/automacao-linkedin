from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.database import get_connection
from app.services.linkedin_service import approve_and_publish_post, reject_post

router = APIRouter(prefix="/actions", tags=["actions"])

@router.get("/approve/{post_id}", response_class=HTMLResponse)
async def handle_email_approve(post_id: int, token: str):
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    conn.close()

    if not post:
        return render_action_html(
            title="Post Não Encontrado",
            message="Esta publicação não foi encontrada ou já foi removida da fila.",
            badge="Erro",
            is_success=False
        )

    if post["approval_token"] != token:
        return render_action_html(
            title="Token de Segurança Inválido",
            message="O link de aprovação expirou ou é inválido.",
            badge="Não Autorizado",
            is_success=False
        )

    success, message = await approve_and_publish_post(post_id)
    return render_action_html(
        title="🎉 Publicação Aprovada!" if success else "⚠️ Falha ao Publicar no LinkedIn",
        message=message,
        badge="Sucesso" if success else "Atenção",
        is_success=success,
        repo_name=post["repo_name"],
        post_snippet=post["post_content"]
    )

@router.get("/reject/{post_id}", response_class=HTMLResponse)
async def handle_email_reject(post_id: int, token: str):
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    conn.close()

    if not post or post["approval_token"] != token:
        return render_action_html(
            title="Ação Não Concluída",
            message="O link expirou ou é inválido.",
            badge="Erro",
            is_success=False
        )

    await reject_post(post_id)
    return render_action_html(
        title="Publicação Descartada",
        message="O post foi marcado como rejeitado e NÃO será enviado ao LinkedIn.",
        badge="Descartado",
        is_success=True,
        repo_name=post["repo_name"]
    )

def render_action_html(title: str, message: str, badge: str, is_success: bool, repo_name: str = "", post_snippet: str = ""):
    badge_color = "#10b981" if is_success else "#ef4444"
    icon_svg = """<svg style="width: 48px; height: 48px; margin: 0 auto 16px; color: #10b981;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>""" if is_success else """<svg style="width: 48px; height: 48px; margin: 0 auto 16px; color: #ef4444;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>"""

    snippet_html = f"""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 10px; padding: 16px; margin: 20px 0; text-align: left; font-size: 14px; color: #cbd5e1; max-height: 200px; overflow-y: auto; white-space: pre-wrap;">{post_snippet}</div>
    """ if post_snippet else ""

    repo_html = f"""<p style="color: #38bdf8; font-size: 14px; margin: 5px 0 15px;">Repositório: <strong>{repo_name}</strong></p>""" if repo_name else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} &bull; GitPost</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }}
    body {{
      background: radial-gradient(circle at top, #0f172a 0%, #07090e 100%);
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .card {{
      background: rgba(16, 22, 34, 0.9);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 20px;
      padding: 40px 32px;
      max-width: 520px;
      width: 100%;
      text-align: center;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
      animation: popIn 0.3s ease-out;
    }}
    @keyframes popIn {{
      from {{ opacity: 0; transform: scale(0.96); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      background: {badge_color}22;
      color: {badge_color};
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 16px;
      border: 1px solid {badge_color}44;
    }}
    h1 {{ font-size: 22px; margin-bottom: 12px; color: #fff; }}
    p.message {{ font-size: 14.5px; color: #94a3b8; line-height: 1.6; margin-bottom: 20px; }}
    .btn {{
      display: inline-block;
      padding: 12px 28px;
      background: linear-gradient(135deg, #0ea5e9, #0284c7);
      color: #fff;
      text-decoration: none;
      font-weight: 600;
      font-size: 14.5px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
      transition: all 0.2s;
    }}
    .btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(14, 165, 233, 0.6);
    }}
  </style>
</head>
<body>
  <div class="card">
    {icon_svg}
    <div class="badge">{badge}</div>
    <h1>{title}</h1>
    {repo_html}
    <p class="message">{message}</p>
    {snippet_html}
    <a href="/" class="btn">Abrir Painel do GitPost</a>
  </div>
</body>
</html>
"""
