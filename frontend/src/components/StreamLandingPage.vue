<template>
  <div class="landing-page">
    <div class="container py-4 py-lg-5 landing-content">
      <nav class="d-flex justify-content-between align-items-center mb-4" aria-label="Landing page navigation">
        <a class="landing-brand text-decoration-none" href="#" @click.prevent="$emit('back')">
          STREAMHUB <span>／ CHANNEL STORIES</span>
        </a>
        <button class="btn btn-outline-light btn-sm" @click="$emit('back')">
          Back to player
        </button>
      </nav>

      <section v-if="selectedStream" class="landing-hero row g-0 align-items-stretch mb-5">
        <div class="col-lg-7 landing-cover-wrap">
          <img
            class="landing-cover"
            :src="selectedStream.thumbnail_url || fallbackImage"
            :alt="`${selectedStream.title} stream cover`"
            @error="useFallbackImage"
          />
          <span class="landing-live-badge" :class="{ offline: !selectedStream.is_live }">
            {{ selectedStream.is_live ? 'LIVE NOW' : 'OFFLINE' }}
          </span>
        </div>

        <div class="col-lg-5 d-flex flex-column justify-content-center p-4 p-xl-5 landing-intro">
          <span class="landing-eyebrow">A CHANNEL MADE FOR YOUR NEXT BREAK</span>
          <h1 class="display-4 fw-bold mt-3">{{ selectedStream.title }}</h1>
          <p class="lead mt-3 mb-4">
            {{ selectedStream.description || defaultDescription }}
          </p>
          <div class="d-flex flex-wrap gap-3 align-items-center">
            <button class="btn btn-primary btn-lg" @click="$emit('watch', selectedStream)">
              {{ selectedStream.is_live ? 'Watch live' : 'Open channel' }}
            </button>
            <span class="landing-viewers">
              {{ selectedStream.viewers_count || 0 }} watching
            </span>
          </div>
          <div class="landing-tags mt-4">
            <span>LIVE BROADCAST</span>
            <span>COMMUNITY CHAT</span>
            <span>ON-DEMAND</span>
          </div>
        </div>
      </section>

      <section v-else class="landing-empty text-center py-5 mb-5">
        <span class="landing-eyebrow">STREAMHUB DIRECTORY</span>
        <h1 class="display-5 fw-bold mt-3">Find your next favorite channel.</h1>
        <p class="lead text-secondary">Choose a channel below to see its landing page.</p>
      </section>

      <section v-if="selectedStream" class="row g-4 mb-5" aria-labelledby="about-heading">
        <div class="col-lg-7">
          <span class="landing-eyebrow">THE CHANNEL</span>
          <h2 id="about-heading" class="h2 fw-bold mt-2">A little about this stream</h2>
          <p class="landing-description mt-3">
            {{ selectedStream.description || defaultDescription }}
          </p>
          <p class="landing-description">
            Drop into the live broadcast, meet the community in chat, and catch up on saved
            recordings whenever they are available.
          </p>
        </div>
        <div class="col-lg-5">
          <div class="landing-facts h-100 p-4">
            <span class="landing-eyebrow">CHANNEL DETAILS</span>
            <dl class="row mt-3 mb-0">
              <dt class="col-5">Streamer</dt>
              <dd class="col-7">{{ selectedStream.owner || 'StreamHub creator' }}</dd>
              <dt class="col-5">Status</dt>
              <dd class="col-7">{{ selectedStream.is_live ? 'Broadcasting now' : 'Next stream soon' }}</dd>
              <dt class="col-5">Audience</dt>
              <dd class="col-7">{{ selectedStream.viewers_count || 0 }} viewers</dd>
              <dt class="col-5">Format</dt>
              <dd class="col-7">Low-latency video</dd>
            </dl>
          </div>
        </div>
      </section>

      <section class="mb-5" aria-labelledby="channels-heading">
        <div class="d-flex justify-content-between align-items-end gap-3 mb-3">
          <div>
            <span class="landing-eyebrow">MORE TO EXPLORE</span>
            <h2 id="channels-heading" class="h2 fw-bold mt-2 mb-0">Choose a channel</h2>
          </div>
          <span class="text-secondary small">{{ streams.length }} channels</span>
        </div>

        <div v-if="streams.length" class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-4">
          <article v-for="stream in streams" :key="stream.id" class="col">
            <div class="card h-100 channel-card">
              <img
                class="card-img-top channel-card-image"
                :src="stream.thumbnail_url || fallbackImage"
                :alt="`${stream.title} channel artwork`"
                loading="lazy"
                @error="useFallbackImage"
              />
              <div class="card-body d-flex flex-column">
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <h3 class="h5 card-title fw-bold">{{ stream.title }}</h3>
                  <span class="channel-status" :class="{ offline: !stream.is_live }">
                    {{ stream.is_live ? 'LIVE' : 'OFFLINE' }}
                  </span>
                </div>
                <p class="card-text text-secondary channel-card-description">
                  {{ stream.description || defaultDescription }}
                </p>
                <div class="mt-auto d-flex justify-content-between align-items-center">
                  <span class="small text-secondary">{{ stream.owner || 'StreamHub creator' }}</span>
                  <button
                    class="btn btn-outline-light btn-sm"
                    :aria-label="`View ${stream.title} landing page`"
                    @click="selectedStream = stream; scrollToTop()"
                  >
                    View channel
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="landing-facts p-4 text-secondary">
          No channels are available yet. Come back when a creator goes live.
        </div>
      </section>

      <section class="landing-about p-4 p-lg-5 mb-5">
        <div class="row align-items-center g-4">
          <div class="col-lg-8">
            <span class="landing-eyebrow">MADE FOR THE MOMENT</span>
            <h2 class="h2 fw-bold mt-2">Good streams are better together.</h2>
            <p class="mb-0 text-secondary">
              Watch the broadcast, join the conversation, and discover creators from one place.
            </p>
          </div>
          <div class="col-lg-4 text-lg-end">
            <button class="btn btn-primary" @click="$emit('back')">Explore StreamHub</button>
          </div>
        </div>
      </section>
    </div>

    <aside class="contact-bar fixed-bottom" aria-label="Channel contact information">
      <div class="container d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2 py-3">
        <div>
          <span class="contact-label">CONTACT</span>
          <span class="contact-copy">
            {{ selectedStream ? `Creator: ${selectedStream.owner || selectedStream.title}` : 'Choose a channel to contact its creator' }}
            · Reach them in the live channel chat
          </span>
        </div>
        <button
          v-if="selectedStream"
          class="btn btn-sm btn-light"
          @click="$emit('watch', selectedStream)"
        >
          Open channel chat
        </button>
        <button v-else class="btn btn-sm btn-light" @click="$emit('back')">
          Open StreamHub
        </button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import fallbackImage from '../assets/hero.png';

