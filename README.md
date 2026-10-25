# GitPost &bull; Automação do GitHub para o LinkedIn

O **GitPost** é uma aplicação completa para desenvolvedores que monitora repositórios no GitHub, identifica novidades ou atualizações de código relevantes e utiliza Inteligência Artificial (Google Gemini) para redigir publicações técnicas para o LinkedIn.

O envio só ocorre após aprovação explícita do desenvolvedor, que recebe um e-mail com visualização prévia e botões de ação com um clique (*Magic Link*).

---

## Funcionalidades

- **Gerenciamento de Repositórios:**
  - Sincronização direta com a API do GitHub (públicos e autenticados).
  - Interruptor (*toggle*) individual para ativar ou pausar o monitoramento de cada projeto.
  - Reconhecimento automático de commits, branches e tags.

- **Monitoramento Contínuo:**
  - **Agendador em segundo plano:** verifica novos commits periodicamente sem necessidade de portas abertas ou túneis.
  - **Recepção por Webhook:** rota pronta (`/api/webhooks/github`) para atualizações em tempo real via eventos *push*.
  - Histórico inteligente de commits processados para evitar postagens duplicadas.

- **Geração de Conteúdo com IA:**
  - Integração com o Google Gemini (`gemini-2.5-flash-lite`, `gemini-3.5-flash`, etc.).
  - Opções de tom de voz (*Profissional, Técnico, Descontraído, Storytelling*).
  - Campo para instruções personalizadas e modelo de fallback caso não configure chave de IA.

- **Aprovação por E-mail (Magic Link):**
  - Notificação por e-mail com layout profissional e responsivo.
  - Suporte a **SMTP tradicional** (Gmail, Outlook, etc.) e à **API do Resend**.
  - Botões de ação direta no e-mail:
    - **Aprovar & Publicar no LinkedIn** (azul oficial)
    - **Editar no Painel** (abre o rascunho no painel web)
    - **Descartar Publicação** (vermelho de exclusão)

- **Publicação Oficial no LinkedIn com Mídia Nativa:**
  - Suporte completo a **upload nativo de imagens e vídeos** via REST Images & Videos API (`urn:li:image` / `urn:li:video`).
  - **3 formas integradas de obter mídia:**
    1. Reconhecimento automático de imagens e banners presentes no `README.md` do repositório.
    2. Geração automática de screenshot da homepage/site ao vivo do projeto (ex: Vercel, Netlify, Pages).
    3. Upload manual de arquivo direto do computador ou inclusão de link pelo painel web.
  - Comunicação com a API oficial do LinkedIn (*REST Posts API* e *UGC Posts*).
  - Suporte a OpenID Connect e resolução de autor pessoal (`urn:li:person`).
  - **Modo Simulação integrado:** ativado por padrão para testar o fluxo de ponta a ponta sem postar no perfil real.

- **Interface Dev Console:**
  - Suporte completo a **Tema Claro** e **Tema Escuro Profundo (Deep Dark)** com persistência local.
  - Paleta unificada no azul oficial do LinkedIn (`#0A66C2`), sem tons verdes.
  - Painel com abas segmentadas, busca rápida, filtros por status, prévia de mídia e tooltips informativos.

---

## Como Executar

### Pré-requisitos
- Python 3.10 ou superior instalado no computador.
- Git instalado.

### 1. Clonar o repositório
```bash
git clone https://github.com/SEU_USUARIO/gitpost.git
cd gitpost
```

### 2. Iniciar a aplicação

**No Windows (recomendado):**
Basta dar dois cliques no arquivo:
```cmd
run.bat
```

**Ou manualmente via terminal:**
```bash
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python main.py
```

O painel estará disponível no navegador em:
**http://localhost:8000**

---

## Configurações no Painel Web

Na aba **Ajustes** da interface você pode definir:

