<template>
  <div class="mcp-modal-backdrop" @click.self="$emit('close')">
    <div class="mcp-modal-window">
      <!-- Header -->
      <div class="mcp-modal-header">
        <div class="header-title-wrap">
          <span class="tech-tag">// C22 MODEL CONTEXT PROTOCOL</span>
          <h2>STREAMHUB MCP SERVER (JSON-RPC 2.0)</h2>
          <span class="status-indicator active">
            &bull; MCP SPEC 2024-11-05 ONLINE
          </span>
        </div>
        <button class="win-btn close" @click="$emit('close')" title="Close">&times;</button>
      </div>

      <!-- Navigation Tabs -->
      <div class="mcp-nav-tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'tools' }"
          @click="activeTab = 'tools'"
        >
          AVAILABLE TOOLS (4 READ &bull; 3 WRITE)
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'console' }"
          @click="activeTab = 'console'"
        >
          JSON-RPC 2.0 TEST CONSOLE
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'config' }"
          @click="activeTab = 'config'"
        >
          CLAUDE &amp; COPILOT CLIENT SETUP
        </button>
      </div>

      <!-- Body -->
      <div class="mcp-modal-body">
        <!-- Tab 1: Tools Explorer -->
        <div v-if="activeTab === 'tools'" class="tab-content">
          <div class="tools-summary-bar">
            <span>TOTAL SPECIFIED TOOLS: <strong>{{ tools.length }}</strong></span>
            <span>READ TOOLS (C1/C5 QUERY): <strong>4</strong></span>
            <span>WRITE TOOLS (C1/C5 MUTATE): <strong>3</strong></span>
          </div>

          <div class="tools-grid">
            <div
              v-for="t in tools"
              :key="t.name"
              class="tool-card"
              :class="{ write: t.name.startsWith('create') || t.name.startsWith('update') || t.name.startsWith('post') }"
            >
              <div class="tool-card-head">
                <div class="tool-title-wrap">
                  <span class="tool-type-badge">
                    {{ (t.name.startsWith('create') || t.name.startsWith('update') || t.name.startsWith('post')) ? '[WRITE TOOL]' : '[READ TOOL]' }}
                  </span>
                  <code>{{ t.name }}</code>
                </div>
                <button
                  class="exec-tool-btn"
                  :disabled="loadingTool === t.name"
                  @click="executeToolQuick(t.name)"
                >
                  {{ loadingTool === t.name ? 'EXECUTING...' : 'RUN VIA MCP' }}
                </button>
              </div>

              <p class="tool-desc">{{ t.description }}</p>

              <div class="schema-box">
                <span class="schema-label">INPUT SCHEMA:</span>
                <pre>{{ JSON.stringify(t.inputSchema, null, 2) }}</pre>
              </div>

              <div v-if="toolResults[t.name]" class="tool-output-box">
                <span class="output-label">MCP RESPONSE (JSON-RPC):</span>
                <pre>{{ toolResults[t.name] }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: Raw JSON-RPC 2.0 Console -->
        <div v-else-if="activeTab === 'console'" class="tab-content console-tab">
          <div class="console-preset-bar">
            <span class="preset-label">LOAD PRESET QUERY:</span>
            <button class="preset-btn" @click="loadPreset('initialize')">initialize</button>
            <button class="preset-btn" @click="loadPreset('tools/list')">tools/list</button>
            <button class="preset-btn" @click="loadPreset('list_streams')">tools/call (list_streams)</button>
            <button class="preset-btn" @click="loadPreset('get_telemetry')">tools/call (telemetry)</button>
            <button class="preset-btn" @click="loadPreset('create_stream')">tools/call (create_stream)</button>
          </div>

          <div class="console-layout">
            <div class="console-pane">
              <span class="pane-title">REQUEST PAYLOAD (POST /api/v1/mcp)</span>
              <textarea v-model="rpcRequestText" class="rpc-input" spellcheck="false"></textarea>
              <button class="action-btn primary mt-2" :disabled="rpcLoading" @click="sendRpcRequest">
                {{ rpcLoading ? 'SENDING TO MCP SERVER...' : 'SEND JSON-RPC 2.0 REQUEST' }}
              </button>
            </div>

            <div class="console-pane">
              <span class="pane-title">MCP SERVER RESPONSE</span>
              <pre class="rpc-output">{{ rpcResponseText || '// Response will be displayed here' }}</pre>
            </div>
          </div>
        </div>

        <!-- Tab 3: Client Config (Claude, Cursor, Copilot) -->
        <div v-else class="tab-content config-tab">
          <h3>// CONNECTING EXTERNAL MCP CLIENTS (CLAUDE / CURSOR / COPILOT)</h3>
          <p>
            The StreamHub MCP server implements the official <strong>Model Context Protocol (2024-11-05)</strong>.
            External agents such as <strong>Claude Desktop</strong>, <strong>GitHub Copilot</strong>, or <strong>Cursor</strong> can directly invoke models from C1 and C5.
          </p>

          <div class="config-block">
            <span class="config-label">Claude Desktop Configuration (<code>claude_desktop_config.json</code>):</span>
            <pre class="code-block">{
  "mcpServers": {
    "streamhub": {
      "command": "npx",
      "args": ["-y", "mcp-proxy", "http://localhost:8000/api/v1/mcp"]
    }
  }
}</pre>
          </div>

          <div class="config-block">
            <span class="config-label">Direct HTTP / SSE Endpoint:</span>
            <pre class="code-block">POST http://localhost:8000/api/v1/mcp
GET  http://localhost:8000/api/v1/mcp/sse</pre>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="mcp-modal-footer">
        <span class="footer-hint">
          JSON-RPC 2.0 PROTOCOL ENGINE &bull; 4 READ TOOLS &bull; 3 WRITE TOOLS &bull; INTEGRATED WITH C21 AGENT
        </span>
        <button class="win-btn" @click="$emit('close')">CLOSE</button>
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
  }
});

