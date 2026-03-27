const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const API = '';

let state = {
    view: 'campaigns',
    campaigns: [],
    currentCampaign: null,
    prospects: [],
    currentProspect: null,
    messages: [],
    analytics: [],
    loading: false,
};

// --- API helpers ---
async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// --- Navigation ---
document.addEventListener('click', (e) => {
    const nav = e.target.closest('.nav-item[data-view]');
    if (nav) {
        state.view = nav.dataset.view;
        state.currentCampaign = null;
        state.currentProspect = null;
        $$('.nav-item').forEach(n => n.classList.remove('active'));
        nav.classList.add('active');
        render();
    }
});

// --- Render router ---
function render() {
    const c = $('#content');
    switch (state.view) {
        case 'campaigns': renderCampaigns(c); break;
        case 'campaign-detail': renderCampaignDetail(c); break;
        case 'prospect-detail': renderProspectDetail(c); break;
        case 'analytics': renderAnalytics(c); break;
    }
}

// --- Campaigns list ---
async function renderCampaigns(el) {
    el.innerHTML = '<h2>Campaigns</h2><div id="campaign-list"></div>';
    try {
        state.campaigns = await api('GET', '/api/campaigns');
    } catch { state.campaigns = []; }

    const list = $('#campaign-list');
    if (state.campaigns.length === 0) {
        list.innerHTML = `
            <div class="empty">
                <h3>No campaigns yet</h3>
                <p>Create your first outreach campaign to get started.</p>
            </div>`;
    } else {
        list.innerHTML = state.campaigns.map(c => `
            <div class="card" style="cursor:pointer" data-campaign="${c.id}">
                <div class="card-header">
                    <h3>${esc(c.name)}</h3>
                    <div style="display:flex;gap:8px;align-items:center">
                        <span class="badge badge-${c.status}">${c.status}</span>
                        <button class="btn btn-danger btn-sm" data-delete-campaign="${c.id}" title="Delete">X</button>
                    </div>
                </div>
                <p style="font-size:13px;color:var(--text-muted)">${esc(c.product_description.substring(0, 120))}${c.product_description.length > 120 ? '...' : ''}</p>
                <p style="font-size:12px;color:var(--text-muted);margin-top:8px">${c.prospect_count} prospect${c.prospect_count !== 1 ? 's' : ''}</p>
            </div>
        `).join('');
    }

    // New campaign form
    el.innerHTML += `
        <div class="card" style="margin-top:24px">
            <h3 style="margin-bottom:12px">New Campaign</h3>
            <div class="form-group">
                <label>Campaign Name</label>
                <input id="camp-name" placeholder="e.g., Q2 Agency Outreach" />
            </div>
            <div class="form-group">
                <label>Product / Service Description</label>
                <textarea id="camp-desc" placeholder="Describe what you're selling. The more detail, the better the outreach..."></textarea>
            </div>
            <button class="btn btn-primary" id="create-campaign">Create Campaign</button>
        </div>`;

    // Events
    $('#create-campaign').onclick = async () => {
        const name = $('#camp-name').value.trim();
        const desc = $('#camp-desc').value.trim();
        if (!name || !desc) return;
        await api('POST', '/api/campaigns', { name, product_description: desc });
        render();
    };

    $$('[data-campaign]').forEach(el => {
        el.onclick = (e) => {
            if (e.target.closest('[data-delete-campaign]')) return;
            state.currentCampaign = state.campaigns.find(c => c.id === +el.dataset.campaign);
            state.view = 'campaign-detail';
            render();
        };
    });

    $$('[data-delete-campaign]').forEach(btn => {
        btn.onclick = async (e) => {
            e.stopPropagation();
            if (!confirm('Delete this campaign?')) return;
            await api('DELETE', `/api/campaigns/${btn.dataset.deleteCampaign}`);
            render();
        };
    });
}

