<template>
  <div class="canvas-modal-backdrop" @click.self="$emit('close')">
    <div class="canvas-modal-window">
      <!-- Header -->
      <div class="canvas-modal-header">
        <div class="header-title-wrap">
          <span class="tech-tag">// F6 CANVAS 2D</span>
          <h2>AUDIO VISUALIZER &amp; 2D PARTICLE STUDIO</h2>
          <span class="status-indicator" :class="{ active: isAudioActive }">
            {{ isAudioActive ? 'AUDIO ENGINE ACTIVE' : 'AUDIO ENGINE READY' }}
          </span>
        </div>
        <div class="header-actions">
          <button class="win-btn" @click="togglePause" :title="isPaused ? 'Resume Animation' : 'Pause Animation'">
            {{ isPaused ? 'RESUME' : 'PAUSE' }}
          </button>
          <button class="win-btn" @click="takeSnapshot" title="Export canvas frame as PNG image">
            SNAPSHOT PNG
          </button>
          <button class="win-btn close" @click="$emit('close')" title="Close">&times;</button>
        </div>
      </div>

      <!-- Main Layout: Canvas Stage + Control Sidebar -->
      <div class="canvas-modal-body">
        <!-- Canvas Stage Area -->
        <div class="stage-container" ref="stageContainer">
          <canvas
            ref="canvasRef"
            class="visualizer-canvas"
            @mousemove="handleCanvasMouseMove"
            @mouseenter="isHovering = true"
            @mouseleave="handleCanvasMouseLeave"
            @mousedown="handleCanvasMouseDown"
          ></canvas>

          <!-- Interactive Canvas Overlays / Crosshairs -->
          <div v-if="isHovering && currentMode !== 'particles'" class="canvas-hud-overlay" :style="crosshairStyle">
            <span class="hud-freq">{{ hoverFreqLabel }}</span>
            <span class="hud-db">{{ hoverDbLabel }}</span>
          </div>

          <!-- Bottom Stage Status Bar -->
          <div class="stage-status-bar">
            <div class="status-cell">
              <span class="label">FPS:</span>
              <span class="val">{{ currentFps }}</span>
            </div>
            <div class="status-cell">
              <span class="label">MODE:</span>
              <span class="val">{{ currentMode.toUpperCase() }}</span>
            </div>
            <div class="status-cell">
              <span class="label">SOURCE:</span>
              <span class="val">{{ audioSource.toUpperCase() }}</span>
            </div>
            <div class="status-cell">
              <span class="label">BASS:</span>
              <div class="mini-meter-bar">
                <div class="mini-meter-fill" :style="{ width: `${bassLevel}%` }"></div>
              </div>
            </div>
            <div class="status-cell">
              <span class="label">TREBLE:</span>
              <div class="mini-meter-bar">
                <div class="mini-meter-fill" :style="{ width: `${trebleLevel}%` }"></div>
              </div>
            </div>
            <div class="status-cell hint">
              <span>CLICK TO SPAWN SHOCKWAVE &bull; DRAG MOUSE TO INTERACT</span>
            </div>
          </div>
        </div>

        <!-- Controls Sidebar -->
        <aside class="control-panel">
          <!-- Visualization Mode -->
          <div class="control-section">
            <span class="section-title">2D VISUALIZATION MODE</span>
            <div class="mode-grid">
              <button
                class="mode-btn"
                :class="{ active: currentMode === 'spectrum' }"
                @click="setMode('spectrum')"
              >
                SPECTRUM BARS
              </button>
              <button
                class="mode-btn"
                :class="{ active: currentMode === 'oscilloscope' }"
                @click="setMode('oscilloscope')"
              >
                OSCILLOSCOPE
              </button>
              <button
                class="mode-btn"
                :class="{ active: currentMode === 'radial' }"
                @click="setMode('radial')"
              >
                RADIAL VORTEX
              </button>
              <button
                class="mode-btn"
                :class="{ active: currentMode === 'particles' }"
                @click="setMode('particles')"
              >
                PARTICLE FIELD
              </button>
            </div>
          </div>

          <!-- Audio Input Source -->
          <div class="control-section">
            <span class="section-title">AUDIO SIGNAL SOURCE</span>
            <div class="source-select-group">
              <button
                class="source-btn"
                :class="{ active: audioSource === 'synth' }"
                @click="setAudioSource('synth')"
              >
                SYNTH BEAT (DEMO)
              </button>
              <button
                class="source-btn"
                :class="{ active: audioSource === 'mic' }"
                @click="setAudioSource('mic')"
              >
                MICROPHONE INPUT
              </button>
              <button
                class="source-btn"
                :class="{ active: audioSource === 'stream' }"
                @click="setAudioSource('stream')"
              >
                LIVE STREAM AUDIO
              </button>
              <button
                class="source-btn"
                :class="{ active: audioSource === 'tone' }"
                @click="setAudioSource('tone')"
              >
                TEST TONE GENERATOR
              </button>
            </div>

            <!-- Tone Generator frequency slider if active -->
            <div v-if="audioSource === 'tone'" class="slider-row sub-row">
              <div class="slider-label">
                <span>TONE FREQUENCY</span>
                <span>{{ toneFrequency }} Hz</span>
              </div>
              <input
                type="range"
                min="50"
                max="5000"
                step="10"
                v-model.number="toneFrequency"
                @input="updateToneFrequency"
              />
            </div>
          </div>

          <!-- DSP & FFT Tuning Controls -->
          <div class="control-section">
            <span class="section-title">DSP &amp; CANVAS TUNING</span>

            <div class="slider-row">
              <div class="slider-label">
                <span>GAIN / SENSITIVITY</span>
                <span>{{ sensitivity.toFixed(1) }}x</span>
              </div>
              <input type="range" min="0.5" max="3.0" step="0.1" v-model.number="sensitivity" />
            </div>

            <div class="slider-row">
              <div class="slider-label">
                <span>FFT SMOOTHING TIME</span>
                <span>{{ smoothing.toFixed(2) }}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                v-model.number="smoothing"
                @input="updateSmoothing"
              />
            </div>

            <div class="slider-row">
              <div class="slider-label">
                <span>FFT BINS RESOLUTION</span>
                <span>{{ fftSize }}</span>
              </div>
              <div class="fft-chips">
                <button
                  v-for="size in [128, 256, 512, 1024]"
                  :key="size"
                  class="chip-btn"
                  :class="{ active: fftSize === size }"
                  @click="setFftSize(size)"
                >
                  {{ size }}
                </button>
              </div>
            </div>

            <div v-if="currentMode === 'particles'" class="slider-row">
              <div class="slider-label">
                <span>PARTICLE COUNT</span>
                <span>{{ particleCount }}</span>
              </div>
              <input
                type="range"
                min="50"
                max="400"
                step="25"
                v-model.number="particleCount"
                @input="reinitParticles"
              />
            </div>
          </div>

          <!-- Toggles & Display Options -->
          <div class="control-section">
            <span class="section-title">2D DISPLAY TOGGLES</span>
            <div class="toggle-list">
              <label class="check-item">
                <input type="checkbox" v-model="showGrid" />
                <span>DECIBEL &amp; FREQ GRID HUD</span>
              </label>
              <label class="check-item">
                <input type="checkbox" v-model="showPeakCaps" />
                <span>PEAK CAPS WITH GRAVITY FALL</span>
              </label>
              <label class="check-item">
                <input type="checkbox" v-model="showTrails" />
                <span>PHOSPHOR MOTION TRAILS</span>
              </label>
              <label class="check-item">
                <input type="checkbox" v-model="invertColors" />
                <span>HIGH-CONTRAST INVERT THEME</span>
              </label>
            </div>
          </div>

          <!-- Audio State Button -->
          <div class="control-footer">
            <button
              class="engine-btn"
              :class="{ active: isAudioActive }"
              @click="toggleAudioEngine"
            >
              {{ isAudioActive ? 'STOP AUDIO GENERATOR' : 'START AUDIO ENGINE' }}
            </button>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  videoElement: {
    type: Object,
    default: null
  }
});

