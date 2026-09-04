/**
 * TelecomCo AI Support Assistant – Frontend Logic
 * NexusTiq24 Hackathon | Track PS04
 *
 * Handles:
 *  - Customer selection & profile rendering
 *  - Chat message sending & conversation history management
 *  - API communication (POST /api/chat, GET /api/customer/:id, etc.)
 *  - Evidence panel update (articles, confidence, escalation badge)
 *  - Quick-chip suggestions, auto-resize textarea, toast notifications
 */

'use strict';

/* ════════════════════════════════════════════════════════════════════════
   CONSTANTS
   ════════════════════════════════════════════════════════════════════════ */
const API_BASE = '';   // same origin

/* ════════════════════════════════════════════════════════════════════════
   STATE
   ════════════════════════════════════════════════════════════════════════ */
const state = {
  customerId: null,
  customerProfile: null,
  conversationHistory: [],   // [{role:'user'|'assistant', content:'...'}]
  isLoading: false,
};

/* ════════════════════════════════════════════════════════════════════════
   DOM REFS
   ════════════════════════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);

const dom = {
  customerSelect:     $('customerSelect'),
  customerEmpty:      $('customerEmpty'),
  customerData:       $('customerData'),
  avatarEl:           $('avatarEl'),
  custName:           $('custName'),
  custId:             $('custId'),
  custPlan:           $('custPlan'),
  custBilling:        $('custBilling'),
  ticketsList:        $('ticketsList'),

  chatWindow:         $('chatWindow'),
  welcomeMsg:         $('welcomeMsg'),
  chatForm:           $('chatForm'),
  messageInput:       $('messageInput'),
  sendBtn:            $('sendBtn'),
  charCount:          $('charCount'),
  typingIndicator:    $('typingIndicator'),
  clearChatBtn:       $('clearChatBtn'),

  statusDot:          $('statusDot'),
  statusLabel:        $('statusLabel'),

  confidenceValue:    $('confidenceValue'),
  confidenceBarFill:  $('confidenceBarFill'),
  confidenceCard:     $('confidenceCard'),

  statusBadgeWrap:    $('statusBadgeWrap'),
  statusBadge:        $('statusBadge'),
  statusBadgeIcon:    $('statusBadgeIcon'),
  statusBadgeText:    $('statusBadgeText'),

  escalationBadge:    $('escalationBadge'),
  escalationText:     $('escalationText'),

  articlesList:       $('articlesList'),

  summarySection:     $('summarySection'),
  agentSummary:       $('agentSummary'),

  toastContainer:     $('toastContainer'),
};

/* ════════════════════════════════════════════════════════════════════════
   INITIALISATION
   ════════════════════════════════════════════════════════════════════════ */
async function init() {
  await loadCustomers();
  bindEvents();
}

/* ════════════════════════════════════════════════════════════════════════
   API HELPERS
   ════════════════════════════════════════════════════════════════════════ */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ════════════════════════════════════════════════════════════════════════
   CUSTOMER LOADING
   ════════════════════════════════════════════════════════════════════════ */
async function loadCustomers() {
  try {
    const customers = await apiFetch('/api/customers');
    customers.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.customer_id;
      opt.textContent = `${c.customer_id} — ${c.name} (${c.plan})`;
      dom.customerSelect.appendChild(opt);
    });
  } catch (e) {
    showToast('Failed to load customer list: ' + e.message, 'error');
  }
}

async function loadCustomerProfile(customerId) {
  try {
    setStatus('loading', 'Loading…');
    const profile = await apiFetch(`/api/customer/${customerId}`);
    state.customerProfile = profile;
    state.customerId = customerId;
    renderCustomerProfile(profile);
    setStatus('ok', 'Ready');
  } catch (e) {
    setStatus('error', 'Error');
    showToast('Customer not found: ' + e.message, 'error');
  }
}

/* ════════════════════════════════════════════════════════════════════════
   CUSTOMER PROFILE RENDERING
   ════════════════════════════════════════════════════════════════════════ */