const props = defineProps({
  streams: { type: Array, default: () => [] },
  selectedStreamId: { type: Number, default: null }
});

defineEmits(['back', 'watch']);

const defaultDescription =
  'Join the channel for live video, friendly conversation, and a community built around the stream.';
const selectedStream = ref(
  props.streams.find((stream) => stream.id === props.selectedStreamId) || props.streams[0] || null
);

watch(
  () => [props.streams, props.selectedStreamId],
  () => {
    selectedStream.value =
      props.streams.find((stream) => stream.id === props.selectedStreamId) ||
      props.streams.find((stream) => stream.id === selectedStream.value?.id) ||
      props.streams[0] ||
      null;
  },
  { deep: true }
);

const useFallbackImage = (event) => {
  if (event.currentTarget.src !== fallbackImage) {
    event.currentTarget.src = fallbackImage;
  }
};

const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });
</script>

<style scoped>
.landing-page {
  --landing-bg: #101014;
  --landing-panel: #19191f;
  --landing-muted: #a5a5b0;
  min-height: 100%;
  overflow-y: auto;
  background:
    radial-gradient(ellipse at 15% 0%, rgba(104, 58, 183, 0.2), transparent 38rem),
    var(--landing-bg);
  color: #f8f7fb;
  padding-bottom: 96px;
}

.landing-content {
  max-width: 1160px;
}

.landing-brand {
  color: #fff;
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.landing-brand span,
.landing-eyebrow,
.contact-label {
  color: #b9a4ff;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.landing-hero,
.landing-facts,
.landing-about {
  overflow: hidden;
  background: var(--landing-panel);
  border: 1px solid #303039;
}

.landing-cover-wrap {
  position: relative;
  min-height: 320px;
  background: #16151b;
}

.landing-cover {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 320px;
  max-height: 490px;
  object-fit: cover;
}

.landing-live-badge,
.channel-status {
  display: inline-flex;
  align-items: center;
  background: #e73555;
  color: #fff;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 0.42rem 0.65rem;
}

.landing-live-badge {
  position: absolute;
  top: 1rem;
  left: 1rem;
}

.landing-live-badge.offline,
.channel-status.offline {
  background: #393942;
  color: #d0ced8;
}

.landing-intro {
  background: linear-gradient(145deg, #201b2e, #18181f 70%);
}

.landing-intro .lead,
.landing-description {
  color: var(--landing-muted);
  line-height: 1.8;
}

.landing-viewers {
  color: #d2cedb;
  font-size: 0.85rem;
}

.landing-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.landing-tags span {
  border: 1px solid #45414e;
  color: #d5cfdf;
  font-size: 0.63rem;
  letter-spacing: 0.07em;
  padding: 0.4rem 0.55rem;
}

.landing-facts dt {
  color: #aaa6b3;
  font-size: 0.84rem;
  font-weight: 500;
  margin-bottom: 0.8rem;
}

.landing-facts dd {
  color: #f5f2fa;
  font-size: 0.84rem;
  margin-bottom: 0.8rem;
}

.channel-card {
  background: var(--landing-panel);
  border: 1px solid #303039;
  color: #f8f7fb;
}

.channel-card-image {
  height: 190px;
  object-fit: cover;
  background: #15131a;
}

.channel-card-description {
  min-height: 3.5rem;
  font-size: 0.88rem;
  line-height: 1.6;
}

.channel-status {
  font-size: 0.58rem;
  padding: 0.32rem 0.45rem;
}

.landing-about {
  background: linear-gradient(115deg, #211b2e, #19191f);
}

.landing-empty {
  border: 1px solid #303039;
  background: var(--landing-panel);
}

.contact-bar {
  z-index: 20;
  border-top: 1px solid #393442;
  background: rgba(18, 17, 23, 0.97);
  box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(12px);
}

.contact-label {
  margin-right: 0.7rem;
}

.contact-copy {
  color: #e7e3ed;
  font-size: 0.8rem;
}

@media (max-width: 575.98px) {
  .landing-cover-wrap,
  .landing-cover {
    min-height: 240px;
  }

  .contact-copy {
    font-size: 0.7rem;
  }
}
</style>