defineEmits(['close']);

// DOM Elements
const stageContainer = ref(null);
const canvasRef = ref(null);

// Visualization settings
const currentMode = ref('spectrum'); // 'spectrum' | 'oscilloscope' | 'radial' | 'particles'
const audioSource = ref('synth'); // 'synth' | 'mic' | 'stream' | 'tone'
const isPaused = ref(false);
const isAudioActive = ref(false);

// Sliders & Tuning
const sensitivity = ref(1.4);
const smoothing = ref(0.82);
const fftSize = ref(256);
const particleCount = ref(180);
const toneFrequency = ref(440);

// Display Toggles
const showGrid = ref(true);
const showPeakCaps = ref(true);
const showTrails = ref(true);
const invertColors = ref(false);

// Metrics & Interaction
const currentFps = ref(60);
const bassLevel = ref(0);
const trebleLevel = ref(0);
const isHovering = ref(false);
const mouseX = ref(-1);
const mouseY = ref(-1);
const hoverFreqLabel = ref('0 Hz');
const hoverDbLabel = ref('-Inf dB');

// Web Audio API objects
let audioCtx = null;
let analyserNode = null;
let synthGainNode = null;
let synthTimer = null;
let micStream = null;
let micSource = null;
let streamSource = null;
let toneOscillator = null;
let toneGainNode = null;

// Animation & Data buffers
let animationFrameId = null;
let lastFrameTime = performance.now();
let frameCount = 0;
let fpsTimer = performance.now();
let peakHeights = [];

// 2D Particles and Shockwaves
let particles = [];
let shockwaves = [];

// Crosshair position calculation
const crosshairStyle = computed(() => {
  if (mouseX.value < 0 || mouseY.value < 0) return { display: 'none' };
  return {
    left: `${mouseX.value + 12}px`,
    top: `${mouseY.value - 24}px`
  };
});

// ==========================================
// Web Audio API Initialization & Lifecycle
// ==========================================
function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function initAnalyser() {
  const ctx = getAudioContext();
  if (!analyserNode) {
    analyserNode = ctx.createAnalyser();
    analyserNode.fftSize = fftSize.value;
    analyserNode.smoothingTimeConstant = smoothing.value;
    analyserNode.minDecibels = -90;
    analyserNode.maxDecibels = -10;
  }
}

