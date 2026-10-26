// GitPost LinkedIn Frontend Engine - Enhanced Pipeline UX

let allRepos = [];
let allPosts = [];
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTabs();
  loadRepositories();
  loadPosts();
  loadSettings();
  setupEventListeners();
});

function initTheme() {
  const savedTheme = localStorage.getItem('gitpost-theme') || 'dark';
  applyTheme(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
  localStorage.setItem('gitpost-theme', newTheme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  const text = document.getElementById('theme-text');
  
  if (theme === 'light') {
    if (icon) {
      icon.className = 'ui-icon icon-moon sm';
    }
    if (text) {
      text.textContent = 'Escuro';
    }
  } else {
    if (icon) {
      icon.className = 'ui-icon icon-sun sm';
    }
    if (text) {
      text.textContent = 'Claro';
    }
  }
}

function initTabs() {
  const tabButtons = document.querySelectorAll('.nav-segment-btn, .tab-btn');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add('active');

      if (targetId === 'tab-repos') loadRepositories();
      if (targetId === 'tab-posts') loadPosts();
    });
  });

  if (window.location.hash.startsWith('#post-')) {
    const postsTabBtn = document.querySelector('[data-tab="tab-posts"]');
    if (postsTabBtn) postsTabBtn.click();
  }
}

