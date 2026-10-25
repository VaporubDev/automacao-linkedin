import os
import re
import urllib.parse
from typing import Optional, Tuple, List, Dict, Any
import httpx
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
    Gera uma URL de captura de tela de alta resolução para o site do projeto
    usando serviços públicos de screenshot para websites (como micropink ou thum.io).
    """
    if not website_url or not (website_url.startswith("http://") or website_url.startswith("https://")):
        return None
    
    encoded = urllib.parse.quote(website_url, safe="")
    screenshot_url = f"https://api.microlink.io/?url={encoded}&screenshot=true&meta=false&embed=screenshot.url"
    return screenshot_url

async def resolve_best_repo_media(repo_dict: Dict[str, Any]) -> Tuple[Optional[str], str, str]:
    """
    Tenta determinar a melhor mídia automática para o post do repositório:
    1. Se tiver README com imagens/vídeos de demonstração -> seleciona a mídia do README.
    2. Se tiver site/homepage no GitHub (ex: vercel, netlify, github pages) -> gera screenshot da homepage.
    3. Retorna (media_url, media_type, media_title)
    """
    repo_name = repo_dict.get("repo_name", "")
    default_branch = repo_dict.get("default_branch") or "main"
    homepage_url = (repo_dict.get("homepage_url") or "").strip()

    try:
        readme_media = await extract_media_from_repo_readme(repo_name, default_branch)
        if readme_media:
            return readme_media["url"], readme_media["type"], readme_media.get("title", f"Screenshot de {repo_name}")
    except Exception as e:
        print(f"[Media Helper] Erro ao buscar mídia no README: {e}")

    if homepage_url and homepage_url.startswith("http"):
        shot_url = generate_website_screenshot_url(homepage_url)
        if shot_url:
            return shot_url, "image", f"Preview ao vivo de {homepage_url}"

    return None, "image", ""
