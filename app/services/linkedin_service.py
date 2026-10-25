import os
import httpx
import uuid
import datetime
from typing import Dict, Any, Tuple, Optional
from app.database import get_setting, get_connection

LINKEDIN_REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_REST_IMAGES_URL = "https://api.linkedin.com/rest/images"
LINKEDIN_REST_VIDEOS_URL = "https://api.linkedin.com/rest/videos"
LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_API_VERSION = "202511"

async def download_media_bytes(media_url: str) -> Tuple[Optional[bytes], str]:
    """
    Obtém os bytes da mídia, seja ela um arquivo local (/static/uploads/...) ou uma URL remota.
    Retorna (bytes_content, content_type).
    """
    if not media_url:
        return None, ""

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
            return content, mime_map.get(ext, "application/octet-stream")

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

async def upload_image_to_linkedin(client: httpx.AsyncClient, owner_urn: str, access_token: str, image_bytes: bytes, content_type: str) -> Optional[str]:
    """
    Realiza o fluxo oficial de upload de imagem para a REST Images API do LinkedIn.
    Retorna o URN da imagem (ex: urn:li:image:D4E10AQ...) ou None se falhar.
    """
    try:
        init_headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": LINKEDIN_API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        init_payload = {
            "initializeUploadRequest": {
                "owner": owner_urn
            }
        }
        init_resp = await client.post(
            f"{LINKEDIN_REST_IMAGES_URL}?action=initializeUpload",
            json=init_payload,
            headers=init_headers
        )
        if init_resp.status_code not in [200, 201]:
            print(f"[LinkedIn Image Upload Init Error] Status {init_resp.status_code}: {init_resp.text}")
            return None

        data = init_resp.json().get("value", {})
        upload_url = data.get("uploadUrl")
        image_urn = data.get("image")

        if not upload_url or not image_urn:
            return None

        put_headers = {
            "Content-Type": content_type or "image/png"
        }
        put_resp = await client.put(upload_url, content=image_bytes, headers=put_headers, timeout=60.0)
        if put_resp.status_code in [200, 201]:
            print(f"🖼️ [LinkedIn Media] Imagem carregada com sucesso! URN: {image_urn}")
            return image_urn
        else:
            print(f"[LinkedIn Image Upload Binary Error] Status {put_resp.status_code}: {put_resp.text[:200]}")
            return None

    except Exception as e:
        print(f"[LinkedIn Media Exception] Erro ao fazer upload de imagem: {e}")
        return None

async def upload_video_to_linkedin(client: httpx.AsyncClient, owner_urn: str, access_token: str, video_bytes: bytes, content_type: str) -> Optional[str]:
    """
    Realiza o fluxo oficial de upload de vídeo para a REST Videos API do LinkedIn.
    Retorna o URN do vídeo (ex: urn:li:video:...) ou None se falhar.
    """
    try:
        init_headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": LINKEDIN_API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        init_payload = {
            "initializeUploadRequest": {
                "owner": owner_urn,
                "fileSizeBytes": len(video_bytes),
                "uploadCaptions": False,
                "uploadThumbnail": False
            }
        }
        init_resp = await client.post(
            f"{LINKEDIN_REST_VIDEOS_URL}?action=initializeUpload",
            json=init_payload,
            headers=init_headers
        )
        if init_resp.status_code not in [200, 201]:
            print(f"[LinkedIn Video Upload Init Error] Status {init_resp.status_code}: {init_resp.text}")
            return None

        val = init_resp.json().get("value", {})
        video_urn = val.get("video")
        upload_instructions = val.get("uploadInstructions", [])

        if not video_urn or not upload_instructions:
            return None

        for instruction in upload_instructions:
            part_url = instruction.get("uploadUrl")
            first_byte = instruction.get("firstByte", 0)
            last_byte = instruction.get("lastByte", len(video_bytes) - 1)
            chunk = video_bytes[first_byte:last_byte + 1]

            put_headers = {"Content-Type": "application/octet-stream"}
            put_resp = await client.put(part_url, content=chunk, headers=put_headers, timeout=120.0)
            if put_resp.status_code not in [200, 201]:
                print(f"[LinkedIn Video Chunk Error] Status {put_resp.status_code}")
                return None

        finalize_payload = {
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadedPartIds": [instr.get("partId") for instr in upload_instructions if "partId" in instr]
            }
        }
        fin_resp = await client.post(
            f"{LINKEDIN_REST_VIDEOS_URL}?action=finalizeUpload",
            json=finalize_payload,
            headers=init_headers
        )
        if fin_resp.status_code in [200, 201]:
            print(f"🎬 [LinkedIn Media] Vídeo carregado com sucesso! URN: {video_urn}")
            return video_urn

        return video_urn

    except Exception as e:
        print(f"[LinkedIn Media Exception] Erro ao fazer upload de vídeo: {e}")
        return None

async def publish_to_linkedin(
    post_content: str,
    media_url: Optional[str] = None,
    media_type: str = "image",
    media_title: str = ""
) -> Tuple[bool, str, str]:
    """
    Publica um texto no perfil ou organização do LinkedIn via API oficial,
    com suporte a anexo nativo de imagens ou vídeos do projeto.
    Se estiver em 'Modo Simulação' ou sem chaves, simula a postagem com sucesso.

    Retorna: (sucesso: bool, linkedin_post_id: str, error_message: str)
    """
    simulation_mode = get_setting("linkedin_simulation_mode", "1") == "1"
    access_token = get_setting("linkedin_access_token", "").strip()
    person_urn = get_setting("linkedin_person_urn", "").strip()

    if simulation_mode or not access_token:
        # Modo simulação ativado: simula envio com imagem/vídeo
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
        async with httpx.AsyncClient(timeout=35.0) as client:
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

            last_err = ""
            last_status = 400

            # 4. Se houver mídia configurada, baixa os bytes
            media_bytes, content_type = (None, "")
            if media_url:
                media_bytes, content_type = await download_media_bytes(media_url)

            for author in unique_candidates:
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

                media_urn = None
                if media_bytes:
                    if media_type == "video" or content_type.startswith("video/"):
                        media_urn = await upload_video_to_linkedin(client, rest_author, access_token, media_bytes, content_type)
                    else:
                        media_urn = await upload_image_to_linkedin(client, rest_author, access_token, media_bytes, content_type)

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

                if media_urn:
                    rest_payload["content"] = {
                        "media": {
                            "id": media_urn,
                            "title": media_title or "Mídia do Projeto"
                        }
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

            # 6. Tenta publicar pelo endpoint alternativo /v2/ugcPosts caso REST tenha falhado
            for author in unique_candidates:
                ugc_author = author
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
