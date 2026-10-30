<template>
  <div class="flags-modal-backdrop" @click.self="$emit('close')">
    <div class="flags-modal-window">
      <!-- Header -->
      <div class="flags-modal-header">
        <div class="header-title-wrap">
          <span class="tech-tag">// B6 FEATURE FLAGS &amp; PLANS</span>
          <h2>SUBSCRIPTION &amp; FEATURE FLAGS MANAGER</h2>
          <span class="plan-pill" :class="activePlan">
            [{{ activePlan.toUpperCase() }} TIER]
          </span>
        </div>
        <button class="win-btn close" @click="$emit('close')" title="Close">&times;</button>
      </div>

      <!-- Body -->
      <div class="flags-modal-body">
        <!-- Plan Switcher Cards -->
        <div class="plans-container">
          <div class="section-label">SELECT SUBSCRIPTION PLAN TIER (C16 + B6)</div>
          <div class="plans-grid">
            <!-- Free Plan -->
            <div class="plan-card" :class="{ current: activePlan === 'free' }">
              <div class="plan-card-header">
                <h3>FREE TIER</h3>
                <span class="plan-price">$0 / MO</span>
              </div>
              <p class="plan-desc">Standard access for general viewers and basic streamers.</p>
              <ul class="plan-perks">
                <li>&bull; Standard 720p Streaming</li>
                <li>&bull; Public Chat Access</li>
                <li class="locked">&times; Special Premium Lounge (Locked)</li>
                <li class="locked">&times; 1080p60 Transcode (Locked)</li>
                <li class="locked">&times; Priority Queue (Standard)</li>
              </ul>
              <button
                class="plan-action-btn"
                :disabled="activePlan === 'free' || isUpdating"
                @click="switchPlan('free')"
              >
                {{ activePlan === 'free' ? 'CURRENT PLAN' : 'DOWNGRADE TO FREE' }}
              </button>
            </div>

            <!-- Premium Plan -->
            <div class="plan-card featured" :class="{ current: activePlan === 'premium' }">
              <div class="featured-badge">RECOMMENDED FOR CREATORS</div>
              <div class="plan-card-header">
                <h3>PREMIUM TIER</h3>
                <span class="plan-price">$19 / MO</span>
              </div>
              <p class="plan-desc">Full creator studio with unlocked Special Lounge page.</p>
              <ul class="plan-perks">
                <li class="highlight">&bull; Special Premium Lounge (UNLOCKED)</li>
                <li>&bull; 1080p 60FPS Video Transcoding</li>
                <li>&bull; 4.0x Priority Queue Acceleration</li>
                <li>&bull; VIP Creator Verified Badge</li>
                <li>&bull; Canvas 2D Studio Pro Mode</li>
              </ul>
              <button
                class="plan-action-btn primary"
                :disabled="activePlan === 'premium' || isUpdating"
                @click="switchPlan('premium')"
              >
                {{ activePlan === 'premium' ? 'CURRENT PLAN' : 'UPGRADE TO PREMIUM' }}
              </button>
            </div>

            <!-- Partner Plan -->
            <div class="plan-card" :class="{ current: activePlan === 'partner' }">
              <div class="plan-card-header">
                <h3>PARTNER &amp; ADMIN</h3>
                <span class="plan-price">ENTERPRISE</span>
              </div>
              <p class="plan-desc">Unrestricted access with individual feature flag overrides.</p>
              <ul class="plan-perks">
                <li class="highlight">&bull; Special Premium Lounge (UNLOCKED)</li>
                <li>&bull; Individual Flag Override Toggles</li>
                <li>&bull; Ultra-HD 4K Hardware Pipeline</li>
                <li>&bull; Direct VIP Discord Webhook</li>
                <li>&bull; Zero-Latency Ingest Server</li>
              </ul>
              <button
                class="plan-action-btn"
                :disabled="activePlan === 'partner' || isUpdating"
                @click="switchPlan('partner')"
              >
                {{ activePlan === 'partner' ? 'CURRENT PLAN' : 'SWITCH TO PARTNER' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Live Feature Flag Matrix -->
        <div class="flags-matrix-container">
          <div class="section-label">LIVE FEATURE FLAGS MATRIX &amp; OVERRIDES</div>
          <div class="flags-table-wrap">
            <table class="flags-table">
              <thead>
                <tr>
                  <th>FEATURE FLAG KEY</th>
                  <th>DESCRIPTION</th>
                  <th>CATEGORY</th>
                  <th>EFFECTIVE STATUS</th>
                  <th>ADMIN TOGGLE</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(def, flagKey) in flagDefinitions" :key="flagKey">
                  <td class="flag-key">
                    <code>{{ flagKey }}</code>
                  </td>
                  <td class="flag-desc">
                    <strong>{{ def.name }}</strong>
                    <small>{{ def.description }}</small>
                  </td>
                  <td class="flag-cat">
                    <span class="cat-pill">{{ def.category.toUpperCase() }}</span>
                  </td>
                  <td class="flag-status">
                    <span
                      class="status-pill"
                      :class="{ enabled: effectiveFlags[flagKey], disabled: !effectiveFlags[flagKey] }"
                    >
                      {{ effectiveFlags[flagKey] ? 'ENABLED' : 'DISABLED' }}
                    </span>
                  </td>
                  <td class="flag-toggle-cell">
                    <button
                      class="toggle-btn"
                      :class="{ active: effectiveFlags[flagKey] }"
                      :disabled="isUpdating"
                      @click="toggleFlag(flagKey, !effectiveFlags[flagKey])"
                    >
                      {{ effectiveFlags[flagKey] ? 'SET OFF' : 'SET ON' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Protected Endpoint Test -->
        <div class="test-panel">
          <div class="test-header">
            <div>
              <strong>PROTECTED ENDPOINT VERIFICATION:</strong>
              <code>GET /api/v1/features/premium-lounge</code>
            </div>
            <button class="test-exec-btn" :disabled="isTesting" @click="testProtectedEndpoint">
              {{ isTesting ? 'TESTING...' : 'RUN VERIFICATION QUERY' }}
            </button>
          </div>
          <div v-if="testResult" class="test-result-box" :class="testResult.status">
            <div class="result-status-row">
              <span class="status-code">HTTP {{ testResult.httpCode }}</span>
              <span class="status-msg">{{ testResult.message }}</span>
            </div>
            <pre class="result-json">{{ testResult.payload }}</pre>
          </div>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="flags-modal-footer">
        <div class="footer-hint">
          <span>FEATURE FLAGS ARE TIED TO USER SUBSCRIPTION (C16 &bull; B6)</span>
        </div>
        <div class="footer-actions">
          <button class="win-btn" @click="fetchMyFlags">REFRESH FLAGS</button>
          <button
            class="win-btn primary"
            @click="navigateToSpecialPage"
          >
            {{ effectiveFlags.premium_page_access ? 'OPEN SPECIAL PREMIUM LOUNGE' : 'VISIT RESTRICTED PAGE' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const props = defineProps({
  coreApi: {
    type: String,
    required: true
  },
  accessToken: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['close', 'navigate-page', 'plan-changed']);

const activePlan = ref('free');
const effectiveFlags = ref({});
const flagDefinitions = ref({});
const isUpdating = ref(false);
const isTesting = ref(false);
const testResult = ref(null);

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (props.accessToken) {
    headers['Authorization'] = `Bearer ${props.accessToken}`;
  }
  return headers;
}

async function fetchFeatureMatrix() {
  try {
    const res = await fetch(`${props.coreApi}/api/v1/features/matrix`);
    if (res.ok) {
      const data = await res.json();
      flagDefinitions.value = data.flags || {};
    }
  } catch (err) {
    console.error('Failed to fetch feature flag matrix:', err);
  }
}

async function fetchMyFlags() {
  try {
    const res = await fetch(`${props.coreApi}/api/v1/features/my-flags`, {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      const data = await res.json();
      activePlan.value = data.plan || 'free';
      effectiveFlags.value = data.effective_flags || {};
      emit('plan-changed', {
        plan: activePlan.value,
        effectiveFlags: effectiveFlags.value
      });
    }
  } catch (err) {
    console.error('Failed to fetch user flags:', err);
  }
}

async function switchPlan(targetPlan) {
  isUpdating.value = true;
  try {
    const res = await fetch(`${props.coreApi}/api/v1/features/change-plan`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ plan: targetPlan })
    });
    if (res.ok) {
      const data = await res.json();
      activePlan.value = data.plan;
      effectiveFlags.value = data.effective_flags;
      emit('plan-changed', {
        plan: activePlan.value,
        effectiveFlags: effectiveFlags.value
      });
      // Run verification test after plan change
      await testProtectedEndpoint();
    } else {
      const err = await res.json();
      alert(`Error switching plan: ${err.detail || 'Unknown error'}`);
    }
  } catch (err) {
    console.error('Error changing plan:', err);
  } finally {
    isUpdating.value = false;
  }
}

async function toggleFlag(flagKey, enabled) {
  isUpdating.value = true;
  try {
    const res = await fetch(`${props.coreApi}/api/v1/features/toggle-flag`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ flag: flagKey, enabled })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.effective_flags) {
        effectiveFlags.value = data.effective_flags;
      } else {
        effectiveFlags.value[flagKey] = enabled;
      }
      emit('plan-changed', {
        plan: activePlan.value,
        effectiveFlags: effectiveFlags.value
      });
      await testProtectedEndpoint();
    }
  } catch (err) {
    console.error('Error toggling flag:', err);
  } finally {
    isUpdating.value = false;
  }
}

async function testProtectedEndpoint() {
  isTesting.value = true;
  try {
    const res = await fetch(`${props.coreApi}/api/v1/features/premium-lounge`, {
      headers: getAuthHeaders()
    });
    const httpCode = res.status;
    const body = await res.json();

    if (res.ok) {
      testResult.value = {
        status: 'success',
        httpCode,
        message: 'HTTP 200 OK — Access Granted by Feature Flag (premium_page_access = true)',
        payload: JSON.stringify(body, null, 2)
      };
    } else {
      testResult.value = {
        status: 'forbidden',
        httpCode,
        message: `HTTP ${httpCode} ${httpCode === 403 ? 'FORBIDDEN' : 'ERROR'} — Gated by Feature Flag`,
        payload: JSON.stringify(body, null, 2)
      };
    }
  } catch (err) {
    testResult.value = {
      status: 'error',
      httpCode: 0,
      message: 'Network Request Failed',
      payload: String(err)
    };
  } finally {
    isTesting.value = false;
  }
}

function navigateToSpecialPage() {
  emit('navigate-page', 'premium');
  emit('close');
}

onMounted(async () => {
  await fetchFeatureMatrix();
  await fetchMyFlags();
  await testProtectedEndpoint();
});
</script>

<style scoped>
.flags-modal-backdrop {
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

.flags-modal-window {
  background: #0a0a0a;
  border: 1px solid #333333;
  width: 100%;
  max-width: 1080px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.9);
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  overflow: hidden;
}

/* Header */
.flags-modal-header {
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

.plan-pill {
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border: 1px solid #333333;
  background: #181818;
  color: #888888;
}

.plan-pill.premium,
.plan-pill.partner {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
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

.win-btn.primary {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.win-btn.close {
  font-size: 1.15rem;
  padding: 0 0.75rem;
  line-height: 1;
}

/* Modal Body */
.flags-modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.section-label {
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #888888;
  border-bottom: 1px solid #1c1c1c;
  padding-bottom: 0.4rem;
  margin-bottom: 0.75rem;
}

/* Plans Grid */
.plans-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.plan-card {
  background: #101010;
  border: 1px solid #252525;
  padding: 1.1rem;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: border-color 0.2s;
}

.plan-card.current {
  border-color: #ffffff;
}

.plan-card.featured {
  border-color: #555555;
  background: #141414;
}

.featured-badge {
  position: absolute;
  top: -9px;
  right: 12px;
  background: #ffffff;
  color: #000000;
  font-family: monospace;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 1px 6px;
  letter-spacing: 0.04em;
}

.plan-card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}

.plan-card-header h3 {
  font-size: 0.95rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: 0.06em;
}

.plan-price {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
}

.plan-desc {
  font-size: 0.78rem;
  color: #888888;
  margin: 0 0 0.85rem 0;
  line-height: 1.35;
}

.plan-perks {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #bbbbbb;
  flex: 1;
}

.plan-perks li.locked {
  color: #555555;
}

.plan-perks li.highlight {
  color: #ffffff;
  font-weight: 700;
}

.plan-action-btn {
  height: 32px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}

.plan-action-btn:hover:not(:disabled) {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.plan-action-btn.primary {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.plan-action-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* Feature Flags Table */
.flags-table-wrap {
  border: 1px solid #222222;
  background: #0d0d0d;
}

.flags-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.flags-table th {
  background: #141414;
  padding: 0.6rem 0.85rem;
  text-align: left;
  font-family: monospace;
  font-size: 0.7rem;
  color: #888888;
  border-bottom: 1px solid #222222;
}

.flags-table td {
  padding: 0.6rem 0.85rem;
  border-bottom: 1px solid #1a1a1a;
  vertical-align: middle;
}

.flag-key code {
  font-family: monospace;
  font-size: 0.75rem;
  color: #ffffff;
}

.flag-desc strong {
  display: block;
  font-size: 0.78rem;
  color: #ffffff;
}

.flag-desc small {
  display: block;
  font-size: 0.7rem;
  color: #777777;
}

.cat-pill {
  font-family: monospace;
  font-size: 0.68rem;
  padding: 2px 6px;
  background: #181818;
  border: 1px solid #282828;
  color: #aaaaaa;
}

.status-pill {
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 7px;
}

.status-pill.enabled {
  background: #ffffff;
  color: #000000;
}

.status-pill.disabled {
  background: #1a1a1a;
  color: #666666;
  border: 1px solid #2a2a2a;
}

.toggle-btn {
  height: 26px;
  padding: 0 0.65rem;
  background: #161616;
  border: 1px solid #333333;
  color: #cccccc;
  font-family: monospace;
  font-size: 0.68rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-btn:hover {
  border-color: #ffffff;
  color: #ffffff;
}

.toggle-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

/* Test Panel */
.test-panel {
  background: #0f0f0f;
  border: 1px solid #242424;
  padding: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.test-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: monospace;
  font-size: 0.75rem;
}

.test-header code {
  margin-left: 0.4rem;
  color: #aaaaaa;
}

.test-exec-btn {
  height: 28px;
  padding: 0 0.8rem;
  background: #1c1c1c;
  border: 1px solid #444444;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.test-exec-btn:hover:not(:disabled) {
  background: #ffffff;
  color: #000000;
}

.test-result-box {
  padding: 0.65rem;
  border: 1px solid #333333;
  background: #090909;
}

.test-result-box.success {
  border-color: #ffffff;
}

.test-result-box.forbidden {
  border-color: #555555;
  background: #0d0d0d;
}

.result-status-row {
  display: flex;
  gap: 0.75rem;
  font-family: monospace;
  font-size: 0.72rem;
  margin-bottom: 0.4rem;
}

.status-code {
  font-weight: 700;
  color: #ffffff;
}

.status-msg {
  color: #888888;
}

.result-json {
  margin: 0;
  font-family: monospace;
  font-size: 0.72rem;
  color: #cccccc;
  max-height: 120px;
  overflow-y: auto;
  line-height: 1.3;
}

/* Footer */
.flags-modal-footer {
  height: 52px;
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
  font-size: 0.72rem;
  color: #666666;
}

.footer-actions {
  display: flex;
  gap: 0.5rem;
}
</style>