// --- Campaign detail ---
async function renderCampaignDetail(el) {
    const c = state.currentCampaign;
    if (!c) { state.view = 'campaigns'; render(); return; }

    try {
        state.prospects = await api('GET', `/api/campaigns/${c.id}/prospects`);
    } catch { state.prospects = []; }

    el.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
            <button class="btn btn-ghost btn-sm" id="back-campaigns">&larr; Back</button>
            <h2 style="margin:0">${esc(c.name)}</h2>
            <span class="badge badge-${c.status}">${c.status}</span>
        </div>
        <p style="color:var(--text-muted);font-size:13px;margin-bottom:24px">${esc(c.product_description)}</p>

        <h3 style="margin-bottom:12px">Prospects (${state.prospects.length})</h3>
        <div id="prospect-list"></div>

        <div class="card" style="margin-top:24px">
            <h3 style="margin-bottom:12px">Add Prospect</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>Name *</label>
                    <input id="p-name" placeholder="Sarah Chen" />
                </div>
                <div class="form-group">
                    <label>Company *</label>
                    <input id="p-company" placeholder="Acme Marketing" />
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Role</label>
                    <input id="p-role" placeholder="VP of Marketing" />
                </div>
                <div class="form-group">
                    <label>Industry</label>
                    <input id="p-industry" placeholder="Digital Marketing" />
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Email</label>
                    <input id="p-email" placeholder="sarah@acme.com" />
                </div>
                <div class="form-group">
                    <label>LinkedIn URL</label>
                    <input id="p-linkedin" placeholder="https://linkedin.com/in/..." />
                </div>
            </div>
            <div class="form-group">
                <label>Notes / Context</label>
                <textarea id="p-notes" placeholder="Any extra context — recent interactions, mutual connections, specific needs..."></textarea>
            </div>
            <button class="btn btn-primary" id="add-prospect">Add Prospect</button>
        </div>`;

    // Prospect list
    const list = $('#prospect-list');
    if (state.prospects.length === 0) {
        list.innerHTML = '<div class="empty"><p>No prospects yet. Add one below.</p></div>';
    } else {
        list.innerHTML = `<table class="table"><thead><tr>
            <th>Name</th><th>Company</th><th>Role</th><th>Status</th><th>Actions</th>
        </tr></thead><tbody>${state.prospects.map(p => `
            <tr style="cursor:pointer" data-prospect="${p.id}">
                <td>${esc(p.name)}</td>
                <td>${esc(p.company)}</td>
                <td>${esc(p.role)}</td>
                <td><span class="badge badge-${p.status}">${p.status}</span></td>
                <td>
                    <button class="btn btn-primary btn-sm" data-generate="${p.id}">Generate</button>
                    <button class="btn btn-ghost btn-sm" data-view-msgs="${p.id}" ${p.status !== 'generated' ? 'disabled' : ''}>View</button>
                    <button class="btn btn-danger btn-sm" data-delete-prospect="${p.id}">X</button>
                </td>
            </tr>
        `).join('')}</tbody></table>`;
    }

    // Events
    $('#back-campaigns').onclick = () => { state.view = 'campaigns'; render(); };

    $('#add-prospect').onclick = async () => {
        const name = $('#p-name').value.trim();
        const company = $('#p-company').value.trim();
        if (!name || !company) return;
        await api('POST', `/api/campaigns/${c.id}/prospects`, {
            name, company,
            role: $('#p-role').value.trim(),
            industry: $('#p-industry').value.trim(),
            email: $('#p-email').value.trim(),
            linkedin_url: $('#p-linkedin').value.trim(),
            notes: $('#p-notes').value.trim(),
        });
        render();
    };

    $$('[data-generate]').forEach(btn => {
        btn.onclick = async (e) => {
            e.stopPropagation();
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Generating...';
            try {
                await api('POST', `/api/generate/${btn.dataset.generate}`);
                render();
            } catch (err) {
                alert('Generation failed: ' + err.message);
                render();
            }
        };
    });

    $$('[data-view-msgs]').forEach(btn => {
        btn.onclick = (e) => {
            e.stopPropagation();
            state.currentProspect = state.prospects.find(p => p.id === +btn.dataset.viewMsgs);
            state.view = 'prospect-detail';
            render();
        };
    });

    $$('[data-prospect]').forEach(row => {
        row.onclick = (e) => {
            if (e.target.closest('button')) return;
            const p = state.prospects.find(p => p.id === +row.dataset.prospect);
            if (p && p.status === 'generated') {
                state.currentProspect = p;
                state.view = 'prospect-detail';
                render();
            }
        };
    });

    $$('[data-delete-prospect]').forEach(btn => {
        btn.onclick = async (e) => {
            e.stopPropagation();
            await api('DELETE', `/api/campaigns/${c.id}/prospects/${btn.dataset.deleteProspect}`);
            render();
        };
    });
}

// --- Prospect detail (messages view) ---
async function renderProspectDetail(el) {
    const p = state.currentProspect;
    if (!p) { state.view = 'campaign-detail'; render(); return; }

    try {
        state.messages = await api('GET', `/api/campaigns/${p.campaign_id}/prospects/${p.id}/messages`);
    } catch { state.messages = []; }

    // Group by sequence step
    const steps = {};
    state.messages.forEach(m => {
        const key = m.sequence_order;
        if (!steps[key]) steps[key] = { order: m.sequence_order, channel: m.channel, send_day: m.send_day, variants: {} };
        steps[key].variants[m.variant] = m;
    });

    const channelLabel = (ch) => ({ email: 'Cold Email', linkedin: 'LinkedIn Message', follow_up_email: 'Follow-up Email' }[ch] || ch);

    el.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
            <button class="btn btn-ghost btn-sm" id="back-campaign">&larr; Back</button>
            <h2 style="margin:0">${esc(p.name)} @ ${esc(p.company)}</h2>
        </div>

        <div class="card" style="margin-bottom:24px">
            <h3 style="margin-bottom:8px">Outreach Sequence</h3>
            <p style="color:var(--text-muted);font-size:13px">${Object.keys(steps).length} touchpoints with A/B variants</p>
        </div>

        ${Object.values(steps).sort((a, b) => a.order - b.order).map(step => `
            <div class="sequence-step">
                <div class="step-indicator">
                    <div class="step-dot">${step.order}</div>
                    <div class="step-line"></div>
                </div>
                <div class="step-content">
                    <div class="step-header">
                        <span class="badge badge-draft">${channelLabel(step.channel)}</span>
                        <span>Day ${step.send_day}</span>
                    </div>
                    <div class="variant-tabs" data-step="${step.order}">
                        ${Object.keys(step.variants).sort().map(v =>
                            `<button class="variant-tab ${v === 'A' ? 'active' : ''}" data-variant="${v}" data-step-id="${step.order}">Variant ${v}</button>`
                        ).join('')}
                    </div>
                    ${Object.entries(step.variants).sort(([a],[b]) => a.localeCompare(b)).map(([v, m]) => `
                        <div class="message-card variant-content" data-step-variant="${step.order}-${v}" style="${v !== 'A' ? 'display:none' : ''}">
                            ${m.subject ? `<div class="subject">Subject: ${esc(m.subject)}</div>` : ''}
                            <div class="body">${esc(m.body)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('')}`;

    // Events
    $('#back-campaign').onclick = () => { state.view = 'campaign-detail'; render(); };

    $$('.variant-tab').forEach(tab => {
        tab.onclick = () => {
            const stepId = tab.dataset.stepId;
            const variant = tab.dataset.variant;
            $$(`.variant-tab[data-step-id="${stepId}"]`).forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            $$(`.variant-content`).forEach(vc => {
                if (vc.dataset.stepVariant.startsWith(stepId + '-')) {
                    vc.style.display = vc.dataset.stepVariant === `${stepId}-${variant}` ? '' : 'none';
                }
            });
        };
    });
}

// --- Analytics ---
async function renderAnalytics(el) {
    try {
        state.analytics = await api('GET', '/api/analytics');
    } catch { state.analytics = []; }

    const totals = state.analytics.reduce((acc, a) => ({
        campaigns: acc.campaigns + 1,
        prospects: acc.prospects + a.total_prospects,
        generated: acc.generated + a.prospects_generated,
        messages: acc.messages + a.total_messages,
    }), { campaigns: 0, prospects: 0, generated: 0, messages: 0 });

    el.innerHTML = `
        <h2>Analytics</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="value">${totals.campaigns}</div><div class="label">Campaigns</div></div>
            <div class="stat-card"><div class="value">${totals.prospects}</div><div class="label">Prospects</div></div>
            <div class="stat-card"><div class="value">${totals.generated}</div><div class="label">Generated</div></div>
            <div class="stat-card"><div class="value">${totals.messages}</div><div class="label">Messages</div></div>
        </div>

        ${state.analytics.length === 0 ? '<div class="empty"><p>No data yet. Create a campaign and generate outreach to see analytics.</p></div>' :
        state.analytics.map(a => `
            <div class="card">
                <div class="card-header">
                    <h3>${esc(a.campaign_name)}</h3>
                    <span style="color:var(--text-muted);font-size:13px">${a.prospects_generated}/${a.total_prospects} prospects done</span>
                </div>
                <div style="display:flex;gap:24px;font-size:13px;color:var(--text-muted)">
                    ${Object.entries(a.messages_by_channel).map(([ch, count]) =>
                        `<span>${ch.replace('_', ' ')}: <strong style="color:var(--text)">${count}</strong></span>`
                    ).join('')}
                </div>
            </div>
        `).join('')}`;
}

// --- Helpers ---
function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

// --- Init ---
render();