function updateSmoothing() {
  if (analyserNode) {
    analyserNode.smoothingTimeConstant = smoothing.value;
  }
}

function setFftSize(size) {
  fftSize.value = size;
  if (analyserNode) {
    analyserNode.fftSize = size;
    peakHeights = new Array(analyserNode.frequencyBinCount).fill(0);
  }
}

function setMode(mode) {
  currentMode.value = mode;
  if (mode === 'particles' && particles.length === 0) {
    reinitParticles();
  }
}

// ==========================================
// Audio Sources Implementation
// ==========================================
function stopCurrentSources() {
  // Stop Synth Beat
  if (synthTimer) {
    clearInterval(synthTimer);
    synthTimer = null;
  }
  if (synthGainNode) {
    try {
      synthGainNode.disconnect();
    } catch (_) {}
    synthGainNode = null;
  }

  // Stop Mic
  if (micStream) {
    micStream.getTracks().forEach(track => track.stop());
    micStream = null;
  }
  if (micSource) {
    try {
      micSource.disconnect();
    } catch (_) {}
    micSource = null;
  }

  // Stop Tone Generator
  if (toneOscillator) {
    try {
      toneOscillator.stop();
      toneOscillator.disconnect();
    } catch (_) {}
    toneOscillator = null;
  }
  if (toneGainNode) {
    try {
      toneGainNode.disconnect();
    } catch (_) {}
    toneGainNode = null;
  }

  isAudioActive.value = false;
}

async function setAudioSource(source) {
  audioSource.value = source;
  stopCurrentSources();
  await startSelectedSource();
}

async function startSelectedSource() {
  const ctx = getAudioContext();
  initAnalyser();

  if (audioSource.value === 'synth') {
    startSynthBeat();
  } else if (audioSource.value === 'mic') {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micSource = ctx.createMediaStreamSource(micStream);
      micSource.connect(analyserNode);
      isAudioActive.value = true;
    } catch (err) {
      console.warn('Microphone permission error or unavailable:', err);
      // Fallback to synth
      audioSource.value = 'synth';
      startSynthBeat();
    }
  } else if (audioSource.value === 'stream') {
    if (props.videoElement && !props.videoElement.paused) {
      try {
        if (!streamSource) {
          streamSource = ctx.createMediaElementSource(props.videoElement);
        }
        streamSource.connect(analyserNode);
        analyserNode.connect(ctx.destination);
        isAudioActive.value = true;
      } catch (err) {
        console.warn('Could not hook stream audio element:', err);
        audioSource.value = 'synth';
        startSynthBeat();
      }
    } else {
      // If stream not playing, fallback to synth
      audioSource.value = 'synth';
      startSynthBeat();
    }
  } else if (audioSource.value === 'tone') {
    startToneGenerator();
  }
}

