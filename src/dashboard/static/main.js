import { initPerformanceChart, updatePerformanceData } from './modules/performance_chart.js?v=6.0';
import { initSynapseNetwork, updateSynapses } from './modules/synapse_viewer.js?v=6.0';
import { updateLogs, updatePromptTab, updateResponseTab } from './modules/log_viewer.js?v=6.0';
import { updateVisuals } from './modules/visuals.js?v=6.0';
import { initVectorPanel, updateVectorData } from './modules/vector_panel.js?v=6.0';
import { initFullscreen } from './modules/fullscreen.js?v=6.0';
import { initWebSocket, startCountdownLoop } from './modules/websocket.js?v=6.0';
import { initPositionPanel, updatePositionData, getLastPosition } from './modules/position_panel.js?v=6.0';
import { initUI } from './modules/ui.js?v=6.0';
import { initStatisticsPanel, updateStatisticsData } from './modules/statistics_panel.js?v=6.0';
import { initNewsPanel, updateNewsData } from './modules/news_panel.js?v=6.0';

const state = {
    isConnected: false,
    fastPollInterval: 10000,
    slowPollInterval: 30000,
    lastUpdateTime: null
};

// ─── Utility ─────────────────────────────────────────────────────────────────

function formatCost(cost) {
    if (cost === 0 || cost === null || cost === undefined) return '$0.00';
    if (cost < 0.0001) return `$${cost.toFixed(8)}`;
    if (cost < 0.01) return `$${cost.toFixed(6)}`;
    if (cost < 1) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
}

function updateLastUpdated() {
    const el = document.getElementById('last-updated');
    if (el && state.lastUpdateTime) {
        el.textContent = `Updated: ${state.lastUpdateTime.toLocaleTimeString()}`;
    }
}

function togglePanelMinimize(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle('minimized');
    const btn = panel.querySelector('[id^="btn-minimize"]');
    if (btn) {
        const isMin = panel.classList.contains('minimized');
        btn.setAttribute('aria-expanded', String(!isMin));
    }
}

// ─── System Status ────────────────────────────────────────────────────────────

async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        if (!response.ok) return;
        const data = await response.json();

        const btnStart = document.getElementById('btn-system-start');
        const btnStop  = document.getElementById('btn-system-stop');
        const apiIcon  = document.getElementById('api-status-icon');
        const apiText  = document.getElementById('api-status-text');

        // API key indicator
        if (apiIcon && apiText) {
            if (data.system_ready) {
                apiIcon.textContent = '✅';
                apiText.textContent  = 'API Keys Ready';
            } else {
                apiIcon.textContent = '❌';
                apiText.textContent  = 'API Keys Missing';
            }
        }

        // Start / Stop / Wakeup button visibility
        const btnWakeup = document.getElementById('btn-system-wakeup');
        if (btnStart && btnStop) {
            if (data.bot_running) {
                // Bot is running — show Stop and Wakeup, hide Start
                btnStart.style.display = 'none';
                btnStop.style.display  = 'flex';
                btnStop.disabled       = false;
                if (btnWakeup) btnWakeup.style.display = 'flex';
                btnStop.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    </svg>
                    Stop AI Engine`;
            } else {
                // Bot is NOT running — show Start, hide Stop and Wakeup
                btnStop.style.display  = 'none';
                if (btnWakeup) btnWakeup.style.display = 'none';
                btnStart.style.display = 'flex';
                btnStart.disabled      = !data.system_ready;
                btnStart.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                    Start AI Engine`;
            }
        }
    } catch (e) {
        console.warn('System status fetch failed', e);
    }
}

// ─── Rules ────────────────────────────────────────────────────────────────────

async function fetchRules() {
    try {
        const response = await fetch('/api/brain/rules');
        if (!response.ok) return;
        const rules = await response.json();

        const countEl = document.getElementById('overview-rules-count');
        const hintEl  = document.getElementById('overview-rules-hint');

        const count = Array.isArray(rules) ? rules.length : 0;
        if (countEl) countEl.textContent = count;
        if (hintEl) {
            hintEl.textContent = count > 0
                ? `${count} semantic rule${count !== 1 ? 's' : ''} active`
                : 'No rules learned yet';
        }
    } catch (e) {
        console.warn('Rules fetch failed', e);
    }
}

