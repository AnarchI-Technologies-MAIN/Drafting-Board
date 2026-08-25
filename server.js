const express = require('express');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { runFullPipeline } = require('./demo');
const { processTelemetryFeedback, loadConfig } = require('./services/analytics/feedback');

const app = express();
const PORT = process.env.PORT || 3080;

app.use(express.json());

const BASE_DIR = __dirname;
const PUBLIC_DIR = path.join(BASE_DIR, 'public');
const POSTS_DIR = path.join(BASE_DIR, 'data', 'posts');
const DIAGRAMS_DIR = path.join(BASE_DIR, 'data', 'diagrams');
const ADS_FILE = path.join(BASE_DIR, 'data', 'ads_config.json');

// Serve static assets (CSS, JS, images) under /blog prefix
app.use('/blog', express.static(PUBLIC_DIR));

// Serve Admin Console routes explicitly at /blog/admin and /admin
app.use('/blog/admin', express.static(path.join(PUBLIC_DIR, 'admin')));
app.get('/blog/admin', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'admin', 'index.html'));
});

// Standalone Article Reader Page at /blog/:slug
app.get('/blog/:slug', (req, res) => {
  const slug = req.params.slug;

  // Handle route fallbacks that are not post slugs.
  if (slug === 'admin') {
    return res.sendFile(path.join(PUBLIC_DIR, 'admin', 'index.html'));
  }

  if (slug === 'categories' || slug === 'catagories') {
    return res.send(renderCategoriesPage());
  }

  const filepath = path.join(POSTS_DIR, `${slug}.md`);

  if (!fs.existsSync(filepath)) {
    // If not a post file, serve blog homepage index.html
    return res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
  }

  const rawContent = fs.readFileSync(filepath, 'utf-8');
  let frontmatter = {};
  let markdownBody = rawContent;

  const fmMatch = rawContent.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (fmMatch) {
    const fmText = fmMatch[1];
    markdownBody = fmMatch[2];
    fmText.split('\n').forEach(line => {
      const idx = line.indexOf(':');
      if (idx !== -1) {
        const key = line.substring(0, idx).trim();
        let val = line.substring(idx + 1).trim();
        if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
        frontmatter[key] = val;
      }
    });
  }

  const title = frontmatter.title || slug;
  let jsonLdRaw = '';
  if (frontmatter.json_ld_schema) {
    try {
      jsonLdRaw = typeof frontmatter.json_ld_schema === 'string' ? frontmatter.json_ld_schema : JSON.stringify(frontmatter.json_ld_schema);
    } catch (e) {
      jsonLdRaw = '';
    }
  }

  const techStackDisplay = Array.isArray(frontmatter.tech_stack)
    ? frontmatter.tech_stack.join(', ')
    : String(frontmatter.tech_stack || '').replace(/[\[\]"]/g, '');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} | Anarchi-Technologies Blog</title>
  <meta name="description" content="${(frontmatter.summary || title).replace(/"/g, '&quot;')} | Deterministic software. Verifiable evidence.">
  <link rel="stylesheet" href="/blog/styles.css">
  ${jsonLdRaw ? `<script type="application/ld+json">${jsonLdRaw}</script>` : ''}
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head>
<body class="public-theme">
  <!-- PUBLIC NAVIGATION HEADER -->
  <nav class="public-nav">
    <div class="nav-brand">
      <a href="https://www.anarchi-tech.com" target="_blank" style="text-decoration:none;">
        <span class="brand-glitch">://ANARCHI-TECH</span>
      </a>
      <span class="brand-sub">THE DEV-STACK CRACK BACK</span>
    </div>
    <div class="nav-links">
      <a href="/blog" class="nav-link active">← Engineering Logs</a>
      <a href="https://www.anarchi-tech.com/wallet-safety-report" class="nav-link highlight-wsrs" target="_blank">🛡️ WSRS Service</a>
      <a href="/blog/admin/" class="nav-link admin-link" target="_blank">⚙️ Operations</a>
    </div>
  </nav>

  <!-- MAIN ARTICLE CONTAINER -->
  <main class="public-container">
    <article class="post-card" style="max-width:960px; margin:0 auto; padding:3rem; border:1px solid var(--border-color); background:var(--bg-card); backdrop-filter:blur(20px); border-radius:20px;">
      
      <header style="margin-bottom:2.5rem; border-bottom:1px solid var(--border-color); padding-bottom:1.75rem;">
        <div style="font-family:var(--font-mono); font-size:0.8rem; color:var(--primary); margin-bottom:0.75rem; letter-spacing:1px;">
          CLUSTER: ${(frontmatter.topic_cluster || 'engineering').toUpperCase()} | STACK: ${techStackDisplay}
        </div>
        <h1 style="font-size:2.4rem; font-weight:800; color:#FFF; line-height:1.3; margin-bottom:1rem; background:linear-gradient(135deg, #FFFFFF 40%, var(--primary) 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
          ${title}
        </h1>
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; color:var(--text-muted);">
          <span>Published by Anarchi-Technologies</span>
          <span style="font-family:var(--font-mono); color:var(--primary);">Deterministic software. Verifiable evidence.</span>
        </div>
      </header>

      <div class="md-body" style="white-space:pre-wrap; font-size:1.08rem; line-height:1.8; color:var(--text-main);">${markdownBody}</div>

      <footer style="margin-top:4rem; padding-top:2rem; border-top:1px solid var(--border-color); text-align:center; display:flex; justify-content:space-between; align-items:center;">
        <a href="/blog" class="btn-read" style="text-decoration:none; display:inline-block;">← Return to All Case Studies</a>
        <a href="https://www.anarchi-tech.com/wallet-safety-report" target="_blank" class="wsrs-btn" style="padding:0.6rem 1.2rem; font-size:0.85rem;">🛡️ Request WSRS Audit Report →</a>
      </footer>

    </article>
  </main>

  <footer class="public-footer">
    <div class="footer-brand">://ANARCHI-TECHNOLOGIES</div>
    <p style="font-weight:600; color:var(--primary); margin:0.3rem 0;">Deterministic software. Verifiable evidence.</p>
    <div class="footer-links" style="margin-top:0.8rem;">
      <a href="https://www.anarchi-tech.com" target="_blank">www.anarchi-tech.com</a> • 
      <a href="https://www.anarchi-tech.com/wallet-safety-report" target="_blank">WSRS Services</a> • 
      <a href="/blog/admin/" target="_blank">Operations Console</a>
    </div>
  </footer>

  <script>
    if (window.mermaid) {
      mermaid.initialize({ startOnLoad: true, theme: 'dark' });
    }
  </script>
</body>
</html>`;

  res.send(html);
});

const normalizeCategoryKey = (value = 'general') => {
  const raw = String(value || 'general').trim();
  const text = raw.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return text || 'general';
};

const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

const loadPublishedPosts = () => {
  if (!fs.existsSync(POSTS_DIR)) return [];

  return fs.readdirSync(POSTS_DIR)
    .filter(file => file.endsWith('.md'))
    .map(file => {
      const filepath = path.join(POSTS_DIR, file);
      const raw = fs.readFileSync(filepath, 'utf-8');
      let frontmatter = {};
      let markdownBody = raw;
      const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);

      if (fmMatch) {
        const fmText = fmMatch[1];
        markdownBody = fmMatch[2];
        fmText.split('\n').forEach(line => {
          const idx = line.indexOf(':');
          if (idx !== -1) {
            const key = line.substring(0, idx).trim();
            let val = line.substring(idx + 1).trim();
            if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
            frontmatter[key] = val;
          }
        });
      }

      return {
        title: frontmatter.title || file.replace(/\.md$/, ''),
        slug: file.replace(/\.md$/, ''),
        category: frontmatter.topic_cluster || frontmatter.category || 'general',
        summary: frontmatter.summary || markdownBody.replace(/[#>*_`\-]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 180),
        markdown: markdownBody
      };
    })
    .sort((a, b) => a.title.localeCompare(b.title));
};

