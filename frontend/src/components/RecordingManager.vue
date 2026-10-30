<template>
  <section class="recording-manager">
    <header class="recording-header">
      <div class="header-title-wrap">
        <h3>RECORDINGS <span>{{ recordings.length.toString().padStart(2, '0') }}</span></h3>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="loadRecordings" :disabled="loading">
          {{ loading ? 'LOADING...' : 'REFRESH' }}
        </button>
      </div>
    </header>

    <form v-if="canManage" class="recording-upload" @submit.prevent="uploadRecording">
      <div class="upload-controls">
        <label class="custom-file-btn">
          <input
            ref="fileInput"
            type="file"
            accept=".mp4,.webm,.mkv,.mov,video/mp4,video/webm,video/quicktime"
            required
            @change="onFileSelected"
          />
          <span>{{ selectedFileName ? selectedFileName : 'CHOOSE VIDEO FILE' }}</span>
        </label>
        <div class="duration-box">
          <span class="unit-tag">SEC</span>
          <input
            v-model.number="uploadDuration"
            type="number"
            min="0"
            placeholder="0"
            aria-label="Recording duration in seconds"
          />
        </div>
        <button
          class="action-btn primary"
          type="submit"
          :disabled="saving || (preflight && !preflight.isValidVideo)"
        >
          {{ saving ? 'UPLOADING...' : 'UPLOAD RECORDING' }}
        </button>
      </div>

      <!-- Low-Level File API Pre-Flight Inspection Card -->
      <div v-if="preflight" class="file-api-card">
        <div class="card-top-bar">
          <span class="api-tag">CLIENT-SIDE PRE-FLIGHT INSPECTION</span>
          <span :class="['validation-pill', preflight.isValidVideo ? 'valid' : 'invalid']">
            {{ preflight.isValidVideo ? 'VALID FORMAT' : 'INVALID FORMAT' }}
          </span>
        </div>

        <div class="card-content">
          <!-- Canvas Thumbnail Preview -->
          <div v-if="preflight.thumbnailUrl" class="thumb-container">
            <img :src="preflight.thumbnailUrl" alt="Video Frame Preview" />
            <span class="thumb-badge">CANVAS FRAME</span>
          </div>

          <div class="preflight-details">
            <div class="detail-row">
              <span class="lbl">NAME:</span>
              <span class="val">{{ preflight.name }} ({{ preflight.formattedSize }})</span>
            </div>
            <div class="detail-row">
              <span class="lbl">CONTAINER:</span>
              <span class="val highlight">{{ preflight.detectedFormat }}</span>
            </div>
            <div class="detail-row" v-if="preflight.dimensions">
              <span class="lbl">DIMENSIONS:</span>
              <span class="val">{{ preflight.dimensions }}</span>
            </div>
            <div class="detail-row" v-if="preflight.duration !== null">
              <span class="lbl">DURATION:</span>
              <span class="val auto-tag">{{ preflight.duration }}s (auto-detected)</span>
            </div>
            <div class="detail-row hash-row" v-if="preflight.sha256">
              <span class="lbl">SHA-256:</span>
              <code class="hash-val">{{ preflight.sha256 }}</code>
            </div>
          </div>
        </div>

        <!-- Raw Binary Hex Dump from ArrayBuffer -->
        <div class="binary-slice-view" v-if="preflight.hexDump">
          <span class="slice-label">// Binary Header Hex (File API slice):</span>
          <code class="hex-text">{{ preflight.hexDump }}</code>
        </div>
      </div>
    </form>

    <p v-if="error" class="recording-error">{{ error }}</p>
    <p v-else-if="!loading && recordings.length === 0" class="recording-empty">
      No recordings yet.
    </p>

    <ul v-else class="recording-list">
      <li v-for="recording in recordings" :key="recording.id" class="recording-item">
        <a :href="`${coreApi}${recording.file_path}`" target="_blank" rel="noopener">
          RECORDING #{{ recording.id }}
        </a>
        <label>
          <span>SECONDS</span>
          <input
            v-model.number="durationEdits[recording.id]"
            type="number"
            min="0"
            :disabled="!canManage"
          />
        </label>
        <template v-if="canManage">
          <button class="action-btn" @click="updateDuration(recording)">SAVE</button>
          <button class="action-btn" title="Enqueue async transcoding (B8)" @click="enqueueTranscode(recording)">TRANSCODE</button>
          <button class="action-btn danger" @click="removeRecording(recording)">DELETE</button>
        </template>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';

