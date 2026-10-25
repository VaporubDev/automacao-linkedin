import httpx
from typing import Optional
from app.database import get_setting

async def generate_linkedin_post(
    repo_name: str,
    repo_url: str,
    repo_description: str,
    commit_message: str,
    commit_author: str,
    homepage_url: str = "",
    has_media: bool = True
) -> str:
    """
    Gera uma sugestão de post para o LinkedIn baseado nas alterações do GitHub.
    Usa a API do Google Gemini se a chave estiver configurada; caso contrário,
    utiliza um modelo estruturado e profissional como fallback.
    """
    gemini_key = get_setting("gemini_api_key")
    ai_tone = get_setting("ai_tone", "Profissional e Engajador")
    custom_instructions = get_setting("ai_custom_instructions", "")

    if gemini_key:
        try:
            return await generate_with_gemini(
                api_key=gemini_key,
                repo_name=repo_name,
                repo_url=repo_url,
                repo_description=repo_description,
                commit_message=commit_message,
                commit_author=commit_author,
                homepage_url=homepage_url,
                has_media=has_media,
                tone=ai_tone,
                custom_instructions=custom_instructions
            )
        except Exception as e:
            print(f"[AI Service] Falha ao chamar Gemini ({e}). Usando template fallback.")

    return generate_fallback_template(
        repo_name=repo_name,
        repo_url=repo_url,
        repo_description=repo_description,
        commit_message=commit_message,
        homepage_url=homepage_url
    )