// ─── Costs ────────────────────────────────────────────────────────────────────

async function fetchCosts() {
    try {
        const response = await fetch('/api/monitor/costs');
        if (!response.ok) return;
        const data = await response.json();
        updateCostDisplay(data);
    } catch (e) {
        console.error('Failed to fetch costs', e);
    }
}

function updateCostDisplay(data) {
    const total = data.total_session_cost || 0;
    const el = document.getElementById('overview-cost');
    if (el) el.textContent = formatCost(total);
}

// ─── Brain Status ─────────────────────────────────────────────────────────────

async function fetchBrainStatus() {
    try {
        const response = await fetch('/api/brain/status');
        if (!response.ok) return;
        const data = await response.json();

        // Connection indicator
        const connStatus = document.getElementById('connection-status');
        const statusDot  = document.querySelector('.status-dot');
        if (connStatus) {
            connStatus.textContent = 'Connected';
            connStatus.classList.remove('disconnected');
            connStatus.classList.add('connected');
        }
        if (statusDot) {
            statusDot.classList.remove('disconnected');
            statusDot.classList.add('connected');
        }

        // Header active pair
        const headerPair = document.getElementById('header-active-pair');
        if (headerPair) {
            headerPair.textContent = `Futures ${data.symbol || '--'}`;
        }

        // KPI — Market Trend
        const trendEl = document.getElementById('overview-trend');
        if (trendEl) {
            trendEl.textContent = data.trend || '--';
            trendEl.className = 'value ' +
                (data.trend === 'BULLISH' ? 'start-green' :
                 data.trend === 'BEARISH' ? 'start-red' : '');
        }

        // KPI — Confidence
        const confEl = document.getElementById('overview-conf');
        if (confEl) confEl.textContent = data.confidence ? `${data.confidence}%` : '--%';

        // KPI — Action
        const actionEl = document.getElementById('overview-action');
        if (actionEl) actionEl.textContent = data.action || 'WAITING';

        state.lastUpdateTime = new Date();
        updateLastUpdated();
    } catch (e) {
        console.warn('Brain status fetch failed', e);
        // Mark as disconnected
        const connStatus = document.getElementById('connection-status');
        const statusDot  = document.querySelector('.status-dot');
        if (connStatus) {
            connStatus.textContent = 'Disconnected';
            connStatus.classList.add('disconnected');
            connStatus.classList.remove('connected');
        }
        if (statusDot) {
            statusDot.classList.add('disconnected');
            statusDot.classList.remove('connected');
        }
    }
}

// ─── Manual Settings ──────────────────────────────────────────────────────────

async function fetchManualSettings() {
    try {
        const response = await fetch('/api/settings/overrides');
        if (!response.ok) return;
        const data = await response.json();

        const map = {
            'setting-coin':             data.manual_coin,
            'setting-timeframe':        data.timeframe,
            'setting-work-interval':    data.check_interval_mins,
            'setting-sl':               data.stop_loss_pct,
            'setting-tp':               data.take_profit_pct,
            'setting-leverage':         data.leverage,
            'setting-initial-capital':  data.initial_capital,
            'setting-min-alloc':        data.min_allocation_pct,
            'setting-max-alloc':        data.max_allocation_pct
        };

        Object.keys(map).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = map[id] != null ? map[id] : '';
        });
    } catch (e) {
        console.error('Failed to fetch settings', e);
    }
}