function renderCustomerProfile(p) {
  dom.customerEmpty.classList.add('hidden');
  dom.customerData.classList.remove('hidden');

  // Avatar & name
  const initials = p.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  dom.avatarEl.textContent = initials;
  dom.custName.textContent = p.name;
  dom.custId.textContent = p.customer_id;
  dom.custPlan.textContent = p.plan;

  // Billing badge
  const billingClass = {
    active: 'billing-active',
    overdue: 'billing-overdue',
    suspended: 'billing-suspended',
  }[p.billing_status] || 'billing-active';
  dom.custBilling.textContent = p.billing_status;
  dom.custBilling.className = `billing-badge ${billingClass}`;

  // Tickets
  dom.ticketsList.innerHTML = '';
  if (!p.recent_tickets || p.recent_tickets.length === 0) {
    dom.ticketsList.innerHTML = '<div class="empty-state-sm">No recent tickets</div>';
    return;
  }
  p.recent_tickets.forEach(t => {
    const statusClass = {
      open: 'ticket-item--open ts-open',
      resolved: 'ticket-item--resolved ts-resolved',
      escalated: 'ticket-item--escalated ts-escalated',
    }[t.status] || 'ticket-item--open ts-open';

    const [itemClass, badgeClass] = statusClass.split(' ');

    dom.ticketsList.insertAdjacentHTML('beforeend', `
      <div class="ticket-item ${itemClass}" role="listitem">
        <div class="ticket-id">${escHtml(t.ticket_id)} · ${escHtml(t.date || '')}</div>
        <div class="ticket-issue">${escHtml(t.issue)}</div>
        <span class="ticket-status ${badgeClass}">${escHtml(t.status)}</span>
      </div>
    `);
  });
}

/* ════════════════════════════════════════════════════════════════════════
   CHAT
   ════════════════════════════════════════════════════════════════════════ */
async function sendMessage(text) {
  if (!text.trim()) return;
  if (!state.customerId) {
    showToast('Please select a customer first.', 'error');
    return;
  }
  if (state.isLoading) return;

  // Hide welcome message
  if (dom.welcomeMsg) dom.welcomeMsg.classList.add('hidden');

  // Append user message
  appendMessage('user', text);
  state.conversationHistory.push({ role: 'user', content: text });

  // Clear input
  dom.messageInput.value = '';
  dom.messageInput.style.height = 'auto';
  updateCharCount();

  // Show typing indicator
  setLoading(true);

  try {
    const result = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        customer_id: state.customerId,
        message: text,
        conversation_history: state.conversationHistory.slice(0, -1),  // exclude latest user msg
      }),
    });

    // Append assistant response
    appendAssistantMessage(result);
    state.conversationHistory.push({ role: 'assistant', content: result.response });

    // Update right panel
    updateEvidencePanel(result);
    setStatus('ok', 'Ready');

  } catch (e) {
    setStatus('error', 'Error');
    appendMessage('assistant', `⚠️ Error: ${e.message}. Please try again.`);
    showToast('Chat error: ' + e.message, 'error');
  } finally {
    setLoading(false);
  }
}

/* ── Message Rendering ─────────────────────────────────────────────────── */
function appendMessage(role, content) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const isUser = role === 'user';
  const avatarChar = isUser
    ? (state.customerProfile?.name?.charAt(0) || 'U')
    : '🤖';

  const msgEl = document.createElement('div');
  msgEl.className = `msg msg--${role}`;
  msgEl.innerHTML = `
    <div class="msg__avatar" aria-hidden="true">${escHtml(avatarChar)}</div>
    <div>
      <div class="msg__bubble">${formatContent(content)}</div>
      <div class="msg__meta">${time}</div>
    </div>
  `;
  dom.chatWindow.appendChild(msgEl);
  scrollToBottom();
}

function appendAssistantMessage(result) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const msgEl = document.createElement('div');
  msgEl.className = 'msg msg--assistant';

  // Build evidence pills
  let evidenceHtml = '';
  if (result.evidence && result.evidence.length > 0) {
    const pills = result.evidence.map(id =>
      `<span class="evidence-pill" title="Article ${escHtml(id)}">${escHtml(id)}</span>`
    ).join('');
    evidenceHtml = `<div class="evidence-pills" aria-label="Supporting articles">${pills}</div>`;
  }

  // Build follow-up questions
  let followupHtml = '';
  if (result.followup_questions && result.followup_questions.length > 0) {
    const items = result.followup_questions.map(q =>
      `<li>${escHtml(q)}</li>`
    ).join('');
    followupHtml = `
      <div class="followup-questions">
        <h4>Could you clarify:</h4>
        <ul>${items}</ul>
      </div>
    `;
  }

  msgEl.innerHTML = `
    <div class="msg__avatar" aria-hidden="true">🤖</div>
    <div>
      <div class="msg__bubble">
        ${formatContent(result.response)}
        ${evidenceHtml}
        ${followupHtml}
      </div>
      <div class="msg__meta">
        ${time}
        · Confidence: <strong>${result.confidence}%</strong>
        · Status: <strong>${result.status}</strong>
      </div>
    </div>
  `;
  dom.chatWindow.appendChild(msgEl);
  scrollToBottom();
}

