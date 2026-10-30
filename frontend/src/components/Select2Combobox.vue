<template>
  <div class="select2-combobox-wrapper" ref="wrapperRef">
    <label v-if="label" class="combobox-label">
      {{ label }}
    </label>

    <!-- Main Select2 Container -->
    <div
      class="select2-container"
      :class="{
        'is-open': isOpen,
        'is-loading': isLoading,
        'has-value': !!selectedItem,
        'is-disabled': disabled
      }"
    >
      <!-- Display / Trigger Bar -->
      <div class="select2-selection" @click="toggleDropdown">
        <span class="select2-prompt-prefix">//</span>

        <!-- Active Selected View -->
        <div v-if="selectedItem && !isOpen" class="select2-rendered-item">
          <span class="status-indicator" :class="{ live: selectedItem.is_live }"></span>
          <span class="item-title">{{ selectedItem.title || selectedItem.text }}</span>
          <span v-if="selectedItem.owner" class="item-owner">@{{ selectedItem.owner }}</span>
        </div>

        <!-- Inline Input Field -->
        <input
          v-else
          ref="inputRef"
          v-model="searchQuery"
          type="text"
          class="select2-search-input"
          :placeholder="selectedItem ? (selectedItem.title || selectedItem.text) : placeholder"
          :disabled="disabled"
          @input="onInput"
          @keydown.down.prevent="onKeyDown"
          @keydown.up.prevent="onKeyUp"
          @keydown.enter.prevent="onKeyEnter"
          @keydown.esc.prevent="closeDropdown"
          @focus="openDropdown"
        />

        <!-- Clear Selection Button -->
        <button
          v-if="selectedItem"
          type="button"
          class="select2-clear-btn"
          title="Clear"
          @click.stop="clearSelection"
        >
          &times;
        </button>

        <!-- Loading Spinner or Caret -->
        <span v-if="isLoading" class="select2-spinner"></span>
        <span v-else class="select2-arrow">[v]</span>
      </div>

      <!-- Dropdown Results Menu -->
      <div v-if="isOpen" class="select2-dropdown">
        <!-- Message: Less than min characters -->
        <div v-if="queryLength < minChars" class="select2-notice">
          <span>Enter {{ minChars }} or more characters to search...</span>
        </div>

        <!-- Message: Searching / Loading -->
        <div v-else-if="isLoading && results.length === 0" class="select2-notice">
          <span class="select2-spinner sm"></span>
          <span>Searching channels...</span>
        </div>

        <!-- Message: No results found -->
        <div v-else-if="!isLoading && queryLength >= minChars && results.length === 0" class="select2-notice empty">
          <span>No channels found for "{{ searchQuery }}"</span>
        </div>

        <!-- Results List -->
        <ul v-else-if="results.length > 0" class="select2-results-list" ref="listRef">
          <li
            v-for="(item, idx) in results"
            :key="item.id"
            class="select2-result-item"
            :class="{
              'is-highlighted': highlightedIndex === idx,
              'is-selected': selectedItem && selectedItem.id === item.id
            }"
            @mouseenter="highlightedIndex = idx"
            @click.stop="selectItem(item)"
          >
            <div class="result-info">
              <div class="result-title-line">
                <span class="result-title" v-html="item.highlights?.title?.[0] || item.title || item.text"></span>
                <span v-if="item.is_live" class="live-pill">LIVE ({{ item.viewers_count || 0 }})</span>
                <span v-else class="offline-pill">OFFLINE</span>
              </div>
              <div class="result-sub-line">
                <span v-if="item.owner" class="result-owner">@{{ item.owner }}</span>
                <span v-if="item.description" class="result-desc" v-html="item.highlights?.description?.[0] || item.description"></span>
              </div>
            </div>
          </li>
        </ul>

        <div v-if="hasMore" class="select2-footer">
          <span>More matches on server...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: [Number, String, Object], default: null },
  endpoint: { type: String, required: true },
  label: { type: String, default: '' },
  placeholder: { type: String, default: 'Search channels (min 3 chars)...' },
  minChars: { type: Number, default: 3 },
  debounceMs: { type: Number, default: 300 },
  disabled: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue', 'change', 'select']);

