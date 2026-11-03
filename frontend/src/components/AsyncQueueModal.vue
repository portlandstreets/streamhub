<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="queue-modal">
      <!-- Modal Header -->
      <div class="modal-header">
        <div class="header-titles">
          <h3>// ASYNCHRONOUS MESSAGE QUEUE &amp; WORKERS</h3>
          <span class="header-sub">
            Producer-Consumer Architecture &middot; Durable RabbitMQ Queue
          </span>
        </div>
        <button class="icon-close-btn" @click="$emit('close')" aria-label="Close">✕</button>
      </div>

      <div class="modal-body">
        <!-- Queue Broker Statistics -->
        <div class="stats-grid">
          <div class="stat-card">
            <span class="label">BROKER ENGINE</span>
            <strong>{{ queueStats.broker || 'RabbitMQ / Redis Streams' }}</strong>
            <span class="sub-label">{{ queueStats.queue_name || 'streamhub.jobs.transcode' }}</span>
          </div>
          <div class="stat-card">
            <span class="label">ACTIVE WORKERS</span>
            <div class="worker-badge-row">
              <span :class="queueStats.status === 'RUNNING' ? 'badge-online' : 'badge-offline'">
                {{ queueStats.status || 'UNAVAILABLE' }}
              </span>
              <strong>{{ queueStats.active_workers || 0 }} Workers</strong>
            </div>
            <span class="sub-label">Asynchronous ACK/NACK Consumers</span>
          </div>
          <div class="stat-card">
            <span class="label">QUEUE DEPTH (PENDING)</span>
            <strong class="metric-num">{{ queueStats.pending_jobs_depth ?? 0 }}</strong>
            <span class="sub-label">{{ queueStats.processing_jobs ?? 0 }} Currently Processing</span>
          </div>
          <div class="stat-card">
            <span class="label">COMPLETED TASKS</span>
            <strong class="metric-num">{{ queueStats.total_processed ?? 0 }}</strong>
            <span class="sub-label">{{ queueStats.failed_jobs ?? 0 }} Failed</span>
          </div>
        </div>

        <!-- Producer Actions Panel -->
        <div class="producer-panel">
          <div class="panel-header">
            <span>// PRODUCER: DISPATCH BACKGROUND JOBS</span>
            <span class="poll-badge">LIVE AUTO-POLLING (1.5s)</span>
          </div>
          <div class="actions-row">
            <select v-model.number="selectedRecordingId" class="recording-select">
              <option :value="0" disabled>Select a saved video</option>
              <option
                v-for="recording in recordings"
                :key="recording.id"
                :value="recording.id"
              >
                {{ recording.title }} / {{ recording.stream_title }}
              </option>
            </select>
            <button
              class="action-btn primary"
              :disabled="loading || !selectedRecording"
              @click="enqueueJob('transcode_vod')"
            >
              + ENQUEUE VOD TRANSCODE
            </button>
            <button
              class="action-btn"
              :disabled="loading || !selectedRecording"
              @click="enqueueJob('extract_thumbnails')"
            >
              + ENQUEUE THUMBNAILS EXTRACTOR
            </button>
            <button
              class="action-btn secondary"
              :disabled="loading"
              @click="fetchJobs"
            >
              REFRESH
            </button>
          </div>
        </div>

        <!-- Feedback Alert -->
        <div v-if="feedbackMsg" class="feedback-banner">
          {{ feedbackMsg }}
        </div>

        <!-- Asynchronous Jobs List & Real-time Progress -->
        <div class="jobs-table-container">
          <div class="table-header">
            <span>// ASYNCHRONOUS JOBS EXECUTION LOG ({{ jobsList.length }})</span>
            <span class="table-sub">Real-time status updates from consumer worker pool</span>
          </div>

          <div v-if="jobsList.length === 0" class="empty-jobs">
            No background video jobs dispatched yet. Select an uploaded video to process it.
          </div>

          <div v-else class="table-scroll-wrap">
            <table class="jobs-table">
              <thead>
                <tr>
                  <th>JOB ID</th>
                  <th>TASK TYPE</th>
                  <th>WORKER</th>
                  <th>PROGRESS</th>
                  <th>STATUS</th>
                  <th>CURRENT EXECUTION STEP</th>
                  <th>DURATION</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in jobsList" :key="job.id" :class="job.status.toLowerCase()">
                  <td><code>{{ job.id }}</code></td>
                  <td><span class="type-badge">{{ formatJobType(job.type) }}</span></td>
                  <td><span class="worker-tag">{{ job.worker_id || 'Awaiting' }}</span></td>
                  <td class="progress-col">
                    <div class="progress-bar-wrap">
                      <div
                        class="progress-fill"
                        :style="{ width: `${job.progress}%` }"
                        :class="{ completed: job.status === 'COMPLETED' }"
                      ></div>
                    </div>
                    <span class="progress-text">{{ job.progress }}%</span>
                  </td>
                  <td>
                    <span class="status-tag" :class="job.status.toLowerCase()">
                      {{ job.status }}
                    </span>
                  </td>
                  <td class="step-cell">
                    <span class="step-desc">{{ job.current_step }}</span>
                  </td>
                  <td class="time-cell">
                    {{ job.duration_seconds > 0 ? `${job.duration_seconds}s` : '...' }}
                  </td>
                  <td>
                    <button
                      v-if="job.status === 'QUEUED'"
                      class="cancel-btn"
                      @click="cancelJob(job.id)"
                    >
                      CANCEL
                    </button>
                    <span v-else class="done-tag">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="modal-footer">
        <span class="footer-note">B8 Requirement: Asynchronous Background Processing with Message Queues</span>
        <button class="action-btn" @click="$emit('close')">CLOSE</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  coreApi: {
    type: String,
    required: true,
  },
  streamId: {
    type: Number,
    default: null,
  },
  currentUserId: {
    type: Number,
    default: null,
  },
});

