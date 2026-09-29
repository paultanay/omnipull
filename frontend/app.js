/**
 * OmniPull - Frontend Application
 * Handles URL fetching, format selection, downloads, SSE progress, and theme.
 */

// -- State --------------------------------------------------------------------
let currentMediaInfo = null;
let selectedFormat = null;
let currentFileId = null;
let progressEventSource = null;
let activeTab = 'video';

// -- Theme --------------------------------------------------------------------
(function initTheme() {
  const saved = localStorage.getItem('omnipull-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  document.getElementById('themeIcon').textContent = saved === 'dark' ? '◐' : '◑';
})();

document.getElementById('themeToggle').addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('omnipull-theme', next);
  document.getElementById('themeIcon').textContent = next === 'dark' ? '◐' : '◑';
});

// -- Utilities ----------------------------------------------------------------
function showError(msg) {
  const el = document.getElementById('errorMsg');
  // Always stringify - handles Error objects, plain objects, and strings
  if (msg && typeof msg === 'object') {
    el.textContent = msg.message || msg.detail || JSON.stringify(msg);
  } else {
    el.textContent = String(msg || 'Something went wrong. Please try again.');
  }
  el.classList.remove('hidden');
}

function hideError() {
  document.getElementById('errorMsg').classList.add('hidden');
}

function showToast(msg, type = 'info', duration = 4000) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), duration);
}

function setFetchLoading(loading) {
  const btn = document.getElementById('fetchBtn');
  const text = document.getElementById('fetchBtnText');
  const spinner = document.getElementById('fetchSpinner');
  btn.disabled = loading;
  text.textContent = loading ? 'Inspecting...' : 'Inspect link';
  spinner.classList.toggle('hidden', !loading);
}

function poll(taskId, intervalMs = 1500, maxAttempts = 120) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const id = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(id);
        reject(new Error('Request timed out. Please try again.'));
        return;
      }
      try {
        const res = await fetch(`/api/task/${taskId}`);
        const data = await res.json();
        if (data.status === 'success') {
          clearInterval(id);
          resolve(data.result);
        } else if (data.status === 'error') {
          clearInterval(id);
          reject(new Error(data.message || 'An error occurred.'));
        }
        // pending / started / progress => keep polling
      } catch (e) {
        clearInterval(id);
        reject(e);
      }
    }, intervalMs);
  });
}

// -- Platform helpers ---------------------------------------------------------
function getPlatformLabel(platform) {
  const map = { youtube: 'YouTube', instagram: 'Instagram', twitter: 'Twitter/X', other: 'Web' };
  return map[platform] || 'Web';
}

// -- Fetch media info ---------------------------------------------------------
async function handleFetch() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) {
    showError('Please paste a URL first.');
    return;
  }
  if (!/^https?:\/\//i.test(url)) {
    showError('Please enter a valid URL starting with http:// or https://');
    return;
  }

  hideError();
  setFetchLoading(true);
  document.getElementById('resultCard').classList.add('hidden');

  // Reset state
  currentMediaInfo = null;
  selectedFormat = null;
  currentFileId = null;
  if (progressEventSource) { progressEventSource.close(); progressEventSource = null; }

  try {
    const res = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Fetch failed.');

    const result = await poll(json.task_id);
    if (!result || !result.data) throw new Error('No media info returned.');

    currentMediaInfo = result.data;
    renderResultCard(currentMediaInfo);
  } catch (e) {
    const msg = (e && e.message) ? e.message : String(e || 'Something went wrong. Please try again.');
    showError(msg);
  } finally {
    setFetchLoading(false);
  }
}

// -- Enter key support --------------------------------------------------------
document.getElementById('urlInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleFetch();
});