const wrapperRef = ref(null);
const inputRef = ref(null);
const listRef = ref(null);

const searchQuery = ref('');
const results = ref([]);
const totalCount = ref(0);
const hasMore = ref(false);
const isOpen = ref(false);
const isLoading = ref(false);
const highlightedIndex = ref(-1);
const selectedItem = ref(null);

let debounceTimer = null;
let abortController = null;

const queryLength = computed(() => searchQuery.value.trim().length);

watch(
  () => props.modelValue,
  (val) => {
    if (val && typeof val === 'object') {
      selectedItem.value = val;
    } else if (!val) {
      selectedItem.value = null;
    }
  },
  { immediate: true }
);

function toggleDropdown() {
  if (props.disabled) return;
  if (isOpen.value) {
    closeDropdown();
  } else {
    openDropdown();
  }
}

function openDropdown() {
  if (props.disabled) return;
  isOpen.value = true;
  highlightedIndex.value = -1;
  setTimeout(() => inputRef.value?.focus(), 50);

  if (queryLength.value >= props.minChars && results.value.length === 0) {
    executeSearch(searchQuery.value);
  }
}

function closeDropdown() {
  isOpen.value = false;
  highlightedIndex.value = -1;
}

function clearSelection() {
  selectedItem.value = null;
  searchQuery.value = '';
  results.value = [];
  emit('update:modelValue', null);
  emit('change', null);
  emit('select', null);
  setTimeout(() => inputRef.value?.focus(), 50);
}

function selectItem(item) {
  selectedItem.value = item;
  searchQuery.value = '';
  closeDropdown();
  emit('update:modelValue', item.id);
  emit('change', item);
  emit('select', item);
}

function onInput() {
  isOpen.value = true;
  highlightedIndex.value = -1;

  if (debounceTimer) clearTimeout(debounceTimer);

  const query = searchQuery.value.trim();

  if (query.length < props.minChars) {
    results.value = [];
    totalCount.value = 0;
    isLoading.value = false;
    if (abortController) abortController.abort();
    return;
  }

  // 300 ms debounce delay before firing request
  isLoading.value = true;
  debounceTimer = setTimeout(() => {
    executeSearch(query);
  }, props.debounceMs);
}

async function executeSearch(query) {
  if (abortController) abortController.abort();
  abortController = new AbortController();

  isLoading.value = true;
  try {
    const url = new URL(props.endpoint, window.location.origin);
    url.searchParams.set('q', query);
    url.searchParams.set('limit', '20');

    const res = await fetch(url.toString(), { signal: abortController.signal });
    if (!res.ok) throw new Error('Search failed');

    const data = await res.json();
    results.value = data.results || [];
    totalCount.value = data.total !== undefined ? data.total : results.value.length;
    hasMore.value = data.pagination?.more || false;
    highlightedIndex.value = results.value.length > 0 ? 0 : -1;
  } catch (err) {
    if (err.name !== 'AbortError') {
      results.value = [];
    }
  } finally {
    isLoading.value = false;
  }
}

function onKeyDown() {
  if (!isOpen.value) {
    openDropdown();
    return;
  }
  if (results.value.length === 0) return;
  highlightedIndex.value = (highlightedIndex.value + 1) % results.value.length;
  scrollToHighlighted();
}

function onKeyUp() {
  if (!isOpen.value) return;
  if (results.value.length === 0) return;
  highlightedIndex.value =
    (highlightedIndex.value - 1 + results.value.length) % results.value.length;
  scrollToHighlighted();
}

function onKeyEnter() {
  if (isOpen.value && highlightedIndex.value >= 0 && results.value[highlightedIndex.value]) {
    selectItem(results.value[highlightedIndex.value]);
  }
}

