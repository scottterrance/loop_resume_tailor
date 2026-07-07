/* ═══════════════════════════════════════════════════════════════
   Loop Resume Tailor — Frontend Application
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────
const state = {
  jobId: null,
  eventSource: null,
  finalResume: '',
  finalPrompt: '',
  finalScore: null,
  iterations: [],
  analysisData: null,
  pdfFilename: null,
  startTime: null,
};

// ── DOM Helpers ───────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const showPanel = id => {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  $(id).classList.add('active');
};

// ── API Key Persistence (localStorage) ──────────────────────────────────
(function initApiKey() {
  const saved = localStorage.getItem('loop_rt_api_key');
  if (saved) {
    $('api-key').value = saved;
  }
})();

$('api-key').addEventListener('input', () => {
  const val = $('api-key').value.trim();
  if (val) {
    localStorage.setItem('loop_rt_api_key', val);
  } else {
    localStorage.removeItem('loop_rt_api_key');
  }
});

// ── Character Counters ────────────────────────────────────────────────────
$('resume-text').addEventListener('input', () => {
  $('resume-char-count').textContent = $('resume-text').value.length.toLocaleString() + ' characters';
});
$('jd-text').addEventListener('input', () => {
  $('jd-char-count').textContent = $('jd-text').value.length.toLocaleString() + ' characters';
});

// ── PDF Upload ────────────────────────────────────────────────────────────
const uploadZone = $('resume-upload-zone');
const fileInput = $('resume-file');

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileUpload(file);
});
fileInput.addEventListener('change', e => {
  if (e.target.files[0]) handleFileUpload(e.target.files[0]);
});

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);

  uploadZone.querySelector('.upload-hint').innerHTML = '<span class="upload-icon">⏳</span> Extracting text...';

  try {
    const res = await fetch('/api/upload-resume', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    $('resume-text').value = data.text;
    $('resume-char-count').textContent = data.length.toLocaleString() + ' characters';
    uploadZone.querySelector('.upload-hint').innerHTML =
      `<span class="upload-icon">✓</span> ${file.name} extracted (${data.length.toLocaleString()} chars)`;
    showToast('Resume extracted successfully', 'success');
  } catch (err) {
    uploadZone.querySelector('.upload-hint').innerHTML =
      '<span class="upload-icon">⬆</span> Drop PDF here or <button class="link-btn" onclick="document.getElementById(\'resume-file\').click()">browse</button>';
    showToast('Upload failed: ' + err.message, 'error');
  }
}

// ── Start Tailoring ───────────────────────────────────────────────────────
async function startTailoring() {
  const resume = $('resume-text').value.trim();
  const jd = $('jd-text').value.trim();
  const apiKey = $('api-key').value.trim();

  if (!resume) { showToast('Please provide your resume', 'error'); return; }
  if (!jd)     { showToast('Please provide the job description', 'error'); return; }
  if (!apiKey) { showToast('Please enter your DeepSeek API key', 'error'); return; }

  // Persist key so user doesn't have to re-enter it
  localStorage.setItem('loop_rt_api_key', apiKey);

  // Reset state
  state.jobId = null;
  state.finalResume = '';
  state.finalPrompt = '';
  state.finalScore = null;
  state.iterations = [];
  state.analysisData = null;
  state.pdfFilename = null;
  state.startTime = Date.now();

  $('log-output').innerHTML = '';
  $('iteration-cards').innerHTML = '';

  // Reset phase indicators
  ['analyze', 'prompt', 'loop', 'complete'].forEach(p => {
    const el = $('phase-' + p);
    el.classList.remove('active', 'done');
  });

  $('start-btn').disabled = true;
  showPanel('progress-panel');
  setPhase('analyze');

  try {
    const res = await fetch('/api/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume, jd, api_key: apiKey })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    state.jobId = data.job_id;
    startStreaming(data.job_id);
  } catch (err) {
    addLog('Error: ' + err.message, 'error');
    showToast('Failed to start: ' + err.message, 'error');
    $('start-btn').disabled = false;
  }
}

// ── SSE Streaming ─────────────────────────────────────────────────────────
function startStreaming(jobId) {
  if (state.eventSource) state.eventSource.close();

  const es = new EventSource(`/api/stream/${jobId}`);
  state.eventSource = es;

  es.onmessage = e => {
    try {
      const event = JSON.parse(e.data);
      handleEvent(event);
    } catch (err) {
      console.error('Parse error:', err);
    }
  };

  es.onerror = () => {
    es.close();
    $('log-spinner').style.display = 'none';
  };
}

function handleEvent(event) {
  switch (event.type) {
    case 'progress':
      handleProgress(event);
      break;
    case 'analysis':
      state.analysisData = event;
      break;
    case 'iteration':
      handleIteration(event);
      break;
    case 'complete':
      handleComplete(event);
      break;
    case 'error':
      handleError(event);
      break;
  }
}

function handleProgress(event) {
  const step = event.step || '';
  const msg = event.message || '';

  // Update phase indicators
  if (step.startsWith('analyze')) setPhase('analyze');
  else if (step.startsWith('generate_prompt')) setPhase('prompt');
  else if (step.startsWith('iteration')) setPhase('loop');
  else if (step === 'target_reached') markPhaseDone('loop');

  // Determine log style
  let style = '';
  if (msg.toLowerCase().includes('error')) style = 'error';
  else if (msg.toLowerCase().includes('score:') || msg.toLowerCase().includes('complete')) style = 'success';
  else if (msg.toLowerCase().includes('iteration')) style = 'accent';

  addLog(msg, style);
}

function handleIteration(event) {
  const { iteration, score } = event;
  state.iterations.push(event);

  const total = score?.total ?? 0;
  const grade = score?.grade ?? '?';

  const card = document.createElement('div');
  card.className = 'iter-card' + (iteration === 1 ? '' : '');
  card.id = `iter-card-${iteration}`;

  const color = scoreColor(total);
  const dims = [
    { label: 'Keywords', key: 'keyword_match', max: 25 },
    { label: 'Skills', key: 'skills_alignment', max: 25 },
    { label: 'Level', key: 'role_level_fit', max: 20 },
    { label: 'Impact', key: 'impact_quantification', max: 15 },
    { label: 'Format', key: 'formatting_readability', max: 15 },
  ];

  const barsHtml = dims.map(d => {
    const s = score?.[d.key]?.score ?? 0;
    const pct = Math.round((s / d.max) * 100);
    return `<div class="mini-bar-row">
      <span class="mini-bar-label">${d.label}</span>
      <div class="mini-bar-track">
        <div class="mini-bar-fill" style="width:${pct}%;background:${scoreColor(pct)}"></div>
      </div>
    </div>`;
  }).join('');

  card.innerHTML = `
    <div class="iter-card-header">
      <span class="iter-label">Iteration ${iteration}</span>
    </div>
    <div class="iter-score" style="color:${color}">${total}</div>
    <div class="iter-grade" style="color:${color}">${grade}</div>
    <div class="iter-mini-bars">${barsHtml}</div>
  `;

  $('iteration-cards').appendChild(card);

  // Mark best card
  updateBestCard();
}

function updateBestCard() {
  let best = 0, bestIter = 0;
  state.iterations.forEach(it => {
    const t = it.score?.total ?? 0;
    if (t > best) { best = t; bestIter = it.iteration; }
  });
  document.querySelectorAll('.iter-card').forEach(c => c.classList.remove('best'));
  const bestCard = $(`iter-card-${bestIter}`);
  if (bestCard) bestCard.classList.add('best');
}

function handleComplete(event) {
  state.finalResume = event.final_resume || '';
  state.finalPrompt = event.final_prompt || '';
  state.finalScore = event.final_score || {};
  state.iterations = event.iterations || state.iterations;
  state.analysisData = {
    jd_analysis: event.jd_analysis,
    resume_analysis: event.resume_analysis,
    gap_analysis: event.gap_analysis,
  };

  markPhaseDone('analyze');
  markPhaseDone('prompt');
  markPhaseDone('loop');
  setPhase('complete');
  markPhaseDone('complete');

  $('log-spinner').style.display = 'none';
  addLog(`✓ Complete! Final score: ${state.finalScore.total}/100 (${state.finalScore.grade})`, 'success');

  const elapsed = Math.round((Date.now() - state.startTime) / 1000);
  addLog(`Total time: ${elapsed}s across ${state.iterations.length} iteration(s)`, '');

  // Show results immediately
  renderResults();
  showPanel('results-panel');
  $('start-btn').disabled = false;

  // Generate PDF in the background
  generatePDFInBackground();
}

async function generatePDFInBackground() {
  try {
    addLog('Generating PDF in background...', 'accent');
    const nameMatch = state.finalResume.match(/^([A-Z][a-z]+ [A-Z][a-z]+)/m);
    const name = nameMatch ? nameMatch[1] : 'resume';

    const res = await fetch('/api/generate-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume: state.finalResume, name })
    });
    const data = await res.json();
    if (!data.error) {
      state.pdfFilename = data.filename;
      addLog('✓ PDF Ready for download', 'success');
      // Update download button state if needed
    }
  } catch (e) {
    console.warn('PDF generation failed:', e);
    addLog('PDF generation failed, will retry on click', 'error');
  }
}

function handleError(event) {
  addLog('ERROR: ' + event.message, 'error');
  $('log-spinner').style.display = 'none';
  $('start-btn').disabled = false;
  showToast('An error occurred. Check the log for details.', 'error');
}

function renderResults() {
  const score = state.finalScore;
  const total = score?.total ?? 0;
  const grade = score?.grade ?? '--';

  // Score circle
  const circle = $('score-circle');
  circle.classList.remove('high', 'mid', 'low');
  if (total >= 90) circle.classList.add('high');
  else if (total >= 75) circle.classList.add('mid');
  else circle.classList.add('low');

  $('final-score-number').textContent = total;
  $('score-grade').textContent = grade;
  $('score-verdict').textContent = score?.recruiter_verdict || '';

  // Score breakdown bars
  const dims = [
    { label: 'Keyword Match (ATS)', key: 'keyword_match', max: 25 },
    { label: 'Skills Alignment', key: 'skills_alignment', max: 25 },
    { label: 'Role / Level Fit', key: 'role_level_fit', max: 20 },
    { label: 'Impact & Metrics', key: 'impact_quantification', max: 15 },
    { label: 'Format & Readability', key: 'formatting_readability', max: 15 },
  ];

  const breakdownHtml = dims.map(d => {
    const s = score?.[d.key]?.score ?? 0;
    const pct = Math.round((s / d.max) * 100);
    const color = scoreColor(pct);
    return `<div class="score-dim">
      <span class="score-dim-label">${d.label}</span>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:0%;background:${color}" data-target="${pct}"></div>
      </div>
      <span class="score-dim-value" style="color:${color}">${s}/${d.max}</span>
    </div>`;
  }).join('');

  $('score-breakdown').innerHTML = breakdownHtml;

  // Animate bars
  setTimeout(() => {
    document.querySelectorAll('.score-bar-fill[data-target]').forEach(el => {
      el.style.width = el.dataset.target + '%';
    });
  }, 100);

  // Analysis summary
  renderAnalysisSummary();

  // Resume text
  $('final-resume-text').textContent = state.finalResume;

  // Prompt text
  $('final-prompt-text').textContent = state.finalPrompt;

  // Iterations detail
  renderIterationsDetail();
}

function renderAnalysisSummary() {
  const jd = state.analysisData?.jd_analysis || {};
  const gap = state.analysisData?.gap_analysis || {};
  const score = state.finalScore || {};

  const matchedKw = score.keyword_match?.matched_keywords?.slice(0, 8) || [];
  const missingKw = score.keyword_match?.missing_keywords?.slice(0, 5) || [];
  const strengths = gap.strong_matches?.slice(0, 5) || [];

  const kwHtml = [
    ...matchedKw.map(k => `<span class="tag match">${k}</span>`),
    ...missingKw.map(k => `<span class="tag missing">${k}</span>`),
  ].join('');

  $('analysis-summary').innerHTML = `
    <div class="analysis-card">
      <div class="analysis-card-title">Target Role</div>
      <ul>
        <li><strong>${jd.job_title || 'N/A'}</strong></li>
        <li>${jd.company_name || 'Company not specified'}</li>
        <li>Level: ${jd.role_level || 'N/A'}</li>
        <li>Experience: ${jd.years_experience_required || 'N/A'} years</li>
        <li>Industry: ${jd.industry || 'N/A'}</li>
      </ul>
    </div>
    <div class="analysis-card">
      <div class="analysis-card-title">ATS Keywords</div>
      <div class="tag-list">${kwHtml || '<span class="tag">No data</span>'}</div>
    </div>
    <div class="analysis-card">
      <div class="analysis-card-title">Positioning Strategy</div>
      <p style="font-size:12px;color:var(--text-secondary);line-height:1.6">${gap.positioning_strategy || 'N/A'}</p>
    </div>
  `;
}

function renderIterationsDetail() {
  const container = $('iterations-detail');
  container.innerHTML = '';

  state.iterations.forEach((iter, idx) => {
    const score = iter.score || {};
    const total = score.total ?? 0;
    const color = scoreColor(total >= 100 ? 100 : total);
    const isBest = idx === state.iterations.reduce((bi, it, i) =>
      (it.score?.total ?? 0) > (state.iterations[bi]?.score?.total ?? 0) ? i : bi, 0);

    const card = document.createElement('div');
    card.className = 'iter-detail-card';
    card.innerHTML = `
      <div class="iter-detail-header" onclick="toggleIterDetail(this)">
        <span class="iter-detail-title">
          Iteration ${iter.iteration}${isBest ? ' ⭐ Best' : ''}
        </span>
        <span class="iter-detail-score" style="color:${color}">${total}/100 (${score.grade || '?'})</span>
      </div>
      <div class="iter-detail-body">
        <div class="iter-section-title">Recruiter Verdict</div>
        <p style="font-size:12px;color:var(--text-secondary)">${score.recruiter_verdict || 'N/A'}</p>
        <div class="iter-section-title">ATS Verdict</div>
        <p style="font-size:12px;color:var(--text-secondary)">${score.ats_verdict || 'N/A'}</p>
        <div class="iter-section-title">Diagnosis</div>
        <p style="font-size:12px;color:var(--text-secondary)">${score.diagnosis || 'N/A'}</p>
        <div class="iter-section-title">Missing Keywords</div>
        <div class="tag-list">${(score.keyword_match?.missing_keywords || []).map(k => `<span class="tag missing">${k}</span>`).join('') || 'None'}</div>
        <div class="iter-section-title">Resume Preview</div>
        <pre style="font-size:11px;color:var(--text-muted);white-space:pre-wrap;max-height:200px;overflow:auto;background:var(--bg-input);padding:12px;border-radius:6px;margin-top:6px">${(iter.resume || '').substring(0, 800)}${iter.resume?.length > 800 ? '\n...' : ''}</pre>
      </div>
    `;
    container.appendChild(card);
  });
}

function toggleIterDetail(header) {
  const body = header.nextElementSibling;
  body.classList.toggle('open');
}

// ── Tab Switching ─────────────────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  $('tab-' + tab).classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(b => {
    if (b.textContent.toLowerCase().includes(tab.replace('-', ' '))) {
      b.classList.add('active');
    }
  });
}

// ── PDF Download ──────────────────────────────────────────────────────────
async function downloadPDF() {
  const btn = $('download-pdf-btn');
  const originalText = btn.innerHTML;

  if (!state.pdfFilename) {
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';
    
    try {
      const nameMatch = state.finalResume.match(/^([A-Z][a-z]+ [A-Z][a-z]+)/m);
      const name = nameMatch ? nameMatch[1] : 'resume';
      const res = await fetch('/api/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume: state.finalResume, name })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      state.pdfFilename = data.filename;
    } catch (e) {
      showToast('PDF generation failed: ' + e.message, 'error');
      btn.disabled = false;
      btn.innerHTML = originalText;
      return;
    }
  }

  btn.disabled = false;
  btn.innerHTML = originalText;
  
  const a = document.createElement('a');
  a.href = `/api/download/${state.pdfFilename}`;
  a.download = state.pdfFilename;
  a.click();
  showToast('PDF download started!', 'success');
}

// ── Copy Helpers ──────────────────────────────────────────────────────────
function copyResume() {
  navigator.clipboard.writeText(state.finalResume).then(() => {
    showToast('Resume copied to clipboard!', 'success');
  });
}

function copyPrompt() {
  navigator.clipboard.writeText(state.finalPrompt).then(() => {
    showToast('Prompt copied to clipboard!', 'success');
  });
}

// ── Reset ─────────────────────────────────────────────────────────────────
function resetApp() {
  if (state.eventSource) state.eventSource.close();
  // Restore persisted API key after panel reset
  const savedKey = localStorage.getItem('loop_rt_api_key');
  showPanel('input-panel');
  if (savedKey) $('api-key').value = savedKey;
  $('start-btn').disabled = false;
}

// ── Phase Management ──────────────────────────────────────────────────────
function setPhase(name) {
  const el = $('phase-' + name);
  if (el && !el.classList.contains('done')) {
    el.classList.add('active');
  }
}

function markPhaseDone(name) {
  const el = $('phase-' + name);
  if (el) {
    el.classList.remove('active');
    el.classList.add('done');
  }
}

// ── Log ───────────────────────────────────────────────────────────────────
function addLog(msg, style = '') {
  const container = $('log-output');
  const elapsed = state.startTime ? ((Date.now() - state.startTime) / 1000).toFixed(1) + 's' : '';
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-time">${elapsed}</span><span class="log-msg ${style}">${escapeHtml(msg)}</span>`;
  container.appendChild(line);
  container.scrollTop = container.scrollHeight;
}

// ── Utilities ─────────────────────────────────────────────────────────────
function scoreColor(pct) {
  if (pct >= 85) return 'var(--success)';
  if (pct >= 65) return 'var(--warning)';
  return 'var(--danger)';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function showToast(msg, type = '') {
  const toast = $('toast');
  toast.textContent = msg;
  toast.className = 'toast show ' + type;
  setTimeout(() => { toast.className = 'toast'; }, 3500);
}