async function loadRepositories() {
  const grid = document.getElementById('repos-grid');
  grid.innerHTML = `
    <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-muted);">
      <div class="pulse-dot" style="margin: 0 auto 14px;"></div>
      <span>Carregando repositórios do GitHub...</span>
    </div>
  `;

  try {
    const res = await fetch('/api/repos');
    const data = await res.json();
    allRepos = data.repositories || [];

    document.getElementById('total-repos-counter').textContent = data.total;
    document.getElementById('monitored-repos-counter').textContent = data.monitored_count;
    document.getElementById('tab-repos-badge').textContent = data.monitored_count;

    renderRepositories(allRepos);
  } catch (err) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="empty-icon-wrap">
          <span class="ui-icon icon-alert lg" style="color: #f87171;"></span>
        </div>
        <h3>Erro ao carregar repositórios</h3>
        <p>Verifique seu usuário ou token do GitHub na aba de configurações.</p>
      </div>
    `;
  }
}

function renderRepositories(repos) {
  const grid = document.getElementById('repos-grid');
  const searchVal = (document.getElementById('repo-search').value || '').toLowerCase().trim();

  const filtered = repos.filter(r => 
    r.repo_name.toLowerCase().includes(searchVal) || 
    (r.description && r.description.toLowerCase().includes(searchVal)) ||
    (r.language && r.language.toLowerCase().includes(searchVal))
  );

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="empty-icon-wrap">
          <span class="ui-icon icon-folder lg" style="color: #38bdf8;"></span>
        </div>
        <h3>Nenhum repositório encontrado</h3>
        <p>Clique em <strong>Sincronizar com GitHub</strong> acima para buscar seus projetos.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(r => `
    <div class="repo-card ${r.is_monitored ? 'monitored' : ''}" id="repo-card-${r.id}">
      <div>
        <div class="repo-top">
          <div class="repo-title">
            <span class="ui-icon ${r.is_private ? 'icon-lock' : 'icon-globe'} sm" style="color: ${r.is_private ? '#e63946' : 'var(--accent-primary)'};"></span>
            <a href="${r.html_url}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.repo_name)}</a>
          </div>
          <span class="tag-badge ${r.is_private ? 'private' : 'public'}">
            <span class="ui-icon ${r.is_private ? 'icon-lock' : 'icon-globe'} sm"></span>
            ${r.is_private ? 'Privado' : 'Público'}
          </span>
        </div>
        <p class="repo-desc">${escapeHtml(r.description) || 'Sem descrição cadastrada no GitHub.'}</p>
        <div class="repo-meta">
          <span><span class="ui-icon icon-star sm" style="color: #e76f51;"></span> ${r.stars || 0}</span>
          <span><span class="ui-icon icon-code sm" style="color: var(--accent-primary);"></span> ${escapeHtml(r.language) || 'Geral'}</span>
          <span><span class="ui-icon icon-branch sm" style="color: var(--color-slate);"></span> ${escapeHtml(r.default_branch) || 'main'}</span>
        </div>
      </div>
      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-color);">
        <button class="btn btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="announceRepo(${r.id})" title="Gera um post comemorando o lançamento deste projeto no LinkedIn">
          <span class="ui-icon icon-sparkles sm" style="color: var(--accent-primary);"></span> Gerar Novidade
        </button>
        <div class="toggle-wrapper">
          <span class="toggle-label ${r.is_monitored ? 'active' : 'inactive'}">
            <span class="pulse-dot" style="${r.is_monitored ? '' : 'background: var(--color-slate); box-shadow: none; animation: none;'}"></span>
            ${r.is_monitored ? 'Monitorando' : 'Inativo'}
          </span>
          <label class="switch">
            <input type="checkbox" ${r.is_monitored ? 'checked' : ''} onchange="toggleRepo(${r.id})">
            <span class="slider"></span>
          </label>
        </div>
      </div>
    </div>
  `).join('');
}

async function toggleRepo(repoId) {
  try {
    const res = await fetch(`/api/repos/${repoId}/toggle`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      loadRepositories();
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao alterar monitoramento', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição ao servidor', 'error');
  }
}

async function announceRepo(repoId) {
  try {
    showToast('Gerando redação de lançamento com IA...', 'info');
    const res = await fetch(`/api/repos/${repoId}/announce`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      loadPosts();
      document.querySelector('[data-tab="tab-posts"]').click();
    } else {
      showToast(data.detail || 'Não foi possível gerar novidade', 'error');
    }
  } catch (e) {
    showToast('Erro ao contatar o servidor', 'error');
  }
}

async function resetRepositories() {
  if (!confirm('Deseja realmente limpar os repositórios para refazer o reconhecimento do zero?')) return;
  try {
    const res = await fetch('/api/repos/reset', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'info');
      loadRepositories();
    } else {
      showToast(data.detail || 'Erro ao reiniciar', 'error');
    }
  } catch (e) {
    showToast('Erro na requisição ao servidor', 'error');
  }
}

async function syncRepositories() {
  const btn = document.getElementById('btn-sync-repos');
  const originalHtml = btn.innerHTML;
  btn.innerHTML = '<span class="ui-icon icon-sync sm" style="animation: spin 1s infinite linear;"></span> Sincronizando...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/repos/sync', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      loadRepositories();
    } else {
      showToast(data.detail || 'Falha ao sincronizar com GitHub', 'error');
    }
  } catch (err) {
    showToast('Erro ao contatar a API do GitHub', 'error');
  } finally {
    btn.innerHTML = originalHtml;
    btn.disabled = false;
  }
}

async function loadPosts() {
  const list = document.getElementById('posts-list');
  try {
    const res = await fetch('/api/posts');
    const data = await res.json();
    allPosts = data.posts || [];

    const pendingCount = data.counts.pending || 0;
    document.getElementById('tab-posts-badge').textContent = pendingCount;
    document.getElementById('count-pending').textContent = pendingCount;
    document.getElementById('count-published').textContent = data.counts.published || 0;
    document.getElementById('count-rejected').textContent = data.counts.rejected || 0;

    renderPosts(allPosts);
  } catch (e) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon-wrap">
          <span class="ui-icon icon-alert lg" style="color: #f87171;"></span>
        </div>
        <h3>Erro ao carregar fila de publicações</h3>
      </div>
    `;
  }
}

function filterPosts(status) {
  currentFilter = status;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  const activeBtn = document.getElementById(`filter-${status}`);
  if (activeBtn) activeBtn.classList.add('active');
  renderPosts(allPosts);
}

