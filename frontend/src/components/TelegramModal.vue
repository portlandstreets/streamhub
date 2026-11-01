<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="telegram-modal">
      <div class="modal-header">
        <div class="header-titles">
          <h3>// TELEGRAM BOT &amp; WEBHOOK INTEGRATION (B2)</h3>
          <span class="header-sub">Outbound Event Webhooks &amp; Telegram Bot API</span>
        </div>
        <button class="icon-close-btn" @click="$emit('close')" aria-label="Close">✕</button>
      </div>

      <div class="modal-body">
        <!-- Configuration & Status -->
        <div class="tele-status-grid">
          <div class="status-card">
            <span class="label">BOT HANDLE</span>
            <strong>@StreamHubAlertBot</strong>
          </div>
          <div class="status-card">
            <span class="label">TARGET CHANNEL</span>
            <strong>{{ currentChatId }}</strong>
          </div>
          <div class="status-card">
            <span class="label">WEBHOOK ENDPOINT</span>
            <code>/api/webhooks/telegram</code>
          </div>
          <div class="status-card">
            <span class="label">INTEGRATION STATE</span>
            <span class="badge-online">ACTIVE / LISTENING</span>
          </div>
        </div>

        <!-- Feedback Messages -->
        <div v-if="feedbackMsg" class="tele-alert" :class="feedbackType">
          {{ feedbackMsg }}
        </div>

        <!-- Action Controls -->
        <div class="tele-actions-panel">
          <div class="panel-heading-row">
            <span class="panel-heading">// DISPATCH ACTIONS</span>
            <span class="stream-status-tag" :class="{ live: hasAnyLiveStream }">
              {{ hasAnyLiveStream ? `${liveStreamObj?.title} (@${liveStreamObj?.owner}): LIVE NOW` : 'СТАТУС: НЕМАЄ АКТИВНИХ СТРІМІВ (OFFLINE)' }}
            </span>
          </div>

          <div class="actions-row">
            <button
              class="action-btn"
              :class="{ primary: hasAnyLiveStream }"
              :disabled="loading"
              @click="broadcastLiveAlert"
            >
              BROADCAST STREAM ALERT
            </button>
            <button
              class="action-btn"
              :disabled="loading"
              @click="sendTestAlert"
            >
              SEND TEST PING
            </button>
            <button
              class="action-btn"
              :disabled="loading"
              @click="simulateBotCommand('/live')"
            >
              SIMULATE /live BOT CMD
            </button>
            <button
              class="action-btn"
              :disabled="loading"
              @click="simulateBotCommand('/status')"
            >
              SIMULATE /status BOT CMD
            </button>
          </div>
        </div>

        <!-- Target Chat Configuration -->
        <div class="config-row">
          <div class="input-group">
            <label>CUSTOM TELEGRAM CHAT / CHANNEL ID:</label>
            <div class="input-with-button">
              <input
                v-model="editChatId"
                type="text"
                placeholder="@streamhub_live_alerts or chat ID"
              />
              <button class="action-btn" :disabled="loading" @click="saveTargetChat">
                UPDATE CHANNEL
              </button>
            </div>
          </div>
        </div>

        <!-- Delivery Audit Log -->
        <div class="audit-section">
          <div class="audit-header">
            <span>// RECENT WEBHOOK &amp; BOT DISPATCH LOGS ({{ historyItems.length }})</span>
            <button class="action-btn small-btn" :disabled="loading" @click="loadStatusAndHistory">
              REFRESH LOG
            </button>
          </div>

          <div v-if="historyItems.length === 0" class="empty-log">
            No notifications dispatched yet. Click "SEND TEST PING" or "BROADCAST STREAM ALERT" above.
          </div>

          <div v-else class="log-table-wrap">
            <table class="log-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>CHAT ID</th>
                  <th>EVENT MESSAGE PREVIEW</th>
                  <th>MODE</th>
                  <th>STATUS</th>
                  <th>TIMESTAMP</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in historyItems" :key="item.id">
                  <td>#{{ item.id }}</td>
                  <td><code>{{ item.chat_id }}</code></td>
                  <td class="preview-cell">
                    <span class="raw-preview">{{ stripHtml(item.text) }}</span>
                  </td>
                  <td><span class="mode-tag">{{ item.mode }}</span></td>
                  <td><span class="status-tag">{{ item.status }}</span></td>
                  <td class="time-cell">{{ formatTime(item.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <span class="footer-hint">B2 Requirement: Telegram Bot &amp; Webhooks Integration</span>
        <button class="action-btn" @click="$emit('close')">CLOSE</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';

const props = defineProps({
  coreApi: {
    type: String,
    required: true,
  },
  streams: {
    type: Array,
    default: () => [],
  },
  streamId: {
    type: Number,
    default: null,
  },
  accessToken: {
    type: String,
    default: '',
  },
  streamTitle: {
    type: String,
    default: 'Live Stream',
  },
  streamOwner: {
    type: String,
    default: 'vlasniktest',
  },
  isLive: {
    type: Boolean,
    default: false,
  },
});

defineEmits(['close']);

const selectedStreamId = ref(props.streamId);

// Auto-select live stream if any is live, or user stream
watch(
  () => props.streams,
  (list) => {
    if (!list || !list.length) return;
    const live = list.find((s) => s.is_live);
    if (live) {
      selectedStreamId.value = live.id;
    } else if (!selectedStreamId.value && list.length > 0) {
      selectedStreamId.value = list[0].id;
    }
  },
  { immediate: true }
);

const liveStreamObj = computed(() => {
  return (props.streams || []).find((s) => s.is_live) || (props.isLive ? {
    id: props.streamId,
    title: props.streamTitle,
    owner: props.streamOwner,
    is_live: true,
  } : null);
});

const hasAnyLiveStream = computed(() => Boolean(liveStreamObj.value));

const storedChatId = localStorage.getItem('telegram_target_chat') || '';
const currentChatId = ref(storedChatId || '@my_streamhub_alert');
const editChatId = ref(storedChatId || '@my_streamhub_alert');
const historyItems = ref([]);
const loading = ref(false);
const feedbackMsg = ref('');
const feedbackType = ref('success');

const REAL_BOT_TOKEN = '9059448823:AAFUOz9KafTIn-S9Qy2a_miErMnGUnS9PQU';

const authHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const token = props.accessToken || localStorage.getItem('stream_token') || localStorage.getItem('access_token') || '';
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const showFeedback = (msg, type = 'success') => {
  feedbackMsg.value = msg;
  feedbackType.value = type;
  setTimeout(() => {
    if (feedbackMsg.value === msg) {
      feedbackMsg.value = '';
    }
  }, 5000);
};

const stripHtml = (html) => {
  if (!html) return '';
  return html.replace(/<[^>]*>?/gm, '').slice(0, 100);
};

const formatTime = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString();
  } catch {
    return iso;
  }
};

const loadStatusAndHistory = async () => {
  loading.value = true;
  try {
    const res = await fetch(`${props.coreApi}/api/telegram/status`);
    if (res.ok) {
      const data = await res.json();
      const saved = localStorage.getItem('telegram_target_chat');
      if (saved) {
        currentChatId.value = saved;
        editChatId.value = saved;
      } else if (data.target_chat_id) {
        currentChatId.value = data.target_chat_id;
        editChatId.value = data.target_chat_id;
      }
      historyItems.value = (data.recent_events || []).slice().reverse();
    }
  } catch (err) {
    console.error('Error fetching Telegram status:', err);
  } finally {
    loading.value = false;
  }
};

const broadcastLiveAlert = async () => {
  if (!hasAnyLiveStream.value) {
    showFeedback('Зараз немає жодного активного стріму (OFFLINE). Запустіть трансляцію в OBS, щоб сповістити підписників.', 'error');
    return;
  }
  loading.value = true;
  feedbackMsg.value = '';
  try {
    const targetStream = liveStreamObj.value;
    const ownerName = targetStream?.owner || props.streamOwner || 'vlasniktest';
    const streamName = targetStream?.title || props.streamTitle || 'Live Stream';
    const alertText = `<b>🔴 СТРІМ У ПРЯМОМУ ЕФІРІ!</b>\n\n<b>Канал:</b> @${ownerName}\n<b>Назва стріму:</b> ${streamName}`;
    const targetChat = currentChatId.value || localStorage.getItem('telegram_target_chat') || '@my_streamhub_alert';

    // Direct Telegram Bot API dispatch
    try {
      const directRes = await fetch(`https://api.telegram.org/bot${REAL_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: targetChat,
          text: alertText,
          parse_mode: 'HTML',
        }),
      });
      const directData = await directRes.json();
      if (!directRes.ok) {
        showFeedback(directData.description || 'Помилка Telegram API', 'error');
        return;
      }
    } catch (directErr) {
      console.warn('Direct telegram dispatch error:', directErr);
    }

    if (targetStream?.id) {
      try {
        await fetch(`${props.coreApi}/api/streams/${targetStream.id}/telegram/notify`, {
          method: 'POST',
          headers: authHeaders(),
        });
      } catch (backendErr) {
        console.warn('Backend stream notify error:', backendErr);
      }
    }

    showFeedback(`Сповіщення про активний стрім надіслано в Telegram: @${ownerName} — ${streamName}`);
    await loadStatusAndHistory();
  } catch (err) {
    showFeedback(err.message || 'Error broadcasting to Telegram', 'error');
  } finally {
    loading.value = false;
  }
};

const sendTestAlert = async () => {
  loading.value = true;
  feedbackMsg.value = '';
  try {
    const targetChat = currentChatId.value || localStorage.getItem('telegram_target_chat') || '@streamhub_live_alerts';
    const testText = `<b>STREAMHUB TELEGRAM TEST</b>\n\nПідключення бота працює коректно.\nЧат ID: <code>${targetChat}</code>`;
    try {
      const directRes = await fetch(`https://api.telegram.org/bot${REAL_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: targetChat,
          text: testText,
          parse_mode: 'HTML',
        }),
      });
      const directData = await directRes.json();
      if (!directRes.ok) {
        showFeedback(directData.description || 'Помилка Telegram API', 'error');
      }
    } catch (directErr) {
      console.warn('Direct test dispatch error:', directErr);
    }

    try {
      await fetch(`${props.coreApi}/api/telegram/test`, {
        method: 'POST',
        headers: authHeaders(),
      });
    } catch (backendErr) {
      console.warn('Backend test ping error:', backendErr);
    }

    showFeedback(`Тестове сповіщення надіслано до Telegram (${targetChat})`);
    await loadStatusAndHistory();
  } catch (err) {
    showFeedback(err.message || 'Error sending test ping', 'error');
  } finally {
    loading.value = false;
  }
};

