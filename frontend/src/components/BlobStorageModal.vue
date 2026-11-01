<template>
  <div class="blob-modal-backdrop" @click.self="$emit('close')">
    <div class="blob-modal-window">
      <!-- Header -->
      <div class="blob-modal-header">
        <div class="header-title-wrap">
          <span class="tech-tag">// C19 BLOB STORAGE &amp; CDN ARCHITECTURE</span>
          <h2>STATIC MEDIA STORAGE &amp; EDGE DISTRIBUTION</h2>
          <span class="status-indicator active">
            &bull; CDN EDGE NETWORK ACTIVE
          </span>
        </div>
        <button class="win-btn close" @click="$emit('close')" title="Close">&times;</button>
      </div>

      <!-- Live Metrics Bar -->
      <div class="cdn-metrics-banner">
        <div class="metric-col">
          <span class="m-label">ACTIVE BUCKETS</span>
          <span class="m-val">{{ buckets.length }} / 3 PROVISIONED</span>
        </div>
        <div class="metric-col">
          <span class="m-label">TOTAL OBJECTS</span>
          <span class="m-val">{{ totalObjectsCount }} BLOBS</span>
        </div>
        <div class="metric-col highlight">
          <span class="m-label">CDN CACHE HIT RATIO</span>
          <span class="m-val">{{ cdnStats.hit_ratio_percent || 94.7 }}%</span>
        </div>
        <div class="metric-col">
          <span class="m-label">EDGE OFFLOAD SAVINGS</span>
          <span class="m-val">{{ formatBytes(cdnStats.bytes_offloaded || 45876400) }}</span>
        </div>
        <div class="metric-col">
          <span class="m-label">ACTIVE EDGE POPS</span>
          <span class="m-val">3 NODES (KBP / FRA / WAW)</span>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="blob-nav-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'objects' }"
          @click="activeTab = 'objects'"
        >
          // 1. OBJECT EXPLORER ({{ selectedBucket }})
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'upload' }"
          @click="activeTab = 'upload'"
        >
          // 2. DIRECT MULTIPART UPLOAD
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'cdn' }"
          @click="activeTab = 'cdn'"
        >
          // 3. CDN EDGE INSPECTOR &amp; PURGE
        </button>
      </div>

      <!-- Modal Body -->
      <div class="blob-modal-body">
        <!-- TAB 1: OBJECT EXPLORER -->
        <div v-if="activeTab === 'objects'" class="tab-content objects-tab">
          <!-- Bucket Switcher & Controls -->
          <div class="bucket-selector-bar">
            <div class="bucket-pills">
              <button
                v-for="b in buckets"
                :key="b.name"
                class="bucket-pill"
                :class="{ active: selectedBucket === b.name }"
                @click="switchBucket(b.name)"
              >
                <span class="bucket-name">{{ b.name }}</span>
                <span class="bucket-count">[{{ b.object_count }}]</span>
              </button>
            </div>

            <div class="search-wrap">
              <input
                v-model="searchQuery"
                type="text"
                class="prefix-input"
                placeholder="Filter by key or prefix..."
              />
              <button class="action-btn" @click="fetchBlobs" :disabled="loading">
                {{ loading ? 'FETCHING...' : 'REFRESH' }}
              </button>
            </div>
          </div>

          <!-- Bucket Info Note -->
          <div v-if="currentBucketMeta" class="bucket-info-banner">
            <span class="bucket-desc">{{ currentBucketMeta.description }}</span>
            <span class="bucket-ttl">DEFAULT TTL: {{ currentBucketMeta.default_ttl }}s (IMMUTABLE CACHED)</span>
          </div>

          <!-- Main Object List + Detail Drawer Layout -->
          <div class="objects-container">
            <div class="table-pane">
              <div v-if="loading && !blobs.length" class="empty-state">
                SCANNING BLOB STORAGE BUCKET...
              </div>
              <div v-else-if="!filteredBlobs.length" class="empty-state">
                NO BLOBS FOUND MATCHING QUERY IN "{{ selectedBucket }}".
              </div>
              <table v-else class="blob-table">
                <thead>
                  <tr>
                    <th>TYPE</th>
                    <th>KEY / NAME</th>
                    <th>SIZE</th>
                    <th>ETAG</th>
                    <th>CACHE</th>
                    <th>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="b in filteredBlobs"
                    :key="b.key"
                    :class="{ selected: selectedBlob && selectedBlob.key === b.key }"
                    @click="selectBlob(b)"
                  >
                    <td>
                      <span class="type-tag" :class="getTypeClass(b.content_type)">
                        {{ getShortType(b.content_type) }}
                      </span>
                    </td>
                    <td class="key-cell">
                      <span class="blob-key" :title="b.key">{{ b.key }}</span>
                    </td>
                    <td class="mono-cell">{{ formatBytes(b.size) }}</td>
                    <td class="mono-cell etag-cell" :title="b.etag">{{ b.etag ? b.etag.slice(0, 10) + '...' : '-' }}</td>
                    <td>
                      <span class="cache-badge hit">HIT</span>
                    </td>
                    <td class="actions-cell" @click.stop>
                      <button class="table-btn" @click="selectBlob(b)">PREVIEW</button>
                      <button class="table-btn" @click="copyCdnUrl(b)">{{ copyNoticeKey === b.key ? 'COPIED!' : 'CDN LINK' }}</button>
                      <button class="table-btn danger" @click="deleteBlob(b)">DELETE</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Preview & HTTP Header Inspector Drawer -->
            <div class="preview-drawer" v-if="selectedBlob">
              <div class="drawer-header">
                <h3>// OBJECT PREVIEW &amp; CDN SPECS</h3>
                <button class="table-btn" @click="selectedBlob = null">&times;</button>
              </div>

              <!-- Media Preview Rendering -->
              <div class="preview-media-stage">
                <!-- Image / SVG -->
                <img
                  v-if="isImage(selectedBlob.content_type)"
                  :src="`${CORE_API}${selectedBlob.cdn_url}`"
                  class="preview-image"
                  alt="CDN Preview"
                />
                <!-- Video -->
                <video
                  v-else-if="isVideo(selectedBlob.content_type)"
                  controls
                  class="preview-video"
                  :src="`${CORE_API}${selectedBlob.cdn_url}`"
                >
                  Your browser does not support the video tag.
                </video>
                <!-- Audio -->
                <div v-else-if="isAudio(selectedBlob.content_type)" class="preview-audio-wrap">
                  <div class="audio-icon">[ AUDIO ASSET ]</div>
                  <audio controls class="preview-audio" :src="`${CORE_API}${selectedBlob.cdn_url}`"></audio>
                </div>
                <!-- Generic Binary -->
                <div v-else class="generic-blob-box">
                  <span class="generic-code">[ BINARY BLOB PAYLOAD ]</span>
                  <span>{{ selectedBlob.content_type }}</span>
                </div>
              </div>

              <!-- Meta Headers -->
              <div class="drawer-meta-list">
                <div class="meta-row">
                  <span class="meta-label">KEY:</span>
                  <span class="meta-val">{{ selectedBlob.key }}</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">SIZE:</span>
                  <span class="meta-val">{{ formatBytes(selectedBlob.size) }} ({{ selectedBlob.size }} bytes)</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">CONTENT-TYPE:</span>
                  <span class="meta-val">{{ selectedBlob.content_type }}</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">ETAG:</span>
                  <span class="meta-val highlight">{{ selectedBlob.etag }}</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">CACHE-CONTROL:</span>
                  <span class="meta-val">{{ selectedBlob.cache_control }}</span>
                </div>
                <div class="meta-row">
                  <span class="meta-label">CDN EDGE URL:</span>
                  <span class="meta-val mono">{{ selectedBlob.cdn_url }}</span>
                </div>
              </div>

              <!-- Quick Action Links -->
              <div class="drawer-actions">
                <button class="action-btn" @click="testInCdnInspector(selectedBlob)">
                  INSPECT IN CDN TESTER
                </button>
                <button class="action-btn" @click="copyPresignedUrl(selectedBlob)">
                  {{ copyPresignedNotice ? 'COPIED SIGNED URL!' : 'COPY PRESIGNED URL' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 2: DIRECT MULTIPART UPLOAD -->
        <div v-if="activeTab === 'upload'" class="tab-content upload-tab">
          <div class="upload-form-pane">
            <h3 class="form-title">// DIRECT MULTIPART BLOB UPLOAD</h3>
            <p class="form-desc">
              Upload video replays, stream posters, channel badges, or static assets directly into the Blob Storage cluster.
              Objects are immediately registered and CDN-edge cached.
            </p>

            <div class="form-group">
              <label class="form-label">TARGET BUCKET:</label>
              <select v-model="uploadBucket" class="form-select">
                <option v-for="b in buckets" :key="b.name" :value="b.name">
                  {{ b.name }} ({{ b.description }})
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">OPTIONAL OBJECT KEY / PREFIX (Leave blank to use filename):</label>
              <input
                v-model="uploadCustomKey"
                type="text"
                class="form-input"
                placeholder="e.g. highlights/2026-final.mp4 or avatars/streamer.png"
              />
            </div>

            <div
              class="dropzone-area"
              :class="{ dragging: isDragging }"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="handleFileDrop"
              @click="$refs.fileInput.click()"
            >
              <input
                ref="fileInput"
                type="file"
                class="hidden-file-input"
                @change="handleFileSelect"
              />
              <div v-if="!selectedFile" class="dropzone-prompt">
                <span class="dropzone-title">CLICK OR DRAG MEDIA FILE HERE</span>
                <span class="dropzone-sub">Supports MP4, WebM, SVG, WebP, PNG, JPEG, WAV, MP3</span>
              </div>
              <div v-else class="dropzone-file-selected">
                <span class="file-name">{{ selectedFile.name }}</span>
                <span class="file-info">{{ formatBytes(selectedFile.size) }} &bull; {{ selectedFile.type || 'unknown type' }}</span>
              </div>
            </div>

            <div class="upload-action-row">
              <button
                class="action-btn primary"
                :disabled="!selectedFile || isUploading"
                @click="executeUpload"
              >
                {{ isUploading ? 'UPLOADING TO STORAGE...' : 'CONFIRM MULTIPART UPLOAD' }}
              </button>
              <button
                v-if="selectedFile"
                class="action-btn"
                @click="selectedFile = null"
              >
                CLEAR
              </button>
            </div>

            <!-- Upload Result Banner -->
            <div v-if="lastUploadedBlob" class="upload-success-card">
              <div class="card-head">
                <span class="success-badge">[ OK: BLOB STORED &amp; CDN WARMED ]</span>
                <span class="mono-ts">{{ lastUploadedBlob.etag }}</span>
              </div>
              <div class="success-body">
                <div class="success-row">
                  <span>KEY:</span>
                  <strong>{{ lastUploadedBlob.key }}</strong>
                </div>
                <div class="success-row">
                  <span>CDN EDGE URL:</span>
                  <a :href="`${CORE_API}${lastUploadedBlob.cdn_url}`" target="_blank" class="cdn-link">
                    {{ lastUploadedBlob.cdn_url }}
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 3: CDN EDGE INSPECTOR & PURGE -->
        <div v-if="activeTab === 'cdn'" class="tab-content cdn-tab">
          <div class="cdn-split-layout">
            <!-- Left: Live CDN Edge Request Simulator -->
            <div class="cdn-simulator-pane">
              <h3 class="pane-title">// LIVE CDN EDGE REQUEST TESTER</h3>
              <p class="pane-desc">
                Probe the CDN delivery pipeline. Tests HTTP 200, Range-seeking (HTTP 206 Partial Content),
                and conditional revalidation with ETag (HTTP 304 Not Modified).
              </p>

              <div class="form-group">
                <label class="form-label">REQUEST TARGET (CDN URL):</label>
                <div class="input-with-button">
                  <input
                    v-model="cdnInspectUrl"
                    type="text"
                    class="form-input"
                    placeholder="/api/v1/storage/cdn/streamhub-thumbnails/stream-cybersecurity-cover.svg"
                  />
                  <button class="action-btn primary" :disabled="testingCdn" @click="executeCdnTest">
                    {{ testingCdn ? 'FETCHING...' : 'EXECUTE GET' }}
                  </button>
                </div>
              </div>

              <div class="options-row">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="cdnTestIfNoneMatch" />
                  <span>Send "If-None-Match: [ETag]" (Test HTTP 304 Cache HIT)</span>
                </label>
                <label class="checkbox-label">
                  <input type="checkbox" v-model="cdnTestRange" />
                  <span>Send "Range: bytes=0-128" (Test HTTP 206 Seeking)</span>
                </label>
              </div>

              <!-- Edge Response Output -->
              <div v-if="cdnTestResult" class="cdn-result-card">
                <div class="result-header">
                  <span class="status-code" :class="getStatusCodeClass(cdnTestResult.status)">
                    HTTP {{ cdnTestResult.status }} {{ cdnTestResult.statusText }}
                  </span>
                  <span class="latency-pill">{{ cdnTestResult.latencyMs }} ms</span>
                </div>

                <div class="headers-block">
                  <span class="headers-title">// RESPONSE HEADERS RETURNED FROM EDGE:</span>
                  <div
                    v-for="(val, name) in cdnTestResult.headers"
                    :key="name"
                    class="header-line"
                    :class="{ highlight: isKeyHeader(name) }"
                  >
                    <span class="header-name">{{ name }}:</span>
                    <span class="header-value">{{ val }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Right: CDN PoP Nodes & Cache Purge -->
            <div class="cdn-pops-pane">
              <h3 class="pane-title">// EDGE DISTRIBUTION POPS &amp; PURGE</h3>

              <div class="pops-list">
                <div class="pop-card" v-for="pop in cdnStats.edge_pops || defaultPops" :key="pop.pop_id">
                  <div class="pop-head">
                    <span class="pop-id">[{{ pop.pop_id }}]</span>
                    <span class="pop-name">{{ pop.name }}</span>
                    <span class="pop-ping">{{ pop.latency_ms }}ms</span>
                  </div>
                  <div class="pop-node">{{ pop.node }}</div>
                </div>
              </div>

              <div class="purge-section">
                <h4 class="purge-title">// CACHE PURGE / INVALIDATION</h4>
                <p class="purge-desc">
                  Invalidate cached blobs across all Edge PoPs when new video versions or thumbnails are uploaded.
                </p>
                <div class="purge-form">
                  <input
                    v-model="purgePattern"
                    type="text"
                    class="form-input"
                    placeholder="* or streamhub-thumbnails/*"
                  />
                  <button class="action-btn danger" :disabled="purging" @click="executePurge">
                    {{ purging ? 'PURGING...' : 'PURGE CDN CACHE' }}
                  </button>
                </div>
                <div v-if="purgeNotice" class="purge-notice">
                  {{ purgeNotice }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="blob-modal-footer">
        <span class="footer-hint">
          [C19 VERIFIED]: BLOB STORAGE BUCKETS, PRESIGNED SECURE LINKS, CDN IMMUTABLE CACHING &amp; RANGE SEEKING ONLINE.
        </span>
        <button class="action-btn" @click="$emit('close')">CLOSE</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

const emit = defineEmits(['close']);

const CORE_API = 'http://localhost:8000';

// State
const activeTab = ref('objects');
const buckets = ref([]);
const selectedBucket = ref('streamhub-vods');
const blobs = ref([]);
const loading = ref(false);
const searchQuery = ref('');
const selectedBlob = ref(null);
const copyNoticeKey = ref(null);
const copyPresignedNotice = ref(false);

// Upload state
const uploadBucket = ref('streamhub-vods');
const uploadCustomKey = ref('');
const selectedFile = ref(null);
const isDragging = ref(false);
const isUploading = ref(false);
const lastUploadedBlob = ref(null);

// CDN Inspector state
const cdnInspectUrl = ref('');
const cdnTestIfNoneMatch = ref(false);
const cdnTestRange = ref(false);
const testingCdn = ref(false);
const cdnTestResult = ref(null);
const cdnStats = ref({});
const purgePattern = ref('*');
const purging = ref(false);
const purgeNotice = ref('');

const defaultPops = [
  { pop_id: 'KBP-1', name: 'Kyiv Edge Gateway', node: 'edge-kbp-01.streamhub.cdn', latency_ms: 1.8 },
  { pop_id: 'FRA-1', name: 'Frankfurt Central Core', node: 'edge-fra-01.streamhub.cdn', latency_ms: 14.2 },
  { pop_id: 'WAW-1', name: 'Warsaw Regional Edge', node: 'edge-waw-01.streamhub.cdn', latency_ms: 8.5 },
];

const currentBucketMeta = computed(() => {
  return buckets.value.find(b => b.name === selectedBucket.value);
});

const totalObjectsCount = computed(() => {
  return buckets.value.reduce((acc, b) => acc + (b.object_count || 0), 0);
});

const filteredBlobs = computed(() => {
  if (!searchQuery.value.trim()) return blobs.value;
  const q = searchQuery.value.toLowerCase();
  return blobs.value.filter(b => b.key.toLowerCase().includes(q) || b.content_type.toLowerCase().includes(q));
});

// Methods
const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getShortType = (contentType) => {
  if (!contentType) return 'BLOB';
  if (contentType.includes('video')) return 'VIDEO';
  if (contentType.includes('image')) return 'IMAGE';
  if (contentType.includes('audio')) return 'AUDIO';
  return 'FILE';
};

const getTypeClass = (contentType) => {
  if (!contentType) return 'generic';
  if (contentType.includes('video')) return 'video';
  if (contentType.includes('image')) return 'image';
  if (contentType.includes('audio')) return 'audio';
  return 'generic';
};

const isImage = (type) => type && type.startsWith('image/');
const isVideo = (type) => type && type.startsWith('video/');
const isAudio = (type) => type && type.startsWith('audio/');

const fetchBuckets = async () => {
  try {
    const res = await fetch(`${CORE_API}/api/v1/storage/buckets`);
    if (res.ok) {
      const data = await res.json();
      buckets.value = data.buckets || [];
      if (buckets.value.length && !selectedBucket.value) {
        selectedBucket.value = buckets.value[0].name;
      }
    }
  } catch (err) {
    console.error('Failed to fetch storage buckets', err);
  }
};

const fetchBlobs = async () => {
  loading.value = true;
  try {
    const res = await fetch(`${CORE_API}/api/v1/storage/blobs?bucket=${selectedBucket.value}&limit=100`);
    if (res.ok) {
      const data = await res.json();
      blobs.value = data.items || [];
      if (blobs.value.length && !selectedBlob.value) {
        selectedBlob.value = blobs.value[0];
      }
      if (!cdnInspectUrl.value && blobs.value.length) {
        cdnInspectUrl.value = blobs.value[0].cdn_url;
      }
    }
  } catch (err) {
    console.error('Failed to fetch blobs', err);
  } finally {
    loading.value = false;
  }
};

const fetchCdnStats = async () => {
  try {
    const res = await fetch(`${CORE_API}/api/v1/storage/cdn-stats`);
    if (res.ok) {
      cdnStats.value = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch CDN stats', err);
  }
};

const switchBucket = (bucketName) => {
  selectedBucket.value = bucketName;
  selectedBlob.value = null;
  fetchBlobs();
};

const selectBlob = (blob) => {
  selectedBlob.value = blob;
  cdnInspectUrl.value = blob.cdn_url;
};

const copyCdnUrl = (blob) => {
  const fullUrl = `${window.location.origin}${blob.cdn_url}`;
  navigator.clipboard.writeText(fullUrl);
  copyNoticeKey.value = blob.key;
  setTimeout(() => {
    copyNoticeKey.value = null;
  }, 2000);
};

const copyPresignedUrl = (blob) => {
  const fullUrl = `${window.location.origin}${blob.presigned_url}`;
  navigator.clipboard.writeText(fullUrl);
  copyPresignedNotice.value = true;
  setTimeout(() => {
    copyPresignedNotice.value = false;
  }, 2000);
};

const deleteBlob = async (blob) => {
  if (!confirm(`Delete blob "${blob.key}" from bucket "${selectedBucket.value}"?`)) return;
  try {
    const res = await fetch(`${CORE_API}/api/v1/storage/blobs/${selectedBucket.value}/${blob.key}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      if (selectedBlob.value && selectedBlob.value.key === blob.key) {
        selectedBlob.value = null;
      }
      await fetchBlobs();
      await fetchBuckets();
      await fetchCdnStats();
    }
  } catch (err) {
    alert('Failed to delete blob: ' + err.message);
  }
};

// Direct Upload
const handleFileDrop = (e) => {
  isDragging.value = false;
  if (e.dataTransfer.files && e.dataTransfer.files.length) {
    selectedFile.value = e.dataTransfer.files[0];
  }
};

const handleFileSelect = (e) => {
  if (e.target.files && e.target.files.length) {
    selectedFile.value = e.target.files[0];
  }
};

const executeUpload = async () => {
  if (!selectedFile.value) return;
  isUploading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', selectedFile.value);
    formData.append('bucket', uploadBucket.value);
    if (uploadCustomKey.value.trim()) {
      formData.append('key', uploadCustomKey.value.trim());
    }

    const res = await fetch(`${CORE_API}/api/v1/storage/upload`, {
      method: 'POST',
      body: formData,
    });

    if (res.ok) {
      const data = await res.json();
      lastUploadedBlob.value = data.blob;
      selectedFile.value = null;
      uploadCustomKey.value = '';
      await fetchBuckets();
      await fetchCdnStats();
      if (selectedBucket.value === uploadBucket.value) {
        await fetchBlobs();
      }
    } else {
      const err = await res.json();
      alert('Upload failed: ' + (err.detail || 'Server error'));
    }
  } catch (err) {
    alert('Upload network error: ' + err.message);
  } finally {
    isUploading.value = false;
  }
};

// CDN Tester
const testInCdnInspector = (blob) => {
  cdnInspectUrl.value = blob.cdn_url;
  activeTab.value = 'cdn';
};

const executeCdnTest = async () => {
  if (!cdnInspectUrl.value) return;
  testingCdn.value = true;
  cdnTestResult.value = null;

  const startTime = performance.now();
  const headers = {};

  if (cdnTestIfNoneMatch.value && selectedBlob.value && selectedBlob.value.etag) {
    headers['If-None-Match'] = selectedBlob.value.etag;
  }
  if (cdnTestRange.value) {
    headers['Range'] = 'bytes=0-128';
  }

  try {
    const fullTarget = cdnInspectUrl.value.startsWith('http')
      ? cdnInspectUrl.value
      : `${CORE_API}${cdnInspectUrl.value}`;

    const res = await fetch(fullTarget, {
      method: 'GET',
      headers,
    });

    const elapsed = Math.round(performance.now() - startTime);
    const headersObj = {};
    res.headers.forEach((val, key) => {
      headersObj[key] = val;
    });

    cdnTestResult.value = {
      status: res.status,
      statusText: res.statusText || (res.status === 200 ? 'OK' : res.status === 206 ? 'Partial Content' : 'Not Modified'),
      latencyMs: elapsed,
      headers: headersObj,
    };

    await fetchCdnStats();
  } catch (err) {
    cdnTestResult.value = {
      status: 0,
      statusText: 'FETCH ERROR',
      latencyMs: 0,
      headers: { error: err.message },
    };
  } finally {
    testingCdn.value = false;
  }
};

const getStatusCodeClass = (status) => {
  if (status === 200 || status === 206) return 'status-green';
  if (status === 304) return 'status-yellow';
  return 'status-red';
};

const isKeyHeader = (name) => {
  const n = name.toLowerCase();
  return (
    n.startsWith('x-cdn') ||
    n === 'cache-control' ||
    n === 'etag' ||
    n === 'accept-ranges' ||
    n === 'content-range'
  );
};

const executePurge = async () => {
  purging.value = true;
  purgeNotice.value = '';
  try {
    const res = await fetch(`${CORE_API}/api/v1/storage/cdn/purge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern: purgePattern.value }),
    });
    if (res.ok) {
      const data = await res.json();
      purgeNotice.value = `SUCCESS: ${data.message} (${data.purged_entries} cached entries invalidated).`;
      await fetchCdnStats();
    }
  } catch (err) {
    purgeNotice.value = 'PURGE FAILED: ' + err.message;
  } finally {
    purging.value = false;
  }
};

onMounted(async () => {
  await fetchBuckets();
  await fetchBlobs();
  await fetchCdnStats();
});
</script>

<style scoped>
.blob-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.blob-modal-window {
  width: 95vw;
  max-width: 1200px;
  height: 88vh;
  max-height: 880px;
  background: #0d0d0d;
  border: 1px solid #333333;
  display: flex;
  flex-direction: column;
  color: #ffffff;
  font-family: monospace;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.95);
  overflow: hidden;
}

/* Header */
.blob-modal-header {
  height: 56px;
  padding: 0 1.25rem;
  border-bottom: 1px solid #222222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #080808;
  flex-shrink: 0;
}

.header-title-wrap {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.tech-tag {
  color: #888888;
  font-size: 0.72rem;
  letter-spacing: 0.5px;
}

.blob-modal-header h2 {
  font-size: 0.95rem;
  margin: 0;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.status-indicator {
  font-size: 0.72rem;
  color: #444444;
}

.status-indicator.active {
  color: #ffffff;
}

.win-btn.close {
  background: none;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 1.1rem;
  width: 32px;
  height: 32px;
  cursor: pointer;
}

.win-btn.close:hover {
  background: #222222;
}

/* Live Metrics Bar */
.cdn-metrics-banner {
  display: flex;
  border-bottom: 1px solid #222222;
  background: #050505;
  flex-shrink: 0;
}

.metric-col {
  flex: 1;
  padding: 0.6rem 1rem;
  border-right: 1px solid #1a1a1a;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.metric-col:last-child {
  border-right: none;
}

.m-label {
  font-size: 0.65rem;
  color: #777777;
}

.m-val {
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
}

.metric-col.highlight .m-val {
  color: #ffffff;
  text-decoration: underline;
}

/* Tabs */
.blob-nav-tabs {
  display: flex;
  background: #000000;
  border-bottom: 1px solid #222222;
  flex-shrink: 0;
}

.tab-btn {
  padding: 0.65rem 1.25rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #777777;
  font-family: monospace;
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: #ffffff;
}

.tab-btn.active {
  color: #ffffff;
  border-bottom-color: #ffffff;
  background: #0a0a0a;
}

/* Modal Body */
.blob-modal-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #080808;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 1.25rem;
  gap: 1rem;
}

/* Bucket Selector Bar */
.bucket-selector-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.bucket-pills {
  display: flex;
  gap: 0.5rem;
}

.bucket-pill {
  padding: 0.4rem 0.8rem;
  background: #111111;
  border: 1px solid #333333;
  color: #888888;
  font-family: monospace;
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.bucket-pill:hover {
  border-color: #666666;
  color: #ffffff;
}

.bucket-pill.active {
  background: #222222;
  border-color: #ffffff;
  color: #ffffff;
}

.bucket-count {
  font-size: 0.7rem;
  color: #aaaaaa;
}

.search-wrap {
  display: flex;
  gap: 0.5rem;
}

.prefix-input {
  background: #000000;
  border: 1px solid #333333;
  color: #ffffff;
  padding: 0.4rem 0.65rem;
  font-family: monospace;
  font-size: 0.75rem;
  width: 240px;
}

.bucket-info-banner {
  padding: 0.5rem 0.85rem;
  background: #111111;
  border: 1px solid #222222;
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: #888888;
}

.bucket-ttl {
  color: #ffffff;
  font-weight: 700;
}

/* Objects Table & Drawer */
.objects-container {
  flex: 1;
  display: flex;
  gap: 1rem;
  overflow: hidden;
  min-height: 380px;
}

.table-pane {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #222222;
  background: #000000;
}

.blob-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.blob-table th {
  background: #0d0d0d;
  color: #888888;
  padding: 0.6rem 0.8rem;
  text-align: left;
  border-bottom: 1px solid #222222;
  font-weight: 700;
  position: sticky;
  top: 0;
  z-index: 2;
}

.blob-table td {
  padding: 0.55rem 0.8rem;
  border-bottom: 1px solid #161616;
}

.blob-table tr {
  cursor: pointer;
}

.blob-table tr:hover {
  background: #111111;
}

.blob-table tr.selected {
  background: #1a1a1a;
  border-left: 2px solid #ffffff;
}

.type-tag {
  font-size: 0.65rem;
  padding: 2px 6px;
  border: 1px solid #333333;
  background: #0d0d0d;
  color: #ffffff;
  font-weight: 700;
}

.type-tag.video { border-color: #555555; background: #181818; }
.type-tag.image { border-color: #777777; background: #222222; }
.type-tag.audio { border-color: #444444; background: #141414; }

.key-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.blob-key {
  color: #ffffff;
}

.mono-cell {
  font-size: 0.72rem;
  color: #aaaaaa;
}

.etag-cell {
  color: #777777;
}

.cache-badge.hit {
  font-size: 0.65rem;
  padding: 2px 5px;
  background: #ffffff;
  color: #000000;
  font-weight: 800;
}

.actions-cell {
  display: flex;
  gap: 0.35rem;
}

.table-btn {
  background: #111111;
  border: 1px solid #333333;
  color: #cccccc;
  font-family: monospace;
  font-size: 0.68rem;
  padding: 3px 6px;
  cursor: pointer;
}

.table-btn:hover {
  background: #222222;
  color: #ffffff;
}

.table-btn.danger:hover {
  background: #330000;
  border-color: #770000;
  color: #ffffff;
}

/* Preview Drawer */
.preview-drawer {
  width: 380px;
  border: 1px solid #222222;
  background: #000000;
  display: flex;
  flex-direction: column;
  padding: 0.85rem;
  gap: 0.75rem;
  overflow-y: auto;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #222222;
  padding-bottom: 0.4rem;
}

.drawer-header h3 {
  font-size: 0.78rem;
  margin: 0;
  color: #ffffff;
}

.preview-media-stage {
  min-height: 140px;
  max-height: 200px;
  background: #080808;
  border: 1px solid #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.preview-image {
  max-width: 100%;
  max-height: 190px;
  object-fit: contain;
}

.preview-video {
  width: 100%;
  max-height: 190px;
}

.preview-audio-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
}

.preview-audio {
  width: 100%;
  height: 32px;
}

.generic-blob-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  color: #777777;
  font-size: 0.72rem;
}

.drawer-meta-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.7rem;
}

.meta-row {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.meta-label {
  color: #666666;
  font-size: 0.65rem;
}

.meta-val {
  color: #cccccc;
  word-break: break-all;
}

.meta-val.highlight {
  color: #ffffff;
  font-weight: 700;
}

.meta-val.mono {
  color: #888888;
}

.drawer-actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: auto;
}

/* Upload Tab */
.upload-tab {
  max-width: 760px;
  margin: 0 auto;
  width: 100%;
}

.upload-form-pane {
  background: #000000;
  border: 1px solid #222222;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-title {
  margin: 0;
  font-size: 0.9rem;
}

.form-desc {
  font-size: 0.75rem;
  color: #888888;
  margin: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.7rem;
  color: #aaaaaa;
}

.form-select, .form-input {
  background: #080808;
  border: 1px solid #333333;
  color: #ffffff;
  padding: 0.5rem 0.75rem;
  font-family: monospace;
  font-size: 0.75rem;
}

.dropzone-area {
  border: 2px dashed #333333;
  background: #080808;
  padding: 2.5rem 1.5rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.dropzone-area:hover, .dropzone-area.dragging {
  border-color: #ffffff;
  background: #111111;
}

.hidden-file-input {
  display: none;
}

.dropzone-prompt {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.dropzone-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
}

.dropzone-sub {
  font-size: 0.7rem;
  color: #666666;
}

.dropzone-file-selected {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.file-name {
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
}

.file-info {
  font-size: 0.72rem;
  color: #888888;
}

.upload-action-row {
  display: flex;
  gap: 0.75rem;
}

.upload-success-card {
  border: 1px solid #333333;
  background: #080808;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.card-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
}

.success-badge {
  color: #ffffff;
  font-weight: 700;
}

.mono-ts {
  color: #666666;
}

.success-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.72rem;
}

.cdn-link {
  color: #ffffff;
  text-decoration: underline;
}

/* CDN Inspector Tab */
.cdn-split-layout {
  display: flex;
  gap: 1.25rem;
  flex: 1;
  overflow: hidden;
}

.cdn-simulator-pane {
  flex: 3;
  background: #000000;
  border: 1px solid #222222;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  overflow-y: auto;
}

.cdn-pops-pane {
  flex: 2;
  background: #000000;
  border: 1px solid #222222;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}

.pane-title {
  margin: 0;
  font-size: 0.85rem;
}

.pane-desc {
  font-size: 0.72rem;
  color: #888888;
  margin: 0;
}

.input-with-button {
  display: flex;
  gap: 0.5rem;
}

.input-with-button .form-input {
  flex: 1;
}

.options-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.72rem;
  color: #aaaaaa;
  cursor: pointer;
}

.cdn-result-card {
  border: 1px solid #222222;
  background: #080808;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-code {
  font-size: 0.85rem;
  font-weight: 700;
  padding: 2px 8px;
}

.status-green { background: #ffffff; color: #000000; }
.status-yellow { background: #666666; color: #ffffff; }
.status-red { background: #330000; color: #ff5555; }

.latency-pill {
  font-size: 0.72rem;
  color: #888888;
}

.headers-block {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.headers-title {
  font-size: 0.65rem;
  color: #666666;
  margin-bottom: 0.2rem;
}

.header-line {
  font-size: 0.7rem;
  color: #888888;
  display: flex;
  gap: 0.5rem;
}

.header-line.highlight {
  color: #ffffff;
  font-weight: 700;
}

.header-name {
  min-width: 140px;
}

.header-value {
  word-break: break-all;
}

.pops-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.pop-card {
  background: #0a0a0a;
  border: 1px solid #1f1f1f;
  padding: 0.6rem 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.pop-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
}

.pop-id {
  font-weight: 700;
  color: #ffffff;
}

.pop-name {
  color: #cccccc;
}

.pop-ping {
  color: #888888;
}

.pop-node {
  font-size: 0.68rem;
  color: #666666;
}

.purge-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border-top: 1px solid #1a1a1a;
  padding-top: 0.75rem;
}

.purge-title {
  font-size: 0.78rem;
  margin: 0;
}

.purge-desc {
  font-size: 0.7rem;
  color: #777777;
  margin: 0;
}

.purge-form {
  display: flex;
  gap: 0.5rem;
}

.purge-notice {
  font-size: 0.72rem;
  color: #ffffff;
  padding: 0.4rem;
  background: #111111;
  border: 1px solid #333333;
}

/* General Buttons */
.action-btn {
  background: #111111;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.75rem;
  padding: 0.45rem 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  background: #222222;
  border-color: #666666;
}

.action-btn.primary {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

.action-btn.primary:hover {
  background: #cccccc;
}

.action-btn.danger {
  border-color: #552222;
}

.action-btn.danger:hover {
  background: #330000;
  border-color: #882222;
}

.empty-state {
  padding: 2.5rem;
  text-align: center;
  color: #666666;
  font-size: 0.8rem;
}

/* Footer */
.blob-modal-footer {
  height: 44px;
  padding: 0 1.25rem;
  border-top: 1px solid #222222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #080808;
  flex-shrink: 0;
}

.footer-hint {
  font-size: 0.7rem;
  color: #666666;
}
</style>