const props = defineProps({
  streamId: { type: Number, required: true },
  coreApi: { type: String, required: true },
  accessToken: { type: String, default: '' },
  canManage: { type: Boolean, default: false }
});

const recordings = ref([]);
const durationEdits = ref({});
const fileInput = ref(null);
const selectedFileName = ref('');
const uploadDuration = ref(0);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const preflight = ref(null);

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

// Low-Level File API: reads file slice on the client side before uploading
const onFileSelected = async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    selectedFileName.value = '';
    preflight.value = null;
    return;
  }

  selectedFileName.value = file.name;

  // 1. Low-level slice reading with File.prototype.slice(0, 64)
  const slice = file.slice(0, 64);
  const arrayBuffer = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(slice);
  });

  // 2. DataView & Uint8Array binary magic byte verification
  const uint8 = new Uint8Array(arrayBuffer);
  const hexArr = [];
  let asciiStr = '';
  for (let i = 0; i < Math.min(32, uint8.length); i++) {
    const b = uint8[i];
    hexArr.push(b.toString(16).padStart(2, '0').toUpperCase());
    asciiStr += (b >= 32 && b <= 126) ? String.fromCharCode(b) : '.';
  }
  const hexDump = hexArr.join(' ') + '  |  ' + asciiStr;

  let isMp4 = false;
  let isWebm = false;
  if (uint8.length >= 8) {
    const tag = String.fromCharCode(uint8[4], uint8[5], uint8[6], uint8[7]);
    if (tag === 'ftyp' || tag === 'moov') {
      isMp4 = true;
    }
  }
  if (uint8.length >= 4 && uint8[0] === 0x1a && uint8[1] === 0x45 && uint8[2] === 0xdf && uint8[3] === 0xa3) {
    isWebm = true;
  }

  let detectedFormat = 'Non-Video / Unknown Container';
  let isValidVideo = false;

  if (isMp4) {
    detectedFormat = 'ISO-BMFF / MP4 (ftyp verified)';
    isValidVideo = true;
  } else if (isWebm) {
    detectedFormat = 'EBML / WebM / MKV (0x1A45DFA3 verified)';
    isValidVideo = true;
  } else if (file.type.startsWith('video/')) {
    detectedFormat = `${file.type} (Generic Video)`;
    isValidVideo = true;
  }

  // 3. Cryptographic SHA-256 header hash via SubtleCrypto
  let sha256 = '';
  try {
    const digestBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    sha256 = Array.from(new Uint8Array(digestBuffer))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  } catch (err) {
    console.warn('Crypto error:', err);
  }

  preflight.value = {
    name: file.name,
    formattedSize: formatBytes(file.size),
    detectedFormat,
    isValidVideo,
    hexDump,
    sha256,
    dimensions: '',
    duration: null,
    thumbnailUrl: null
  };

  // 4. HTML5 Video Metadata & Canvas Frame Extraction using URL.createObjectURL(file)
  const blobUrl = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.preload = 'metadata';
  video.muted = true;
  video.playsInline = true;
  video.src = blobUrl;

  video.onloadedmetadata = () => {
    const dur = Math.round(video.duration || 0);
    if (preflight.value) {
      preflight.value.duration = dur;
      preflight.value.dimensions = `${video.videoWidth} × ${video.videoHeight}px`;
    }
    uploadDuration.value = dur;
    video.currentTime = Math.min(1.0, (video.duration || 1) * 0.1);
  };

  video.onseeked = () => {
    try {
      const canvas = document.createElement('canvas');
      const maxW = 160;
      const scale = video.videoWidth > 0 ? maxW / video.videoWidth : 1;
      canvas.width = maxW;
      canvas.height = Math.round((video.videoHeight || 90) * scale);
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        if (preflight.value) {
          preflight.value.thumbnailUrl = canvas.toDataURL('image/jpeg', 0.85);
        }
      }
    } catch (e) {
      console.warn('Canvas frame error:', e);
    } finally {
      URL.revokeObjectURL(blobUrl);
    }
  };

  video.onerror = () => {
    URL.revokeObjectURL(blobUrl);
  };
};

