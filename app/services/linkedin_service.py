import os
import httpx
import uuid
import datetime
from typing import Dict, Any, Tuple, Optional
from app.database import get_setting, get_connection

LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_ASSETS_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"
LINKEDIN_REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_VERSION = "202511"

async def download_media_bytes(media_url: str) -> Tuple[Optional[bytes], str]:
    """
    Obtém os bytes da mídia, seja ela um arquivo local (/static/uploads/...) ou uma URL remota.
    Retorna (bytes_content, content_type).
    """
    if not media_url:
        return None, ""

    # Se for arquivo local salvo no static/uploads
    if "/static/uploads/" in media_url or media_url.startswith("static/uploads/"):
        filename = os.path.basename(media_url)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_path = os.path.join(base_dir, "static", "uploads", filename)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                content = f.read()
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".mp4": "video/mp4",
                ".mov": "video/quicktime",
                ".webm": "video/webm"
            }
            return content, mime_map.get(ext, "image/png")

    # Se for URL externa na internet
    if media_url.startswith("http://") or media_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(media_url)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                    if not content_type:
                        clean = media_url.lower().split("?")[0]
                        if clean.endswith(".png"):
                            content_type = "image/png"
                        elif clean.endswith((".jpg", ".jpeg")):
                            content_type = "image/jpeg"
                        elif clean.endswith(".mp4"):
                            content_type = "video/mp4"
                        else:
                            content_type = "image/png"
                    return resp.content, content_type
        except Exception as e:
            print(f"[LinkedIn Media] Falha ao baixar mídia remota ({media_url}): {e}")

    return None, ""

async def upload_asset_to_linkedin(
    client: httpx.AsyncClient,
    owner_urn: str,
    access_token: str,
    media_bytes: bytes,
    content_type: str,
    media_type: str = "image"
) -> Optional[str]:
    """
    Realiza o fluxo oficial com a Assets API (registerUpload + PUT binary).
    Garante que a imagem ou vídeo renderize de forma visível e nativa no feed do LinkedIn.
    Retorna o asset URN (ex: urn:li:digitalmediaAsset:...)
    """
    try:
        is_video = (media_type == "video" or content_type.startswith("video/"))
        recipe = "urn:li:digitalmediaRecipe:feedshare-video" if is_video else "urn:li:digitalmediaRecipe:feedshare-image"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }

        reg_payload = {
            "registerUploadRequest": {
                "recipes": [recipe],
                "owner": owner_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }],
                "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
            }
        }

        reg_resp = await client.post(LINKEDIN_ASSETS_URL, json=reg_payload, headers=headers)
        if reg_resp.status_code not in [200, 201]:
            print(f"[LinkedIn Asset Reg Error] Status {reg_resp.status_code}: {reg_resp.text}")
            return None

        val = reg_resp.json().get("value", {})
        asset_urn = val.get("asset")
        mech = val.get("uploadMechanism", {}).get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
        upload_url = mech.get("uploadUrl")

        if not asset_urn or not upload_url:
            print(f"[LinkedIn Asset Error] Não retornou asset ou uploadUrl: {val}")
            return None

        # Upload dos bytes binários na URL retornada
        put_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type or ("video/mp4" if is_video else "image/png")
        }
        put_resp = await client.put(upload_url, content=media_bytes, headers=put_headers, timeout=90.0)
        if put_resp.status_code in [200, 201]:
            print(f"🖼️ [LinkedIn Media] Anexo ({media_type.upper()}) enviado com sucesso! Asset: {asset_urn}")
            return asset_urn
        else:
            print(f"[LinkedIn Binary Upload Error] Status {put_resp.status_code}: {put_resp.text[:200]}")
            return None

    except Exception as e:
        print(f"[LinkedIn Media Exception] Erro ao registrar asset: {e}")
        return None