function renderPosts(posts) {
  const list = document.getElementById('posts-list');
  const filtered = currentFilter === 'all' ? posts : posts.filter(p => p.status === currentFilter);

  if (filtered.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon-wrap">
          <span class="ui-icon icon-inbox lg" style="color: #38bdf8;"></span>
        </div>
        <h3>Nenhum post nesta visualização</h3>
        <p>Quando você subir novidades nos repositórios monitorados, elas aparecerão preparadas aqui!</p>
      </div>
    `;
    return;
  }

  list.innerHTML = filtered.map(p => {
    const statusMeta = {
      pending: { label: 'Aguardando Aprovação', icon: 'icon-clock', color: '#38bdf8' },
      published: { label: 'Publicado no LinkedIn', icon: 'icon-check', color: '#0a66c2' },
      rejected: { label: 'Rejeitado / Descartado', icon: 'icon-close', color: '#e63946' },
      failed: { label: 'Falha ao Publicar', icon: 'icon-alert', color: '#e76f51' }
    };

    const currentMeta = statusMeta[p.status] || { label: p.status, icon: 'icon-clock', color: 'var(--color-slate)' };
    const isPending = p.status === 'pending';
    const cleanDate = p.created_at ? new Date(p.created_at).toLocaleString('pt-BR') : '';

    return `
      <div class="post-card ${p.status}" id="post-${p.id}">
        <div class="post-header">
          <div>
            <div class="post-repo">
              <span class="ui-icon icon-github sm" style="color: var(--accent-primary);"></span> 
              ${escapeHtml(p.repo_name)}
            </div>
            <span style="font-size: 12px; color: var(--text-sub); display: inline-flex; align-items: center; gap: 4px; margin-top: 2px;">
              <span class="ui-icon icon-clock sm" style="color: var(--text-sub);"></span> ${cleanDate}
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="post-status-pill ${p.status}">
              <span class="ui-icon ${currentMeta.icon} sm" style="color: ${currentMeta.color};"></span>
              ${currentMeta.label}
            </span>
            <button class="btn-trash" onclick="deletePost(${p.id})" title="Excluir este post">
              <span class="ui-icon icon-trash sm"></span>
            </button>
          </div>
        </div>

        <div class="post-commit-info">
          <span><span class="ui-icon icon-code sm" style="color: var(--accent-primary);"></span> <strong>Atualização:</strong> ${escapeHtml(p.commit_message)}</span>
          <span>&bull;</span>
          <a href="${p.commit_url}" target="_blank" style="color: var(--accent-primary); text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
            <span class="ui-icon icon-github sm"></span> Link GitHub
          </a>
          <span>&bull;</span>
          <span>Autor: <strong>${escapeHtml(p.commit_author)}</strong></span>
        </div>

        ${p.status === 'failed' && p.error_message ? `
          <div style="background: rgba(230, 57, 70, 0.12); border: 1px solid rgba(230, 57, 70, 0.35); border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 14px; color: #ff5260; font-size: 13px; line-height: 1.5; display: flex; align-items: center; gap: 10px;">
            <span class="ui-icon icon-alert sm" style="color: #e63946;"></span>
            <div><strong>Motivo da falha:</strong> ${escapeHtml(p.error_message)}</div>
          </div>
        ` : ''}

        <label style="display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-main); margin-bottom: 6px;">
          <span class="ui-icon icon-linkedin sm" style="color: var(--accent-primary);"></span> Texto do Post para o LinkedIn:
        </label>
        <textarea class="post-textarea" id="text-post-${p.id}" ${(!isPending && p.status !== 'failed') ? 'readonly' : ''}>${escapeHtml(p.post_content)}</textarea>

        <!-- BLOCO DE MÍDIA DO PROJETO (IMAGEM / VÍDEO / SCREENSHOT) -->
        <div class="post-media-container" id="media-container-${p.id}">
          <div class="post-media-header">
            <span style="display: inline-flex; align-items: center; gap: 6px;">
              <span class="ui-icon icon-sparkles sm" style="color: var(--accent-primary);"></span>
              Mídia do Projeto (Anexo Nativo no LinkedIn):
            </span>
            ${p.media_url ? `
              <span class="post-media-badge" style="position: static;">
                ${p.media_type === 'video' ? '🎬 Vídeo Detectado' : '🖼️ Imagem / Screenshot'}
              </span>
            ` : `
              <span style="font-size: 11px; color: var(--text-sub);">Nenhuma mídia anexada</span>
            `}
          </div>

          ${p.media_url ? `
            <div class="post-media-preview-box">
              <span class="post-media-badge">
                ${p.media_type === 'video' ? '🎬 Vídeo' : '🖼️ Imagem'}
              </span>
              ${p.media_type === 'video' ? `
                <video src="${escapeHtml(p.media_url)}" controls style="width: 100%; max-height: 240px;"></video>
              ` : `
                <img src="${escapeHtml(p.media_url)}" alt="${escapeHtml(p.media_title || 'Preview do projeto')}" loading="lazy">
              `}
            </div>
          ` : ''}

          ${(isPending || p.status === 'failed') ? `
            <div class="post-media-controls">
              <input type="text" class="post-media-input-url" id="media-url-${p.id}" value="${escapeHtml(p.media_url || '')}" placeholder="Cole URL de imagem/vídeo ou deixe em branco">
              <select id="media-type-${p.id}" style="background: var(--bg-input); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 8px 10px; font-size: 12px; color: var(--text-main);">
                <option value="image" ${p.media_type !== 'video' ? 'selected' : ''}>Imagem</option>
                <option value="video" ${p.media_type === 'video' ? 'selected' : ''}>Vídeo</option>
              </select>
              <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 11px;" onclick="promptWebsiteScreenshot(${p.id})" title="Capturar foto/screenshot do site">
                <span class="ui-icon icon-globe sm"></span> Foto do Site
              </button>
              <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 11px;" onclick="promptWebsiteVideoRecording(${p.id})" title="Gravar vídeo em MP4 do site funcionando com rolagem e animações">
                <span class="ui-icon icon-video sm"></span> Vídeo do Site
              </button>
              <label class="btn btn-secondary" style="font-size: 12px; padding: 7px 11px; cursor: pointer;" title="Fazer upload de imagem ou vídeo do seu computador">
                <span class="ui-icon icon-save sm"></span> Upload
                <input type="file" accept="image/*,video/*" style="display: none;" onchange="uploadPostMediaFile(${p.id}, this)">
              </label>
              ${p.media_url ? `
                <button class="btn btn-secondary" style="font-size: 12px; padding: 7px 10px; color: #ff5260;" onclick="removePostMedia(${p.id})" title="Remover mídia deste post">
                  <span class="ui-icon icon-trash sm"></span>
                </button>
              ` : ''}
            </div>
          ` : ''}
        </div>

        <div class="post-actions">
          ${isPending ? `
            <button class="btn btn-secondary" onclick="savePostText(${p.id})">
              <span class="ui-icon icon-save sm"></span> Salvar Edição
            </button>
            <button class="btn btn-danger" onclick="rejectPostAction(${p.id})">
              <span class="ui-icon icon-close sm"></span> Não Postar
            </button>
            <button class="btn btn-success" onclick="approvePostAction(${p.id})">
              <span class="ui-icon icon-linkedin sm"></span> Aprovar & Postar no LinkedIn
            </button>
          ` : p.status === 'failed' ? `
            <button class="btn btn-secondary" onclick="savePostText(${p.id})">
              <span class="ui-icon icon-save sm"></span> Salvar Edição
            </button>
            <button class="btn btn-danger" onclick="deletePost(${p.id})">
              <span class="ui-icon icon-trash sm"></span> Excluir
            </button>
            <button class="btn btn-warning" onclick="approvePostAction(${p.id})">
              <span class="ui-icon icon-sync sm"></span> Tentar Novamente
            </button>
          ` : `
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <span style="font-size: 13px; color: var(--text-sub); display: inline-flex; align-items: center; gap: 6px;">
                <span class="ui-icon icon-check sm" style="color: var(--accent-primary);"></span>
                ${p.status === 'published' ? `Post sincronizado no LinkedIn (ID: ${escapeHtml(p.linkedin_post_id) || 'OK'})` : 'Registro finalizado'}
              </span>
              <button class="btn btn-secondary" style="font-size: 11px; padding: 5px 12px;" onclick="deletePost(${p.id})">
                <span class="ui-icon icon-trash sm"></span> Excluir Registro
              </button>
            </div>
          `}
        </div>
      </div>
    `;
  }).join('');
}

async function deletePost(postId) {
  if (!confirm('Deseja realmente excluir este post permanentemente?')) return;
  try {
    const res = await fetch(`/api/posts/${postId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Post excluído com sucesso!', 'info');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao excluir post', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação com o servidor', 'error');
  }
}

async function clearAnsweredPosts() {
  if (!confirm('Deseja limpar todos os posts já respondidos (publicados, rejeitados ou finalizados)?')) return;
  try {
    const res = await fetch('/api/posts/clear-answered', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Fila limpa com sucesso!', 'success');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao limpar', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação com o servidor', 'error');
  }
}

async function approvePostAction(postId) {
  if (!confirm('Deseja realmente aprovar e publicar este post no LinkedIn?')) return;
  try {
    // Primeiro salva se houve alterações manuais no texto
    await savePostText(postId, false);

    const res = await fetch(`/api/posts/${postId}/approve`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Publicado com sucesso no LinkedIn!', 'success');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao publicar no LinkedIn', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação com o servidor', 'error');
  }
}

async function rejectPostAction(postId) {
  try {
    const res = await fetch(`/api/posts/${postId}/reject`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Post descartado da fila', 'info');
    loadPosts();
  } catch (e) {
    showToast('Erro ao rejeitar', 'error');
  }
}

async function savePostText(postId, showSuccessToast = true) {
  const content = document.getElementById(`text-post-${postId}`).value;
  const urlInput = document.getElementById(`media-url-${postId}`);
  const typeSelect = document.getElementById(`media-type-${postId}`);
  
  const mediaUrl = urlInput ? urlInput.value.trim() : null;
  const mediaType = typeSelect ? typeSelect.value : 'image';

  try {
    const res = await fetch(`/api/posts/${postId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        post_content: content,
        media_url: mediaUrl,
        media_type: mediaType
      })
    });
    if (res.ok) {
      if (showSuccessToast) showToast('Conteúdo e mídia salvos com sucesso!', 'success');
      loadPosts();
    }
  } catch (e) {
    if (showSuccessToast) showToast('Erro ao salvar post', 'error');
  }
}

async function promptWebsiteScreenshot(postId) {
  const defaultUrl = 'https://meu-projeto.vercel.app';
  const url = prompt('Digite a URL do site/demonstração do projeto para capturar o screenshot:', defaultUrl);
  if (!url || !url.startsWith('http')) {
    if (url) showToast('URL inválida. Comece com http:// ou https://', 'error');
    return;
  }

  showToast('Gerando captura de tela em alta resolução do site...', 'info');
  try {
    const res = await fetch(`/api/posts/${postId}/fetch-screenshot?website_url=${encodeURIComponent(url)}`, {
      method: 'POST'
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Screenshot capturado com sucesso!', 'success');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao capturar screenshot', 'error');
    }
  } catch (e) {
    showToast('Falha na conexão ao capturar site', 'error');
  }
}

async function promptWebsiteVideoRecording(postId) {
  const defaultUrl = 'https://vaporubdev.github.io/Portfolio/';
  const url = prompt('Digite a URL do site/projeto para gravar um vídeo dele funcionando (scroll e animações):', defaultUrl);
  if (!url || !url.startsWith('http')) {
    if (url) showToast('URL inválida. Comece com http:// ou https://', 'error');
    return;
  }

  showToast('Gravando demonstração em vídeo do site funcionando... Isso pode levar de 15 a 30 segundos.', 'info');
  try {
    const res = await fetch(`/api/posts/${postId}/record-site-video?website_url=${encodeURIComponent(url)}`, {
      method: 'POST'
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Vídeo do site gravado e anexado com sucesso!', 'success');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro ao gravar vídeo do site', 'error');
    }
  } catch (e) {
    showToast('Falha na conexão ao gravar vídeo do site', 'error');
  }
}

async function uploadPostMediaFile(postId, inputElem) {
  if (!inputElem.files || !inputElem.files[0]) return;
  const file = inputElem.files[0];
  const formData = new FormData();
  formData.append('file', file);

  showToast(`Enviando ${file.name}...`, 'info');
  try {
    const res = await fetch(`/api/posts/${postId}/upload-media`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Mídia enviada com sucesso!', 'success');
      loadPosts();
    } else {
      showToast(data.detail || 'Erro no envio da mídia', 'error');
    }
  } catch (e) {
    showToast('Falha ao enviar arquivo de mídia', 'error');
  }
}

async function removePostMedia(postId) {
  if (!confirm('Deseja remover a mídia deste post?')) return;
  const urlInput = document.getElementById(`media-url-${postId}`);
  if (urlInput) urlInput.value = '';
  await savePostText(postId, false);
  showToast('Mídia desvinculada do post', 'info');
  loadPosts();
}

async function triggerManualCheck() {
  const btn = document.getElementById('btn-manual-check') || document.getElementById('btn-quick-check');
  const oldText = btn.innerHTML;
  btn.innerHTML = '<span class="ui-icon icon-sync sm" style="animation: spin 1s infinite linear;"></span> Verificando...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/posts/manual-check', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'info');
    loadPosts();
  } catch (e) {
    showToast('Erro ao verificar repositórios', 'error');
  } finally {
    btn.innerHTML = oldText;
    btn.disabled = false;
  }
}

async function simulateNewRepo() {
  const repoName = prompt('Nome do novo repositório a simular:', 'VaporubDev/Novo-Projeto-Incrivel');
  if (!repoName) return;

  showToast('Gerando post de NOVIDADE com IA...', 'info');

  try {
    const res = await fetch('/api/posts/simulate-new-repo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_name: repoName })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Post de NOVIDADE criado na fila! Confira na aba Fila de Publicações.', 'success');
      loadPosts();
      document.querySelector('[data-tab="tab-posts"]').click();
    } else {
      showToast(data.detail || 'Erro ao simular novidade', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação com o servidor', 'error');
  }
}

async function loadSettings() {
  const localSaved = localStorage.getItem('gitpost-device-settings');
  let deviceSettings = {};
  if (localSaved) {
    try {
      deviceSettings = JSON.parse(localSaved);
    } catch (_) {}
  }

  let serverSettings = {};
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    serverSettings = data.settings || {};
  } catch (e) {
    console.error('Erro ao buscar configurações do servidor:', e);
  }

  const merged = { ...serverSettings, ...deviceSettings };

  for (const [key, val] of Object.entries(merged)) {
    const input = document.getElementById(`setting-${key}`);
    if (input && val !== undefined && val !== null) {
      if (input.type === 'checkbox') {
        input.checked = val === '1';
      } else {
        input.value = val;
      }
    }
  }

  const appBaseUrlInput = document.getElementById('setting-app_base_url');
  if (appBaseUrlInput && (!appBaseUrlInput.value || appBaseUrlInput.value.includes('localhost') || appBaseUrlInput.value.includes('127.0.0.1'))) {
    if (window.location.origin && !window.location.origin.includes('localhost') && !window.location.origin.includes('127.0.0.1')) {
      appBaseUrlInput.value = window.location.origin;
    }
  }

  if (Object.keys(deviceSettings).length > 0) {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deviceSettings)
      });
    } catch (_) {}
  }
}

async function saveSettings(e) {
  if (e) e.preventDefault();
  const formData = {};

  document.querySelectorAll('[id^="setting-"]').forEach(el => {
    const key = el.id.replace('setting-', '');
    if (el.type === 'checkbox') {
      formData[key] = el.checked ? '1' : '0';
    } else {
      formData[key] = el.value.trim();
    }
  });

  try {
    localStorage.setItem('gitpost-device-settings', JSON.stringify(formData));
  } catch (_) {}

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Configurações salvas no dispositivo e servidor!', 'success');
    } else {
      showToast(data.detail || 'Erro ao salvar configurações', 'error');
    }
  } catch (err) {
    showToast('Salvo no dispositivo! (Sem conexão com o servidor)', 'info');
  }
}

async function testEmail() {
  const email = document.getElementById('setting-email_recipient').value.trim();
  if (!email) {
    showToast('Preencha o campo "Email de Destino" antes de testar.', 'error');
    return;
  }

  showToast('Enviando email de teste...', 'info');
  try {
    const res = await fetch('/api/settings/test-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to_email: email })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
    } else {
      showToast(data.detail || 'Falha ao enviar email', 'error');
    }
  } catch (e) {
    showToast('Erro de conexão com o servidor', 'error');
  }
}

async function testAI() {
  await saveSettings();
  showToast('Testando IA do Gemini...', 'info');
  try {
    const res = await fetch('/api/settings/test-ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt_sample: 'Otimização com cache e testes automatizados' })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Resultado gerado pela IA:\n\n${data.generated_post}`);
    } else {
      showToast(data.detail || 'Erro ao testar IA', 'error');
    }
  } catch (e) {
    showToast('Falha ao comunicar com IA: ' + e.message, 'error');
  }
}

function setupEventListeners() {
  const searchInput = document.getElementById('repo-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderRepositories(allRepos));
  }

  const settingsForm = document.getElementById('settings-form');
  if (settingsForm) {
    settingsForm.addEventListener('submit', saveSettings);
  }
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  const iconMap = {
    success: 'icon-check',
    error: 'icon-close',
    info: 'icon-bolt'
  };

  const iconClass = iconMap[type] || 'icon-bolt';
  const iconColor = type === 'success' ? '#0a66c2' : type === 'error' ? '#e63946' : '#38bdf8';

  toast.innerHTML = `
    <span class="ui-icon ${iconClass} sm" style="color: ${iconColor};"></span>
    <div>${escapeHtml(msg)}</div>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