const simulateBotCommand = async (command) => {
  loading.value = true;
  feedbackMsg.value = '';
  try {
    const res = await fetch(`${props.coreApi}/api/webhooks/telegram/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Simulation failed');
    showFeedback(`Bot responded to ${command}: "${stripHtml(data.preview || '')}"`);
    await loadStatusAndHistory();
  } catch (err) {
    showFeedback(err.message || 'Error executing bot simulation', 'error');
  } finally {
    loading.value = false;
  }
};

const saveTargetChat = async () => {
  const newChat = editChatId.value.trim();
  if (!newChat) return;
  loading.value = true;
  try {
    localStorage.setItem('telegram_target_chat', newChat);
    currentChatId.value = newChat;

    const res = await fetch(`${props.coreApi}/api/telegram/config`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        chat_id: newChat,
        bot_token: REAL_BOT_TOKEN,
        enabled: true,
      }),
    });
    const data = await res.json();
    if (res.ok && data.target_chat_id) {
      currentChatId.value = data.target_chat_id;
      editChatId.value = data.target_chat_id;
      localStorage.setItem('telegram_target_chat', data.target_chat_id);
    }
    showFeedback(`Telegram bot linked to ${currentChatId.value}!`);
    await loadStatusAndHistory();
  } catch (err) {
    showFeedback(err.message || 'Error saving channel', 'error');
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  const savedChat = localStorage.getItem('telegram_target_chat');
  try {
    const configBody = {
      bot_token: REAL_BOT_TOKEN,
      enabled: true,
    };
    if (savedChat) {
      configBody.chat_id = savedChat;
    }
    await fetch(`${props.coreApi}/api/telegram/config`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(configBody),
    });
  } catch (_) {}
  await loadStatusAndHistory();
});
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.telegram-modal {
  background: #0a0a0a;
  border: 1px solid #ffffff;
  width: 100%;
  max-width: 820px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  color: #ffffff;
  font-family: inherit;
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.9);
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

.tele-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.status-card {
  background: #141414;
  border: 1px solid #222222;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-card .label {
  font-size: 10px;
  color: #777777;
  letter-spacing: 0.06em;
  font-family: monospace;
}

.status-card strong {
  font-size: 13px;
  color: #ffffff;
}

.status-card code {
  font-size: 11px;
  color: #bbbbbb;
  font-family: monospace;
}

.badge-online {
  font-size: 10px;
  font-weight: 700;
  color: #000000;
  background: #ffffff;
  padding: 2px 6px;
  width: fit-content;
  letter-spacing: 0.05em;
}

.tele-alert {
  padding: 10px 14px;
  font-size: 12px;
  font-family: monospace;
  border: 1px solid #ffffff;
}

.tele-alert.success {
  background: #181818;
  color: #ffffff;
  border-color: #555555;
}

.tele-alert.error {
  background: #2a1010;
  color: #ff8888;
  border-color: #ff4444;
}

.tele-actions-panel {
  background: #111111;
  border: 1px solid #222222;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-heading-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.stream-status-tag {
  font-size: 11px;
  font-family: monospace;
  padding: 2px 8px;
  border: 1px solid #444444;
  background: #1a1a1a;
  color: #aaaaaa;
}

.stream-status-tag.live {
  background: #2a1010;
  border-color: #ff3333;
  color: #ff5555;
  font-weight: 700;
}

.stream-picker-row {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #141414;
  padding: 8px 10px;
  border: 1px solid #222222;
}

.picker-label {
  font-size: 11px;
  color: #888888;
  font-family: monospace;
  white-space: nowrap;
}

.stream-picker-select {
  flex: 1;
  background: #000000;
  color: #ffffff;
  border: 1px solid #444444;
  padding: 5px 8px;
  font-size: 12px;
  font-family: inherit;
  outline: none;
}

.panel-heading {
  font-size: 11px;
  font-weight: 700;
  color: #888888;
  letter-spacing: 0.06em;
  font-family: monospace;
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

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.small-btn {
  height: 26px;
  padding: 0 10px;
  font-size: 10px;
}

.config-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  display: block;
  font-size: 10px;
  color: #888888;
  font-family: monospace;
  margin-bottom: 6px;
  letter-spacing: 0.05em;
}

.input-with-button {
  display: flex;
  gap: 8px;
}

.input-with-button input {
  flex: 1;
  background: #141414;
  border: 1px solid #2a2a2a;
  color: #ffffff;
  padding: 0 12px;
  height: 32px;
  font-size: 12px;
  outline: none;
  font-family: monospace;
}

.input-with-button input:focus {
  border-color: #ffffff;
}

.audit-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.audit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #888888;
  letter-spacing: 0.05em;
  font-family: monospace;
}

.empty-log {
  background: #111111;
  border: 1px dashed #262626;
  padding: 24px;
  text-align: center;
  font-size: 12px;
  color: #666666;
  font-family: monospace;
}

.log-table-wrap {
  border: 1px solid #222222;
  max-height: 220px;
  overflow-y: auto;
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  text-align: left;
}

.log-table th {
  background: #141414;
  padding: 8px 12px;
  border-bottom: 1px solid #262626;
  color: #777777;
  font-family: monospace;
  font-size: 10px;
  letter-spacing: 0.05em;
}

.log-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #1a1a1a;
  color: #cccccc;
}

.preview-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.raw-preview {
  font-family: monospace;
  font-size: 10px;
}

.mode-tag {
  font-family: monospace;
  font-size: 9px;
  background: #1c1c1c;
  border: 1px solid #333333;
  padding: 2px 6px;
  color: #aaaaaa;
}

.status-tag {
  font-family: monospace;
  font-size: 9px;
  background: #ffffff;
  color: #000000;
  font-weight: 700;
  padding: 2px 6px;
}

.time-cell {
  font-family: monospace;
  font-size: 10px;
  color: #777777;
  white-space: nowrap;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-top: 1px solid #222222;
  background: #111111;
}

.footer-hint {
  font-size: 11px;
  color: #666666;
  font-family: monospace;
}
</style>