function scrollToHighlighted() {
  setTimeout(() => {
    const list = listRef.value;
    if (!list) return;
    const items = list.querySelectorAll('.select2-result-item');
    const target = items[highlightedIndex.value];
    if (target) {
      target.scrollIntoView({ block: 'nearest' });
    }
  }, 10);
}

function handleDocumentClick(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    closeDropdown();
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick);
  if (debounceTimer) clearTimeout(debounceTimer);
  if (abortController) abortController.abort();
});
</script>

<style scoped>
.select2-combobox-wrapper {
  position: relative;
  width: 100%;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 11px;
}

.combobox-label {
  display: block;
  font-size: 10px;
  color: #888;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Pure Black and White Container */
.select2-container {
  position: relative;
  background: #0d0d0d;
  border: 1px solid #333333;
  transition: border-color 0.15s ease;
}

.select2-container:hover {
  border-color: #666666;
}

.select2-container.is-open {
  border-color: #ffffff;
}

.select2-selection {
  display: flex;
  align-items: center;
  padding: 0 10px;
  height: 32px;
  cursor: text;
  gap: 8px;
}

.select2-prompt-prefix {
  font-size: 11px;
  color: #666666;
  font-weight: 700;
  user-select: none;
}

.select2-rendered-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
}

.status-indicator {
  width: 6px;
  height: 6px;
  background: #444444;
  flex-shrink: 0;
}

.status-indicator.live {
  background: #ffffff;
}

.item-title {
  color: #ffffff;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-owner {
  color: #888888;
  font-size: 10px;
}

.select2-search-input {
  flex: 1;
  background: transparent;
  border: 0;
  color: #ffffff;
  font-family: inherit;
  font-size: 11px;
  outline: none;
  padding: 0;
  min-width: 0;
}

.select2-search-input::placeholder {
  color: #666666;
}

.select2-clear-btn {
  background: transparent;
  border: 0;
  color: #888888;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}

.select2-clear-btn:hover {
  color: #ffffff;
}

.select2-arrow {
  color: #666666;
  font-size: 10px;
  pointer-events: none;
  font-family: inherit;
}

.select2-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #333333;
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: s2-spin 0.6s linear infinite;
  flex-shrink: 0;
}

.select2-spinner.sm {
  width: 10px;
  height: 10px;
}

@keyframes s2-spin {
  to {
    transform: rotate(360deg);
  }
}

/* Dropdown Results Overlay */
.select2-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  background: #0d0d0d;
  border: 1px solid #ffffff;
  border-top: 0;
  max-height: 240px;
  overflow-y: auto;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.95);
}

.select2-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  color: #888888;
  font-size: 10px;
  justify-content: center;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.select2-results-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.select2-result-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  cursor: pointer;
  border-bottom: 1px solid #1a1a1a;
  transition: background 0.1s ease;
}

.select2-result-item:last-child {
  border-bottom: 0;
}

.select2-result-item.is-highlighted {
  background: #222222;
}

.select2-result-item.is-selected {
  background: #1c1c1c;
  border-left: 2px solid #ffffff;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.result-title-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.result-title {
  color: #ffffff;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(mark) {
  background: #ffffff;
  color: #000000;
  padding: 0 2px;
  font-weight: 800;
}

.live-pill {
  font-size: 8px;
  background: #ffffff;
  color: #000000;
  padding: 1px 4px;
  font-weight: 700;
  flex-shrink: 0;
}

.offline-pill {
  font-size: 8px;
  color: #666666;
  border: 1px solid #333333;
  padding: 0 3px;
  flex-shrink: 0;
}

.result-sub-line {
  display: flex;
  gap: 8px;
  font-size: 10px;
  color: #777777;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.result-owner {
  color: #aaaaaa;
}

.result-desc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select2-footer {
  padding: 6px 10px;
  font-size: 9px;
  color: #666666;
  background: #080808;
  text-align: center;
  border-top: 1px solid #1a1a1a;
  text-transform: uppercase;
}
</style>