async def generate_with_gemini(
    api_key: str,
    repo_name: str,
    repo_url: str,
    repo_description: str,
    commit_message: str,
    commit_author: str,
    homepage_url: str,
    has_media: bool,
    tone: str,
    custom_instructions: str
) -> str:
    """Chama a API do Google Gemini para criar o post do LinkedIn."""
    clean_key = api_key.strip()
    
    # Modelos ativos no Google AI Studio
    models = ["gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
    last_error = ""

    demo_info = f"- Site / Demonstração ao vivo: {homepage_url}\n" if homepage_url else ""
    media_guidance = "- Mencione de forma natural a captura visual/demonstração que está em anexo na publicação (ex: 'Confira no print/vídeo anexo a interface em ação...').\n" if has_media else ""

    prompt = f"""
Você é um especialista em LinkedIn e Personal Branding para desenvolvedores de software.
Sua missão é criar uma publicação autêntica, atrativa e profissional para o LinkedIn, compartilhando uma nova atualização em um projeto no GitHub.

Informações da atualização:
- Repositório: {repo_name}
- Link: {repo_url}
- Descrição do Projeto: {repo_description or 'Projeto de desenvolvimento de software'}
{demo_info}- Mensagem do Commit/Atualização: {commit_message}
- Autor: {commit_author}

Diretrizes de estilo:
- Tom desejado: {tone}
- Instruções extras do usuário: {custom_instructions or 'Nenhuma'}
{media_guidance}- Estrutura recomendada:
  1. Gancho inicial curto e cativante (mostre o que foi feito ou o desafio superado).
  2. Parágrafo conciso explicando a melhoria, feature ou refatoração.
  3. Convite para conferir a demonstração e o código no GitHub ({repo_url}).
  4. Hashtags estratégicas e relevantes no final (ex: #GitHub #Desenvolvimento #Tech #OpenSource).
- Seja natural, sem jargões corporativos forçados. Use emojis de forma moderada e profissional.
- Escreva em Português do Brasil.
- Retorne APENAS o texto final do post, sem explicações extras ou aspas ao redor.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                else:
                    last_error = f"{model} status {resp.status_code}: {resp.text}"
            except Exception as ex:
                last_error = str(ex)

    raise Exception(f"Falha na API Gemini: {last_error}")

def generate_fallback_template(
    repo_name: str,
    repo_url: str,
    repo_description: str,
    commit_message: str,
    homepage_url: str = ""
) -> str:
    """Modelo padrão caso a chave de IA não esteja preenchida."""
    clean_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    desc = f" ({repo_description})" if repo_description else ""
    demo_part = f"\n🌐 Demonstração ao vivo: {homepage_url}" if homepage_url else ""

    return f"""🚀 Nova atualização no projeto {clean_name}!

Acabei de subir novidades para o repositório{desc}:
📌 O que foi feito: {commit_message}{demo_part}

Acompanhar a evolução constante do código e manter boas práticas tem sido um ótimo aprendizado prático.

🔗 Confira a demonstração visual no post e o repositório no GitHub:
{repo_url}

Feedbacks, sugestões ou contribuições são sempre muito bem-vindos! 💬

#GitHub #Dev #OpenSource #Programação #Coding #{clean_name.replace('-', '_')}"""

async def generate_new_repo_post(
    repo_name: str,
    repo_url: str,
    repo_description: str,
    language: str = "",
    homepage_url: str = "",
    has_media: bool = True
) -> str:
    """
    Gera uma sugestão de post para o LinkedIn celebrando o LANÇAMENTO/NOVIDADE de um NOVO REPOSITÓRIO.
    Foca no anúncio do projeto, tecnologias utilizadas e convite para a comunidade conferir.
    """
    gemini_key = get_setting("gemini_api_key")
    ai_tone = get_setting("ai_tone", "Profissional e Engajador")
    custom_instructions = get_setting("ai_custom_instructions", "")

    if gemini_key:
        try:
            return await generate_new_repo_with_gemini(
                api_key=gemini_key,
                repo_name=repo_name,
                repo_url=repo_url,
                repo_description=repo_description,
                language=language,
                homepage_url=homepage_url,
                has_media=has_media,
                tone=ai_tone,
                custom_instructions=custom_instructions
            )
        except Exception as e:
            print(f"[AI Service] Falha ao chamar Gemini para novidade ({e}). Usando template fallback.")

    return generate_new_repo_fallback_template(
        repo_name=repo_name,
        repo_url=repo_url,
        repo_description=repo_description,
        language=language,
        homepage_url=homepage_url
    )

async def generate_new_repo_with_gemini(
    api_key: str,
    repo_name: str,
    repo_url: str,
    repo_description: str,
    language: str,
    homepage_url: str,
    has_media: bool,
    tone: str,
    custom_instructions: str
) -> str:
    """Gera post comemorativo de novo projeto usando Gemini AI."""
    clean_key = api_key.strip()
    clean_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    models = ["gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
    last_error = ""

    demo_info = f"- Site / Demonstração ao vivo: {homepage_url}\n" if homepage_url else ""
    media_guidance = "- Chame a atenção do leitor para a prévia visual/vídeo em anexo demonstrando o sistema em execução.\n" if has_media else ""

    prompt = f"""
Você é um especialista em LinkedIn e Personal Branding para desenvolvedores de software.
Sua missão é criar uma publicação autêntica, empolgante e altamente profissional para o LinkedIn anunciando o LANÇAMENTO / NOVIDADE de um NOVO REPOSITÓRIO no GitHub.

Informações da NOVIDADE:
- Nome do Projeto: {clean_name} ({repo_name})
- Link Oficial: {repo_url}
- Descrição / Propósito: {repo_description or 'Novo projeto de desenvolvimento de software'}
{demo_info}- Linguagem Principal / Tecnologias: {language or 'Geral / Multi-tecnologia'}

Diretrizes de estilo:
- Tom desejado: {tone}
- Instruções extras do usuário: {custom_instructions or 'Nenhuma'}
{media_guidance}- Estrutura recomendada:
  1. Gancho inicial impactante anunciando a NOVIDADE (ex: "🚀 Tem projeto novo no ar!", "Apresentando meu mais novo projeto...").
  2. Parágrafo claro e envolvente explicando qual problema o projeto resolve, principais recursos e o que motivou a sua criação.
  3. Destaque das tecnologias utilizadas ({language or 'tecnologias modernas'}) e boas práticas aplicadas.
  4. Chamada calorosa para ação convidando a rede a ver o anexo visual, conhecer o repositório no GitHub ({repo_url}), deixar uma estrela ⭐ e contribuir com feedbacks.
  5. Hashtags estratégicas e relevantes (ex: #GitHub #OpenSource #Dev #Novidade #{clean_name.replace('-', '_')} #Tech).
- Seja natural, comunicativo e autêntico. Use emojis de forma atrativa e equilibrada.
- Escreva em Português do Brasil.
- Retorne APENAS o texto final do post, sem explicações extras ou aspas ao redor.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                else:
                    last_error = f"{model} status {resp.status_code}: {resp.text}"
            except Exception as ex:
                last_error = str(ex)

    raise Exception(f"Falha na API Gemini: {last_error}")

def generate_new_repo_fallback_template(
    repo_name: str,
    repo_url: str,
    repo_description: str,
    language: str = "",
    homepage_url: str = ""
) -> str:
    """Modelo padrão de anúncio de novo repositório."""
    clean_name = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    desc = f"\n\n📌 Sobre o projeto: {repo_description}" if repo_description else ""
    tech = f" desenvolvido em {language}" if language and language != "Outro" else ""
    demo_part = f"\n🌐 Demonstração ao vivo: {homepage_url}" if homepage_url else ""

    return f"""🚀 Tem novidade no ar! Acabei de disponibilizar um novo projeto no meu GitHub: {clean_name}!{tech}{desc}{demo_part}

Construir e disponibilizar novos projetos é uma das melhores maneiras de colocar boas práticas em ação, testar soluções modernas e evoluir constantemente como desenvolvedor.

🔗 Convido todos a conferirem o projeto, explorarem a estrutura no GitHub e deixarem uma ⭐:
{repo_url}

Feedbacks, sugestões de melhorias e conexões são sempre muito bem-vindos! 💬

#GitHub #Dev #OpenSource #Programação #Projetos #Novidade #{clean_name.replace('-', '_')}"""