// Built-in Synthesizer Beat Generator (Sub-bass, Hi-hat, Chord, Arp)
function startSynthBeat() {
  const ctx = getAudioContext();
  synthGainNode = ctx.createGain();
  synthGainNode.gain.setValueAtTime(0.2, ctx.currentTime);
  synthGainNode.connect(analyserNode);
  analyserNode.connect(ctx.destination);

  let step = 0;
  const bassNotes = [55, 55, 65.4, 73.4, 55, 82.4, 73.4, 49]; // A1, C2, D2...
  const chordFrequencies = [
    [220, 261.6, 329.6], // A minor
    [174.6, 220, 261.6], // F major
    [261.6, 329.6, 392], // C major
    [196, 246.9, 293.7]  // G major
  ];

  function playBeatStep() {
    if (!synthGainNode || !audioCtx) return;
    const now = audioCtx.currentTime;

    // 1. Kick / Sub-bass pulse on beats 0, 4, 8, 12
    if (step % 4 === 0) {
      const kickOsc = audioCtx.createOscillator();
      const kickGain = audioCtx.createGain();
      kickOsc.type = 'sine';
      kickOsc.frequency.setValueAtTime(140, now);
      kickOsc.frequency.exponentialRampToValueAtTime(38, now + 0.12);
      kickGain.gain.setValueAtTime(0.6, now);
      kickGain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

      kickOsc.connect(kickGain);
      kickGain.connect(synthGainNode);
      kickOsc.start(now);
      kickOsc.stop(now + 0.25);
    }

    // 2. Snare / Noise burst on beats 4, 12
    if (step % 8 === 4) {
      const snareOsc = audioCtx.createOscillator();
      const snareGain = audioCtx.createGain();
      snareOsc.type = 'triangle';
      snareOsc.frequency.setValueAtTime(180, now);
      snareGain.gain.setValueAtTime(0.35, now);
      snareGain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      snareOsc.connect(snareGain);
      snareGain.connect(synthGainNode);
      snareOsc.start(now);
      snareOsc.stop(now + 0.18);
    }

    // 3. Hi-Hat on every off-beat
    if (step % 2 === 1) {
      const hatOsc = audioCtx.createOscillator();
      const hatGain = audioCtx.createGain();
      hatOsc.type = 'sawtooth';
      hatOsc.frequency.setValueAtTime(6000 + (step % 4) * 500, now);
      hatGain.gain.setValueAtTime(0.08, now);
      hatGain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);

      hatOsc.connect(hatGain);
      hatGain.connect(synthGainNode);
      hatOsc.start(now);
      hatOsc.stop(now + 0.06);
    }

    // 4. Bassline tone
    const bassFreq = bassNotes[step % bassNotes.length];
    const bassOsc = audioCtx.createOscillator();
    const bassGain = audioCtx.createGain();
    bassOsc.type = 'sawtooth';
    bassOsc.frequency.setValueAtTime(bassFreq, now);

    // Filter
    const bFilter = audioCtx.createBiquadFilter();
    bFilter.type = 'lowpass';
    bFilter.frequency.setValueAtTime(450, now);
    bFilter.frequency.exponentialRampToValueAtTime(120, now + 0.16);

    bassGain.gain.setValueAtTime(0.2, now);
    bassGain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);

    bassOsc.connect(bFilter);
    bFilter.connect(bassGain);
    bassGain.connect(synthGainNode);
    bassOsc.start(now);
    bassOsc.stop(now + 0.2);

    // 5. Ambient Chord pad (every 16 steps)
    if (step % 16 === 0) {
      const chordIndex = Math.floor(step / 16) % chordFrequencies.length;
      const chord = chordFrequencies[chordIndex];
      chord.forEach(f => {
        const padOsc = audioCtx.createOscillator();
        const padGain = audioCtx.createGain();
        padOsc.type = 'sine';
        padOsc.frequency.setValueAtTime(f, now);
        padGain.gain.setValueAtTime(0.06, now);
        padGain.gain.linearRampToValueAtTime(0.12, now + 0.8);
        padGain.gain.exponentialRampToValueAtTime(0.001, now + 2.0);

        padOsc.connect(padGain);
        padGain.connect(synthGainNode);
        padOsc.start(now);
        padOsc.stop(now + 2.1);
      });
    }

    step = (step + 1) % 32;
  }

  synthTimer = setInterval(playBeatStep, 130); // ~115 BPM 16th notes
  isAudioActive.value = true;
}

function startToneGenerator() {
  const ctx = getAudioContext();
  toneOscillator = ctx.createOscillator();
  toneGainNode = ctx.createGain();

  toneOscillator.type = 'sine';
  toneOscillator.frequency.setValueAtTime(toneFrequency.value, ctx.currentTime);
  toneGainNode.gain.setValueAtTime(0.15, ctx.currentTime);

  toneOscillator.connect(toneGainNode);
  toneGainNode.connect(analyserNode);
  analyserNode.connect(ctx.destination);
  toneOscillator.start();
  isAudioActive.value = true;
}

function updateToneFrequency() {
  if (toneOscillator && audioCtx) {
    toneOscillator.frequency.setValueAtTime(toneFrequency.value, audioCtx.currentTime);
  }
}

function toggleAudioEngine() {
  if (isAudioActive.value) {
    stopCurrentSources();
  } else {
    startSelectedSource();
  }
}

function togglePause() {
  isPaused.value = !isPaused.value;
}

// ==========================================
// 2D Physics Particle System Setup
// ==========================================
class Particle2D {
  constructor(w, h) {
    this.reset(w, h);
  }

  reset(w, h) {
    this.x = Math.random() * w;
    this.y = Math.random() * h;
    const speed = 0.5 + Math.random() * 1.5;
    const angle = Math.random() * Math.PI * 2;
    this.vx = Math.cos(angle) * speed;
    this.vy = Math.sin(angle) * speed;
    this.baseRadius = 1.5 + Math.random() * 2.5;
    this.radius = this.baseRadius;
    this.mass = this.baseRadius;
    this.band = Math.floor(Math.random() * 3); // 0: bass, 1: mid, 2: treble
  }

  update(w, h, energyBands, targetX, targetY) {
    // React to specific frequency band
    const bandEnergy = energyBands[this.band] / 255;
    this.radius = this.baseRadius * (1 + bandEnergy * 2.2);

    // Apply audio velocity boost
    const audioPush = bandEnergy * 1.5;

    // Mouse gravity attraction
    if (targetX >= 0 && targetY >= 0) {
      const dx = targetX - this.x;
      const dy = targetY - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > 10 && dist < 300) {
        const force = (1.5 * this.mass) / Math.max(dist, 40);
        this.vx += (dx / dist) * force;
        this.vy += (dy / dist) * force;
      }
    }

    // Velocity update with damping
    this.x += this.vx * (1 + audioPush);
    this.y += this.vy * (1 + audioPush);
    this.vx *= 0.985;
    this.vy *= 0.985;