defineEmits(['close']);

const queueStats = ref({});
const jobsList = ref([]);
const recordings = ref([]);
const selectedRecordingId = ref(0);
const loading = ref(false);
const feedbackMsg = ref('');
let pollInterval = null;
const selectedRecording = computed(() =>
  recordings.value.find((recording) => recording.id === selectedRecordingId.value)
);

const formatJobType = (t) => {
  switch (t) {
    case 'transcode_vod':
      return 'VOD TRANSCODE';
    case 'extract_thumbnails':
      return 'THUMBNAILS';
    default:
      return (t || 'TASK').toUpperCase();
  }
};

const fetchJobs = async () => {
  try {
    const res = await fetch(`${props.coreApi}/api/queue/jobs?limit=50`);
    if (res.ok) {
      const data = await res.json();
      jobsList.value = data.items || [];
      if (data.queue_stats) {
        queueStats.value = data.queue_stats;
      }
    }
  } catch (err) {
    console.error('Error fetching queue jobs:', err);
  }
};

const fetchStats = async () => {
  try {
    const res = await fetch(`${props.coreApi}/api/queue/stats`);
    if (res.ok) {
      queueStats.value = await res.json();
    }
  } catch (err) {
    console.error('Error fetching queue stats:', err);
  }
};

const fetchRecordings = async () => {
  try {
    const res = await fetch(`${props.coreApi}/api/recordings?skip=0&limit=100`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not load saved videos');
    recordings.value = (data.items || []).filter((recording) =>
      Number(recording.user_id) === Number(props.currentUserId)
      && (!props.streamId || recording.stream_id === props.streamId)
    );
    if (!selectedRecording.value && recordings.value.length) {
      selectedRecordingId.value = recordings.value[0].id;
    }
  } catch (err) {
    feedbackMsg.value = err instanceof Error ? err.message : 'Could not load saved videos';
  }
};

const enqueueJob = async (type) => {
  loading.value = true;
  feedbackMsg.value = '';
  try {
    if (!selectedRecording.value) {
      throw new Error('Select one of your saved videos first.');
    }
    const token = localStorage.getItem('stream_token') || localStorage.getItem('access_token') || '';
    const headers = { 'Content-Type': 'application/json' };
    if (!token) throw new Error('Sign in before starting video processing.');
    headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${props.coreApi}/api/queue/jobs`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        type,
        stream_id: selectedRecording.value.stream_id,
        file_path: selectedRecording.value.file_path,
        options: { recording_id: selectedRecording.value.id },
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to enqueue job');
    feedbackMsg.value = `Dispatched ${formatJobType(type)} (ID: ${data.job_id}) to message queue!`;
    await fetchJobs();
    setTimeout(() => {
      if (feedbackMsg.value.includes(data.job_id)) feedbackMsg.value = '';
    }, 4000);
  } catch (err) {
    feedbackMsg.value = err.message || 'Error enqueuing job';
  } finally {
    loading.value = false;
  }
};

const cancelJob = async (jobId) => {
  try {
    const token = localStorage.getItem('stream_token') || localStorage.getItem('access_token') || '';
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${props.coreApi}/api/queue/jobs/${jobId}/cancel`, {
      method: 'POST',
      headers,
    });
    if (res.ok) {
      await fetchJobs();
    }
  } catch (err) {
    console.error('Error cancelling job:', err);
  }
};

onMounted(async () => {
  await fetchRecordings();
  await fetchJobs();
  await fetchStats();
  // Auto-poll while modal is open to animate progress bars in real-time
  pollInterval = setInterval(fetchJobs, 1200);
});

onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.queue-modal {
  background: #0a0a0a;
  border: 1px solid #ffffff;
  width: 100%;
  max-width: 960px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  color: #ffffff;
  font-family: inherit;
  box-shadow: 0 0 50px rgba(0, 0, 0, 0.95);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 24px;
  border-bottom: 1px solid #222222;
  background: #111111;
}