async function saveManualSettingsGroup(group) {
    const statusEl = document.getElementById('settings-save-status');
    const payload  = {};

    if (group === 'target') {
        const coin = document.getElementById('setting-coin');
        const tf   = document.getElementById('setting-timeframe');
        const wi   = document.getElementById('setting-work-interval');
        if (coin) payload.manual_coin         = coin.value.trim().toUpperCase();
        if (tf)   payload.timeframe           = tf.value;
        if (wi)   payload.check_interval_mins = parseInt(wi.value) || 0;
    } else if (group === 'risk') {
        const sl = document.getElementById('setting-sl');
        const tp = document.getElementById('setting-tp');
        const lev = document.getElementById('setting-leverage');
        if (sl) payload.stop_loss_pct   = parseFloat(sl.value) || 0;
        if (tp) payload.take_profit_pct = parseFloat(tp.value) || 0;
        if (lev) payload.leverage = parseInt(lev.value) || 0;
    } else if (group === 'capital') {
        const ic   = document.getElementById('setting-initial-capital');
        const minA = document.getElementById('setting-min-alloc');
        const maxA = document.getElementById('setting-max-alloc');
        if (ic)   payload.initial_capital    = parseFloat(ic.value) || 0;
        if (minA) payload.min_allocation_pct = parseFloat(minA.value) || 0;
        if (maxA) payload.max_allocation_pct = parseFloat(maxA.value) || 0;
    }

    try {
        const response = await fetch('/api/settings/overrides', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });

        if (response.ok) {
            if (statusEl) {
                statusEl.style.display = 'block';
                setTimeout(() => { statusEl.style.display = 'none'; }, 2500);
            }
            if (group === 'capital') updatePerformanceData();
        } else {
            console.error('Save settings failed with status', response.status);
        }
    } catch (err) {
        console.error('Save failed', err);
    }
}

// ─── App Init ─────────────────────────────────────────────────────────────────

function initApp() {
    console.log('Initializing Dashboard App...');

    // Expose globals needed by inline HTML handlers
    window.updateAll          = updateAll;
    window.togglePanelMinimize = togglePanelMinimize;

    try {
        initUI();
        initPerformanceChart();
        initSynapseNetwork();
        initVectorPanel();
        initFullscreen();
        initPositionPanel();
        initStatisticsPanel();
        initNewsPanel();
        initWebSocket();
        startCountdownLoop();

        // Partial save buttons (Trade Settings tab)
        document.querySelectorAll('.btn-partial-save').forEach(btn => {
            btn.addEventListener('click', () => {
                const group = btn.getAttribute('data-group');
                saveManualSettingsGroup(group);
            });
        });

        // System Start button
        const btnSysStart = document.getElementById('btn-system-start');
        if (btnSysStart) {
            btnSysStart.addEventListener('click', async () => {
                btnSysStart.innerHTML = '<span class="spinner spinner-sm"></span> Booting...';
                btnSysStart.disabled = true;
                try {
                    await fetch('/api/system/start', { method: 'POST' });
                } catch (e) {
                    console.error('Start request failed', e);
                }
                setTimeout(updateFastLane, 2000);
            });
        }

        // System Stop button
        const btnSysStop = document.getElementById('btn-system-stop');
        if (btnSysStop) {
            btnSysStop.addEventListener('click', async () => {
                btnSysStop.innerHTML = '<span class="spinner spinner-sm"></span> Halting...';
                btnSysStop.disabled = true;
                try {
                    await fetch('/api/system/stop', { method: 'POST' });
                } catch (e) {
                    console.error('Stop request failed', e);
                }
                setTimeout(updateFastLane, 2000);
            });
        }

        // System Wakeup button
        const btnSysWakeup = document.getElementById('btn-system-wakeup');
        if (btnSysWakeup) {
            btnSysWakeup.addEventListener('click', async () => {
                const originalHtml = btnSysWakeup.innerHTML;
                btnSysWakeup.innerHTML = '<span class="spinner spinner-sm"></span> Waking Up...';
                btnSysWakeup.disabled = true;
                try {
                    const res = await fetch('/api/system/wakeup', { method: 'POST' });
                    if (res.ok) {
                        btnSysWakeup.style.background = '#10b981';
                        btnSysWakeup.textContent = '✅ Working...';
                    } else {
                        const data = await res.json();
                        alert('Error: ' + (data.error || 'Failed to wakeup'));
                    }
                } catch (e) {
                    console.error('Wakeup request failed', e);
                }
                setTimeout(() => {
                    btnSysWakeup.innerHTML = originalHtml;
                    btnSysWakeup.disabled = false;
                    btnSysWakeup.style.background = '#3b82f6';
                    updateFastLane();
                }, 3000);
            });
        }

        // System Buy button
        const btnSysBuy = document.getElementById('btn-system-buy');
        if (btnSysBuy) {
            btnSysBuy.addEventListener('click', async () => {
                const originalHtml = btnSysBuy.innerHTML;
                btnSysBuy.innerHTML = '<span class="spinner spinner-sm"></span> Buying...';
                btnSysBuy.disabled = true;
                try {
                    const res = await fetch('/api/system/manual_buy', { method: 'POST' });
                    if (res.ok) {
                        btnSysBuy.style.background = '#10b981';
                        btnSysBuy.textContent = '✅ Bought';
                    } else {
                        const data = await res.json();
                        alert('Error: ' + (data.error || 'Failed to buy'));
                    }
                } catch (e) {
                    console.error('Buy request failed', e);
                }
                setTimeout(() => {
                    btnSysBuy.innerHTML = originalHtml;
                    btnSysBuy.disabled = false;
                    btnSysBuy.style.background = '#10b981';
                }, 3000);
            });
        }

        // System Sell button
        const btnSysSell = document.getElementById('btn-system-sell');
        if (btnSysSell) {
            btnSysSell.addEventListener('click', async () => {
                const originalHtml = btnSysSell.innerHTML;
                btnSysSell.innerHTML = '<span class="spinner spinner-sm"></span> Selling...';
                btnSysSell.disabled = true;
                try {
                    const res = await fetch('/api/system/manual_sell', { method: 'POST' });
                    if (res.ok) {
                        btnSysSell.style.background = '#ef4444';
                        btnSysSell.textContent = '✅ Sold';
                    } else {
                        const data = await res.json();
                        alert('Error: ' + (data.error || 'Failed to sell'));
                    }
                } catch (e) {
                    console.error('Sell request failed', e);
                }
                setTimeout(() => {
                    btnSysSell.innerHTML = originalHtml;
                    btnSysSell.disabled = false;
                    btnSysSell.style.background = '#ef4444';
                }, 3000);
            });
        }

        // Initial data load

        // Initial data load
        updateAll();
        fetchManualSettings();

        // Polling loops
        setInterval(updateFastLane, state.fastPollInterval);
        setInterval(updateSlowLane, state.slowPollInterval);

        // WebSockets for dashboard modules are implemented per module
        document.addEventListener('analysis-complete', () => {
            updateFastLane();
            updateSlowLane();
        });

    } catch (e) {
        console.error('Error initializing dashboard:', e);
    } finally {
        const loadingEl = document.getElementById('loading');
        if(loadingEl) loadingEl.style.display = 'none';
        const contentEl = document.getElementById('dashboard-content');
        if(contentEl) contentEl.classList.remove('hidden');
    }
}