    // Bounce off walls
    if (this.x < 0) {
      this.x = 0;
      this.vx *= -1;
    } else if (this.x > w) {
      this.x = w;
      this.vx *= -1;
    }
    if (this.y < 0) {
      this.y = 0;
      this.vy *= -1;
    } else if (this.y > h) {
      this.y = h;
      this.vy *= -1;
    }
  }

  draw(ctx, isInv) {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fillStyle = isInv ? '#000000' : '#ffffff';
    ctx.fill();
  }
}

function reinitParticles() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const w = canvas.width;
  const h = canvas.height;
  particles = [];
  for (let i = 0; i < particleCount.value; i++) {
    particles.push(new Particle2D(w, h));
  }
}

// 2D Shockwave expansion on click
class Shockwave2D {
  constructor(x, y) {
    this.x = x;
    this.y = y;
    this.radius = 2;
    this.maxRadius = 260;
    this.speed = 7;
    this.alpha = 1.0;
  }

  update() {
    this.radius += this.speed;
    this.alpha = Math.max(0, 1 - this.radius / this.maxRadius);
  }

  draw(ctx, isInv) {
    if (this.alpha <= 0) return;
    ctx.save();
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.strokeStyle = isInv
      ? `rgba(0, 0, 0, ${this.alpha * 0.7})`
      : `rgba(255, 255, 255, ${this.alpha * 0.7})`;
    ctx.lineWidth = Math.max(1, 4 * this.alpha);
    ctx.stroke();

    // Inner thin ring
    ctx.beginPath();
    ctx.arc(this.x, this.y, Math.max(0, this.radius - 12), 0, Math.PI * 2);
    ctx.strokeStyle = isInv
      ? `rgba(0, 0, 0, ${this.alpha * 0.3})`
      : `rgba(255, 255, 255, ${this.alpha * 0.3})`;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  }
}

// ==========================================
// User Interactions & Canvas Coordinates
// ==========================================
function handleCanvasMouseMove(e) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;

  mouseX.value = (e.clientX - rect.left) * scaleX;
  mouseY.value = (e.clientY - rect.top) * scaleY;

  // Calculate Hz and dB under cursor for HUD
  if (analyserNode) {
    const nyquist = (audioCtx ? audioCtx.sampleRate : 48000) / 2;
    const freqRatio = Math.max(0, Math.min(1, mouseX.value / canvas.width));
    const freqHz = Math.round(freqRatio * nyquist);
    hoverFreqLabel.value = `${freqHz.toLocaleString()} Hz`;

    const dbRatio = 1 - Math.max(0, Math.min(1, mouseY.value / canvas.height));
    const dbVal = Math.round(-90 + dbRatio * 80);
    hoverDbLabel.value = `${dbVal} dB`;
  }
}

function handleCanvasMouseLeave() {
  isHovering.value = false;
  mouseX.value = -1;
  mouseY.value = -1;
}

function handleCanvasMouseDown(e) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const x = (e.clientX - rect.left) * scaleX;
  const y = (e.clientY - rect.top) * scaleY;

  // Spawn shockwave ring
  shockwaves.push(new Shockwave2D(x, y));

  // If in particle mode, blast particles outward
  if (currentMode.value === 'particles') {
    particles.forEach(p => {
      const dx = p.x - x;
      const dy = p.y - y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 180) {
        const force = (180 - dist) * 0.15;
        p.vx += (dx / Math.max(dist, 1)) * force;
        p.vy += (dy / Math.max(dist, 1)) * force;
      }
    });
  }

  // Audio kick impulse on click if synth active
  if (audioCtx && isAudioActive.value && synthGainNode) {
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.exponentialRampToValueAtTime(60, now + 0.15);
    g.gain.setValueAtTime(0.3, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
    osc.connect(g);
    g.connect(synthGainNode);
    osc.start(now);
    osc.stop(now + 0.18);
  }
}

function takeSnapshot() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `streamhub-canvas-2d-${currentMode.value}-${Date.now()}.png`;
  a.click();
}