const loadRecordings = async () => {
  loading.value = true;
  error.value = '';
  try {
    const response = await fetch(`${props.coreApi}/api/streams/${props.streamId}/recordings`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to load recordings');
    const list = Array.isArray(data) ? data : (data.items || data.value || []);
    recordings.value = list;
    durationEdits.value = Object.fromEntries(list.map((item) => [item.id, item.duration_seconds]));
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load recordings';
  } finally {
    loading.value = false;
  }
};

const uploadRecording = async () => {
  const file = fileInput.value?.files?.[0];
  if (!file) {
    error.value = 'Choose a recording file first.';
    return;
  }

  saving.value = true;
  error.value = '';
  try {
    const body = new FormData();
    body.append('file', file);
    const uploadResponse = await fetch(
      `${props.coreApi}/api/streams/${props.streamId}/recordings/upload`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${props.accessToken}` },
        body
      }
    );
    const uploadedFile = await uploadResponse.json();
    if (!uploadResponse.ok) throw new Error(uploadedFile.detail || 'Unable to upload recording');

    const response = await fetch(
      `${props.coreApi}/api/streams/${props.streamId}/recordings`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${props.accessToken}`
        },
        body: JSON.stringify({
          file_path: uploadedFile.file_path,
          duration_seconds: uploadDuration.value || 0
        })
      }
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to create recording');
    fileInput.value.value = '';
    selectedFileName.value = '';
    uploadDuration.value = 0;
    preflight.value = null;
    await loadRecordings();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to upload recording';
  } finally {
    saving.value = false;
  }
};

const updateDuration = async (recording) => {
  error.value = '';
  try {
    const response = await fetch(`${props.coreApi}/api/recordings/${recording.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${props.accessToken}`
      },
      body: JSON.stringify({ duration_seconds: Number(durationEdits.value[recording.id]) })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to update recording');
    await loadRecordings();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to update recording';
  }
};

const removeRecording = async (recording) => {
  if (!window.confirm(`Delete recording #${recording.id}?`)) return;
  error.value = '';
  try {
    const response = await fetch(`${props.coreApi}/api/recordings/${recording.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${props.accessToken}` }
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Unable to delete recording');
    }
    await loadRecordings();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to delete recording';
  }
};