const renderCategoriesPage = (selectedCategory = null) => {
  const posts = loadPublishedPosts();
  const grouped = new Map();
  posts.forEach(post => {
    const key = normalizeCategoryKey(post.category);
    if (!grouped.has(key)) grouped.set(key, { key, label: post.category || 'General', posts: [] });
    grouped.get(key).posts.push(post);
  });

  const categoryList = [...grouped.values()].sort((a, b) => a.label.localeCompare(b.label));
  const selectedPosts = selectedCategory
    ? (grouped.get(normalizeCategoryKey(selectedCategory))?.posts || [])
    : posts.slice(0, 12);

  const categoryMarkup = categoryList.map(cat => `
    <a class="category-pill ${selectedCategory && normalizeCategoryKey(cat.label) === normalizeCategoryKey(selectedCategory) ? 'active' : ''}" href="/blog/categories/${encodeURIComponent(normalizeCategoryKey(cat.label))}">
      ${escapeHtml(cat.label)} <span>${cat.posts.length}</span>
    </a>
  `).join('');

  const listingMarkup = selectedPosts.length === 0
    ? '<p class="empty-state">No posts are tagged in this category yet.</p>'
    : selectedPosts.map(post => `
      <article class="mini-post-card">
        <div class="mini-post-kicker">${escapeHtml(post.category || 'General')}</div>
        <h3><a href="/blog/${encodeURIComponent(post.slug)}">${escapeHtml(post.title)}</a></h3>
        <p>${escapeHtml(post.summary || 'Deterministic systems and engineering notes.')}</p>
        <a class="mini-post-link" href="/blog/${encodeURIComponent(post.slug)}">Read the case study →</a>
      </article>
    `).join('');

  return `<!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Categories | Anarchi-Technologies Blog</title>
    <meta name="description" content="Searchable engineering categories across deterministic systems, developer tooling, security, and architecture case studies.">
    <link rel="stylesheet" href="/blog/styles.css">
  </head>
  <body>
    <header class="navWrap">
      <div class="nav-brand">
        <a href="https://www.anarchi-tech.com" target="_blank" style="text-decoration:none; display:flex; align-items:center; gap:10px;">
          <div class="brand-emblem">▲</div>
          <span class="brand-text">ANARCHI TECHNOLOGIES</span>
        </a>
        <span class="brand-sub">DEV-STACK CRACK BACK</span>
      </div>
      <div class="nav-links">
        <a href="/blog" class="nav-link">Engineering Logs</a>
        <a href="/blog/categories" class="nav-link active">Categories</a>
        <a href="https://www.anarchi-tech.com/wallet-safety-report" class="nav-link" target="_blank">Wallet Report</a>
      </div>
    </header>

    <main class="public-container">
      <section class="category-page-header">
        <p class="eyebrow">INDEXED TOPIC MAP</p>
        <h1>Category clusters for search and editorial optimization</h1>
        <p class="hero-lead">The bot pipeline indexes the corpus by theme and query intent so the blog, search, and topical clusters stay aligned with the content engine.</p>
      </section>

      <section class="category-toolbar">
        <a href="/blog" class="quiet-btn" style="text-decoration:none;">← Back to the feed</a>
        <a href="/blog/categories" class="quiet-btn" style="text-decoration:none;">All topics</a>
      </section>

      <section class="category-list">${categoryMarkup}</section>

      <section class="category-results">
        <div class="category-results-header">
          <h2>${selectedCategory ? `${escapeHtml(selectedCategory)} cluster` : 'All topics'}</h2>
          <span>${selectedPosts.length} posts</span>
        </div>
        <div class="category-grid">${listingMarkup}</div>
      </section>
    </main>
  </body>
  </html>`;
};