function formatContent(text) {
  if (!text) return '';
  // Escape first then convert newlines to <br>
  return escHtml(text).replace(/\n/g, '<br>');
}

/* ════════════════════════════════════════════════════════════════════════
   EVIDENCE PANEL
   ════════════════════════════════════════════════════════════════════════ */
function updateEvidencePanel(result) {
  // ── Confidence bar ───────────────────────────────────────────────────
  const conf = result.confidence || 0;
  dom.confidenceValue.textContent = conf + '%';
  dom.confidenceBarFill.style.width = conf + '%';

  // Color the bar based on confidence level
  if (conf >= 70) {
    dom.confidenceBarFill.style.background = 'linear-gradient(90deg, #10b981, #22d3ee)';
  } else if (conf >= 40) {
    dom.confidenceBarFill.style.background = 'linear-gradient(90deg, #f59e0b, #fbbf24)';
  } else {
    dom.confidenceBarFill.style.background = 'linear-gradient(90deg, #f43f5e, #fb7185)';
  }

  // ── Status badge ─────────────────────────────────────────────────────
  dom.statusBadgeWrap.classList.remove('hidden');
  const statusMap = {
    resolved:        { icon: '✅', text: 'Issue Resolved',           cls: 'badge--resolved' },
    followup_needed: { icon: '❓', text: 'Follow-up Needed',         cls: 'badge--followup' },
    escalated:       { icon: '🚨', text: 'Escalated to Human Agent', cls: 'badge--escalated' },
  };
  const statusInfo = statusMap[result.status] || { icon: '💬', text: result.status, cls: 'badge--followup' };
  dom.statusBadge.className = `status-badge ${statusInfo.cls}`;
  dom.statusBadgeIcon.textContent = statusInfo.icon;
  dom.statusBadgeText.textContent = statusInfo.text;

  // ── Escalation badge ─────────────────────────────────────────────────
  if (result.status === 'escalated') {
    dom.escalationBadge.classList.remove('hidden');
    const reasons = result.escalation_reasons || [];
    dom.escalationText.textContent = reasons.length > 0
      ? reasons.join(' | ')
      : 'Issue requires specialist review.';
  } else {
    dom.escalationBadge.classList.add('hidden');
  }

  // ── Retrieved articles ────────────────────────────────────────────────
  const articles = result.retrieved_articles || [];
  dom.articlesList.innerHTML = '';
  if (articles.length === 0) {
    dom.articlesList.innerHTML = '<div class="empty-state-sm">No articles retrieved</div>';
  } else {
    articles.forEach(art => {
      const isEvidence = result.evidence && result.evidence.includes(art.article_id);
      const score = art.similarity_score || 0;
      const scorePercent = Math.round(score * 100);
      dom.articlesList.insertAdjacentHTML('beforeend', `
        <div class="article-card ${isEvidence ? 'evidence-highlight' : ''}">
          <div class="article-card__top">
            <span class="article-id">${escHtml(art.article_id)}</span>
            <span class="article-score">${scorePercent}%</span>
          </div>
          <div class="article-title">${escHtml(art.title)}</div>
          <div class="article-category">${escHtml(art.category)}</div>
          <div class="score-bar">
            <div class="score-bar-fill" style="width: ${scorePercent}%"></div>
          </div>
        </div>
      `);
    });
  }

  // ── Agent summary ─────────────────────────────────────────────────────
  if (result.summary_for_agent && result.summary_for_agent.trim()) {
    dom.summarySection.classList.remove('hidden');
    dom.agentSummary.textContent = result.summary_for_agent;
  } else {
    dom.summarySection.classList.add('hidden');
  }
}

/* ════════════════════════════════════════════════════════════════════════
   UI HELPERS
   ════════════════════════════════════════════════════════════════════════ */
function setLoading(loading) {
  state.isLoading = loading;
  dom.sendBtn.disabled = loading;
  dom.messageInput.disabled = loading;
  dom.typingIndicator.classList.toggle('hidden', !loading);
  if (loading) {
    setStatus('loading', 'AI thinking…');
    scrollToBottom();
  }
}