// ─── Poll Lanes ───────────────────────────────────────────────────────────────

async function updateAll() {
    await updateFastLane();
    await updateSlowLane();
}

async function updateFastLane() {
    await fetchSystemStatus();
    await fetchBrainStatus();
    await updatePositionData();
}

async function updateSlowLane() {
    await fetchRules();
    await fetchCosts();
    await updatePerformanceData();
    await updateSynapses();
    await updateLogs();
    await updateVisuals();
    await updateVectorData();
    await updateStatisticsData();
    await updateNewsData();
}


// ─── Bootstrap ────────────────────────────────────────────────────────────────

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Removed duplicate function declarations that caused SyntaxError

// Wire live override buttons after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const btn      = document.getElementById('btn-live-override');
    const btnPct   = document.getElementById('btn-live-override-pct');
    const msg      = document.getElementById('live-override-msg');

    // Helper to send override
    async function sendOverride(payload, button, originalText) {
        try {
            button.disabled = true;
            button.innerHTML = '<span class="spinner spinner-sm"></span>...';
            const res = await fetch('/api/position/override', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                if (msg) {
                    msg.style.color = '#10b981';
                    msg.textContent = `✅ OK! TP=$${data.take_profit?.toLocaleString()} | SL=$${data.stop_loss?.toLocaleString()}`;
                }
                // Clear inputs
                ['live-override-tp','live-override-sl','live-override-tp-pct','live-override-sl-pct'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = '';
                });
            } else {
                if (msg) { msg.style.color = '#f87171'; msg.textContent = '❌ ' + (data.error || 'Gagal!'); }
            }
        } catch (e) {
            if (msg) { msg.style.color = '#f87171'; msg.textContent = '❌ Network error'; }
        } finally {
            button.disabled = false;
            button.textContent = originalText;
            setTimeout(() => { if (msg) msg.textContent = ''; }, 5000);
        }
    }

    if (btn) {
        btn.addEventListener('click', () => {
            const tp = document.getElementById('live-override-tp')?.value;
            const sl = document.getElementById('live-override-sl')?.value;
            if (!tp && !sl) {
                if (msg) { msg.style.color = '#f87171'; msg.textContent = '⚠ Isi minimal satu nilai!'; }
                return;
            }
            const body = {};
            if (tp) body.take_profit = parseFloat(tp);
            if (sl) body.stop_loss = parseFloat(sl);
            sendOverride(body, btn, '⚡ Set Price');
        });
    }

    if (btnPct) {
        btnPct.addEventListener('click', () => {
            const tpPct = document.getElementById('live-override-tp-pct')?.value;
            const slPct = document.getElementById('live-override-sl-pct')?.value;
            if (!tpPct && !slPct) {
                if (msg) { msg.style.color = '#f87171'; msg.textContent = '⚠ Isi % target!'; }
                return;
            }

            const pos = getLastPosition();
            if (!pos || !pos.entry_price) {
                if (msg) { msg.style.color = '#f87171'; msg.textContent = '❌ Tidak ada posisi aktif untuk menghitung %!'; }
                return;
            }

            const entry = pos.entry_price;
            const isLong = pos.direction === 'LONG';
            const body = {};

            if (tpPct) {
                const p = parseFloat(tpPct) / 100;
                body.take_profit = isLong ? entry * (1 + p) : entry * (1 - p);
            }
            if (slPct) {
                const p = parseFloat(slPct) / 100;
                body.stop_loss = isLong ? entry * (1 - p) : entry * (1 + p);
            }

            sendOverride(body, btnPct, '⚡ Set %');
        });
    }
});