defineEmits(['close']);

const activeTab = ref('tools');
const tools = ref([]);
const loadingTool = ref('');
const toolResults = ref({});

const rpcRequestText = ref('{\n  "jsonrpc": "2.0",\n  "id": 1,\n  "method": "tools/list"\n}');
const rpcResponseText = ref('');
const rpcLoading = ref(false);

async function fetchToolsList() {
  try {
    const res = await fetch(`${props.coreApi}/api/v1/mcp/tools`);
    if (res.ok) {
      const data = await res.json();
      tools.value = data.tools || [];
    }
  } catch (err) {
    console.error('Failed to load MCP tools list:', err);
  }
}

async function executeToolQuick(toolName) {
  loadingTool.value = toolName;
  let args = {};

  if (toolName === 'list_streams') {
    args = { live_only: false, limit: 5 };
  } else if (toolName === 'get_stream_telemetry') {
    args = { stream_id: 1 };
  } else if (toolName === 'get_recordings_archive') {
    args = { limit: 3 };
  } else if (toolName === 'create_stream') {
    args = { title: `MCP Broadcast #${Math.floor(Math.random() * 900 + 100)}`, description: 'Created via MCP Quick Run' };
  } else if (toolName === 'update_stream_settings') {
    args = { stream_id: 1, low_latency_enabled: true, max_resolution: '1080p' };
  } else if (toolName === 'post_chat_announcement') {
    args = { stream_id: 1, announcement_text: 'Broadcast scheduled for 20:00 UTC' };
  }

  const payload = {
    jsonrpc: '2.0',
    id: Date.now(),
    method: 'tools/call',
    params: {
      name: toolName,
      arguments: args
    }
  };

  try {
    const res = await fetch(`${props.coreApi}/api/v1/mcp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    toolResults.value[toolName] = JSON.stringify(data, null, 2);
  } catch (err) {
    toolResults.value[toolName] = `Error: ${String(err)}`;
  } finally {
    loadingTool.value = '';
  }
}

function loadPreset(type) {
  if (type === 'initialize') {
    rpcRequestText.value = JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: { protocolVersion: '2024-11-05' }
    }, null, 2);
  } else if (type === 'tools/list') {
    rpcRequestText.value = JSON.stringify({
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/list'
    }, null, 2);
  } else if (type === 'list_streams') {
    rpcRequestText.value = JSON.stringify({
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: {
        name: 'list_streams',
        arguments: { live_only: true }
      }
    }, null, 2);
  } else if (type === 'get_telemetry') {
    rpcRequestText.value = JSON.stringify({
      jsonrpc: '2.0',
      id: 4,
      method: 'tools/call',
      params: {
        name: 'get_stream_telemetry',
        arguments: { stream_id: 1 }
      }
    }, null, 2);
  } else if (type === 'create_stream') {
    rpcRequestText.value = JSON.stringify({
      jsonrpc: '2.0',
      id: 5,
      method: 'tools/call',
      params: {
        name: 'create_stream',
        arguments: {
          title: 'Night Speedrun via MCP',
          description: 'Created through Model Context Protocol write tool'
        }
      }
    }, null, 2);
  }
}

async function sendRpcRequest() {
  rpcLoading.value = true;
  try {
    let parsed;
    try {
      parsed = JSON.parse(rpcRequestText.value);
    } catch {
      alert('Invalid JSON in request textarea');
      return;
    }
    const res = await fetch(`${props.coreApi}/api/v1/mcp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed)
    });
    const data = await res.json();
    rpcResponseText.value = JSON.stringify(data, null, 2);
  } catch (err) {
    rpcResponseText.value = `Request Failed: ${String(err)}`;
  } finally {
    rpcLoading.value = false;
  }
}