// -- Render result card -------------------------------------------------------
function renderResultCard(info) {
  // Thumbnail
  const thumb = document.getElementById('thumbnail');
  if (info.thumbnail) {
    thumb.src = info.thumbnail;
    thumb.onerror = () => { thumb.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><rect width="160" height="90" fill="%23333"/><text x="80" y="50" fill="%23666" text-anchor="middle" font-size="14">No Preview</text></svg>'; };
  }

  // Duration badge
  const durEl = document.getElementById('duration');
  if (info.duration) {
    durEl.textContent = info.duration;
    durEl.classList.remove('hidden');
  } else {
    durEl.classList.add('hidden');
  }

  // Platform overlay
  const platformEl = document.getElementById('platformBadge');
  platformEl.textContent = getPlatformLabel(info.platform);
  platformEl.className = `platform-overlay ${info.platform}`;

  // Title
  document.getElementById('mediaTitle').textContent = info.title;

  // Uploader
  const uploaderEl = document.getElementById('mediaUploader');
  if (info.uploader) {
    uploaderEl.textContent = `by ${info.uploader}`;
    uploaderEl.classList.remove('hidden');
  } else {
    uploaderEl.classList.add('hidden');
  }

  // URL
  const urlEl = document.getElementById('mediaUrl');
  try { urlEl.textContent = new URL(info.original_url).hostname; } catch { urlEl.textContent = info.original_url; }

  // Render formats
  renderFormats(info.formats);

  // Show card
  document.getElementById('resultCard').classList.remove('hidden');
  document.getElementById('progressSection').classList.add('hidden');
  document.getElementById('downloadBtn').disabled = true;
  document.getElementById('downloadBtnText').textContent = 'Select a format above';
  selectedFormat = null;

  // Smooth scroll to result
  setTimeout(() => {
    document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, 100);
}

// -- Render formats -----------------------------------------------------------
function renderFormats(formats) {
  const videoFormats = formats.filter(f => f.type === 'video' || f.type === 'video_only');
  const audioFormats = formats.filter(f => f.type === 'audio');

  renderFormatList('formatListVideo', videoFormats);
  renderFormatList('formatListAudio', audioFormats);

  // Switch to audio tab if no video formats
  if (videoFormats.length === 0 && audioFormats.length > 0) {
    switchTab('audio');
  } else {
    switchTab('video');
  }
}

function renderFormatList(containerId, formats) {
  const container = document.getElementById(containerId);
  if (!formats.length) {
    container.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:20px;font-size:14px;">No formats available in this category.</p>';
    return;
  }

  container.innerHTML = formats.map((fmt, i) => {
    const isBest = i === 0;
    const codecInfo = buildCodecInfo(fmt);
    return `
      <div class="format-card"
           role="radio"
           aria-checked="false"
           tabindex="0"
           onclick="selectFormat(this, '${escapeAttr(JSON.stringify(fmt))}')"
           onkeydown="if(event.key==='Enter'||event.key===' ')selectFormat(this,'${escapeAttr(JSON.stringify(fmt))}')">
        <div class="format-left">
          <div class="format-radio"></div>
          <div class="format-quality">${escapeHtml(fmt.quality_label)}</div>
          <div class="format-ext">${escapeHtml(fmt.ext)}</div>
          ${codecInfo ? `<div class="format-codecs">${escapeHtml(codecInfo)}</div>` : ''}
        </div>
        <div class="format-right">
          ${fmt.filesize_human ? `<div class="format-size">${escapeHtml(fmt.filesize_human)}</div>` : ''}
          ${isBest ? '<div class="best-badge">Best</div>' : ''}
        </div>
      </div>`;
  }).join('');
}

function buildCodecInfo(fmt) {
  const parts = [];
  if (fmt.fps && fmt.fps > 30) parts.push(`${fmt.fps}fps`);
  // All video formats now have audio merged in - no need to warn
  return parts.join(' · ');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  return str.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

// -- Select format ------------------------------------------------------------
function selectFormat(el, fmtJson) {
  // Deselect all in both lists
  document.querySelectorAll('.format-card').forEach(c => {
    c.classList.remove('selected');
    c.setAttribute('aria-checked', 'false');
  });

  el.classList.add('selected');
  el.setAttribute('aria-checked', 'true');

  try {
    selectedFormat = JSON.parse(fmtJson.replace(/&quot;/g, '"').replace(/&#39;/g, "'"));
  } catch (e) {
    selectedFormat = null;
  }

  const downloadBtn = document.getElementById('downloadBtn');
  downloadBtn.disabled = false;
  document.getElementById('downloadBtnText').textContent = `Download ${selectedFormat?.quality_label || ''} · ${(selectedFormat?.ext || '').toUpperCase()}`;
}

// -- Tab switching ------------------------------------------------------------
function switchTab(tab) {
  activeTab = tab;
  document.getElementById('tabVideo').classList.toggle('active', tab === 'video');
  document.getElementById('tabAudio').classList.toggle('active', tab === 'audio');
  document.getElementById('formatListVideo').classList.toggle('hidden', tab !== 'video');
  document.getElementById('formatListAudio').classList.toggle('hidden', tab !== 'audio');
}

// -- Download -----------------------------------------------------------------
async function handleDownload() {
  if (!selectedFormat || !currentMediaInfo) return;

  const downloadBtn = document.getElementById('downloadBtn');
  downloadBtn.disabled = true;
  document.getElementById('downloadBtnText').textContent = 'Preparing download...';

  // Close any existing progress stream
  if (progressEventSource) { progressEventSource.close(); progressEventSource = null; }

  // Show progress section
  const progressSection = document.getElementById('progressSection');
  progressSection.classList.remove('hidden');
  resetProgress();

  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: currentMediaInfo.original_url,
        format_id: selectedFormat.format_id,
      }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Download request failed.');

    currentFileId = json.file_id;
    const taskId = json.task_id;

    // Start SSE progress stream
    startProgressStream(currentFileId);

    // Poll for task completion
    // Long videos may take well over ten minutes to download and merge.
    // The Celery result is the source of truth for when a file is ready.
    await poll(taskId, 2000, 3600);

    // Trigger browser download
    triggerDownload(currentFileId);
    showToast('Download started! Check your Downloads folder.', 'success');
    document.getElementById('downloadBtnText').textContent = `Download ${selectedFormat?.quality_label || ''} · ${(selectedFormat?.ext || '').toUpperCase()}`;

  } catch (e) {
    showToast(e.message || 'Download failed. Please try again.', 'error');
    document.getElementById('downloadBtnText').textContent = `Download ${selectedFormat?.quality_label || ''} · ${(selectedFormat?.ext || '').toUpperCase()}`;
    progressSection.classList.add('hidden');
  } finally {
    downloadBtn.disabled = false;
    if (progressEventSource) { progressEventSource.close(); progressEventSource = null; }
  }
}

function triggerDownload(fileId) {
  const a = document.createElement('a');
  a.href = `/api/file/${fileId}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// -- SSE Progress -------------------------------------------------------------
function startProgressStream(fileId) {
  progressEventSource = new EventSource(`/api/progress/${fileId}`);

  progressEventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateProgress(data);
      if (data.status === 'complete' || data.status === 'error') {
        progressEventSource.close();
        progressEventSource = null;
      }
    } catch (e) { /* ignore parse errors */ }
  };

  progressEventSource.onerror = () => {
    progressEventSource.close();
    progressEventSource = null;
  };
}

function resetProgress() {
  document.getElementById('progressBar').style.width = '0%';
  document.getElementById('progressPercent').textContent = '0%';
  document.getElementById('progressSpeed').textContent = '';
  document.getElementById('progressEta').textContent = '';
  document.getElementById('progressStatus').textContent = 'Connecting...';
}

function updateProgress(data) {
  const percent = data.percent || 0;
  document.getElementById('progressBar').style.width = `${percent}%`;
  document.getElementById('progressPercent').textContent = `${percent}%`;
  document.getElementById('progressSpeed').textContent = data.speed || '';
  document.getElementById('progressEta').textContent = data.eta ? `ETA: ${data.eta}` : '';

  const statusMap = {
    downloading: 'Downloading...',
    processing: 'Processing & merging...',
    complete: 'Complete!',
    error: 'Error occurred',
  };
  document.getElementById('progressStatus').textContent = statusMap[data.status] || data.status || '';
}
