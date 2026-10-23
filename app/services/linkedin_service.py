import httpx
import uuid
import datetime
from typing import Dict, Any, Tuple
from app.database import get_setting, get_connection

LINKEDIN_REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_API_VERSION = "202511"

async def publish_to_linkedin(post_content: str) -> Tuple[bool, str, str]:
    """
    Publica um texto no perfil ou organização do LinkedIn via API oficial.
    Se estiver em 'Modo Simulação' ou sem chaves, simula a postagem com sucesso
    para testes práticos do fluxo sem travar.

    Retorna: (sucesso: bool, linkedin_post_id: str, error_message: str)
    """
    simulation_mode = get_setting("linkedin_simulation_mode", "1") == "1"
    access_token = get_setting("linkedin_access_token", "").strip()
    person_urn = get_setting("linkedin_person_urn", "").strip()

    if simulation_mode or not access_token:
        # Modo simulação ativado: simula envio perfeito
        mock_id = f"mock-share-{uuid.uuid4().hex[:10]}"
        print(f"\n[LinkedIn - SIMULAÇÃO] Post publicado com sucesso em Modo Teste!")
        print(f"Conteúdo:\n{post_content}\n")
        return True, mock_id, ""

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            real_author = None
            userinfo_permitted = False

            # 1. Consulta o usuário proprietário do token na API do LinkedIn (OpenID Connect)
            try:
                uinfo = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
                print(f"[LinkedIn Debug] /v2/userinfo status={uinfo.status_code}")
                if uinfo.status_code == 200:
                    userinfo_permitted = True
                    sub = uinfo.json().get("sub")
                    if sub:
                        real_author = f"urn:li:person:{sub}"
                        print(f"[LinkedIn Auth] Autor autenticado identificado com sucesso: {real_author}")
                elif uinfo.status_code == 403:
                    userinfo_permitted = False
            except Exception as e:
                print(f"[LinkedIn Debug] Erro ao consultar /v2/userinfo: {e}")

            # 2. Se não conseguiu pelo userinfo, tenta pelo /v2/me legado
            if not real_author:
                try:
                    me_resp = await client.get("https://api.linkedin.com/v2/me", headers=headers)
                    if me_resp.status_code == 200:
                        me_id = me_resp.json().get("id")
                        if me_id:
                            real_author = f"urn:li:person:{me_id}"
                except Exception:
                    pass

            # 3. Monta lista de autores candidatos
            candidates = []
            if real_author:
                candidates.append(real_author)

            # Extrai ID limpo configurado manualmente
            clean_urn = person_urn.strip()
            raw_id = clean_urn.split(":")[-1] if ":" in clean_urn else clean_urn

            if clean_urn:
                if clean_urn.startswith("urn:li:"):
                    candidates.append(clean_urn)
                else:
                    candidates.append(f"urn:li:person:{clean_urn}")

                # Variações úteis (person vs member vs organization)
                if raw_id:
                    if raw_id.isdigit():
                        candidates.append(f"urn:li:member:{raw_id}")
                        candidates.append(f"urn:li:person:{raw_id}")
                    else:
                        candidates.append(f"urn:li:person:{raw_id}")

            # Remove duplicados preservando ordem
            unique_candidates = []
            for c in candidates:
                if c and c not in unique_candidates:
                    unique_candidates.append(c)

            print(f"[LinkedIn Debug] Candidatos a autor: {unique_candidates}")

            last_err = ""
            last_status = 400

            # 4. Tenta publicar primeiro pela moderna REST Posts API (LinkedIn Standard)
            for author in unique_candidates:
                # O REST posts aceita urn:li:person: ou urn:li:organization:
                rest_author = author
                if rest_author.startswith("urn:li:member:"):
                    rest_author = rest_author.replace("urn:li:member:", "urn:li:person:")

                print(f"[LinkedIn Attempt REST] Tentando autor: {rest_author}")
                rest_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": LINKEDIN_API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json"
                }
                rest_payload = {
                    "author": rest_author,
                    "commentary": post_content,
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MAIN_FEED"
                    },
                    "lifecycleState": "PUBLISHED",
                    "isReshareDisabledByAuthor": False
                }

                resp_rest = await client.post(LINKEDIN_REST_POSTS_URL, json=rest_payload, headers=rest_headers)
                print(f"[LinkedIn Debug REST] Status {resp_rest.status_code}: {resp_rest.text[:200]}")
                if resp_rest.status_code in [200, 201]:
                    post_id = resp_rest.headers.get("x-restli-id") or f"urn:li:share:{uuid.uuid4().hex[:8]}"
                    print(f"🎉 [LinkedIn Success] Post publicado via REST Posts API! ID: {post_id}")
                    return True, post_id, ""
                else:
                    last_status = resp_rest.status_code
                    last_err = resp_rest.text

            # 5. Tenta publicar pelo endpoint alternativo /v2/ugcPosts caso REST tenha falhado
            for author in unique_candidates:
                ugc_author = author
                # ugcPosts exige urn:li:member: para pessoas físicas ou urn:li:company: para empresas
                if ugc_author.startswith("urn:li:person:"):
                    p_id = ugc_author.split(":")[-1]
                    if p_id.isdigit():
                        ugc_author = f"urn:li:member:{p_id}"
                elif ugc_author.startswith("urn:li:organization:"):
                    o_id = ugc_author.split(":")[-1]
                    ugc_author = f"urn:li:company:{o_id}"

                print(f"[LinkedIn Attempt UGC] Tentando autor: {ugc_author}")
                ugc_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json"
                }
                ugc_payload = {
                    "author": ugc_author,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": post_content},
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
                }
                resp_ugc = await client.post(LINKEDIN_UGC_POSTS_URL, json=ugc_payload, headers=ugc_headers)
                print(f"[LinkedIn Debug UGC] Status {resp_ugc.status_code}: {resp_ugc.text[:200]}")
                if resp_ugc.status_code in [200, 201]:
                    data = resp_ugc.json()
                    post_id = data.get("id", f"urn:li:share:{uuid.uuid4().hex[:8]}")
                    print(f"🎉 [LinkedIn Success] Post publicado via UGC Posts API! ID: {post_id}")
                    return True, post_id, ""
                else:
                    last_status = resp_ugc.status_code
                    last_err = resp_ugc.text

            # Mensagem diagnóstica detalhada se nenhuma tentativa passou
            if not userinfo_permitted:
                friendly_error = (
                    "O token do LinkedIn não tem permissão para identificar sua conta (erro 403 no userinfo). "
                    "Para corrigir: no LinkedIn Developers > seu App > aba 'Products', adicione 'Sign In with LinkedIn using OpenID Connect'. "
                    "Depois em 'Auth' > 'OAuth 2.0 tools', gere um novo token marcando 'openid', 'profile' e 'w_member_social'. "
                    "(Dica: Você pode ativar o 'Modo Simulação' nas Configurações para testar o sistema sem precisar da API do LinkedIn)."
                )
                print(f"[LinkedIn Auth Warning] {friendly_error}")
                return False, "", friendly_error

            return False, "", f"Erro LinkedIn ({last_status}): {last_err}"

    except Exception as e:
        err_msg = f"Exceção ao conectar no LinkedIn: {str(e)}"
        print(f"[LinkedIn Exception] {err_msg}")
        return False, "", err_msg

