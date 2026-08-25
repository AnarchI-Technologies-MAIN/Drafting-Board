// Initialize Mermaid.js for visual architecture diagrams
if (window.mermaid) {
  mermaid.initialize({ startOnLoad: false, theme: 'dark' });
}

let currentPosts = [];
let currentDiagrams = [];
let currentConfig = {};

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('hostInfo')) {
    loadStatus();
    setInterval(loadStatus, 10000);
  }

  loadPosts();

  if (document.getElementById('diagramsContainer')) {
    loadDiagrams();
  }

  if (document.getElementById('deadTopicsContainer')) {
    loadConfig();
  }
});

async function loadStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const infoEl = document.getElementById('hostInfo');
    const ramEl = document.getElementById('statRam');
    if (infoEl) infoEl.textContent = `${data.hardware_target} | RSS: ${data.memory.process_rss_mb}MB`;
    if (ramEl) ramEl.textContent = `${data.memory.process_rss_mb} MB`;
  } catch (err) {
    console.error('Failed to load status:', err);
  }
}

async function loadPosts() {
  try {
    const res = await fetch('/api/posts');
    currentPosts = await res.json();

    const statPosts = document.getElementById('statPosts');
    if (statPosts) statPosts.textContent = currentPosts.length;

    if (document.getElementById('publicPostsContainer')) {
      renderPublicPosts(currentPosts);
    } else if (document.getElementById('postsContainer')) {
      renderAdminPosts(currentPosts);
    }
  } catch (err) {
    console.error('Failed to load posts:', err);
  }
}

async function loadDiagrams() {
  try {
    const res = await fetch('/api/diagrams');
    currentDiagrams = await res.json();
    const statDiagrams = document.getElementById('statDiagrams');
    if (statDiagrams) statDiagrams.textContent = currentDiagrams.length;
    renderDiagrams(currentDiagrams);
  } catch (err) {
    console.error('Failed to load diagrams:', err);
  }
}

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    currentConfig = await res.json();
    const statDead = document.getElementById('statDead');
    if (statDead) statDead.textContent = (currentConfig.dead_topics || []).length;
    renderMatrix(currentConfig);
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

/* CUSTOMER-FACING PUBLIC BLOG RENDERER */
function renderPublicPosts(posts) {
  const container = document.getElementById('publicPostsContainer');
  if (posts.length === 0) {
    container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color:var(--text-muted);">No published case studies available. Pipeline auto-runs periodically.</div>`;
    return;
  }

  container.innerHTML = posts.map((post, idx) => {
    const fm = post.frontmatter;
    const wsrsRouted = fm.wsrs_routed === 'true' || fm.wsrs_routed === true;
    const hasDiagram = Boolean(fm.linked_diagram_hash);

    return `
      <article class="post-card">
        <div>
          <div class="tag-list">
            <span class="tag">${fm.topic_cluster || 'general'}</span>
            ${wsrsRouted ? `<span class="tag wsrs">🛡️ WSRS Security Lead</span>` : ''}
            ${hasDiagram ? `<span class="tag diagram">📐 SHA-256 Schema</span>` : ''}
          </div>
          <h3 class="post-title">${escapeHtml(fm.title || post.slug)}</h3>
          <p class="post-summary">${escapeHtml(post.markdown.substring(0, 190))}...</p>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem; padding-top:1rem; border-top:1px solid var(--line);">
          <span style="font-size:0.75rem; font-family:var(--mono); color:var(--text-dim);">Schema.org TechArticle</span>
          <a href="/blog/${post.slug}" class="quiet-btn" style="text-decoration:none; font-size:0.72rem; padding:0.4rem 0.9rem;">Read Full Case Study →</a>
        </div>
      </article>
    `;
  }).join('');
}

/* ADMIN CONSOLE POSTS RENDERER */
function renderAdminPosts(posts) {
  const container = document.getElementById('postsContainer');
  if (posts.length === 0) {
    container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem; color:var(--text-muted);">No compiled posts yet. Click "Trigger Pipeline Cycle" above.</div>`;
    return;
  }

  container.innerHTML = posts.map((post, idx) => {
    const fm = post.frontmatter;
    const wsrsRouted = fm.wsrs_routed === 'true' || fm.wsrs_routed === true;
    const hasDiagram = Boolean(fm.linked_diagram_hash);

    return `
      <div class="post-card">
        <div class="post-header">
          <div class="tag-list">
            <span class="tag">${fm.topic_cluster || 'general'}</span>
            ${wsrsRouted ? `<span class="tag wsrs">🛡️ WSRS Routed</span>` : ''}
            ${hasDiagram ? `<span class="tag diagram">📐 SHA-256 Diagram</span>` : ''}
          </div>
          <h2 class="post-title">${escapeHtml(fm.title || post.slug)}</h2>
          <p class="post-summary">${escapeHtml(post.markdown.substring(0, 180))}...</p>
        </div>
        <div class="post-footer">
          <span style="color:var(--text-dim);">Slug: ${post.slug}</span>
          <button class="btn-secondary" onclick="viewPostModal(${idx})">View Raw Markdown</button>
        </div>
      </div>
    `;
  }).join('');
}