// Standalone Public Blog Homepage
app.get('/blog', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

app.get(['/blog/categories', '/blog/catagories'], (req, res) => {
  res.send(renderCategoriesPage());
});

app.get(['/blog/categories/:slug', '/blog/catagories/:slug'], (req, res) => {
  const slug = decodeURIComponent(req.params.slug || '').replace(/-/g, ' ');
  res.send(renderCategoriesPage(slug));
});

// API Routes
const handleStatus = (req, res) => {
  const totalMemMb = Math.round(os.totalmem() / (1024 * 1024));
  const freeMemMb = Math.round(os.freemem() / (1024 * 1024));
  const memoryUsage = process.memoryUsage();

  res.json({
    system: "Anarchi-Technologies Dual-Engine Blog & Revenue Matrix",
    host: `${os.hostname()} (${os.type()} ${os.arch()})`,
    hardware_target: "Intel N150 800MHz, 4GB RAM (Local Fiber Pipe)",
    memory: {
      total_ram_mb: totalMemMb,
      free_ram_mb: freeMemMb,
      process_rss_mb: Math.round(memoryUsage.rss / (1024 * 1024)),
      heap_used_mb: Math.round(memoryUsage.heapUsed / (1024 * 1024))
    },
    uptime_seconds: Math.round(process.uptime()),
    status: "HEALTHY"
  });
};

const handlePosts = (req, res) => {
  if (!fs.existsSync(POSTS_DIR)) {
    return res.json([]);
  }
  const files = fs.readdirSync(POSTS_DIR).filter(f => f.endsWith('.md'));
  const posts = files.map(file => {
    const filepath = path.join(POSTS_DIR, file);
    const rawContent = fs.readFileSync(filepath, 'utf-8');
    
    let frontmatter = {};
    let markdownBody = rawContent;
    
    const fmMatch = rawContent.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
    if (fmMatch) {
      const fmText = fmMatch[1];
      markdownBody = fmMatch[2];
      fmText.split('\n').forEach(line => {
        const idx = line.indexOf(':');
        if (idx !== -1) {
          const key = line.substring(0, idx).trim();
          let val = line.substring(idx + 1).trim();
          if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
          frontmatter[key] = val;
        }
      });
    }

    return {
      filename: file,
      slug: file.replace('.md', ''),
      frontmatter,
      markdown: markdownBody,
      raw: rawContent
    };
  });
  res.json(posts);
};

const handleDiagrams = (req, res) => {
  if (!fs.existsSync(DIAGRAMS_DIR)) {
    return res.json([]);
  }
  const files = fs.readdirSync(DIAGRAMS_DIR).filter(f => f.endsWith('.mmd'));
  const diagrams = files.map(file => {
    const hash = file.replace('.mmd', '');
    const content = fs.readFileSync(path.join(DIAGRAMS_DIR, file), 'utf-8');
    const stats = fs.statSync(path.join(DIAGRAMS_DIR, file));
    return {
      hash,
      filename: file,
      size_bytes: stats.size,
      created_at: stats.birthtime.toISOString(),
      content
    };
  });
  res.json(diagrams);
};

app.get('/api/status', handleStatus);
app.get('/blog/api/status', handleStatus);

app.get('/api/posts', handlePosts);
app.get('/blog/api/posts', handlePosts);

app.get('/api/diagrams', handleDiagrams);
app.get('/blog/api/diagrams', handleDiagrams);

app.get('/api/config', (req, res) => res.json(loadConfig()));
app.get('/blog/api/config', (req, res) => res.json(loadConfig()));

app.post('/api/pipeline/run', (req, res) => {
  try {
    runFullPipeline();
    res.json({ status: "success", message: "Full pipeline execution finished.", config: loadConfig() });
  } catch (err) {
    res.status(500).json({ status: "error", message: err.message });
  }
});

// Fallback Root Route
app.get('/', (req, res) => {
  const host = (req.get('host') || '').toLowerCase();
  if (host.startsWith('dev.') || host.startsWith('dev-')) {
    return res.redirect('/blog/admin/');
  }
  return res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

// Start Server
app.listen(PORT, () => {
  console.log(`\n===============================================================`);
  console.log(`🌐 ANARCHI-TECH DUAL-ENGINE WEB SERVER RUNNING ON PORT ${PORT}`);
  console.log(`   Standalone Blog Page: http://localhost:${PORT}/blog`);
  console.log(`   Direct WSRS Traffic URL: https://www.anarchi-tech.com/wallet-safety-report`);
  console.log(`   Admin Operations Console: http://localhost:${PORT}/blog/admin/`);
  console.log(`===============================================================\n`);
});
