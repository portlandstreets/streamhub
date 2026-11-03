<template>
  <section ref="editorSection" class="markdown-editor-section">
    <!-- Section Header -->
    <div class="editor-header">
      <div class="header-titles">
        <h3>// CHANNEL BIO &amp; RULES</h3>
        <span class="header-subtitle">
          Streamer biography, channel guidelines, and broadcast schedule.
        </span>
      </div>

      <div class="header-meta">
        <span class="save-indicator" :class="{ 'just-saved': justSaved }">
          {{ saveStatusText }}
        </span>
        <div class="view-toggles">
          <button
            type="button"
            class="action-btn sm"
            :class="{ active: viewMode === 'interactive' }"
            @click="viewMode = 'interactive'"
          >
            BLOCK EDITOR
          </button>
          <button
            type="button"
            class="action-btn sm"
            :class="{ active: viewMode === 'preview' }"
            @click="viewMode = 'preview'"
          >
            CLEAN PREVIEW
          </button>
          <button
            type="button"
            class="action-btn sm"
            :class="{ active: viewMode === 'raw' }"
            @click="viewMode = 'raw'"
          >
            RAW MARKDOWN
          </button>
        </div>
      </div>
    </div>

    <!-- Quick Block Creation Toolbar (Notion Style) -->
    <div v-if="viewMode === 'interactive'" class="block-toolbar">
      <button
        type="button"
        class="toolbar-label"
        aria-label="Add paragraph block"
        @click="addBlock('paragraph')"
      >
        + ADD BLOCK:
      </button>
      <button type="button" class="tool-btn" @click="addBlock('paragraph')">PARAGRAPH</button>
      <button type="button" class="tool-btn" @click="addBlock('h1')">HEADING 1</button>
      <button type="button" class="tool-btn" @click="addBlock('h2')">HEADING 2</button>
      <button type="button" class="tool-btn" @click="addBlock('bullet')">BULLET LIST</button>
      <button type="button" class="tool-btn" @click="addBlock('callout')">RULE / CALLOUT</button>
      <button type="button" class="tool-btn" @click="addBlock('code')">CODE / COMMAND</button>

      <div class="toolbar-spacer"></div>

      <button type="button" class="tool-btn secondary" @click="copyFullMarkdown">
        {{ copySuccess ? 'COPIED!' : 'COPY RAW MD' }}
      </button>
      <button type="button" class="tool-btn secondary" @click="resetToTemplate">
        RESET DEFAULT
      </button>
    </div>

    <!-- 1. Interactive Block Editor View with Drag-n-Drop (F3) -->
    <div
      v-if="viewMode === 'interactive'"
      class="blocks-container"
      @dragover.prevent
    >
      <div
        v-for="(block, index) in blocks"
        :key="block.id"
        class="block-item"
        :class="{
          'is-dragging': draggedBlockIndex === index,
          'drag-over': dragOverIndex === index && draggedBlockIndex !== index,
          [block.type]: true
        }"
        draggable="true"
        @dragstart="handleDragStart(index, $event)"
        @dragenter.prevent="handleDragEnter(index)"
        @dragover.prevent="handleDragOver(index)"
        @dragleave="handleDragLeave(index)"
        @drop.prevent="handleDrop(index)"
        @dragend="handleDragEnd"
      >
        <!-- Drag Handle (F3) -->
        <div class="drag-handle" title="Drag to reorder block (F3)">
          <span>⋮⋮</span>
        </div>

        <!-- Block Type Selector -->
        <div class="block-type-picker">
          <select v-model="block.type" @change="triggerSave">
            <option value="paragraph">TEXT</option>
            <option value="h1">H1</option>
            <option value="h2">H2</option>
            <option value="bullet">LIST</option>
            <option value="callout">RULE</option>
            <option value="code">CODE</option>
          </select>
        </div>

        <!-- Content Input & Live Markdown Preview -->
        <div class="block-content-area">
          <textarea
            v-model="block.content"
            class="block-textarea"
            :placeholder="getPlaceholder(block.type)"
            rows="1"
            @input="autoResizeTextarea($event); triggerSave()"
            @keydown.enter.exact="handleEnterKey(index, $event)"
          ></textarea>

          <!-- Inline live markdown preview -->
          <div
            v-if="block.content.trim()"
            class="block-live-preview"
            v-html="renderMarkdownBlock(block)"
          ></div>
        </div>

        <!-- Block Controls: Move Up, Move Down, Delete -->
        <div class="block-actions">
          <button
            type="button"
            class="ctrl-btn"
            :disabled="index === 0"
            title="Move Up"
            @click="moveBlock(index, -1)"
          >
            ↑
          </button>
          <button
            type="button"
            class="ctrl-btn"
            :disabled="index === blocks.length - 1"
            title="Move Down"
            @click="moveBlock(index, 1)"
          >
            ↓
          </button>
          <button
            type="button"
            class="ctrl-btn danger"
            title="Delete Block"
            @click="deleteBlock(index)"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Add Block Bottom Bar -->
      <button type="button" class="add-block-bottom" @click="addBlock('paragraph')">
        + CLICK TO ADD NEW BLOCK (OR PRESS ENTER INSIDE ANY BLOCK)
      </button>
    </div>

    <!-- 2. Clean Formatted Markdown Preview View -->
    <div v-else-if="viewMode === 'preview'" class="clean-preview-container">
      <div v-if="blocks.length === 0" class="empty-state">
        No bio or rules created yet. Switch to Block Editor to add content.
      </div>
      <div v-else class="markdown-rendered-doc">
        <div
          v-for="block in blocks"
          :key="block.id"
          class="preview-rendered-block"
          v-html="renderMarkdownBlock(block)"
        ></div>
      </div>
    </div>

    <!-- 3. Raw Markdown Export View -->
    <div v-else-if="viewMode === 'raw'" class="raw-markdown-container">
      <div class="raw-actions-top">
        <span>// GENERATED MARKDOWN SOURCE</span>
        <button type="button" class="action-btn sm" @click="copyFullMarkdown">
          {{ copySuccess ? 'COPIED TO CLIPBOARD' : 'COPY ALL MARKDOWN' }}
        </button>
      </div>
      <pre class="raw-code"><code>{{ rawMarkdownText }}</code></pre>
    </div>

    <!-- Footer info -->
    <div class="editor-footer">
      <span class="info-tag">BLOCKS COUNT: {{ blocks.length }}</span>
      <span class="info-tag">LOCALSTORAGE KEY: streamhub_channel_notes_{{ streamId }}</span>
      <span class="info-tag">PERSISTENCE: AUTOMATIC ON EVERY KEYSTROKE</span>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';