function setStatus(type, label) {
  dom.statusDot.className = `status-indicator status--${type}`;
  dom.statusLabel.textContent = label;
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
  });
}

function updateCharCount() {
  const len = dom.messageInput.value.length;
  dom.charCount.textContent = `${len} / 1000`;
  dom.charCount.style.color = len > 900 ? 'var(--clr-rose)' : '';
}

function clearChat() {
  state.conversationHistory = [];
  dom.chatWindow.innerHTML = '';
  // Re-add welcome message (recreate it)
  dom.chatWindow.insertAdjacentHTML('afterbegin', `
    <div class="welcome-msg" id="welcomeMsg">
      <div class="welcome-msg__icon">🤖</div>
      <h3>Hello! I'm your AI Support Assistant</h3>
      <p>Select a customer and type your message to begin. I'll retrieve relevant articles and generate a grounded, evidence-based response.</p>
      <div class="welcome-chips">
        <button class="chip" data-msg="My internet is very slow, what can I do?">📶 Slow Internet?</button>
        <button class="chip" data-msg="I have an issue with my bill, I was charged incorrectly.">💳 Billing Issue?</button>
        <button class="chip" data-msg="My router is not connecting to the internet.">📡 Router Problem?</button>
        <button class="chip" data-msg="My SIM card is not activating.">📱 SIM Activation?</button>
      </div>
    </div>
  `);
  // Rebind chip events
  dom.chatWindow.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      dom.messageInput.value = chip.dataset.msg;
      updateCharCount();
      autoResizeTextarea();
      dom.messageInput.focus();
    });
  });

  // Reset right panel
  dom.confidenceValue.textContent = '—';
  dom.confidenceBarFill.style.width = '0%';
  dom.statusBadgeWrap.classList.add('hidden');
  dom.escalationBadge.classList.add('hidden');
  dom.articlesList.innerHTML = '<div class="empty-state-sm">No articles retrieved yet</div>';
  dom.summarySection.classList.add('hidden');
  setStatus('idle', 'Idle');
}

/* ════════════════════════════════════════════════════════════════════════
   TOAST
   ════════════════════════════════════════════════════════════════════════ */
function showToast(message, type = 'info') {
  const iconMap = { error: '❌', success: '✅', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `<span class="toast__icon">${iconMap[type] || 'ℹ️'}</span><span>${escHtml(message)}</span>`;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ════════════════════════════════════════════════════════════════════════
   SECURITY
   ════════════════════════════════════════════════════════════════════════ */
function escHtml(str) {
  if (typeof str !== 'string') return String(str ?? '');
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/* ════════════════════════════════════════════════════════════════════════
   AUTO-RESIZE TEXTAREA
   ════════════════════════════════════════════════════════════════════════ */
function autoResizeTextarea() {
  const el = dom.messageInput;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

/* ════════════════════════════════════════════════════════════════════════
   EVENT BINDING
   ════════════════════════════════════════════════════════════════════════ */
function bindEvents() {
  // Customer select
  dom.customerSelect.addEventListener('change', async e => {
    const id = e.target.value;
    if (!id) {
      state.customerId = null;
      state.customerProfile = null;
      dom.customerEmpty.classList.remove('hidden');
      dom.customerData.classList.add('hidden');
      clearChat();
      return;
    }
    clearChat();
    await loadCustomerProfile(id);
    showToast(`Loaded profile for ${id}`, 'success');
  });

  // Form submit
  dom.chatForm.addEventListener('submit', async e => {
    e.preventDefault();
    const msg = dom.messageInput.value.trim();
    if (msg) await sendMessage(msg);
  });

  // Shift+Enter = newline, Enter = send
  dom.messageInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      dom.chatForm.dispatchEvent(new Event('submit'));
    }
  });

  // Auto-resize & char count
  dom.messageInput.addEventListener('input', () => {
    autoResizeTextarea();
    updateCharCount();
  });

  // Clear chat
  dom.clearChatBtn.addEventListener('click', () => {
    if (confirm('Clear the conversation?')) clearChat();
  });

  // Quick chips (initial set)
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      dom.messageInput.value = chip.dataset.msg;
      updateCharCount();
      autoResizeTextarea();
      dom.messageInput.focus();
    });
  });
}

/* ════════════════════════════════════════════════════════════════════════
   BOOT
   ════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', init);
