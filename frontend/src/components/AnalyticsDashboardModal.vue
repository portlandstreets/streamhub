<template>
  <div class="analytics-modal-backdrop" @click.self="$emit('close')">
    <div class="analytics-modal-window">
      <!-- Header -->
      <div class="analytics-modal-header">
        <div class="header-title-wrap">
          <span class="tech-tag">// F1 STATISTICAL VISUALIZATIONS</span>
          <h2>STREAM METRICS &amp; CHART.JS STUDIO</h2>
          <span class="status-indicator live">
            &bull; TELEMETRY ENGINE CONNECTED
          </span>
        </div>
        <div class="header-actions">
          <label class="live-toggle">
            <input type="checkbox" v-model="autoRefresh" />
            <span>LIVE REFRESH (5S)</span>
          </label>
          <button class="win-btn" @click="exportChartsPng" title="Export composite charts as PNG">
            EXPORT CHARTS PNG
          </button>
          <button class="win-btn close" @click="$emit('close')" title="Close">&times;</button>
        </div>
      </div>

      <!-- Filter & Stream Select Bar -->
      <div class="analytics-toolbar">
        <div class="toolbar-cell">
          <span class="toolbar-label">TARGET CHANNEL:</span>
          <select v-model="selectedStreamId" @change="fetchAnalyticsData" class="channel-select">
            <option v-for="st in streams" :key="st.id" :value="st.id">
              {{ st.title }} ({{ st.is_live ? 'LIVE' : 'OFFLINE' }})
            </option>
          </select>
        </div>

        <div class="toolbar-cell">
          <span class="toolbar-label">TIMEFRAME:</span>
          <div class="timeframe-group">
            <button
              v-for="tf in timeframes"
              :key="tf.id"
              class="tf-btn"
              :class="{ active: selectedTimeframe === tf.id }"
              @click="setTimeframe(tf.id)"
            >
              {{ tf.label }}
            </button>
          </div>
        </div>

        <div class="toolbar-cell refresh-cell">
          <button class="refresh-btn" :disabled="isLoading" @click="fetchAnalyticsData">
            {{ isLoading ? 'FETCHING...' : 'REFRESH NOW' }}
          </button>
        </div>
      </div>

      <!-- Modal Body -->
      <div class="analytics-modal-body">
        <!-- KPI Summary Cards -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <span class="kpi-label">PEAK VIEWERS</span>
            <div class="kpi-val">{{ summary.peak_viewers.toLocaleString() }}</div>
            <span class="kpi-sub">CONCURRENT AUDIENCE</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">AVG BITRATE</span>
            <div class="kpi-val">{{ summary.avg_bitrate_kbps.toLocaleString() }} <small>KBPS</small></div>
            <span class="kpi-sub">TARGET: {{ summary.target_bitrate_kbps }} KBPS</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">FRAME STABILITY</span>
            <div class="kpi-val">{{ summary.frame_stability }}</div>
            <span class="kpi-sub">PACKET LOSS: {{ summary.packet_loss_pct }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">HEALTH STATUS</span>
            <div class="kpi-val highlight">{{ summary.health_status }}</div>
            <span class="kpi-sub">TOTAL CHAT: {{ summary.total_chat_messages }} MSGS</span>
          </div>
        </div>

        <!-- Charts Grid (Chart.js) -->
        <div class="charts-grid">
          <!-- Chart 1: Viewers Over Time (Line Chart) -->
          <div class="chart-panel">
            <div class="chart-header">
              <span class="chart-tag">// CHART 1 &bull; LINE</span>
              <h3>CONCURRENT VIEWERS TIMELINE</h3>
              <span class="chart-unit">AUDIENCE COUNT</span>
            </div>
            <div class="canvas-wrap">
              <canvas ref="viewersCanvas"></canvas>
            </div>
          </div>

          <!-- Chart 2: Bitrate Stability (Line Chart with Threshold) -->
          <div class="chart-panel">
            <div class="chart-header">
              <span class="chart-tag">// CHART 2 &bull; HEALTH</span>
              <h3>INGEST BITRATE STABILITY (KBPS)</h3>
              <span class="chart-unit">OBS ENCODER</span>
            </div>
            <div class="canvas-wrap">
              <canvas ref="bitrateCanvas"></canvas>
            </div>
          </div>

          <!-- Chart 3: Chat Velocity (Bar Chart) -->
          <div class="chart-panel">
            <div class="chart-header">
              <span class="chart-tag">// CHART 3 &bull; BARS</span>
              <h3>CHAT ACTIVITY &amp; MESSAGE VELOCITY</h3>
              <span class="chart-unit">MSGS / INTERVAL</span>
            </div>
            <div class="canvas-wrap">
              <canvas ref="chatCanvas"></canvas>
            </div>
          </div>

          <!-- Chart 4: Resolution Breakdown (Doughnut Chart) -->
          <div class="chart-panel">
            <div class="chart-header">
              <span class="chart-tag">// CHART 4 &bull; DOUGHNUT</span>
              <h3>RESOLUTION &amp; CODEC DISTRIBUTION</h3>
              <span class="chart-unit">BANDWIDTH EGRESS</span>
            </div>
            <div class="canvas-wrap doughnut-wrap">
              <canvas ref="resolutionCanvas"></canvas>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="analytics-modal-footer">
        <span class="footer-hint">
          CHART.JS 4.x ENGINE INTEGRATION &bull; REAL-TIME TIME-SERIES TELEMETRY (F1)
        </span>
        <button class="win-btn" @click="$emit('close')">CLOSE DASHBOARD</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { Chart, registerables } from 'chart.js';

// Register all Chart.js controllers, scales, elements and plugins
Chart.register(...registerables);

const props = defineProps({
  coreApi: {
    type: String,
    required: true
  },
  streams: {
    type: Array,
    default: () => []
  },
  initialStreamId: {
    type: Number,
    default: null
  }
});

defineEmits(['close']);

// Canvas refs
const viewersCanvas = ref(null);
const bitrateCanvas = ref(null);
const chatCanvas = ref(null);
const resolutionCanvas = ref(null);

// Chart instances
let viewersChart = null;
let bitrateChart = null;
let chatChart = null;
let resolutionChart = null;

// State
const selectedStreamId = ref(props.initialStreamId || (props.streams[0]?.id ?? 1));
const selectedTimeframe = ref('1h');
const autoRefresh = ref(true);
const isLoading = ref(false);
let refreshTimer = null;

const timeframes = [
  { id: '10m', label: 'LIVE 10M' },
  { id: '1h', label: 'PAST 1 HOUR' },
  { id: '24h', label: 'PAST 24 HOURS' },
  { id: '7d', label: 'PAST 7 DAYS' }
];

const summary = ref({
  peak_viewers: 0,
  avg_viewers: 0,
  avg_bitrate_kbps: 6000,
  target_bitrate_kbps: 6000,
  packet_loss_pct: '0.00%',
  frame_stability: '60.0 FPS',
  health_status: 'EXCELLENT',
  total_chat_messages: 0
});

// Common monochrome Chart.js styling
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  color: '#888888',
  plugins: {
    legend: {
      labels: {
        color: '#aaaaaa',
        font: { family: 'monospace', size: 10 }
      }
    },
    tooltip: {
      backgroundColor: '#111111',
      titleColor: '#ffffff',
      bodyColor: '#cccccc',
      borderColor: '#444444',
      borderWidth: 1,
      padding: 10,
      titleFont: { family: 'monospace', size: 11, weight: 'bold' },
      bodyFont: { family: 'monospace', size: 11 }
    }
  },
  scales: {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#777777', font: { family: 'monospace', size: 9 } }
    },
    y: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#777777', font: { family: 'monospace', size: 9 } }
    }
  }
};