const props = defineProps({
  streamId: {
    type: [Number, String],
    required: true,
  },
  channelTitle: {
    type: String,
    default: 'Stream',
  },
  isOwner: {
    type: Boolean,
    default: true,
  },
});

const viewMode = ref('interactive'); // 'interactive' | 'preview' | 'raw'
const blocks = ref([]);
const editorSection = ref(null);
const justSaved = ref(false);
const saveStatusText = ref('SAVED TO LOCALSTORAGE');
const copySuccess = ref(false);

// Drag and drop state (F3 requirement)
const draggedBlockIndex = ref(null);
const dragOverIndex = ref(null);

const storageKey = computed(() => `streamhub_channel_notes_${props.streamId}`);

const defaultTemplate = [
  {
    id: 'block-init-1',
    type: 'h1',
    content: 'Welcome to the Official Channel Broadcast',
  },
  {
    id: 'block-init-2',
    type: 'paragraph',
    content: 'Live interactive streams featuring **low-latency HLS video**, real-time WebSocket chat, and community highlights.',
  },
  {
    id: 'block-init-3',
    type: 'callout',
    content: 'CHAT RULES: Be respectful to all viewers, no spamming, and enjoy the stream!',
  },
  {
    id: 'block-init-4',
    type: 'h2',
    content: 'Broadcast Schedule',
  },
  {
    id: 'block-init-5',
    type: 'bullet',
    content: '**Weekdays:** 19:00 - 23:00 UTC (Interactive Gaming & Coding)',
  },
  {
    id: 'block-init-6',
    type: 'bullet',
    content: '**Weekends:** Special community watch parties & VOD reviews',
  },
  {
    id: 'block-init-7',
    type: 'code',
    content: '!discord - Join our community server\n!schedule - View upcoming stream calendar\n!specs - Streamer workstation configuration',
  },
];