.header-titles h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #ffffff;
}

.header-sub {
  font-size: 11px;
  color: #888888;
  letter-spacing: 0.04em;
  margin-top: 4px;
  display: block;
}

.icon-close-btn {
  background: transparent;
  border: none;
  color: #888888;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  line-height: 1;
}

.icon-close-btn:hover {
  color: #ffffff;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.stat-card {
  background: #121212;
  border: 1px solid #222222;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-card .label {
  font-size: 10px;
  color: #777777;
  letter-spacing: 0.06em;
  font-family: monospace;
}

.stat-card strong {
  font-size: 13px;
  color: #ffffff;
}

.metric-num {
  font-size: 20px;
  font-family: monospace;
  color: #ffffff;
}

.sub-label {
  font-size: 10px;
  color: #888888;
  font-family: monospace;
}

.worker-badge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge-online {
  font-size: 9px;
  font-weight: 700;
  background: #ffffff;
  color: #000000;
  padding: 2px 5px;
}

.badge-offline {
  font-size: 9px;
  font-weight: 700;
  background: #482828;
  color: #ffb0b0;
  padding: 2px 5px;
}

.recording-select {
  min-width: 220px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #333;
  background: #000;
  color: #eee;
}

.producer-panel {
  background: #111111;
  border: 1px solid #222222;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #888888;
  font-family: monospace;
}

.poll-badge {
  font-size: 9px;
  color: #666666;
  border: 1px solid #262626;
  padding: 2px 6px;
}

.actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-btn {
  height: 32px;
  padding: 0 14px;
  background: #000000;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: #222222;
  border-color: #ffffff;
}

.action-btn.primary {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.action-btn.primary:hover:not(:disabled) {
  background: #dddddd;
  border-color: #dddddd;
}

.action-btn.secondary {
  color: #888888;
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.feedback-banner {
  background: #181818;
  border: 1px solid #ffffff;
  color: #ffffff;
  padding: 10px 14px;
  font-size: 12px;
  font-family: monospace;
}

.jobs-table-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: monospace;
  font-size: 11px;
  color: #888888;
}

.table-sub {
  font-size: 10px;
  color: #666666;
}

.empty-jobs {
  background: #111111;
  border: 1px dashed #262626;
  padding: 28px;
  text-align: center;
  font-size: 12px;
  color: #666666;
  font-family: monospace;
}

.table-scroll-wrap {
  border: 1px solid #222222;
  max-height: 280px;
  overflow-y: auto;
}

.jobs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  text-align: left;
}

.jobs-table th {
  background: #141414;
  padding: 8px 10px;
  border-bottom: 1px solid #262626;
  color: #777777;
  font-family: monospace;
  font-size: 10px;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.jobs-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #1a1a1a;
  color: #cccccc;
}

.type-badge {
  font-family: monospace;
  font-size: 10px;
  background: #1c1c1c;
  border: 1px solid #333333;
  padding: 2px 6px;
  color: #ffffff;
  white-space: nowrap;
}

.worker-tag {
  font-family: monospace;
  font-size: 10px;
  color: #888888;
  white-space: nowrap;
}

.progress-col {
  min-width: 120px;
}

.progress-bar-wrap {
  width: 100%;
  height: 6px;
  background: #222222;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background: #ffffff;
  transition: width 0.3s ease;
}

.progress-fill.completed {
  background: #ffffff;
}

.progress-text {
  font-family: monospace;
  font-size: 10px;
  color: #888888;
}

.status-tag {
  font-family: monospace;
  font-size: 9px;
  padding: 2px 6px;
  font-weight: 700;
  white-space: nowrap;
}

.status-tag.queued {
  background: #2a2a2a;
  color: #aaaaaa;
}

.status-tag.processing {
  background: #ffffff;
  color: #000000;
  animation: pulse-tag 1s infinite alternate;
}

.status-tag.completed {
  background: #ffffff;
  color: #000000;
}

.status-tag.failed {
  background: #ff4444;
  color: #000000;
}

.status-tag.cancelled {
  background: #444444;
  color: #999999;
}

@keyframes pulse-tag {
  from { opacity: 0.8; }
  to { opacity: 1; }
}

.step-cell {
  max-width: 220px;
}

.step-desc {
  font-family: monospace;
  font-size: 10px;
  color: #aaaaaa;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-cell {
  font-family: monospace;
  font-size: 10px;
  color: #888888;
  white-space: nowrap;
}

.cancel-btn {
  background: transparent;
  border: 1px solid #444444;
  color: #888888;
  font-size: 9px;
  font-family: monospace;
  padding: 2px 6px;
  cursor: pointer;
}

.cancel-btn:hover {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.done-tag {
  color: #444444;
  font-family: monospace;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-top: 1px solid #222222;
  background: #111111;
}

.footer-note {
  font-size: 11px;
  color: #666666;
  font-family: monospace;
}
</style>
