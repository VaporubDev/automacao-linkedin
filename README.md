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

- **Publicação Oficial no LinkedIn:**
  - Comunicação com a API oficial do LinkedIn (*REST Posts API* e *UGC Posts*).
  - Suporte a OpenID Connect e resolução de autor pessoal (`urn:li:person`).
  - **Modo Simulação integrado:** ativado por padrão para testar o fluxo de ponta a ponta sem postar no perfil real.

- **Interface Dev Console:**
  - Suporte completo a **Tema Claro** e **Tema Escuro Profundo (Deep Dark)** com persistência local.
  - Paleta unificada no azul oficial do LinkedIn (`#0A66C2`), sem tons verdes.
  - Painel com abas segmentadas, busca rápida, filtros por status e tooltips informativos.

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
2. **E-mail:** E-mail de destino para aprovações. Configure SMTP tradicional (ex: Gmail porta 587 com Senha de App) ou API Key do Resend.
3. **LinkedIn:** Token de acesso oficial gerado no portal de desenvolvedores do LinkedIn ou deixe o *Modo Simulação* ligado para testes.
4. **Gemini IA:** Chave de API gratuita obtida no Google AI Studio e instruções personalizadas de escrita.

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