function renderDiagrams(diagrams) {
  const container = document.getElementById('diagramsContainer');
  if (!container) return;

  if (diagrams.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:3rem; color:var(--text-muted);">No extracted diagrams in object store.</div>`;
    return;
  }

  container.innerHTML = diagrams.map((diag, idx) => `
    <div class="diagram-card" style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:16px; padding:1.5rem; margin-bottom:1.5rem;">
      <div style="display:flex; justify-content:space-between; margin-bottom:1rem; font-family:var(--font-mono); font-size:0.85rem;">
        <span style="color:var(--primary);">🔑 SHA-256 Hash: ${diag.hash}</span>
        <span style="color:var(--text-muted);">${diag.filename} (${diag.size_bytes} bytes)</span>
      </div>
      <pre style="background:#030509; padding:1rem; border-radius:8px; overflow-x:auto; font-family:var(--font-mono); font-size:0.85rem; color:#A0B0C0; border:1px solid var(--border-color);"><code>${escapeHtml(diag.content)}</code></pre>
      <div id="mermaid-render-${idx}" style="margin-top:1rem; background:#0A0E17; padding:1rem; border-radius:10px;"></div>
    </div>
  `).join('');

  setTimeout(() => {
    diagrams.forEach((diag, idx) => {
      const target = document.getElementById(`mermaid-render-${idx}`);
      if (target && window.mermaid) {
        try {
          mermaid.render(`mermaid-svg-${idx}`, diag.content).then(res => {
            target.innerHTML = res.svg;
          });
        } catch (e) {
          target.innerHTML = `<span style="color:var(--text-muted);">Diagram render preview</span>`;
        }
      }
    });
  }, 300);
}

function renderMatrix(config) {
  const deadContainer = document.getElementById('deadTopicsContainer');
  if (deadContainer) {
    const dead = config.dead_topics || [];
    deadContainer.innerHTML = dead.length === 0 
      ? `<span style="color:var(--text-muted); font-size:0.9rem;">No topics blacklisted yet.</span>`
      : dead.map(t => `<span class="dead-topic-pill" style="display:inline-block; background:rgba(255,51,102,0.15); border:1px solid rgba(255,51,102,0.3); color:var(--danger); padding:0.3rem 0.8rem; border-radius:20px; font-size:0.8rem; font-family:var(--font-mono); margin-right:0.5rem; margin-bottom:0.5rem;">✖ ${t}</span>`).join('');
  }

  const ampContainer = document.getElementById('amplifiedContainer');
  if (ampContainer) {
    const amp = config.amplified_topics || {};
    const ampKeys = Object.keys(amp);
    ampContainer.innerHTML = ampKeys.length === 0
      ? `<span style="color:var(--text-muted); font-size:0.9rem;">No topics amplified yet.</span>`
      : ampKeys.map(k => `
        <div style="padding:0.6rem; background:rgba(0,255,136,0.08); border:1px solid rgba(0,255,136,0.2); border-radius:8px; margin-bottom:0.5rem; display:flex; justify-content:space-between; font-size:0.85rem;">
          <span style="color:#FFF;">🚀 <strong>${k}</strong></span>
          <span style="color:var(--success); font-family:var(--font-mono);">Priority Tier ${amp[k].priority_tier} (${amp[k].boost_factor}x Boost)</span>
        </div>
      `).join('');
  }

  const modContainer = document.getElementById('modifiersContainer');
  if (modContainer) {
    const mods = config.layout_modifiers || {};
    const modKeys = Object.keys(mods);
    modContainer.innerHTML = modKeys.length === 0
      ? `<span style="color:var(--text-muted); font-size:0.9rem;">No active layout overrides.</span>`
      : modKeys.map(k => `
        <div style="padding:0.6rem; background:rgba(255,184,0,0.08); border:1px solid rgba(255,184,0,0.2); border-radius:8px; margin-bottom:0.5rem; display:flex; justify-content:space-between; font-size:0.85rem;">
          <span style="color:#FFF;">🔄 <strong>${k}</strong></span>
          <span style="color:var(--warning); font-family:var(--font-mono);">CTA Rotate: ${mods[k].cta_layout_rotation} | Affiliate Swap: ${mods[k].affiliate_mix_swap}</span>
        </div>
      `).join('');
  }
}

async function triggerPipelineRun() {
  const btn = document.querySelector('.btn-primary');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Running Cycle...</span>`;
  }

  try {
    const res = await fetch('/api/pipeline/run', { method: 'POST' });
    const data = await res.json();
    alert('Pipeline execution finished: ' + data.message);
    loadPosts();
    if (document.getElementById('diagramsContainer')) loadDiagrams();
    if (document.getElementById('deadTopicsContainer')) loadConfig();
  } catch (err) {
    alert('Failed to trigger pipeline: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🚀 Trigger Pipeline Cycle</span>`;
    }
  }
}

function viewPostModal(idx) {
  const post = currentPosts[idx];
  if (!post) return;

  const modal = document.getElementById('mdModal');
  const body = document.getElementById('modalBody');

  body.innerHTML = `
    <h2 style="margin-bottom:1rem; color:var(--primary); font-size:1.6rem;">${escapeHtml(post.frontmatter.title || post.slug)}</h2>
    <div style="font-family:var(--font-sans); line-height:1.7; color:var(--text-main); white-space:pre-wrap;">${escapeHtml(post.markdown)}</div>
  `;
  modal.classList.add('active');
}

function closeModal() {
  document.getElementById('mdModal').classList.remove('active');
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  if (event && event.target) {
    event.target.classList.add('active');
  }
  const target = document.getElementById(`tab-${tabName}`);
  if (target) target.classList.add('active');
}

function escapeHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