async def approve_and_publish_post(post_id: int) -> Tuple[bool, str]:
    """
    Aprova um post na fila e o envia para publicação no LinkedIn.
    """
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return False, "Post não encontrado na fila."

    if post["status"] == "published":
        conn.close()
        return True, "Este post já foi publicado anteriormente."

    success, linkedin_id, error_msg = await publish_to_linkedin(post["post_content"])
    now_str = datetime.datetime.now().isoformat()

    if success:
        conn.execute("""
            UPDATE posts_queue 
            SET status = 'published', linkedin_post_id = ?, published_at = ?, error_message = ''
            WHERE id = ?
        """, (linkedin_id, now_str, post_id))
        conn.commit()
        conn.close()
        return True, f"Post publicado com sucesso! ID: {linkedin_id}"
    else:
        conn.execute("""
            UPDATE posts_queue 
            SET status = 'failed', error_message = ?
            WHERE id = ?
        """, (error_msg, post_id))
        conn.commit()
        conn.close()
        return False, f"Falha ao publicar: {error_msg}"

async def reject_post(post_id: int) -> Tuple[bool, str]:
    """Marca um post como rejeitado para não ser publicado."""
    conn = get_connection()
    conn.execute("UPDATE posts_queue SET status = 'rejected' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return True, "Post descartado com sucesso."