async def publish_to_linkedin(
    post_content: str,
    media_url: Optional[str] = None,
    media_type: str = "image",
    media_title: str = ""
) -> Tuple[bool, str, str]:
    """
    Publica um texto no perfil ou organização do LinkedIn via API oficial,
    com suporte comprovado a anexo nativo visível de imagens ou vídeos do projeto.
    Se estiver em 'Modo Simulação' ou sem chaves, simula a postagem com sucesso.

    Retorna: (sucesso: bool, linkedin_post_id: str, error_message: str)
    """
    simulation_mode = get_setting("linkedin_simulation_mode", "1") == "1"
    access_token = get_setting("linkedin_access_token", "").strip()
    person_urn = get_setting("linkedin_person_urn", "").strip()

    if simulation_mode or not access_token:
        mock_id = f"mock-share-{uuid.uuid4().hex[:10]}"
        print(f"\n[LinkedIn - SIMULAÇÃO] Post publicado com sucesso em Modo Teste!")
        if media_url:
            print(f"[LinkedIn - SIMULAÇÃO MÍDIA] Anexo nativo ({media_type.upper()}): {media_url}")
        print(f"Conteúdo:\n{post_content}\n")
        return True, mock_id, ""

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            real_author = None
            userinfo_permitted = False

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

            if not real_author:
                try:
                    me_resp = await client.get("https://api.linkedin.com/v2/me", headers=headers)
                    if me_resp.status_code == 200:
                        me_id = me_resp.json().get("id")
                        if me_id:
                            real_author = f"urn:li:person:{me_id}"
                except Exception:
                    pass

            candidates = []
            if real_author:
                candidates.append(real_author)

            clean_urn = person_urn.strip()
            raw_id = clean_urn.split(":")[-1] if ":" in clean_urn else clean_urn

            if clean_urn:
                if clean_urn.startswith("urn:li:"):
                    candidates.append(clean_urn)
                else:
                    candidates.append(f"urn:li:person:{clean_urn}")

                if raw_id:
                    if raw_id.isdigit():
                        candidates.append(f"urn:li:member:{raw_id}")
                        candidates.append(f"urn:li:person:{raw_id}")
                    else:
                        candidates.append(f"urn:li:person:{raw_id}")

            unique_candidates = []
            for c in candidates:
                if c and c not in unique_candidates:
                    unique_candidates.append(c)

            print(f"[LinkedIn Debug] Candidatos a autor: {unique_candidates}")

            # Baixa os bytes da mídia se houver URL configurada
            media_bytes, content_type = (None, "")
            if media_url:
                media_bytes, content_type = await download_media_bytes(media_url)

            last_err = ""
            last_status = 400

            # 1. FLUXO PRIORITÁRIO: UGC Posts API com Asset Nativo
            # Garante que imagens e vídeos sejam renderizados de forma 100% nativa no feed do LinkedIn
            for author in unique_candidates:
                ugc_author = author
                if ugc_author.startswith("urn:li:member:"):
                    ugc_author = ugc_author.replace("urn:li:member:", "urn:li:person:")

                print(f"[LinkedIn Attempt UGC] Tentando autor: {ugc_author}")
                ugc_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json"
                }

                # Upload de mídia via Assets API
                asset_urn = None
                if media_bytes:
                    asset_urn = await upload_asset_to_linkedin(
                        client=client,
                        owner_urn=ugc_author,
                        access_token=access_token,
                        media_bytes=media_bytes,
                        content_type=content_type,
                        media_type=media_type
                    )

                if asset_urn:
                    is_video = (media_type == "video" or content_type.startswith("video/"))
                    cat = "VIDEO" if is_video else "IMAGE"
                    ugc_payload = {
                        "author": ugc_author,
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {
                            "com.linkedin.ugc.ShareContent": {
                                "shareCommentary": {"text": post_content},
                                "shareMediaCategory": cat,
                                "media": [{
                                    "status": "READY",
                                    "description": {"text": media_title or "Mídia do Projeto"},
                                    "media": asset_urn,
                                    "title": {"text": media_title or "Demonstração do Projeto"}
                                }]
                            }
                        },
                        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
                    }
                else:
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
                    print(f"🎉 [LinkedIn Success] Post com anexo de mídia publicado com sucesso! ID: {post_id}")
                    return True, post_id, ""
                else:
                    last_status = resp_ugc.status_code
                    last_err = resp_ugc.text

            # 2. FLUXO SECUNDÁRIO DE FALLBACK: REST Posts API
            for author in unique_candidates:
                rest_author = author
                if rest_author.startswith("urn:li:member:"):
                    rest_author = rest_author.replace("urn:li:member:", "urn:li:person:")

                print(f"[LinkedIn Attempt REST Fallback] Tentando autor: {rest_author}")
                rest_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "LinkedIn-Version": LINKEDIN_API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json"
                }

                rest_payload: Dict[str, Any] = {
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
                if resp_rest.status_code in [200, 201]:
                    post_id = resp_rest.headers.get("x-restli-id") or f"urn:li:share:{uuid.uuid4().hex[:8]}"
                    print(f"🎉 [LinkedIn Success] Post publicado via REST Posts API! ID: {post_id}")
                    return True, post_id, ""
                else:
                    last_status = resp_rest.status_code
                    last_err = resp_rest.text

            if not userinfo_permitted:
                friendly_error = (
                    "O token do LinkedIn não tem permissão para identificar sua conta (erro 403 no userinfo). "
                    "Para corrigir: no LinkedIn Developers > seu App > aba 'Products', adicione 'Sign In with LinkedIn using OpenID Connect'. "
                    "Depois em 'Auth' > 'OAuth 2.0 tools', gere um novo token marcando 'openid', 'profile' e 'w_member_social'."
                )
                return False, "", friendly_error

            return False, "", f"Erro LinkedIn ({last_status}): {last_err}"

    except Exception as e:
        err_msg = f"Exceção ao conectar no LinkedIn: {str(e)}"
        print(f"[LinkedIn Exception] {err_msg}")
        return False, "", err_msg

async def approve_and_publish_post(post_id: int) -> Tuple[bool, str]:
    """
    Aprova um post na fila e o envia para publicação no LinkedIn,
    incluindo a mídia associada (imagem ou vídeo do projeto).
    """
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts_queue WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return False, "Post não encontrado na fila."

    if post["status"] == "published":
        conn.close()
        return True, "Este post já foi publicado anteriormente."

    post_dict = dict(post)
    success, linkedin_id, error_msg = await publish_to_linkedin(
        post_content=post_dict["post_content"],
        media_url=post_dict.get("media_url"),
        media_type=post_dict.get("media_type") or "image",
        media_title=post_dict.get("media_title") or ""
    )
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