1. **GitHub:** Usuário do GitHub e/ou Personal Access Token para acesso a repositórios privados.
2. **E-mail:** E-mail de destino para aprovações via Gmail/SMTP ou API Key do Resend.
3. **LinkedIn:** Token de acesso oficial gerado no portal de desenvolvedores do LinkedIn ou deixe o *Modo Simulação* ligado para testes.
4. **Gemini IA:** Chave de API gratuita obtida no Google AI Studio e instruções personalizadas de escrita.

### Como configurar o E-mail de Aprovação

O GitPost oferece duas opções simples para envio de e-mails:

#### Opção A: Rodando no seu computador (Gmail / SMTP gratuito - Sem cadastro em outro serviço)
Se você estiver executando o GitPost localmente (`localhost`), pode usar qualquer conta do Gmail:
1. Acesse as [Configurações de Segurança do Google](https://myaccount.google.com/security).
2. Ative a **Verificação em duas etapas** (caso ainda não esteja ativa).
3. Pesquise por **"Senhas de app"** (ou acesse `myaccount.google.com/apppasswords`).
4. Crie uma senha com o nome `GitPost` e copie o código gerado de 16 letras.
5. No painel do GitPost, na aba **Ajustes**:
   - **Servidor SMTP:** `smtp.gmail.com`
   - **Porta:** `465` (com SSL) ou `587` (com TLS)
   - **Usuário SMTP:** seu e-mail do Gmail
   - **Senha de App:** o código de 16 letras gerado
   - **Seu Email (Destinatário):** o e-mail onde deseja receber os alertas
6. Clique em **Salvar Configurações** e teste no botão **Enviar Email de Teste**.

---

#### Opção B: Rodando na Nuvem / Deploy (Render, Railway, Fly.io via Resend)
Em provedores de nuvem gratuitos, conexões SMTP tradicionais (portas 465/587) são bloqueadas para evitar spam. Nesses casos, o envio via API HTTP é a solução:
1. Crie uma conta gratuita em [resend.com](https://resend.com).
2. Vá em **API Keys** e crie uma chave (começa com `re_...`).
3. No painel do GitPost, na aba **Ajustes**, cole a chave no campo **Alternativa: Chave de API do Resend**.
4. Deixe o campo de senha SMTP vazio e clique em **Salvar Configurações**.

> **Nota:** O envio por e-mail é opcional. Você também pode aprovar e publicar posts diretamente pela aba **Fila de Posts** no painel web com apenas 1 clique!

---

## Estrutura do Projeto

```
Linkedin/
├── app/
│   ├── database.py           # Conexão e modelos do banco SQLite/PostgreSQL
│   ├── routes/               # Endpoints REST e Webhooks
│   │   ├── actions.py        # Links mágicos de aprovação/rejeição por e-mail
│   │   ├── posts.py          # Gerenciamento da fila de publicações
│   │   ├── repos.py          # Sincronização e monitoramento de repositórios
│   │   ├── settings.py       # Leitura e gravação de configurações
│   │   └── webhooks.py       # Receptor de webhooks do GitHub
│   ├── services/             # Lógica de integração externa
│   │   ├── ai_service.py     # Prompting e geração de texto com Google Gemini
│   │   ├── email_service.py  # Envio de notificações via SMTP e Resend
│   │   ├── github_service.py # Consulta de repositórios e commits no GitHub
│   │   ├── linkedin_service.py # Publicação oficial na API do LinkedIn
│   │   └── scheduler.py      # Agendador periódico de checagem
│   ├── static/               # Assets do frontend (CSS, JS e ícones SVG)
│   └── templates/            # Frontend HTML (index.html)
├── main.py                   # Inicialização da aplicação FastAPI
├── requirements.txt          # Dependências Python
├── run.bat                   # Script de inicialização rápida no Windows
├── render.yaml               # Configuração para deploy em nuvem
└── .gitignore                # Arquivos ignorados pelo Git
```

---

## Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais informações.