// ==========================================
// 2D Canvas Render Loop (requestAnimationFrame)
// ==========================================
function renderLoop(timestamp) {
  animationFrameId = requestAnimationFrame(renderLoop);

  // Compute FPS
  frameCount++;
  if (timestamp - fpsTimer >= 1000) {
    currentFps.value = Math.round((frameCount * 1000) / (timestamp - fpsTimer));
    frameCount = 0;
    fpsTimer = timestamp;
  }

  if (isPaused.value) return;

  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  const isInv = invertColors.value;

  // Retrieve audio data
  const binCount = analyserNode ? analyserNode.frequencyBinCount : 128;
  const freqData = new Uint8Array(binCount);
  const timeData = new Uint8Array(analyserNode ? analyserNode.fftSize : 256);

  if (analyserNode && isAudioActive.value) {
    analyserNode.getByteFrequencyData(freqData);
    analyserNode.getByteTimeDomainData(timeData);
  } else {
    // Idle subtle sinusoidal pulse if engine stopped
    const t = timestamp * 0.003;
    for (let i = 0; i < binCount; i++) {
      freqData[i] = Math.max(0, Math.sin(t + i * 0.08) * 40 + 20);
    }
    for (let i = 0; i < timeData.length; i++) {
      timeData[i] = 128 + Math.sin(t * 2 + i * 0.1) * 15;
    }
  }

  // Calculate Bass and Treble metrics
  let bassSum = 0;
  const bassCount = Math.min(10, binCount);
  for (let i = 0; i < bassCount; i++) bassSum += freqData[i];
  const bVal = Math.round((bassSum / bassCount / 255) * 100);
  bassLevel.value = bVal;

  let trebleSum = 0;
  const trebleStart = Math.floor(binCount * 0.6);
  const trebleCount = binCount - trebleStart;
  for (let i = trebleStart; i < binCount; i++) trebleSum += freqData[i];
  const tVal = Math.round((trebleSum / Math.max(1, trebleCount) / 255) * 100);
  trebleLevel.value = tVal;

  // Clear canvas with optional phosphor motion trails
  if (showTrails.value) {
    ctx.fillStyle = isInv ? 'rgba(255, 255, 255, 0.22)' : 'rgba(10, 10, 10, 0.22)';
    ctx.fillRect(0, 0, w, h);
  } else {
    ctx.fillStyle = isInv ? '#ffffff' : '#0a0a0a';
    ctx.fillRect(0, 0, w, h);
  }

  // Draw Background Grid HUD if enabled
  if (showGrid.value) {
    drawGridHud(ctx, w, h, isInv);
  }

  // Render chosen mode
  if (currentMode.value === 'spectrum') {
    drawSpectrumBars(ctx, w, h, freqData, binCount, isInv);
  } else if (currentMode.value === 'oscilloscope') {
    drawOscilloscope(ctx, w, h, timeData, isInv);
  } else if (currentMode.value === 'radial') {
    drawRadialVortex(ctx, w, h, freqData, binCount, isInv, timestamp);
  } else if (currentMode.value === 'particles') {
    drawParticleField(ctx, w, h, bVal, tVal, isInv);
  }

  // Update and draw Shockwaves
  for (let i = shockwaves.length - 1; i >= 0; i--) {
    const sw = shockwaves[i];
    sw.update();
    sw.draw(ctx, isInv);
    if (sw.alpha <= 0) shockwaves.splice(i, 1);
  }

  // Draw interactive crosshair lines if hovering
  if (isHovering.value && mouseX.value >= 0 && mouseY.value >= 0) {
    drawCrosshairs(ctx, w, h, isInv);
  }
}

// ------------------------------------------
// Sub-renderer: Grid HUD
// ------------------------------------------
function drawGridHud(ctx, w, h, isInv) {
  ctx.save();
  ctx.strokeStyle = isInv ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.07)';
  ctx.fillStyle = isInv ? 'rgba(0, 0, 0, 0.4)' : 'rgba(255, 255, 255, 0.35)';
  ctx.lineWidth = 1;
  ctx.font = '9px monospace';

  // Horizontal decibel lines (-20dB, -40dB, -60dB, -80dB)
  const dbs = ['0 dB', '-20 dB', '-40 dB', '-60 dB', '-80 dB'];
  dbs.forEach((label, idx) => {
    const y = (h / (dbs.length - 1)) * idx;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
    ctx.fillText(label, 8, Math.max(12, y - 4));
  });

  // Vertical frequency marks
  const freqs = ['100 Hz', '500 Hz', '1 kHz', '2.5 kHz', '5 kHz', '10 kHz', '20 kHz'];
  freqs.forEach((fLabel, idx) => {
    const x = (w / (freqs.length + 1)) * (idx + 1);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
    ctx.fillText(fLabel, x + 4, h - 8);
  });

  ctx.restore();
}

// ------------------------------------------
// Sub-renderer: Mode 1 - Spectrum Bars
// ------------------------------------------
function drawSpectrumBars(ctx, w, h, freqData, binCount, isInv) {
  const bars = Math.min(binCount, 128);
  const barSpacing = 2;
  const barWidth = Math.max(1, (w - barSpacing * (bars - 1)) / bars);
  const sens = sensitivity.value;

  if (peakHeights.length !== bars) {
    peakHeights = new Array(bars).fill(0);
  }

  for (let i = 0; i < bars; i++) {
    const rawVal = freqData[i] || 0;
    const barHeight = Math.min(h, ((rawVal / 255) * h * sens));
    const x = i * (barWidth + barSpacing);
    const y = h - barHeight;

    // Peak cap physics
    if (barHeight >= peakHeights[i]) {
      peakHeights[i] = barHeight;
    } else {
      peakHeights[i] = Math.max(0, peakHeights[i] - 2.5); // gravity fall
    }

    // Bar fill
    ctx.fillStyle = isInv ? '#111111' : '#ffffff';
    ctx.fillRect(x, y, barWidth, barHeight);

    // Subtle segmented line notches
    ctx.fillStyle = isInv ? 'rgba(255, 255, 255, 0.4)' : 'rgba(0, 0, 0, 0.4)';
    for (let ny = y + 8; ny < h; ny += 8) {
      ctx.fillRect(x, ny, barWidth, 1);
    }

    // Peak Caps
    if (showPeakCaps.value && peakHeights[i] > 2) {
      const peakY = h - peakHeights[i];
      ctx.fillStyle = isInv ? '#000000' : '#ffffff';
      ctx.fillRect(x, peakY - 3, barWidth, 2);
    }
  }
}

