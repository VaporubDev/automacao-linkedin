import os
import re
import uuid
import asyncio
import subprocess
import urllib.parse
from typing import Optional, Tuple, List, Dict, Any
import httpx
try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None
from app.database import get_setting

MEDIA_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
os.makedirs(MEDIA_UPLOAD_DIR, exist_ok=True)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm")

def get_media_type_from_filename(filename_or_url: str) -> str:
    """Retorna 'image' ou 'video' com base na extensão da URL ou arquivo."""
    clean = filename_or_url.lower().split("?")[0]
    if any(clean.endswith(ext) for ext in VIDEO_EXTENSIONS):
        return "video"
    return "image"

async def extract_media_from_repo_readme(repo_name: str, default_branch: str = "main") -> Optional[Dict[str, str]]:
    """
    Busca o README.md no repositório GitHub e procura por tags de imagem/vídeo ou screenshots.
    Retorna dict com {'url': str, 'type': 'image'|'video', 'title': str} ou None.
    """
    token = get_setting("github_token", "").strip()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitPost-LinkedIn-App"
    }
    if token and (token.startswith("ghp_") or token.startswith("github_pat_") or token.startswith("gho_")):
        headers["Authorization"] = f"Bearer {token}"

    readme_content = ""
    api_url = f"https://api.github.com/repos/{repo_name}/readme"
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                download_url = data.get("download_url")
                if download_url:
                    content_resp = await client.get(download_url)
                    if content_resp.status_code == 200:
                        readme_content = content_resp.text
        except Exception as e:
            print(f"[Media Extraction] Falha ao ler README via API para {repo_name}: {e}")

    if not readme_content:
        for branch in [default_branch, "main", "master"]:
            raw_url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/README.md"
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(raw_url)
                    if resp.status_code == 200:
                        readme_content = resp.text
                        break
            except Exception:
                continue

    if not readme_content:
        return None

    md_img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    html_img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

    raw_urls = []
    for match in md_img_pattern.finditer(readme_content):
        alt = match.group(1).strip()
        url = match.group(2).strip()
        raw_urls.append((url, alt))

    for match in html_img_pattern.finditer(readme_content):
        url = match.group(1).strip()
        raw_urls.append((url, "Screenshot do projeto"))

    ignored_domains = ["shields.io", "badge.fury.io", "github.com/workflows", "travis-ci", "circleci", "codecov.io"]
    
    for url, alt in raw_urls:
        if any(ign in url.lower() for ign in ignored_domains):
            continue
        final_url = url
        if not url.startswith("http://") and not url.startswith("https://"):
            clean_rel = url.lstrip("./").lstrip("/")
            final_url = f"https://raw.githubusercontent.com/{repo_name}/{default_branch}/{clean_rel}"

        media_type = get_media_type_from_filename(final_url)
        return {
            "url": final_url,
            "type": media_type,
            "title": alt or f"Mídia de {repo_name}"
        }

    return None

def generate_website_screenshot_url(website_url: str) -> Optional[str]:
    """
    Gera uma URL de captura de tela de alta resolução para o site do projeto.
    """
    if not website_url or not (website_url.startswith("http://") or website_url.startswith("https://")):
        return None
    
    encoded = urllib.parse.quote(website_url, safe="")
    screenshot_url = f"https://api.microlink.io/?url={encoded}&screenshot=true&meta=false&embed=screenshot.url"
    return screenshot_url