const enqueueTranscode = async (recording) => {
  try {
    const res = await fetch(`${props.coreApi}/api/queue/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'transcode_vod',
        stream_id: props.streamId,
        file_path: recording.file_path,
        options: { recording_id: recording.id },
      }),
    });
    const data = await res.json();
    if (res.ok) {
      window.alert(`Background Job ${data.job_id} enqueued for processing! Open QUEUE in top nav.`);
    } else {
      throw new Error(data.detail || 'Failed to enqueue job');
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to enqueue transcode job';
  }
};

watch(() => props.streamId, loadRecordings);
onMounted(loadRecordings);
</script>

<style scoped>
.recording-manager {
  border-top: 1px solid #222;
  background: #101010;
  padding: 12px 20px;
  max-height: 480px;
  overflow-y: auto;
  font-family: inherit;
}

.recording-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.header-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.recording-header h3 {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin: 0;
  color: #fff;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.recording-header h3 span,
.recording-item label span,
.recording-empty {
  color: #777;
  font-size: 10px;
}

.recording-upload {
  margin-top: 12px;
}

.upload-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.custom-file-btn {
  height: 32px;
  line-height: 30px;
  padding: 0 12px;
  background: #141414;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  white-space: nowrap;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  max-width: 260px;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.custom-file-btn input[type="file"] {
  position: absolute;
  left: 0;
  top: 0;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.custom-file-btn:hover {
  background: #222222;
  border-color: #666666;
}

.custom-file-btn span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duration-box {
  display: flex;
  align-items: center;
  height: 32px;
  border: 1px solid #333333;
  background: #141414;
  box-sizing: border-box;
}

.duration-box .unit-tag {
  font-size: 10px;
  color: #777777;
  padding: 0 8px;
  font-weight: 700;
  user-select: none;
  border-right: 1px solid #222222;
}

.duration-box input {
  width: 60px;
  height: 100%;
  background: transparent;
  border: none;
  color: #ffffff;
  padding: 0 8px;
  font-family: inherit;
  font-size: 11px;
  outline: none;
}

/* File API Pre-Flight Inspection Card */
.file-api-card {
  margin-top: 10px;
  background: #141414;
  border: 1px solid #2a2a2a;
  padding: 10px 12px;
  font-size: 11px;
}

.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #222;
  padding-bottom: 6px;
  margin-bottom: 8px;
}

.api-tag {
  color: #ffffff;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.5px;
}

.validation-pill {
  font-size: 9px;
  padding: 2px 6px;
  font-weight: bold;
  letter-spacing: 0.5px;
}

.validation-pill.valid {
  background: #141414;
  color: #ffffff;
  border: 1px solid #ffffff;
}

.validation-pill.invalid {
  background: #141414;
  color: #888888;
  border: 1px solid #444444;
}

.card-content {
  display: flex;
  gap: 12px;
  align-items: center;
}

.thumb-container {
  position: relative;
  width: 120px;
  flex-shrink: 0;
  border: 1px solid #333;
  background: #000;
}

.thumb-container img {
  width: 100%;
  display: block;
}

.thumb-badge {
  position: absolute;
  bottom: 2px;
  left: 2px;
  background: rgba(0, 0, 0, 0.85);
  color: #ffffff;
  font-size: 8px;
  padding: 1px 4px;
  letter-spacing: 0.5px;
}

.preflight-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.detail-row {
  display: flex;
  gap: 6px;
}

.detail-row .lbl {
  color: #777;
  width: 90px;
  flex-shrink: 0;
}

.detail-row .val {
  color: #ddd;
}

.detail-row .val.highlight {
  color: #ffffff;
  font-weight: 700;
}

.auto-tag {
  color: #888888 !important;
}

.hash-row {
  align-items: baseline;
}

.hash-val {
  font-size: 10px;
  color: #888888;
  word-break: break-all;
  font-family: inherit;
}

.binary-slice-view {
  margin-top: 8px;
  background: #0b0b0b;
  border: 1px solid #1f1f1f;
  padding: 6px 8px;
}

.slice-label {
  display: block;
  font-size: 9px;
  color: #666;
  margin-bottom: 2px;
}

.hex-text {
  font-size: 10px;
  color: #888888;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}

.recording-list {
  list-style: none;
  margin-top: 8px;
  padding: 0;
}

.recording-item {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #222;
  padding: 8px 0;
}

.recording-item a {
  color: #ddd;
  margin-right: auto;
  text-decoration: none;
}

.recording-item a:hover {
  text-decoration: underline;
}

.recording-item label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.recording-item input {
  width: 90px;
  background: #181818;
  border: 1px solid #333;
  color: #eee;
  padding: 4px 6px;
  font-size: 11px;
}

.recording-error {
  color: #ffffff;
  font-size: 12px;
  margin-top: 8px;
}

.recording-empty {
  margin-top: 8px;
}

.action-btn {
  height: 32px;
  line-height: 30px;
  padding: 0 12px;
  background: #141414;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  white-space: nowrap;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.action-btn:hover {
  background: #222222;
  border-color: #666666;
  color: #ffffff;
}

.action-btn.primary {
  background: #ffffff;
  border-color: #ffffff;
  color: #000000;
  font-weight: 700;
}

.action-btn.primary:hover {
  background: #cccccc;
  border-color: #cccccc;
  color: #000000;
}

.action-btn.danger {
  background: #181818;
  border-color: #444444;
  color: #ffffff;
}

.action-btn.danger:hover {
  background: #2a2a2a;
  border-color: #777777;
}

button:disabled {
  cursor: wait;
  opacity: 0.6;
}

@media (max-width: 760px) {
  .upload-controls,
  .recording-item,
  .card-content {
    align-items: stretch;
    flex-wrap: wrap;
  }
}
</style>