// ------------------------------------------
// Sub-renderer: Mode 2 - Oscilloscope
// ------------------------------------------
function drawOscilloscope(ctx, w, h, timeData, isInv) {
  ctx.save();
  ctx.strokeStyle = isInv ? '#000000' : '#ffffff';
  ctx.lineWidth = 2.2;
  ctx.beginPath();

  const sliceWidth = w / timeData.length;
  let x = 0;
  const centerY = h / 2;
  const sens = sensitivity.value;

  for (let i = 0; i < timeData.length; i++) {
    const v = (timeData[i] - 128) / 128; // -1 to +1
    const y = centerY + v * (h * 0.44) * sens;

    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
    x += sliceWidth;
  }

  ctx.stroke();

  // Draw center zero-crossing dashed baseline
  ctx.strokeStyle = isInv ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.2)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(0, centerY);
  ctx.lineTo(w, centerY);
  ctx.stroke();

  ctx.restore();
}

// ------------------------------------------
// Sub-renderer: Mode 3 - Radial Vortex
// ------------------------------------------
function drawRadialVortex(ctx, w, h, freqData, binCount, isInv, timestamp) {
  const centerX = w / 2;
  const centerY = h / 2;
  const baseRadius = Math.min(w, h) * 0.18;
  const maxRays = Math.min(binCount, 96);
  const angleStep = (Math.PI * 2) / maxRays;
  const rot = timestamp * 0.0006;
  const sens = sensitivity.value;

  ctx.save();
  ctx.translate(centerX, centerY);
  ctx.rotate(rot);

  // Outer radial rays
  ctx.strokeStyle = isInv ? '#000000' : '#ffffff';
  ctx.lineWidth = 2.0;

  for (let i = 0; i < maxRays; i++) {
    const angle = i * angleStep;
    const val = (freqData[i] / 255) * (baseRadius * 1.4) * sens;
    const r1 = baseRadius + (bassLevel.value * 0.2);
    const r2 = r1 + val;

    const x1 = Math.cos(angle) * r1;
    const y1 = Math.sin(angle) * r1;
    const x2 = Math.cos(angle) * r2;
    const y2 = Math.sin(angle) * r2;

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  // Inner pulsing core circle
  const coreRadius = Math.max(10, baseRadius * 0.6 + (bassLevel.value * 0.35));
  ctx.beginPath();
  ctx.arc(0, 0, coreRadius, 0, Math.PI * 2);
  ctx.strokeStyle = isInv ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Inner rotating hexagon
  ctx.beginPath();
  const hexSides = 6;
  for (let s = 0; s <= hexSides; s++) {
    const hAngle = (s * Math.PI * 2) / hexSides - rot * 2;
    const hx = Math.cos(hAngle) * (coreRadius * 0.65);
    const hy = Math.sin(hAngle) * (coreRadius * 0.65);
    if (s === 0) ctx.moveTo(hx, hy);
    else ctx.lineTo(hx, hy);
  }
  ctx.stroke();

  ctx.restore();
}

// ------------------------------------------
// Sub-renderer: Mode 4 - Particle Field 2D
// ------------------------------------------
function drawParticleField(ctx, w, h, bVal, tVal, isInv) {
  const energyBands = [bVal, (bVal + tVal) / 2, tVal];

  // Update & Draw particles
  particles.forEach(p => {
    p.update(w, h, energyBands, mouseX.value, mouseY.value);
    p.draw(ctx, isInv);
  });

  // Draw constellation interconnect lines between nearby particles
  ctx.strokeStyle = isInv ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.08)';
  ctx.lineWidth = 1;
  const maxDist = 65;

  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d < maxDist) {
        ctx.beginPath();
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.stroke();
      }
    }
  }
}

// ------------------------------------------
// Sub-renderer: Crosshair overlay
// ------------------------------------------
function drawCrosshairs(ctx, w, h, isInv) {
  ctx.save();
  ctx.strokeStyle = isInv ? 'rgba(0, 0, 0, 0.35)' : 'rgba(255, 255, 255, 0.35)';
  ctx.setLineDash([2, 4]);
  ctx.lineWidth = 1;

  // Vertical line
  ctx.beginPath();
  ctx.moveTo(mouseX.value, 0);
  ctx.lineTo(mouseX.value, h);
  ctx.stroke();

  // Horizontal line
  ctx.beginPath();
  ctx.moveTo(0, mouseY.value);
  ctx.lineTo(w, mouseY.value);
  ctx.stroke();

  // Target ring at cursor
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.arc(mouseX.value, mouseY.value, 6, 0, Math.PI * 2);
  ctx.stroke();

  ctx.restore();
}

// ==========================================
// Resize & Canvas Calibration
// ==========================================
function resizeCanvas() {
  const container = stageContainer.value;
  const canvas = canvasRef.value;
  if (!container || !canvas) return;

  const rect = container.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);

  if (particles.length === 0) {
    reinitParticles();
  }
}

let resizeObserver = null;