function setTimeframe(tf) {
  selectedTimeframe.value = tf;
  fetchAnalyticsData();
}

async function fetchAnalyticsData() {
  if (!selectedStreamId.value) return;
  isLoading.value = true;
  try {
    const res = await fetch(
      `${props.coreApi}/api/v1/analytics/stream/${selectedStreamId.value}?timeframe=${selectedTimeframe.value}`
    );
    if (!res.ok) throw new Error('Failed to fetch analytics');
    const data = await res.json();

    if (data.summary) {
      summary.value = data.summary;
    }

    renderCharts(data);
  } catch (err) {
    console.error('Error fetching stream analytics:', err);
  } finally {
    isLoading.value = false;
  }
}

function renderCharts(data) {
  const ts = data.time_series;
  if (!ts) return;

  // 1. Concurrent Viewers Line Chart
  if (viewersCanvas.value) {
    if (viewersChart) viewersChart.destroy();
    const ctx = viewersCanvas.value.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 220);
    grad.addColorStop(0, 'rgba(255, 255, 255, 0.22)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0.00)');

    viewersChart = new Chart(viewersCanvas.value, {
      type: 'line',
      data: {
        labels: ts.labels,
        datasets: [{
          label: 'Concurrent Viewers',
          data: ts.viewers,
          borderColor: '#ffffff',
          backgroundColor: grad,
          borderWidth: 2,
          pointBackgroundColor: '#ffffff',
          pointRadius: 3,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.35
        }]
      },
      options: {
        ...chartDefaults,
        scales: {
          ...chartDefaults.scales,
          y: {
            ...chartDefaults.scales.y,
            beginAtZero: true
          }
        }
      }
    });
  }

  // 2. Ingest Bitrate Line Chart (with 6000 kbps target guideline)
  if (bitrateCanvas.value) {
    if (bitrateChart) bitrateChart.destroy();
    const targetArray = new Array(ts.labels.length).fill(6000);

    bitrateChart = new Chart(bitrateCanvas.value, {
      type: 'line',
      data: {
        labels: ts.labels,
        datasets: [
          {
            label: 'Live Bitrate (kbps)',
            data: ts.bitrate_kbps,
            borderColor: '#ffffff',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 5,
            tension: 0.2
          },
          {
            label: 'Optimal Baseline (6,000 kbps)',
            data: targetArray,
            borderColor: '#666666',
            borderDash: [5, 5],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        ...chartDefaults,
        scales: {
          ...chartDefaults.scales,
          y: {
            ...chartDefaults.scales.y,
            min: 5000,
            max: 7000
          }
        }
      }
    });
  }

  // 3. Chat Messages Velocity (Bar Chart)
  if (chatCanvas.value) {
    if (chatChart) chatChart.destroy();
    chatChart = new Chart(chatCanvas.value, {
      type: 'bar',
      data: {
        labels: ts.labels,
        datasets: [{
          label: 'Messages per Interval',
          data: ts.chat_messages,
          backgroundColor: '#ffffff',
          borderColor: '#ffffff',
          borderWidth: 1,
          barPercentage: 0.55
        }]
      },
      options: {
        ...chartDefaults,
        scales: {
          ...chartDefaults.scales,
          y: {
            ...chartDefaults.scales.y,
            beginAtZero: true
          }
        }
      }
    });
  }

  // 4. Resolution Distribution (Doughnut Chart)
  if (resolutionCanvas.value && data.resolution_distribution) {
    if (resolutionChart) resolutionChart.destroy();
    const rd = data.resolution_distribution;

    resolutionChart = new Chart(resolutionCanvas.value, {
      type: 'doughnut',
      data: {
        labels: rd.labels,
        datasets: [{
          data: rd.data,
          backgroundColor: ['#ffffff', '#aaaaaa', '#555555', '#222222'],
          borderColor: '#0a0a0a',
          borderWidth: 2,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              color: '#aaaaaa',
              font: { family: 'monospace', size: 10 },
              padding: 12
            }
          },
          tooltip: chartDefaults.plugins.tooltip
        }
      }
    });
  }
}

