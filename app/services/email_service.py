import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from app.database import get_setting

async def send_approval_email(post_data: Dict[str, Any]) -> bool:
    """
    Monta e envia um email com design moderno perguntando ao usuário se
    ele autoriza a publicação no LinkedIn, com botões de ação em 1 clique.
    """
    recipient = get_setting("email_recipient")
    smtp_host = get_setting("smtp_host")
    smtp_port = int(get_setting("smtp_port") or 587)
    smtp_user = get_setting("smtp_user")
    smtp_pass = get_setting("smtp_pass")
    smtp_from = get_setting("smtp_from") or smtp_user
    base_url = get_setting("app_base_url", "http://localhost:8000").rstrip("/")

    post_id = post_data["id"]
    repo_name = post_data["repo_name"]
    commit_msg = post_data["commit_message"]
    commit_sha = post_data["commit_sha"][:7]
    commit_url = post_data.get("commit_url", "#")
    post_content = post_data["post_content"]
    token = post_data["approval_token"]

    approve_url = f"{base_url}/actions/approve/{post_id}?token={token}"
    reject_url = f"{base_url}/actions/reject/{post_id}?token={token}"
    edit_url = f"{base_url}/#post-{post_id}"

    subject = f"🔔 [GitPost] Nova atualização em '{repo_name}' - Postar no LinkedIn?"

    html_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0a111a; margin: 0; padding: 28px 16px; color: #f1faee; }}
    .container {{ max-width: 620px; margin: 0 auto; background: #0f1c2d; border-radius: 14px; border: 1px solid rgba(168, 218, 220, 0.2); overflow: hidden; box-shadow: 0 12px 35px rgba(0,0,0,0.5); }}
    .top-accent {{ height: 3px; background: linear-gradient(90deg, #0a66c2, #38bdf8, #1d3557); }}
    .header {{ background: #16263b; padding: 24px 30px; border-bottom: 1px solid rgba(168, 218, 220, 0.15); }}
    .header h1 {{ margin: 0; font-size: 18px; font-weight: 800; color: #f1faee; letter-spacing: -0.3px; }}
    .header p {{ margin: 6px 0 0; font-size: 12.5px; color: #8fa0b5; font-family: 'JetBrains Mono', monospace; }}
    .content {{ padding: 26px 30px; }}
    .repo-pill {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; background: rgba(10, 102, 194, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); margin-bottom: 16px; }}
    .info-box {{ background: #0a111a; border: 1px solid rgba(168, 218, 220, 0.12); border-radius: 8px; padding: 14px 16px; margin: 14px 0 20px; font-size: 13px; line-height: 1.5; }}
    .info-row {{ margin-bottom: 5px; color: #8fa0b5; }}
    .info-row:last-child {{ margin-bottom: 0; }}
    .info-row strong {{ color: #f1faee; }}
    .preview-label {{ font-size: 12.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #38bdf8; margin: 18px 0 8px; }}
    .post-box {{ background: #0a111a; border-left: 4px solid #0a66c2; border-radius: 8px; padding: 16px 18px; margin: 0 0 24px; white-space: pre-wrap; font-size: 13.5px; line-height: 1.6; color: #e2e8f0; border: 1px solid rgba(168, 218, 220, 0.12); border-left: 4px solid #0a66c2; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 24px 0 10px; }}
    .btn {{ display: inline-block; text-decoration: none; padding: 11px 20px; border-radius: 6px; font-size: 13px; font-weight: 700; text-align: center; transition: all 0.2s ease; }}
    .btn-approve {{ background: #0a66c2; color: #ffffff !important; box-shadow: 0 4px 14px rgba(10, 102, 194, 0.4); }}
    .btn-edit {{ background: #16263b; color: #f1faee !important; border: 1px solid rgba(168, 218, 220, 0.25); }}
    .btn-delete {{ background: #e63946; color: #ffffff !important; box-shadow: 0 4px 14px rgba(230, 57, 70, 0.35); }}
    .footer {{ padding: 16px 30px; background: #0a111a; border-top: 1px solid rgba(168, 218, 220, 0.12); text-align: center; font-size: 11.5px; color: #8fa0b5; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="top-accent"></div>
    <div class="header">
      <h1>GitPost &bull; Publicação de Novidade no LinkedIn</h1>
      <p>Pipeline GitHub &rarr; Gemini IA &rarr; LinkedIn</p>
    </div>
    <div class="content">
      <span class="repo-pill">📁 Repositório: {repo_name}</span>
      
      <div class="info-box">
        <div class="info-row"><strong>Atualização:</strong> {commit_msg}</div>
        <div class="info-row"><strong>Commit SHA:</strong> <a href="{commit_url}" style="color: #38bdf8; text-decoration: none;">{commit_sha}</a></div>
      </div>

      <div class="preview-label">Texto Gerado para o LinkedIn:</div>
      <div class="post-box">{post_content}</div>

      <p style="font-size: 12.5px; color: #8fa0b5; margin-bottom: 14px;">Escolha a ação desejada diretamente por este e-mail:</p>
      
      <div class="actions">
        <a href="{approve_url}" class="btn btn-approve">Aprovar & Postar no LinkedIn</a>
        <a href="{edit_url}" class="btn btn-edit">Editar Texto</a>
        <a href="{reject_url}" class="btn btn-delete">Excluir / Descartar</a>
      </div>
    </div>
    <div class="footer">
      GitPost Automation &bull; Executando localmente no seu computador.
    </div>
  </div>
</body>
</html>
"""

    resend_api_key = get_setting("resend_api_key")

    # Se tiver chave do Resend configurada, envia via API HTTP do Resend
    if resend_api_key:
        import httpx
        payload = {
            "from": get_setting("email_from_custom") or "GitPost <onboarding@resend.dev>",
            "to": [recipient],
            "subject": subject,
            "html": html_body,
            "text": f"Nova atualizacao em {repo_name}!\nAprovar: {approve_url}\nRejeitar: {reject_url}"
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if resp.status_code in (200, 201):
                print(f"[Email-Resend] Notificação enviada com sucesso para {recipient}")
                return True
            else:
                error_detail = resp.text
                print(f"[Email-Resend] Erro ao enviar email: {error_detail}")
                raise Exception(f"Erro Resend ({resp.status_code}): {error_detail}")

    if not smtp_user or not smtp_pass or not recipient:
        print("[GitPost Email] Credenciais de SMTP ou Resend ainda não foram preenchidas nas Configurações.")
        print(f"Destinatário pretendido: {recipient or 'NÃO DEFINIDO'}")
        print(f"Assunto: {subject}")
        print(f"Link de Aprovação Direta: {approve_url}")
        print(f"Link de Rejeição: {reject_url}\n")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = recipient

    plain_text = f"""GitPost: Nova atualização em {repo_name}!
Commit: {commit_msg}

Rascunho do Post no LinkedIn:
{post_content}

Para aprovar e postar: {approve_url}
Para rejeitar: {reject_url}
Para editar: {edit_url}
"""
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [recipient], msg.as_string())
        print(f"[Email] Notificação de aprovação enviada com sucesso para {recipient}")
        return True
    except Exception as e:
        print(f"[Email] Erro ao enviar email via {smtp_host}:{smtp_port}: {e}")
        raise e

async def send_test_email(to_email: str) -> bool:
    """Envia um email de teste para verificar as credenciais SMTP ou Resend."""
    resend_api_key = get_setting("resend_api_key")
    if resend_api_key:
        import httpx
        html = f"""
        <div style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 500px;">
          <h2 style="color: #38bdf8;">Conexão de Email Funcionando! 🎉</h2>
          <p>O envio via <strong>Resend API</strong> no GitPost está configurado e funcionando perfeitamente!</p>
          <p style="color: #94a3b8; font-size: 13px;">Quando você fizer commits em repositórios monitorados, os emails de autorização chegarão aqui com botões para postar no LinkedIn.</p>
        </div>
        """
        payload = {
            "from": get_setting("email_from_custom") or "GitPost <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "[GitPost] Teste de Conexão bem-sucedido via Resend!",
            "html": html,
            "text": "Conexão de email funcionando via Resend!"
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if resp.status_code in (200, 201):
                return True
            else:
                raise Exception(f"Erro no Resend ({resp.status_code}): {resp.text}")

    smtp_host = get_setting("smtp_host")
    smtp_port = int(get_setting("smtp_port") or 587)
    smtp_user = get_setting("smtp_user")
    smtp_pass = get_setting("smtp_pass")
    smtp_from = get_setting("smtp_from") or smtp_user

    if not smtp_user or not smtp_pass:
        raise ValueError("Configure uma chave do Resend OU usuário e senha SMTP.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[GitPost] Teste de Conexão de Email bem-sucedido!"
    msg["From"] = smtp_from
    msg["To"] = to_email

    html = f"""
    <div style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 500px;">
      <h2 style="color: #38bdf8;">Conexão de Email Funcionando! 🎉</h2>
      <p>Suas configurações de SMTP no <strong>GitPost</strong> estão corretas.</p>
      <p style="color: #94a3b8; font-size: 13px;">Quando você fizer commits em repositórios monitorados, os emails de autorização chegarão aqui com botões para postar no LinkedIn.</p>
    </div>
    """
    msg.attach(MIMEText("Teste de Conexão de Email bem-sucedido!", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())

    return True