onMounted(() => {
  resizeCanvas();
  reinitParticles();

  if (window.ResizeObserver && stageContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeCanvas();
    });
    resizeObserver.observe(stageContainer.value);
  }

  // Start synth beat by default
  startSelectedSource();

  // Start Animation loop
  animationFrameId = requestAnimationFrame(renderLoop);
});

onBeforeUnmount(() => {
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  stopCurrentSources();
  if (audioCtx && audioCtx.state !== 'closed') {
    audioCtx.close();
  }
});
</script>

<style scoped>
.canvas-modal-backdrop {
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

.canvas-modal-window {
  background: #0a0a0a;
  border: 1px solid #333333;
  width: 100%;
  max-width: 1220px;
  height: 86vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.9);
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  overflow: hidden;
}

/* Header */
.canvas-modal-header {
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
  letter-spacing: 0.05em;
}

.header-title-wrap h2 {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

.status-indicator {
  font-size: 0.7rem;
  font-family: monospace;
  padding: 2px 8px;
  background: #181818;
  border: 1px solid #333333;
  color: #888888;
}

.status-indicator.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

/* Modal Body Layout */
.canvas-modal-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* Stage Area */
.stage-container {
  flex: 1;
  position: relative;
  background: #000000;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.visualizer-canvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: crosshair;
}

/* Canvas HUD Tooltip */
.canvas-hud-overlay {
  position: absolute;
  pointer-events: none;
  background: rgba(10, 10, 10, 0.9);
  border: 1px solid #444444;
  padding: 3px 8px;
  font-family: monospace;
  font-size: 0.75rem;
  color: #ffffff;
  display: flex;
  gap: 0.6rem;
  z-index: 10;
  white-space: nowrap;
}

.hud-freq {
  color: #ffffff;
  font-weight: 700;
}

.hud-db {
  color: #aaaaaa;
}

/* Stage Status Bar */
.stage-status-bar {
  height: 34px;
  background: #0e0e0e;
  border-top: 1px solid #222222;
  display: flex;
  align-items: center;
  padding: 0 1rem;
  gap: 1.25rem;
  font-family: monospace;
  font-size: 0.72rem;
  flex-shrink: 0;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-cell .label {
  color: #666666;
}

.status-cell .val {
  color: #ffffff;
  font-weight: 700;
}

.status-cell.hint {
  margin-left: auto;
  color: #666666;
}

.mini-meter-bar {
  width: 50px;
  height: 8px;
  background: #222222;
  border: 1px solid #333333;
  overflow: hidden;
}

.mini-meter-fill {
  height: 100%;
  background: #ffffff;
  transition: width 0.05s linear;
}

/* Control Sidebar */
.control-panel {
  width: 320px;
  background: #0c0c0c;
  border-left: 1px solid #222222;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 1.25rem;
  gap: 1.25rem;
  flex-shrink: 0;
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.section-title {
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #888888;
  border-bottom: 1px solid #1c1c1c;
  padding-bottom: 0.35rem;
}

/* Mode Grid */
.mode-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}

.mode-btn {
  height: 32px;
  background: #141414;
  border: 1px solid #282828;
  color: #999999;
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: all 0.15s ease;
}

.mode-btn:hover {
  border-color: #555555;
  color: #ffffff;
}

.mode-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

/* Audio Source Buttons */
.source-select-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.source-btn {
  height: 32px;
  padding: 0 0.75rem;
  background: #141414;
  border: 1px solid #282828;
  color: #999999;
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.15s ease;
}

.source-btn:hover {
  border-color: #555555;
  color: #ffffff;
}

.source-btn.active {
  background: #202020;
  color: #ffffff;
  border-color: #ffffff;
  font-weight: 700;
}

/* Sliders */
.slider-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.slider-row.sub-row {
  margin-top: 0.4rem;
  padding: 0.5rem;
  background: #121212;
  border: 1px solid #242424;
}

.slider-label {
  display: flex;
  justify-content: space-between;
  font-family: monospace;
  font-size: 0.7rem;
  color: #777777;
}

.slider-label span:last-child {
  color: #ffffff;
  font-weight: 700;
}

input[type='range'] {
  width: 100%;
  accent-color: #ffffff;
  cursor: pointer;
  height: 4px;
  background: #252525;
}

/* Chips */
.fft-chips {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.3rem;
}

.chip-btn {
  height: 26px;
  background: #141414;
  border: 1px solid #282828;
  color: #888888;
  font-family: monospace;
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
}

.chip-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

/* Checkboxes */
.toggle-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-family: monospace;
  font-size: 0.72rem;
  color: #aaaaaa;
  cursor: pointer;
  user-select: none;
}

.check-item input[type='checkbox'] {
  accent-color: #ffffff;
  width: 14px;
  height: 14px;
  cursor: pointer;
}

/* Footer Action */
.control-footer {
  margin-top: auto;
  padding-top: 0.75rem;
}

.engine-btn {
  width: 100%;
  height: 38px;
  background: #161616;
  border: 1px solid #444444;
  color: #ffffff;
  font-family: monospace;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all 0.2s ease;
}

.engine-btn:hover {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.engine-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}
</style>