function exportChartsPng() {
  if (!viewersCanvas.value) return;
  const url = viewersCanvas.value.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = url;
  a.download = `streamhub-viewers-chart-${selectedStreamId.value}-${Date.now()}.png`;
  a.click();
}

onMounted(async () => {
  await nextTick();
  await fetchAnalyticsData();

  refreshTimer = setInterval(() => {
    if (autoRefresh.value) {
      fetchAnalyticsData();
    }
  }, 5000);
});

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (viewersChart) viewersChart.destroy();
  if (bitrateChart) bitrateChart.destroy();
  if (chatChart) chatChart.destroy();
  if (resolutionChart) resolutionChart.destroy();
});
</script>

<style scoped>
.analytics-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.analytics-modal-window {
  background: #0a0a0a;
  border: 1px solid #333333;
  width: 100%;
  max-width: 1240px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.9);
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  overflow: hidden;
}

/* Header */
.analytics-modal-header {
  height: 56px;
  padding: 0 1.25rem;
  border-bottom: 1px solid #222222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #0e0e0e;
  flex-shrink: 0;
}

.header-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.tech-tag {
  font-family: monospace;
  font-size: 0.75rem;
  color: #888888;
}

.header-title-wrap h2 {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

.status-indicator.live {
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.live-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: monospace;
  font-size: 0.7rem;
  color: #888888;
  cursor: pointer;
  user-select: none;
}

.live-toggle input {
  accent-color: #ffffff;
  cursor: pointer;
}

.win-btn {
  height: 32px;
  padding: 0 0.9rem;
  background: #161616;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 600;
  font-family: monospace;
  cursor: pointer;
  letter-spacing: 0.05em;
  transition: all 0.15s ease;
}

.win-btn:hover {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.win-btn.close {
  font-size: 1.15rem;
  padding: 0 0.75rem;
  line-height: 1;
}

/* Toolbar */
.analytics-toolbar {
  background: #111111;
  border-bottom: 1px solid #222222;
  padding: 0.6rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-shrink: 0;
}

.toolbar-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toolbar-label {
  font-family: monospace;
  font-size: 0.72rem;
  color: #777777;
}

.channel-select {
  height: 30px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.72rem;
  padding: 0 0.6rem;
  cursor: pointer;
}

.timeframe-group {
  display: flex;
  gap: 0.25rem;
}

.tf-btn {
  height: 28px;
  padding: 0 0.65rem;
  background: #161616;
  border: 1px solid #282828;
  color: #888888;
  font-family: monospace;
  font-size: 0.68rem;
  cursor: pointer;
  transition: all 0.15s;
}

.tf-btn:hover {
  border-color: #555555;
  color: #ffffff;
}

.tf-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

.refresh-cell {
  margin-left: auto;
}

.refresh-btn {
  height: 28px;
  padding: 0 0.8rem;
  background: #181818;
  border: 1px solid #333333;
  color: #cccccc;
  font-family: monospace;
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
}

.refresh-btn:hover:not(:disabled) {
  background: #ffffff;
  color: #000000;
}

/* Modal Body */
.analytics-modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  flex: 1;
}

/* KPI Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.85rem;
}

.kpi-card {
  background: #101010;
  border: 1px solid #242424;
  padding: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.kpi-label {
  font-family: monospace;
  font-size: 0.68rem;
  color: #777777;
  letter-spacing: 0.05em;
}

.kpi-val {
  font-family: monospace;
  font-size: 1.35rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.02em;
}

.kpi-val small {
  font-size: 0.75rem;
  color: #888888;
}

.kpi-val.highlight {
  font-size: 1.05rem;
  font-weight: 700;
}

.kpi-sub {
  font-family: monospace;
  font-size: 0.68rem;
  color: #555555;
}

/* Charts Grid */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.chart-panel {
  background: #0d0d0d;
  border: 1px solid #222222;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  height: 290px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
  border-bottom: 1px solid #1a1a1a;
  padding-bottom: 0.4rem;
}

.chart-tag {
  font-family: monospace;
  font-size: 0.68rem;
  color: #666666;
}

.chart-header h3 {
  font-size: 0.82rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0.04em;
  color: #ffffff;
}

.chart-unit {
  font-family: monospace;
  font-size: 0.68rem;
  color: #888888;
}

.canvas-wrap {
  flex: 1;
  position: relative;
  min-height: 0;
}

.doughnut-wrap {
  padding: 0.5rem 0;
}

/* Footer */
.analytics-modal-footer {
  height: 48px;
  padding: 0 1.25rem;
  border-top: 1px solid #222222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #0e0e0e;
  flex-shrink: 0;
}

.footer-hint {
  font-family: monospace;
  font-size: 0.7rem;
  color: #666666;
}
</style>