async def generate_website_video_recording(website_url: str) -> Optional[str]:
    """
    Grava um vídeo do site em funcionamento realizando scroll suave cadenciado
    do topo até o final exato da página, encerrando apenas quando chegar ao fim.
    Salva o vídeo gravado em MP4 no servidor local e retorna a URL relativa (/static/uploads/...).
    """
    if not website_url or not (website_url.startswith("http://") or website_url.startswith("https://")):
        return None

    # Tenta gravação interna de alta resolução com Playwright e rolagem suave até o rodapé
    try:
        from playwright.async_api import async_playwright

        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        executable = edge_path if os.path.exists(edge_path) else (chrome_path if os.path.exists(chrome_path) else None)

        async with async_playwright() as p:
            launch_kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]}
            if executable:
                launch_kwargs["executable_path"] = executable

            try:
                browser = await p.chromium.launch(**launch_kwargs)
            except Exception as launch_err:
                if "executable_path" in launch_kwargs:
                    launch_kwargs.pop("executable_path", None)
                    browser = await p.chromium.launch(**launch_kwargs)
                else:
                    raise launch_err

            temp_record_dir = os.path.join(MEDIA_UPLOAD_DIR, "tmp_recordings")
            os.makedirs(temp_record_dir, exist_ok=True)

            viewport_w = 1440
            viewport_h = 810

            context = await browser.new_context(
                record_video_dir=temp_record_dir,
                record_video_size={"width": viewport_w, "height": viewport_h},
                viewport={"width": viewport_w, "height": viewport_h}
            )

            page = await context.new_page()
            nav_success = False
            for strategy in ["load", "domcontentloaded"]:
                try:
                    await page.goto(website_url, wait_until=strategy, timeout=15000)
                    nav_success = True
                    break
                except Exception:
                    continue

            if not nav_success:
                try:
                    await page.goto(website_url, timeout=12000)
                except Exception:
                    pass

            await asyncio.sleep(1.5)

            try:
                total_height = await page.evaluate(
                    "() => Math.max(document.body ? document.body.scrollHeight : 0, document.documentElement ? document.documentElement.scrollHeight : 0, 1000)"
                )
            except Exception:
                total_height = 2000

            max_scroll = max(0, total_height - viewport_h)

            current_y = 0
            step = 65
            delay = 0.045

            while current_y < max_scroll:
                current_y += step
                if current_y > max_scroll:
                    current_y = max_scroll
                try:
                    await page.evaluate(f"window.scrollTo(0, {current_y})")
                except Exception:
                    break
                await asyncio.sleep(delay)

            await asyncio.sleep(2.0)

            video_obj = page.video
            await page.close()
            await context.close()
            await browser.close()

            raw_video_path = await video_obj.path() if video_obj else None
            if raw_video_path and os.path.exists(raw_video_path):
                file_id = uuid.uuid4().hex[:10]
                output_mp4_filename = f"site_rec_{file_id}.mp4"
                output_mp4_path = os.path.join(MEDIA_UPLOAD_DIR, output_mp4_filename)

                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe() if imageio_ffmpeg else None
                if not ffmpeg_bin:
                    playwright_ffmpeg = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\ffmpeg-1013\ffmpeg-win64.exe")
                    if os.path.exists(playwright_ffmpeg):
                        ffmpeg_bin = playwright_ffmpeg

                converted = False
                if ffmpeg_bin and os.path.exists(ffmpeg_bin):
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-ss", "00:00:01",
                        "-i", raw_video_path,
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-preset", "fast", "-crf", "22",
                        output_mp4_path
                    ]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode == 0 and os.path.exists(output_mp4_path):
                        converted = True

                if not converted:
                    fallback_name = f"site_rec_{file_id}.webm"
                    fallback_path = os.path.join(MEDIA_UPLOAD_DIR, fallback_name)
                    import shutil
                    shutil.copyfile(raw_video_path, fallback_path)
                    try:
                        os.remove(raw_video_path)
                    except Exception:
                        pass
                    return f"/static/uploads/{fallback_name}"

                try:
                    os.remove(raw_video_path)
                except Exception:
                    pass

                return f"/static/uploads/{output_mp4_filename}"

    except Exception as err:
        print(f"[Media Helper] Gravação local via Playwright falhou ({err}), tentando fallback online...")

    # Fallback se Playwright não puder executar no ambiente: Microlink API
    encoded = urllib.parse.quote(website_url, safe="")
    api_endpoint = f"https://api.microlink.io/?url={encoded}&screenshot=true&screenshot.animated=true&scroll=%23footer&meta=false"

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(api_endpoint)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                animated_info = data.get("screenshot", {}).get("animated", {})
                video_url = animated_info.get("url")
                if video_url:
                    try:
                        dl_resp = await client.get(video_url)
                        if dl_resp.status_code == 200 and dl_resp.content:
                            file_id = uuid.uuid4().hex[:10]
                            local_filename = f"site_rec_{file_id}.mp4"
                            local_path = os.path.join(MEDIA_UPLOAD_DIR, local_filename)
                            with open(local_path, "wb") as f:
                                f.write(dl_resp.content)
                            return f"/static/uploads/{local_filename}"
                    except Exception as dl_err:
                        print(f"[Media Helper] Falha ao baixar vídeo remoto do Microlink: {dl_err}")
                    return video_url
    except Exception as e:
        print(f"[Media Helper] Falha ao gravar vídeo do site ({website_url}): {e}")

    return None

async def resolve_best_repo_media(repo_dict: Dict[str, Any], prefer_video: bool = False) -> Tuple[Optional[str], str, str]:
    """
    Tenta determinar a melhor mídia automática para o post do repositório:
    1. Se prefer_video=True e houver site/homepage -> grava vídeo do site funcionando.
    2. Se tiver README com imagens/vídeos de demonstração -> seleciona a mídia do README.
    3. Se tiver site/homepage no GitHub -> gera screenshot da homepage.
    4. Retorna (media_url, media_type, media_title)
    """
    repo_name = repo_dict.get("repo_name", "")
    default_branch = repo_dict.get("default_branch") or "main"
    homepage_url = (repo_dict.get("homepage_url") or "").strip()

    # 1. Se foi solicitada gravação de vídeo do site
    if prefer_video and homepage_url and homepage_url.startswith("http"):
        video_rec = await generate_website_video_recording(homepage_url)
        if video_rec:
            return video_rec, "video", f"Vídeo do site {homepage_url} em ação"

    # 2. Tenta extrair do README
    try:
        readme_media = await extract_media_from_repo_readme(repo_name, default_branch)
        if readme_media:
            return readme_media["url"], readme_media["type"], readme_media.get("title", f"Demonstração de {repo_name}")
    except Exception as e:
        print(f"[Media Helper] Erro ao buscar mídia no README: {e}")

    # 3. Se tiver site/homepage, gera print do site
    if homepage_url and homepage_url.startswith("http"):
        shot_url = generate_website_screenshot_url(homepage_url)
        if shot_url:
            return shot_url, "image", f"Preview ao vivo de {homepage_url}"

    return None, "image", ""