onMounted(() => {
  fetchToolsList();
});
</script>

<style scoped>
.mcp-modal-backdrop {
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

.mcp-modal-window {
  background: #0a0a0a;
  border: 1px solid #333333;
  width: 100%;
  max-width: 1200px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.9);
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  overflow: hidden;
}

/* Header */
.mcp-modal-header {
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

.status-indicator.active {
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
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

/* Navigation Tabs */
.mcp-nav-tabs {
  height: 40px;
  background: #111111;
  border-bottom: 1px solid #222222;
  display: flex;
  padding: 0 1rem;
  gap: 0.5rem;
  flex-shrink: 0;
}

.tab-btn {
  height: 100%;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #888888;
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: #ffffff;
}

.tab-btn.active {
  color: #ffffff;
  border-bottom-color: #ffffff;
}

/* Body */
.mcp-modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.tools-summary-bar {
  display: flex;
  gap: 1.5rem;
  font-family: monospace;
  font-size: 0.75rem;
  color: #888888;
  border-bottom: 1px solid #222222;
  padding-bottom: 0.6rem;
  margin-bottom: 1rem;
}

.tools-summary-bar strong {
  color: #ffffff;
}

/* Tools Grid */
.tools-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.tool-card {
  background: #0f0f0f;
  border: 1px solid #222222;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.tool-card.write {
  border-color: #383838;
  background: #121212;
}

.tool-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tool-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tool-type-badge {
  font-family: monospace;
  font-size: 0.68rem;
  color: #aaaaaa;
}

.tool-card-head code {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
}

.exec-tool-btn {
  height: 26px;
  padding: 0 0.7rem;
  background: #181818;
  border: 1px solid #444444;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.68rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.exec-tool-btn:hover:not(:disabled) {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.tool-desc {
  font-size: 0.75rem;
  color: #888888;
  margin: 0;
  line-height: 1.35;
}

.schema-box {
  background: #080808;
  border: 1px solid #1c1c1c;
  padding: 0.5rem;
}

.schema-label {
  font-family: monospace;
  font-size: 0.65rem;
  color: #666666;
  display: block;
  margin-bottom: 0.25rem;
}

.schema-box pre {
  margin: 0;
  font-family: monospace;
  font-size: 0.68rem;
  color: #aaaaaa;
  max-height: 80px;
  overflow-y: auto;
}

.tool-output-box {
  background: #050505;
  border: 1px solid #333333;
  padding: 0.5rem;
}

.output-label {
  font-family: monospace;
  font-size: 0.65rem;
  color: #ffffff;
  display: block;
  margin-bottom: 0.25rem;
}

.tool-output-box pre {
  margin: 0;
  font-family: monospace;
  font-size: 0.68rem;
  color: #cccccc;
  max-height: 120px;
  overflow-y: auto;
}

/* Console Tab */
.console-preset-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.preset-label {
  font-family: monospace;
  font-size: 0.72rem;
  color: #888888;
}

.preset-btn {
  height: 26px;
  padding: 0 0.6rem;
  background: #141414;
  border: 1px solid #282828;
  color: #cccccc;
  font-family: monospace;
  font-size: 0.68rem;
  cursor: pointer;
}

.preset-btn:hover {
  border-color: #ffffff;
}

.console-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  height: calc(100% - 40px);
}

.console-pane {
  display: flex;
  flex-direction: column;
}

.pane-title {
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  color: #888888;
  margin-bottom: 0.4rem;
}

.rpc-input {
  flex: 1;
  background: #080808;
  border: 1px solid #242424;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.75rem;
  padding: 0.75rem;
  resize: none;
  min-height: 320px;
}

.rpc-output {
  flex: 1;
  background: #080808;
  border: 1px solid #242424;
  color: #cccccc;
  font-family: monospace;
  font-size: 0.75rem;
  padding: 0.75rem;
  margin: 0;
  overflow-y: auto;
  min-height: 320px;
}

/* Config Tab */
.config-tab h3 {
  font-size: 0.95rem;
  margin: 0 0 0.5rem 0;
}

.config-tab p {
  font-size: 0.8rem;
  color: #888888;
  margin-bottom: 1.25rem;
}

.config-block {
  margin-bottom: 1.25rem;
}

.config-label {
  font-family: monospace;
  font-size: 0.72rem;
  color: #ffffff;
  display: block;
  margin-bottom: 0.35rem;
}

.code-block {
  background: #080808;
  border: 1px solid #222222;
  padding: 0.85rem;
  margin: 0;
  font-family: monospace;
  font-size: 0.75rem;
  color: #cccccc;
}

/* Footer */
.mcp-modal-footer {
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