// Force Scan Wake-Up logic
document.addEventListener("DOMContentLoaded", () => {
    const wakeUpBtn = document.getElementById("btn-wake-up");
    if (wakeUpBtn) {
        wakeUpBtn.addEventListener("click", () => {
            const originalHTML = wakeUpBtn.innerHTML;
            wakeUpBtn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:0px;"></span> SCANNIN...';
            wakeUpBtn.disabled = true;
            fetch("/api/settings/wake-up", { method: "POST" })
                .then(r => r.json())
                .then(data => {
                    setTimeout(() => {
                        wakeUpBtn.innerHTML = originalHTML;
                        wakeUpBtn.disabled = false;
                        if (data.status === "success" && window.showToast) {
                            window.showToast("🚀 " + data.message, "success");
                        } else {
                            if (window.showToast) window.showToast(data.message, "error");
                            else alert(data.message);
                        }
                    }, 800);
                })
                .catch(err => {
                    console.error(err);
                    wakeUpBtn.innerHTML = originalHTML;
                    wakeUpBtn.disabled = false;
                    if (window.showToast) window.showToast("Failed to wake up bot", "error");
                    else alert("Failed to wake up bot");
                });
        });
    }

    const btnAutoPilot = document.getElementById("btn-ai-autopilot");
    if (btnAutoPilot) {
        btnAutoPilot.addEventListener("click", async () => {
            if (!confirm("Reset manual configurations and allow AI Auto-Pilot to take control?")) return;
            const originalHTML = btnAutoPilot.innerHTML;
            btnAutoPilot.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:5px;"></span> Resetting...';
            btnAutoPilot.disabled = true;
            try {
                ['setting-sl', 'setting-tp', 'setting-leverage'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = '';
                });
                
                const payload = { stop_loss_pct: 0, take_profit_pct: 0, leverage: 0 };
                
                await fetch('/api/settings/overrides', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                await fetch("/api/settings/wake-up", { method: "POST" });
                
                if (window.showToast) window.showToast("🚀 AI Auto-Pilot Active!", "success");
            } catch(e) {
                console.error(e);
            } finally {
                btnAutoPilot.innerHTML = originalHTML;
                btnAutoPilot.disabled = false;
            }
        });
    }
});