// Load from browser localStorage
const loadBlocks = () => {
  try {
    const raw = localStorage.getItem(storageKey.value);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        blocks.value = parsed;
        updateSaveIndicator();
        return;
      }
    }
  } catch (err) {
    console.warn('Could not read from localStorage:', err);
  }
  // Initialize with default template if nothing saved
  blocks.value = JSON.parse(JSON.stringify(defaultTemplate));
  saveBlocks();
};

// Save to browser localStorage (C12 Requirement)
const saveBlocks = () => {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(blocks.value));
    updateSaveIndicator();
  } catch (err) {
    console.error('Failed to save blocks to localStorage:', err);
  }
};

const updateSaveIndicator = () => {
  const now = new Date();
  const timeStr = now.toLocaleTimeString();
  saveStatusText.value = `AUTO-SAVED (LOCALSTORAGE ${timeStr})`;
  justSaved.value = true;
  setTimeout(() => {
    justSaved.value = false;
  }, 1200);
};

let saveDebounceTimer = null;
const triggerSave = () => {
  clearTimeout(saveDebounceTimer);
  saveDebounceTimer = setTimeout(() => {
    saveBlocks();
  }, 250);
};

const addBlock = (type = 'paragraph', insertAfterIndex = null) => {
  const newBlock = {
    id: `block-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type,
    content: '',
  };
  if (insertAfterIndex !== null && insertAfterIndex >= 0) {
    blocks.value.splice(insertAfterIndex + 1, 0, newBlock);
  } else {
    blocks.value.push(newBlock);
  }
  saveBlocks();
  nextTick(() => {
    const textareas = editorSection.value?.querySelectorAll('.block-textarea');
    const targetIdx = insertAfterIndex !== null ? insertAfterIndex + 1 : blocks.value.length - 1;
    if (textareas[targetIdx]) {
      textareas[targetIdx].focus();
    }
  });
};

const deleteBlock = (index) => {
  if (blocks.value.length <= 1) {
    blocks.value = [{
      id: `block-${Date.now()}`,
      type: 'paragraph',
      content: '',
    }];
  } else {
    blocks.value.splice(index, 1);
  }
  triggerSave();
};

const moveBlock = (index, delta) => {
  const targetIndex = index + delta;
  if (targetIndex < 0 || targetIndex >= blocks.value.length) return;
  const item = blocks.value.splice(index, 1)[0];
  blocks.value.splice(targetIndex, 0, item);
  triggerSave();
};

const handleEnterKey = (index, event) => {
  if (event.shiftKey) return; // Allow multiline on Shift+Enter
  event.preventDefault();
  addBlock('paragraph', index);
};

// Drag and drop handlers (F3 Requirement)
const handleDragStart = (index, event) => {
  draggedBlockIndex.value = index;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(index));
  }
};

const handleDragEnter = (index) => {
  dragOverIndex.value = index;
};

const handleDragOver = (index) => {
  dragOverIndex.value = index;
};

const handleDragLeave = (index) => {
  if (dragOverIndex.value === index) {
    dragOverIndex.value = null;
  }
};

const handleDrop = (dropIndex) => {
  const dragIdx = draggedBlockIndex.value;
  if (dragIdx !== null && dragIdx !== dropIndex) {
    const moved = blocks.value.splice(dragIdx, 1)[0];
    blocks.value.splice(dropIndex, 0, moved);
    triggerSave();
  }
  draggedBlockIndex.value = null;
  dragOverIndex.value = null;
};

const handleDragEnd = () => {
  draggedBlockIndex.value = null;
  dragOverIndex.value = null;
};

const resetToTemplate = () => {
  if (confirm('Reset channel notes to default template?')) {
    blocks.value = JSON.parse(JSON.stringify(defaultTemplate));
    saveBlocks();
  }
};

const getPlaceholder = (type) => {
  switch (type) {
    case 'h1':
      return 'Main Section Heading (# Heading 1)...';
    case 'h2':
      return 'Subsection Heading (## Heading 2)...';
    case 'bullet':
      return 'List item (* bold, `code`, links)...';
    case 'callout':
      return 'Important Rule, Notice or Disclaimer...';
    case 'code':
      return 'Code, chat commands or technical parameters...';
    default:
      return 'Write paragraph in Markdown (**bold**, *italic*, `code`, [link](url))...';
  }
};

const autoResizeTextarea = (event) => {
  const el = event.target;
  el.style.height = 'auto';
  el.style.height = `${el.scrollHeight}px`;
};

// Lightweight, secure Markdown rendering
const escapeHtml = (str) => {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

const parseInlineMarkdown = (raw) => {
  let text = escapeHtml(raw);
  // Bold: **text**
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Inline code: `code`
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Links: [label](url)
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  // Line breaks
  text = text.replace(/\n/g, '<br/>');
  return text;
};

const renderMarkdownBlock = (block) => {
  const content = (block.content || '').trim();
  if (!content) return '';

  switch (block.type) {
    case 'h1':
      return `<h1 class="rendered-h1">${parseInlineMarkdown(content)}</h1>`;
    case 'h2':
      return `<h2 class="rendered-h2">${parseInlineMarkdown(content)}</h2>`;
    case 'bullet':
      return `<div class="rendered-bullet"><span class="bullet-dot">•</span><div>${parseInlineMarkdown(content)}</div></div>`;
    case 'callout':
      return `<div class="rendered-callout"><span class="callout-bar"></span><div class="callout-body">${parseInlineMarkdown(content)}</div></div>`;
    case 'code':
      return `<pre class="rendered-code"><code>${escapeHtml(content)}</code></pre>`;
    default:
      return `<p class="rendered-paragraph">${parseInlineMarkdown(content)}</p>`;
  }
};

const rawMarkdownText = computed(() => {
  return blocks.value
    .map((b) => {
      const c = (b.content || '').trim();
      switch (b.type) {
        case 'h1':
          return `# ${c}\n`;
        case 'h2':
          return `## ${c}\n`;
        case 'bullet':
          return `- ${c}`;
        case 'callout':
          return `> **NOTE:** ${c.replace(/\n/g, '\n> ')}\n`;
        case 'code':
          return `\`\`\`\n${c}\n\`\`\`\n`;
        default:
          return `${c}\n`;
      }
    })
    .join('\n');
});

const copyFullMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(rawMarkdownText.value);
    copySuccess.value = true;
    setTimeout(() => {
      copySuccess.value = false;
    }, 2000);
  } catch (err) {
    console.error('Copy failed:', err);
  }
};

watch(() => props.streamId, () => {
  loadBlocks();
});

onMounted(() => {
  loadBlocks();
});
</script>

<style scoped>
.markdown-editor-section {
  background: #000000;
  border: 1px solid #222222;
  margin-top: 24px;
  color: #ffffff;
  display: flex;
  flex-direction: column;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: #0d0d0d;
  border-bottom: 1px solid #222222;
  flex-wrap: wrap;
  gap: 12px;
}

.header-titles h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #ffffff;
}

.header-subtitle {
  font-size: 11px;
  color: #777777;
  letter-spacing: 0.04em;
  margin-top: 4px;
  display: block;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.save-indicator {
  font-family: monospace;
  font-size: 10px;
  color: #666666;
  border: 1px solid #262626;
  padding: 4px 8px;
  background: #111111;
  transition: all 0.3s ease;
}

.save-indicator.just-saved {
  color: #000000;
  background: #ffffff;
  border-color: #ffffff;
  font-weight: 700;
}

.view-toggles {
  display: flex;
  gap: 4px;
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

.action-btn:hover {
  background: #1a1a1a;
  border-color: #ffffff;
}

.action-btn.sm {
  height: 28px;
  padding: 0 10px;
  font-size: 10px;
}

.action-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.block-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: #111111;
  border-bottom: 1px solid #222222;
  flex-wrap: wrap;
}

.toolbar-label {
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 10px;
  font-family: monospace;
  color: #888888;
  margin-right: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.toolbar-label:hover {
  color: #ffffff;
}

.tool-btn {
  height: 26px;
  padding: 0 8px;
  background: #1c1c1c;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
}

.tool-btn:hover {
  background: #333333;
  border-color: #ffffff;
}

.tool-btn.secondary {
  background: #000000;
  color: #888888;
}

.tool-btn.secondary:hover {
  color: #ffffff;
  border-color: #ffffff;
}

.toolbar-spacer {
  flex: 1;
}

.blocks-container {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #0c0c0c;
  border: 1px solid #222222;
  padding: 10px 12px;
  transition: border-color 0.15s ease, background-color 0.15s ease, transform 0.15s ease;
}

.block-item:hover {
  border-color: #444444;
}

.block-item.is-dragging {
  opacity: 0.35;
  background: #1e1e1e;
  border-color: #ffffff;
  border-style: dashed;
}

.block-item.drag-over {
  border-color: #ffffff;
  transform: translateY(-2px);
  background: #141414;
}

.drag-handle {
  cursor: grab;
  user-select: none;
  font-size: 14px;
  color: #666666;
  padding: 4px 2px;
  line-height: 1;
}

.drag-handle:hover {
  color: #ffffff;
}

.block-type-picker select {
  height: 28px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  font-family: monospace;
  padding: 0 4px;
  cursor: pointer;
  outline: none;
}

.block-content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.block-textarea {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  color: #ffffff;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  padding: 4px 6px;
  box-sizing: border-box;
}

.block-textarea:focus {
  background: #141414;
  border-color: #333333;
}

.block-item.h1 .block-textarea {
  font-size: 18px;
  font-weight: 700;
}

.block-item.h2 .block-textarea {
  font-size: 15px;
  font-weight: 700;
}

.block-item.code .block-textarea {
  font-family: monospace;
  font-size: 12px;
  background: #121212;
  border-color: #222222;
  padding: 8px;
}

.block-live-preview {
  padding: 6px 8px;
  background: #121212;
  border-left: 2px solid #444444;
  font-size: 12px;
}

.block-actions {
  display: flex;
  gap: 4px;
}

.ctrl-btn {
  width: 26px;
  height: 26px;
  background: #181818;
  border: 1px solid #333333;
  color: #888888;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}

.ctrl-btn:hover:not(:disabled) {
  background: #333333;
  color: #ffffff;
  border-color: #ffffff;
}

.ctrl-btn.danger:hover {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.ctrl-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

.add-block-bottom {
  height: 38px;
  background: #080808;
  border: 1px dashed #333333;
  color: #888888;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  font-family: monospace;
  cursor: pointer;
  transition: all 0.15s ease;
}

.add-block-bottom:hover {
  background: #141414;
  color: #ffffff;
  border-color: #ffffff;
  border-style: solid;
}

/* 2. Clean Preview Styles */
.clean-preview-container {
  padding: 24px;
  min-height: 200px;
}

.empty-state {
  color: #666666;
  font-family: monospace;
  text-align: center;
  padding: 40px;
}

.markdown-rendered-doc {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

:deep(.rendered-h1) {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 10px 0 4px 0;
  border-bottom: 1px solid #222222;
  padding-bottom: 6px;
  color: #ffffff;
}

:deep(.rendered-h2) {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.03em;
  margin: 8px 0 2px 0;
  color: #dddddd;
}

:deep(.rendered-paragraph) {
  font-size: 13px;
  line-height: 1.6;
  color: #cccccc;
  margin: 0;
}

:deep(.rendered-bullet) {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: #cccccc;
}

:deep(.bullet-dot) {
  color: #ffffff;
  font-weight: 700;
}

:deep(.rendered-callout) {
  display: flex;
  background: #111111;
  border: 1px solid #2a2a2a;
}

:deep(.callout-bar) {
  width: 4px;
  background: #ffffff;
  flex-shrink: 0;
}

:deep(.callout-body) {
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.5;
  color: #ffffff;
  font-weight: 500;
}

:deep(.rendered-code) {
  background: #0d0d0d;
  border: 1px solid #222222;
  padding: 12px 16px;
  font-family: monospace;
  font-size: 12px;
  color: #eeeeee;
  overflow-x: auto;
  margin: 0;
}

:deep(a) {
  color: #ffffff;
  text-decoration: underline;
}

:deep(code) {
  font-family: monospace;
  background: #1c1c1c;
  padding: 2px 6px;
  font-size: 11px;
  border: 1px solid #333333;
}

/* 3. Raw Markdown View */
.raw-markdown-container {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.raw-actions-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: monospace;
  font-size: 11px;
  color: #777777;
}

.raw-code {
  background: #080808;
  border: 1px solid #222222;
  padding: 16px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #ffffff;
  overflow-x: auto;
  white-space: pre-wrap;
  margin: 0;
}

.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #0a0a0a;
  border-top: 1px solid #222222;
  flex-wrap: wrap;
  gap: 10px;
}

.info-tag {
  font-size: 10px;
  font-family: monospace;
  color: #555555;
  letter-spacing: 0.05em;
}
</style>
