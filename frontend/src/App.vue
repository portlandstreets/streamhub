<template>
  <div class="app-layout">
    <!-- Верхняя навигационная панель -->
    <header class="top-nav">
      <div class="brand">
        <span class="logo-text">StreamHub</span>
        <span class="sub-text">broadcast</span>
      </div>

      <div class="search-box">
        <Select2Combobox
          :endpoint="`${CORE_API}/api/streams/autocomplete`"
          placeholder="Select2 Search (min 3 chars, 300ms delay)..."
          :min-chars="3"
          :debounce-ms="300"
          @select="handleChannelSelectFromCombobox"
        />
      </div>

      <div class="auth-actions">
        <!-- Compact Dropdown Menu [ = ] -->
        <div class="tools-menu-wrap">
          <button
            class="nav-btn menu-btn"
            :class="{ active: showToolsMenu }"
            @click.stop="showToolsMenu = !showToolsMenu"
            title="Platform Features & Tools Menu"
          >
            [ = ]
          </button>

          <!-- Dropdown Popover Menu -->
          <div v-if="showToolsMenu" class="tools-dropdown-menu" @click.stop>
            <div class="dropdown-header">
              <span class="dropdown-title">// PLATFORM TOOLS</span>
              <span class="dropdown-count">{{ userPlan.toUpperCase() }} TIER</span>
            </div>

            <div class="dropdown-group">
              <span class="group-title">AI &amp; PROTOCOLS</span>
              <button class="dropdown-item" @click="openTool('ai')">
                <span class="item-tag">[C21]</span>
                <span class="item-name">AI ASSISTANT (SSE STREAM)</span>
              </button>
              <button class="dropdown-item" @click="openTool('mcp')">
                <span class="item-tag">[C22]</span>
                <span class="item-name">MCP SERVER (JSON-RPC 2.0)</span>
              </button>
              <button class="dropdown-item" @click="openTool('telegram')">
                <span class="item-tag">[B2]</span>
                <span class="item-name">TELEGRAM BOT &amp; WEBHOOKS</span>
              </button>
            </div>

            <div class="dropdown-group">
              <span class="group-title">STUDIO &amp; TELEMETRY</span>
              <button class="dropdown-item" @click="openTool('analytics')">
                <span class="item-tag">[F1]</span>
                <span class="item-name">ANALYTICS &amp; CHART.JS</span>
              </button>
              <button class="dropdown-item" @click="openTool('canvas')">
                <span class="item-tag">[F6]</span>
                <span class="item-name">CANVAS 2D AUDIO MONITOR</span>
              </button>
              <button class="dropdown-item" @click="openTool('queue')">
                <span class="item-tag">[B8]</span>
                <span class="item-name">VOD &amp; MESSAGE QUEUE</span>
              </button>
            </div>

            <div class="dropdown-group">
              <span class="group-title">STORAGE &amp; MEDIA</span>
              <button class="dropdown-item" @click="openTool('blob')">
                <span class="item-tag">[C19]</span>
                <span class="item-name">BLOB STORAGE &amp; CDN</span>
              </button>
            </div>

            <div class="dropdown-group">
              <span class="group-title">SETTINGS &amp; PAGES</span>
              <button class="dropdown-item" @click="openTool('flags')">
                <span class="item-tag">[B6]</span>
                <span class="item-name">FLAGS &amp; PLANS ({{ userPlan.toUpperCase() }})</span>
              </button>
              <button class="dropdown-item" @click="openTool('channels')">
                <span class="item-tag">[C6]</span>
                <span class="item-name">{{ showLandingPage ? 'BACK TO PLAYER' : 'CHANNELS DIRECTORY' }}</span>
              </button>
            </div>
          </div>
        </div>
        <template v-if="currentUser">
          <span class="user-badge">{{ currentUser }}</span>
          <button class="nav-btn" @click="openStreamModal()">NEW STREAM</button>
          <button class="nav-btn" @click="handleLogout">LOG OUT</button>
        </template>
        <template v-else>
          <button class="nav-btn" @click="openAuthModal('login')">LOG IN</button>
          <button class="nav-btn primary" @click="openAuthModal('register')">SIGN UP</button>
        </template>
      </div>
    </header>

    <div v-if="!showLandingPage" class="main-body">
      <!-- Левый сайдбар со списком стримов -->
      <aside class="sidebar">
        <nav class="nav-links">
          <button
            v-for="page in navigationPages"
            :key="page.id"
            class="nav-item"
            :class="{ active: currentPage === page.id }"
            @click="navigate(page.id)"
          >// {{ page.label }}</button>
        </nav>

        <div class="sidebar-section-title">
          <span>RECOMMENDED</span>
          <span>{{ liveStreams.length.toString().padStart(2, '0') }}</span>
        </div>

        <div class="stream-list">
          <div
            v-for="st in liveStreams"
            :key="st.id"
            class="stream-item"
            :class="{ active: currentStream && currentStream.id === st.id }"
            @click="openChannel(st)"
          >
            <div class="avatar">{{ st.title.slice(0, 2).toUpperCase() }}</div>
            <div class="stream-meta">
              <span class="author">{{ st.title }}</span>
              <span class="category">{{ st.description || 'STREAM' }}</span>
            </div>
            <div class="live-pill is_live">■ LIVE</div>
          </div>
          <p v-if="!liveStreams.length" class="sidebar-empty">No active streams</p>
        </div>
      </aside>

      <!-- Центральная сцена с плеером -->
      <main class="player-stage">
        <template v-if="currentPage === 'home'">
        <div class="video-container" v-if="currentStream">
          <div class="status-overlay">
            <span class="badge">{{ playerStatus }}</span>
          </div>

          <video
            ref="videoElement"
            class="video-feed"
            controls
            autoplay
            muted
            playsinline
            @loadedmetadata="markVideoReady"
            @loadeddata="markVideoReady"
            @canplay="markVideoReady"
            @playing="markVideoReady"
            @timeupdate="onVideoTimeUpdate"
            @waiting="markVideoWaiting"
            @error="handleVideoError"
          ></video>

          <div v-if="!hasVideoFrame" class="offline-placeholder" :class="{ 'is-loading': currentStream.is_live }">
            <span>{{ currentStream.is_live ? '// PREPARING LIVE VIDEO //' : '// BROADCAST OFFLINE //' }}</span>
            <small>{{ playerStatus === 'VIDEO ERROR' ? 'Could not decode the stream. Check the OBS video source.' : currentStream.is_live ? 'Waiting for the first decoded video frame… (Tip: Set OBS Keyframe Interval to 1s)' : 'WAITING FOR RTMP PUBLISHER' }}</small>
            <button v-if="currentStream.is_live" class="action-btn sm mt-2" @click="forceReloadPlayer">RELOAD PLAYER</button>
          </div>
        </div>
        <div v-else class="empty-page">Choose a live stream or start one from your profile.</div>

        <!-- Информация о стриме под плеером -->
        <div class="broadcast-footer" v-if="currentStream">
          <div class="avatar large">
            {{ currentStream.title.slice(0, 2).toUpperCase() }}
          </div>
          <div class="info">
            <div class="title-row">
              <h2>{{ currentStream.title }}</h2>
              <span class="verified-tag">[VERIFIED]</span>
            </div>
            <p>{{ currentStream.description }}</p>
            <div class="tags">
              <span class="tag">FASTAPI</span>
              <span class="tag">LL-HLS</span>
              <span class="tag">MEDIAMTX</span>
            </div>
          </div>

          <div class="actions">
            <template v-if="isCurrentUserOwner">
              <button class="action-btn" @click="openStreamModal(currentStream)">EDIT</button>
              <button class="action-btn danger" @click="deleteCurrentStream">DELETE</button>
              <button class="action-btn" @click="showTelegramModal = true">TELEGRAM BOT</button>
            </template>
            <button class="action-btn" @click="showAnalyticsModal = true" title="View Stream Analytics & Chart.js Metrics (F1)">ANALYTICS</button>
            <button class="action-btn" @click="showCanvasModal = true" title="Open 2D Canvas Audio Monitor (F6)">CANVAS 2D</button>
            <button class="action-btn" :disabled="isCurrentUserOwner" @click="toggleFollow">
              {{ followingIds.includes(currentStream.id) ? 'UNFOLLOW' : 'FOLLOW' }}
            </button>
            <button class="action-btn primary" :disabled="isCurrentUserOwner" @click="toggleSubscription">
              {{ subscriptionIds.includes(currentStream.id) ? 'SUBSCRIBED' : 'SUBSCRIBE' }}
            </button>
            <div class="viewers">
              <span class="label">VIEWERS</span>
              <span class="value">{{ currentStream.viewers_count }}</span>
            </div>
          </div>
        </div>
        <RecordingManager
          v-if="currentStream"
          :key="currentStream.id"
          :stream-id="currentStream.id"
          :core-api="CORE_API"
          :access-token="accessToken"
          :can-manage="isCurrentUserOwner"
        />
        <MarkdownBlockEditor
          v-if="currentStream"
          :key="`markdown-editor-${currentStream.id}`"
          :stream-id="currentStream.id"
          :channel-title="currentStream.title"
          :is-owner="isCurrentUserOwner"
        />
        </template>

        <section v-else-if="currentPage === 'browse'" class="directory-page">
          <div class="directory-header">
            <div>
              <h1>// BROWSE CHANNELS</h1>
              <p>Discover live broadcasts and creator channels.</p>
            </div>
            <div class="pagination-status" v-if="paginationTotal > 0">
              <span class="badge">TOTAL: {{ paginationTotal }}</span>
              <span class="badge">PAGE {{ Math.floor(paginationSkip / paginationLimit) + 1 }} OF {{ Math.ceil(paginationTotal / paginationLimit) || 1 }}</span>
            </div>
          </div>
          <div class="channel-grid">
            <button v-for="st in streamsList" :key="st.id" class="channel-card" @click="openChannel(st)">
              <strong>{{ st.title }}</strong>
              <span>{{ st.owner }} · {{ st.is_live ? 'LIVE NOW' : 'OFFLINE' }}</span>
              <small>{{ st.description || 'No channel description yet.' }}</small>
            </button>
          </div>
          <p v-if="!streamsList.length" class="empty-page">No channels have been created yet.</p>

          <!-- B1 Pagination Controls -->
          <div v-if="paginationTotal > paginationLimit" class="pagination-bar">
            <button
              class="action-btn"
              :disabled="!prevLinkUrl"
              @click="goToPage(prevLinkUrl)"
            >
              PREVIOUS
            </button>
            <span class="page-indicator">
              PAGE {{ Math.floor(paginationSkip / paginationLimit) + 1 }} OF {{ Math.ceil(paginationTotal / paginationLimit) }}
            </span>
            <button
              class="action-btn"
              :disabled="!nextLinkUrl"
              @click="goToPage(nextLinkUrl)"
            >
              NEXT
            </button>
          </div>
        </section>

        <section v-else-if="currentPage === 'following'" class="directory-page">
          <h1>// FOLLOWING</h1>
          <p>Channels you follow that are broadcasting now.</p>
          <div class="channel-grid">
            <button v-for="st in followingStreams" :key="st.id" class="channel-card" @click="openChannel(st)">
              <strong>{{ st.title }}</strong><span>{{ st.owner }} · LIVE NOW</span>
              <small>{{ st.description || 'Live channel' }}</small>
            </button>
          </div>
          <p v-if="!followingStreams.length" class="empty-page">No followed channels are live. Browse channels to follow one.</p>
        </section>

        <section v-else-if="currentPage === 'archive'" class="directory-page">
          <h1>// ARCHIVE (SAVED VODs &amp; RECORDINGS)</h1>
          <p>Saved video recordings and offline streams. Open any stream to watch saved recordings or upload new VOD files.</p>
          <div class="channel-grid">
            <button v-for="st in offlineStreams" :key="st.id" class="channel-card" @click="openChannel(st)">
              <strong>{{ st.title }}</strong><span>{{ st.owner }} · OFFLINE</span>
              <small>{{ st.description || 'Open stream to view and manage recordings.' }}</small>
            </button>
          </div>
          <p v-if="!offlineStreams.length" class="empty-page">No offline streams in the archive.</p>
        </section>

        <!-- B6 Requirement: Special Page gated by Feature Flags -->
        <section v-else-if="currentPage === 'premium'" class="directory-page premium-page">
          <!-- Unlocked View if user has premium_page_access flag -->
          <template v-if="canAccessPremiumLounge">
            <div class="premium-header-row">
              <div>
                <h1>// VIP CREATOR LOUNGE (SPECIAL PAGE &bull; B6)</h1>
                <p>Exclusive broadcast telemetry, high-bitrate hardware transcode, and priority queue gated by the <code>premium_page_access</code> feature flag.</p>
              </div>
              <div class="premium-badges">
                <span class="vip-pill active">[FEATURE FLAG: ACTIVE]</span>
                <span class="vip-pill tier">[{{ userPlan.toUpperCase() }} TIER]</span>
              </div>
            </div>

            <div class="vip-grid">
              <div class="vip-card">
                <div class="vip-card-head">
                  <span class="vip-tag">INGEST PIPELINE</span>
                  <span class="vip-indicator live">&bull; LIVE</span>
                </div>
                <h3>Dedicated VIP Edge Node</h3>
                <p>High-throughput low-latency RTMP ingest cluster with dedicated 12,000 kbps cap.</p>
                <div class="vip-metrics">
                  <div class="metric-item">
                    <span>SERVER:</span>
                    <code>rtmp://vip-edge-eu.streamhub.internal/live</code>
                  </div>
                  <div class="metric-item">
                    <span>NVENC CODEC:</span>
                    <strong>HEVC / AV1 (4K &bull; 1080p60)</strong>
                  </div>
                  <div class="metric-item">
                    <span>EDGE LATENCY:</span>
                    <strong>18 ms &bull; 0.00% Packet Loss</strong>
                  </div>
                </div>
              </div>

              <div class="vip-card">
                <div class="vip-card-head">
                  <span class="vip-tag">QUEUE ACCELERATOR</span>
                  <span class="vip-indicator live">4.0x SPEED</span>
                </div>
                <h3>Priority Transcoding Queue</h3>
                <p>Background video workers allocate dedicated slots for your VODs with zero waiting line.</p>
                <div class="vip-metrics">
                  <div class="metric-item">
                    <span>WORKER POOL:</span>
                    <strong>VIP FastTrack Workers (2 dedicated)</strong>
                  </div>
                  <div class="metric-item">
                    <span>QUEUE BYPASS:</span>
                    <strong>Enabled (B8 Priority Flag)</strong>
                  </div>
                </div>
              </div>

              <div class="vip-card">
                <div class="vip-card-head">
                  <span class="vip-tag">CREATOR PERKS</span>
                  <span class="vip-indicator live">VERIFIED</span>
                </div>
                <h3>Exclusive VIP Identity</h3>
                <p>Subscribers and VIP partners receive unique monochrome badges and custom chat styling.</p>
                <div class="vip-metrics">
                  <div class="metric-item">
                    <span>CHAT BADGE:</span>
                    <span class="user-badge">[VIP CREATOR]</span>
                  </div>
                  <div class="metric-item">
                    <span>AI COPILOT VIP:</span>
                    <strong>Unlimited Token Stream</strong>
                  </div>
                </div>
              </div>
            </div>

            <div class="vip-controls-panel">
              <div class="panel-head">
                <h3>// FEATURE FLAG CONTROLS (TESTING B6)</h3>
                <p>Test the feature flag gating mechanism: downgrade to Free to verify the page immediately locks, or open the matrix to toggle individual flags.</p>
              </div>
              <div class="panel-actions">
                <button class="action-btn" @click="showFlagsModal = true">MANAGE FEATURE FLAGS</button>
                <button class="action-btn danger" @click="upgradeToPlan('free')">DOWNGRADE TO FREE (TEST GATE LOCK)</button>
              </div>
            </div>
          </template>

          <!-- Gated / Restricted View if feature flag is false -->
          <template v-else>
            <div class="premium-gated-box">
              <div class="gate-lock-badge">// ACCESS RESTRICTED &bull; FEATURE FLAG REQUIRED (B6) //</div>
              <h2>THIS SPECIAL PAGE IS LOCKED</h2>
              <p>
                The <code>premium_page_access</code> feature flag is currently <strong>DISABLED</strong> for your account (current plan: <strong>{{ userPlan.toUpperCase() }}</strong>).
                In accordance with <strong>B6</strong>, this special area requires a Premium or Partner subscription.
              </p>

              <div class="gated-plans-preview">
                <div class="gate-tier-card current">
                  <h4>FREE TIER</h4>
                  <span class="tier-state">[ACTIVE]</span>
                  <p>Standard 720p &bull; Public chat &bull; Standard queue</p>
                </div>
                <div class="gate-tier-card unlock-card">
                  <h4>PREMIUM CREATOR</h4>
                  <span class="tier-state highlight">[UNLOCKS SPECIAL PAGE]</span>
                  <p>VIP Lounge &bull; 1080p60 Transcode &bull; 4x Priority Queue</p>
                  <button class="action-btn primary" @click="upgradeToPlan('premium')">
                    UPGRADE TO PREMIUM (1-CLICK UNLOCK)
                  </button>
                </div>
                <div class="gate-tier-card">
                  <h4>PARTNER &amp; ADMIN</h4>
                  <span class="tier-state">[FULL ACCESS]</span>
                  <p>Individual Flag Overrides &bull; 4K Ingest</p>
                  <button class="action-btn" @click="upgradeToPlan('partner')">
                    ACTIVATE PARTNER PASS
                  </button>
                </div>
              </div>

              <div class="gate-footer-actions">
                <button class="action-btn" @click="showFlagsModal = true">OPEN FEATURE FLAGS MANAGER</button>
                <button class="action-btn" @click="navigate('home')">RETURN TO HOME</button>
              </div>
            </div>
          </template>
        </section>

        <section v-else class="directory-page profile-page">
          <h1>// CREATOR PROFILE</h1>
          <template v-if="currentUser">
            <p>Signed in as <strong>{{ currentUser }}</strong>. Manage your streams and OBS broadcast connection.</p>
            <div class="profile-panel">
              <h2>Broadcast setup</h2>
              <p>OBS server: <code>rtmp://127.0.0.1:1935/live</code></p>
              <p v-if="streamKey" class="stream-key-row">
                <span>OBS stream key:</span>
                <code>{{ streamKey }}</code>
                <button class="action-btn" @click="copyStreamKey">COPY KEY</button>
              </p>
              <p v-else class="profile-hint">
                Loading your OBS stream key…
                <button class="action-btn" @click="loadProfile">RETRY</button>
              </p>
              <p class="profile-hint">In OBS open Settings → Stream, select Custom, enter the server above and paste this key. Do not add “live/” to the key.</p>
              <button class="action-btn primary" @click="openStreamModal()">CREATE STREAM</button>
            </div>
            <h2>Your streams</h2>
            <div class="channel-grid">
              <div v-for="st in ownStreams" :key="st.id" class="channel-card profile-channel-card">
                <div class="channel-card-body" @click="openChannel(st)">
                  <strong>{{ st.title }}</strong>
                  <span class="live-pill" :class="{ is_live: st.is_live }">{{ st.is_live ? '■ LIVE' : 'OFFLINE' }}</span>
                  <small>{{ st.description || 'Manage stream and recordings.' }}</small>
                </div>
                <div class="channel-card-actions">
                  <button class="action-btn sm" @click.stop="openChannel(st)">OPEN</button>
                  <button class="action-btn sm" @click.stop="openStreamModal(st)">EDIT</button>
                  <button class="action-btn sm danger" @click.stop="deleteStreamDirect(st)">DELETE</button>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="empty-page">
            <p>Sign in or create an account to set up your channel and stream from OBS.</p>
            <button class="action-btn primary" @click="openAuthModal('register')">CREATE ACCOUNT</button>
          </div>
        </section>
      </main>

      <!-- Правый сайдбар чата -->
      <section v-if="currentPage === 'home' && currentStream" class="chat-section">
        <div class="chat-header">
          <span>STREAM CHAT</span>
          <button class="chat-ai-toggle" @click="toggleAiModal">AI ASSISTANT</button>
        </div>

        <section v-if="showAiPanel" class="ai-panel">
          <strong>AI stream guide</strong>
          <p>{{ aiAnswer }}</p>
          <div v-for="st in aiRecommendations" :key="st.id" class="ai-result" @click="openChannel(st)">
            {{ st.title }} · LIVE
          </div>
          <div class="ai-input">
            <input v-model="aiQuery" @keyup.enter="askAi" placeholder="What would you like to watch?" />
            <button @click="askAi">ASK</button>
          </div>
        </section>

        <div class="chat-messages" ref="chatScrollContainer">
          <div v-for="(msg, index) in messages" :key="msg.id || `${msg.user}-${index}`" class="chat-msg">
            <span class="time">{{ formatMessageTime(msg.timestamp || msg.time) }}</span>
            <span class="author-tag" :class="{ SYS: msg.is_warning }">{{ msg.user || msg.author }}:</span>
            <span class="text">{{ msg.text }}</span>
          </div>
        </div>

        <div class="chat-input-area">
          <input
            v-model="inputMessage"
            @keyup.enter="sendMessage"
            type="text"
            placeholder="SEND A MESSAGE..."
          />
          <button @click="sendMessage">SEND</button>
        </div>
      </section>
    </div>

    <div v-else class="landing-page-shell">
      <StreamLandingPage
        :streams="streamsList"
        :selected-stream-id="currentStream?.id ?? null"
        @back="toggleLandingPage"
        @watch="openPlayerFromLanding"
      />
    </div>

    <div v-if="showStreamModal" class="app-modal-backdrop">
      <div class="app-modal">
        <h3>// {{ editingStreamId ? 'EDIT STREAM' : 'NEW STREAM' }}</h3>
        <form @submit.prevent="saveStream">
          <input v-model="streamForm.title" type="text" placeholder="Stream title" maxlength="100" required />
          <textarea v-model="streamForm.description" placeholder="Description"></textarea>
          <input v-model="streamForm.thumbnail_url" type="url" placeholder="Thumbnail URL (optional)" />

          <!-- F2 Autocomplete Selector in Editing Form -->
          <div class="modal-combobox-wrap">
            <Select2Combobox
              label="Linked Channel / Raid Target (Select2 Combobox):"
              :endpoint="`${CORE_API}/api/streams/autocomplete`"
              placeholder="Search channels to link (min 3 chars, 300ms debounce)..."
              :min-chars="3"
              :debounce-ms="300"
              v-model="streamForm.linked_stream_id"
            />
          </div>

          <div v-if="streamError" class="modal-err">{{ streamError }}</div>
          <div class="modal-actions">
            <button type="submit" class="action-btn primary">SAVE</button>
            <button type="button" class="action-btn" @click="showStreamModal = false">CANCEL</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Модальное окно входа / регистрации -->
    <div v-if="showAuthModal" class="app-modal-backdrop">
      <div class="app-modal">
        <h3>// {{ authMode.toUpperCase() }}</h3>
        <form @submit.prevent="submitAuth">
          <input v-model="authForm.username" type="text" placeholder="Username" required />
          <input
            v-if="authMode === 'register'"
            v-model="authForm.email"
            type="email"
            placeholder="Email"
            required
          />
          <input
            v-model="authForm.password"
            type="password"
            placeholder="Password (8-72 characters)"
            minlength="8"
            maxlength="72"
            required
          />

          <div v-if="authError" class="modal-err">{{ authError }}</div>

          <div class="modal-actions">
            <button type="submit" class="action-btn primary">SUBMIT</button>
            <button type="button" class="action-btn" @click="showAuthModal = false">CANCEL</button>
          </div>

          <!-- C16 Requirement: OAuth2 Social Logins -->
          <div class="oauth-divider">
            <span>OR CONTINUE WITH OAUTH2 (C16)</span>
          </div>

          <div class="oauth-buttons">
            <button
              type="button"
              class="oauth-action-btn"
              :disabled="oauthLoading"
              @click="loginWithOAuth('google')"
            >
              <span class="oauth-tag">[GOOGLE]</span>
              <span>CONTINUE WITH GOOGLE</span>
            </button>
            <button
              type="button"
              class="oauth-action-btn"
              :disabled="oauthLoading"
              @click="loginWithOAuth('github')"
            >
              <span class="oauth-tag">[GITHUB]</span>
              <span>CONTINUE WITH GITHUB</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Модальне вікно ШІ-асистента -->
    <div v-if="showAiModal" class="app-modal-backdrop ai-modal-backdrop" @click.self="showAiModal = false">
      <div class="ai-assistant-modal">
        <div class="ai-assistant-header">
          <div class="ai-header-info">
            <span class="ai-avatar-badge">[AI]</span>
            <div>
              <h3>STREAMHUB AI ASSISTANT</h3>
              <span class="ai-status-badge">ONLINE &middot; REAL-TIME LLM GUIDE</span>
            </div>
          </div>
          <button class="ai-close-btn" @click="showAiModal = false" title="Close">&times;</button>
        </div>

        <!-- Quick prompt chips (C21 & C22 Tool Triggers) -->
        <div class="ai-quick-prompts">
          <button class="quick-chip" @click="sendAiQuickPrompt('Які стріми зараз онлайн?')">// ОНЛАЙН СТРІМИ (list_streams)</button>
          <button class="quick-chip" @click="sendAiQuickPrompt('Покажи телеметрію потоку та бітрейт')">// ТЕЛЕМЕТРІЯ (telemetry)</button>
          <button class="quick-chip" @click="sendAiQuickPrompt('Покажи збережені записи VOD')">// АРХІВ VOD (recordings)</button>
          <button class="quick-chip" @click="sendAiQuickPrompt('Створи новий стрім Cyberpunk Night')">// СТВОРИТИ СТРІМ (create_stream)</button>
          <button class="quick-chip" @click="sendAiQuickPrompt('Який стан платформи StreamHub?')">// СТАН СЕРВЕРА (status)</button>
        </div>

        <div class="ai-messages-container" ref="aiScrollContainer">
          <div
            v-for="(msg, i) in aiChatMessages"
            :key="i"
            class="ai-chat-bubble-wrap"
            :class="msg.role"
          >
            <div class="ai-bubble-avatar">
              {{ msg.role === 'assistant' ? 'AI' : 'YOU' }}
            </div>
            <div class="ai-bubble-content">
              <div class="ai-bubble-author">{{ msg.role === 'assistant' ? 'STREAMHUB AI AGENT (C21 SSE)' : (currentUser || 'YOU') }}</div>

              <!-- C21 Thinking & Tool Calling Steps visualization -->
              <div v-if="msg.steps && msg.steps.length" class="ai-workflow-box">
                <div class="workflow-header" @click="msg.showSteps = !msg.showSteps">
                  <span class="workflow-title">// AGENT REASONING &amp; MCP TOOL CALLS ({{ msg.steps.length }} STEPS)</span>
                  <span class="workflow-toggle">{{ msg.showSteps ? '▲ HIDE' : '▼ VIEW' }}</span>
                </div>
                <div v-if="msg.showSteps !== false" class="workflow-body">
                  <div v-for="(st, sIdx) in msg.steps" :key="sIdx" class="workflow-item" :class="st.type">
                    <span class="workflow-badge">[{{ st.type.toUpperCase() }}]</span>
                    <span v-if="st.type === 'thinking'" class="workflow-thought">{{ st.text }}</span>
                    <span v-else-if="st.type === 'tool_call'" class="workflow-tool">
                      <code>mcp.{{ st.tool }}({{ JSON.stringify(st.args) }})</code>
                    </span>
                    <span v-else-if="st.type === 'tool_result'" class="workflow-res">
                      <code>Status: 200 OK &bull; Result: {{ JSON.stringify(st.result).slice(0, 140) }}...</code>
                    </span>
                    <span v-else class="workflow-info">{{ st.text }}</span>
                  </div>
                </div>
              </div>

              <div class="ai-bubble-text" style="white-space: pre-wrap;">{{ msg.content }}</div>

              <!-- Recommendation cards if present -->
              <div v-if="msg.recommendations && msg.recommendations.length > 0" class="ai-rec-cards">
                <div
                  v-for="st in msg.recommendations"
                  :key="st.id"
                  class="ai-rec-card"
                  @click="openChannelFromAi(st)"
                >
                  <div class="rec-card-thumb">
                    <img :src="st.thumbnail_url || fallbackImage" :alt="st.title" @error="onRecThumbError" />
                    <span class="rec-live-tag" :class="{ live: st.is_live }">{{ st.is_live ? 'LIVE' : 'OFFLINE' }}</span>
                  </div>
                  <div class="rec-card-info">
                    <h4>{{ st.title }}</h4>
                    <p>{{ st.description || 'Live broadcast' }}</p>
                    <div class="rec-card-footer">
                      <span>@{{ st.owner }}</span>
                      <button class="rec-watch-btn">WATCH</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="aiIsLoading" class="ai-chat-bubble-wrap assistant">
            <div class="ai-bubble-avatar">AI</div>
            <div class="ai-bubble-content">
              <div class="ai-bubble-author">STREAMHUB AI</div>
              <div class="ai-typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="ai-input-bar">
          <input
            v-model="aiUserQuery"
            @keyup.enter="handleAiSubmit"
            type="text"
            placeholder="Ask AI anything (recommendations, OBS settings, help)..."
            :disabled="aiIsLoading"
          />
          <button class="action-btn primary" @click="handleAiSubmit" :disabled="aiIsLoading || !aiUserQuery.trim()">
            SEND
          </button>
        </div>
      </div>
    </div>

    <!-- B2 Telegram Webhooks & Bot Modal -->
    <TelegramModal
      v-if="showTelegramModal"
      :core-api="CORE_API"
      :streams="streamsList"
      :stream-id="currentStream ? currentStream.id : null"
      :stream-title="currentStream ? currentStream.title : 'Live Stream'"
      :stream-owner="currentStream ? currentStream.owner : (currentUser || 'vlasniktest')"
      :is-live="Boolean(currentStream && currentStream.is_live)"
      :access-token="accessToken"
      @close="showTelegramModal = false"
    />

    <!-- B8 Async Message Queue & Workers Modal -->
    <AsyncQueueModal
      v-if="showQueueModal"
      :core-api="CORE_API"
      :stream-id="currentStream ? currentStream.id : null"
      @close="showQueueModal = false"
    />

    <!-- F6 JavaScript Canvas 2D Audio Visualizer & Studio Modal -->
    <CanvasStudioModal
      v-if="showCanvasModal"
      :video-element="videoElement"
      @close="showCanvasModal = false"
    />

    <!-- B6 Feature Flags & Subscription Plans Modal -->
    <FeatureFlagsModal
      v-if="showFlagsModal"
      :core-api="CORE_API"
      :access-token="accessToken"
      @close="showFlagsModal = false"
      @navigate-page="navigate"
      @plan-changed="onPlanChanged"
    />

    <!-- F1 Chart.js Analytics & Visualizations Modal -->
    <AnalyticsDashboardModal
      v-if="showAnalyticsModal"
      :core-api="CORE_API"
      :streams="streamsList"
      :initial-stream-id="currentStream?.id ?? (streamsList[0]?.id ?? 1)"
      @close="showAnalyticsModal = false"
    />

    <!-- C22 Model Context Protocol Server Modal -->
    <McpServerModal
      v-if="showMcpModal"
      :core-api="CORE_API"
      @close="showMcpModal = false"
    />

    <!-- C19 Blob Storage & CDN Architecture Modal -->
    <BlobStorageModal
      v-if="showBlobModal"
      @close="showBlobModal = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import Hls from 'hls.js';
import RecordingManager from './components/RecordingManager.vue';
import StreamLandingPage from './components/StreamLandingPage.vue';
import FileApiModal from './components/FileApiModal.vue';
import Select2Combobox from './components/Select2Combobox.vue';
import TelegramModal from './components/TelegramModal.vue';
import MarkdownBlockEditor from './components/MarkdownBlockEditor.vue';
import AsyncQueueModal from './components/AsyncQueueModal.vue';
import CanvasStudioModal from './components/CanvasStudioModal.vue';
import FeatureFlagsModal from './components/FeatureFlagsModal.vue';
import AnalyticsDashboardModal from './components/AnalyticsDashboardModal.vue';
import McpServerModal from './components/McpServerModal.vue';
import BlobStorageModal from './components/BlobStorageModal.vue';
import fallbackImage from './assets/hero.png';

const CORE_API = 'http://localhost:8000';
const CHAT_WS_URL = 'ws://localhost:8001';
const AI_API_URL = 'http://localhost:8002';

const videoElement = ref(null);
const streamsList = ref([]);
const currentStream = ref(null);
const showLandingPage = ref(false);
const showFileApiModal = ref(false);
const showTelegramModal = ref(false);
const showQueueModal = ref(false);
const showCanvasModal = ref(false);
const showFlagsModal = ref(false);
const showAnalyticsModal = ref(false);
const showMcpModal = ref(false);
const showBlobModal = ref(false);
const showToolsMenu = ref(false);

const openTool = (toolKey) => {
  showToolsMenu.value = false;
  if (toolKey === 'mcp') showMcpModal.value = true;
  else if (toolKey === 'blob') showBlobModal.value = true;
  else if (toolKey === 'analytics') showAnalyticsModal.value = true;
  else if (toolKey === 'flags') showFlagsModal.value = true;
  else if (toolKey === 'canvas') showCanvasModal.value = true;
  else if (toolKey === 'queue') showQueueModal.value = true;
  else if (toolKey === 'telegram') showTelegramModal.value = true;
  else if (toolKey === 'channels') toggleLandingPage();
  else if (toolKey === 'ai') toggleAiModal();
};

const closeToolsMenuOnOutside = (e) => {
  if (showToolsMenu.value && !e.target.closest('.tools-menu-wrap')) {
    showToolsMenu.value = false;
  }
};

// B6 Feature Flags & Subscription State
const userPlan = ref('free');
const userFlags = ref({
  premium_page_access: false,
  '1080p60_transcode': false,
  vod_priority_queue: false,
  ai_copilot_vip: false,
  canvas_studio_pro: false,
  custom_vip_badge: false,
  admin_override_flags: false
});
const canAccessPremiumLounge = computed(() => Boolean(userFlags.value && userFlags.value.premium_page_access));

const currentPage = ref('home');
const navigationPages = [
  { id: 'home', label: 'HOME' },
  { id: 'browse', label: 'BROWSE' },
  { id: 'following', label: 'FOLLOWING' },
  { id: 'archive', label: 'ARCHIVE' },
  { id: 'premium', label: 'PREMIUM LOUNGE' },
  { id: 'profile', label: 'PROFILE' }
];
const liveStreams = computed(() => {
  const rawLive = streamsList.value.filter((stream) => stream.is_live);
  // An owner only broadcasts one live stream at a time through their OBS key
  const seenOwners = new Set();
  const deduped = [];
  for (const st of rawLive) {
    if (!seenOwners.has(st.owner)) {
      seenOwners.add(st.owner);
      deduped.push(st);
    }
  }
  return deduped;
});

const offlineStreams = computed(() => {
  const liveIds = new Set(liveStreams.value.map((s) => s.id));
  return streamsList.value.filter((stream) => !liveIds.has(stream.id));
});
const followingIds = ref([]);
const subscriptionIds = ref([]);
const followingStreams = computed(() =>
  liveStreams.value.filter((stream) => followingIds.value.includes(stream.id))
);
const ownStreams = computed(() =>
  streamsList.value.filter((stream) => stream.user_id === currentUserId.value)
);
const messages = ref([]);
const inputMessage = ref('');
const chatScrollContainer = ref(null);
const playerStatus = ref('OFFLINE');
const hasVideoFrame = ref(false);
const profile = ref(null);
const streamKey = ref(localStorage.getItem('stream_stream_key') || '');
const showAiPanel = ref(false);
const aiQuery = ref('');
const aiAnswer = ref('Tell me what you like and I will find an active stream.');
const aiRecommendations = ref([]);

const showAiModal = ref(false);
const aiUserQuery = ref('');
const aiIsLoading = ref(false);
const aiScrollContainer = ref(null);
const aiChatMessages = ref([
  {
    role: 'assistant',
    content: 'Вітаю. Я ШІ-асистент StreamHub.\n\nМожу порекомендувати стріми, розповісти про платформу або підказати, як правильно налаштувати OBS Studio для трансляції з низькою затримкою.',
    recommendations: []
  }
]);

const currentUser = ref(localStorage.getItem('stream_user') || '');
const showAuthModal = ref(false);
const authMode = ref('login');
const authForm = ref({ username: '', email: '', password: '' });
const authError = ref('');
const currentUserId = ref(Number(localStorage.getItem('stream_user_id')) || null);
const showStreamModal = ref(false);
const editingStreamId = ref(null);
const streamForm = ref({ title: '', description: '', thumbnail_url: '' });
const streamError = ref('');

const isCurrentUserOwner = computed(
  () => Boolean(currentUserId.value && currentStream.value?.user_id === currentUserId.value)
);
const accessToken = computed(() => localStorage.getItem('stream_token') || '');

let hlsInstance = null;
let wsInstance = null;
let reconnectTimer = null;
let pollTimer = null;

const paginationSkip = ref(0);
const paginationLimit = ref(20);
const paginationTotal = ref(0);
const nextLinkUrl = ref(null);
const prevLinkUrl = ref(null);
const currentStreamsUrl = ref(`${CORE_API}/api/streams?skip=0&limit=20`);

const goToPage = (link) => {
  if (link) {
    fetchStreams(link);
  }
};

const fetchStreams = async (targetUrl = null) => {
  const url = targetUrl || currentStreamsUrl.value;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Unable to load streams (${res.status})`);
    const data = await res.json();
    streamsList.value = data.items || (Array.isArray(data) ? data : []);
    if (data.total !== undefined) {
      paginationTotal.value = data.total;
      paginationSkip.value = data.skip ?? 0;
      paginationLimit.value = data.limit ?? 20;
      nextLinkUrl.value = data.nextLink || null;
      prevLinkUrl.value = data.prevLink || null;
      currentStreamsUrl.value = url;
    }

    if (streamsList.value.length > 0) {
      if (currentStream.value) {
        const updated = streamsList.value.find((s) => s.id === currentStream.value.id);
        if (updated) {
          const wasLive = currentStream.value.is_live;
          Object.assign(currentStream.value, updated);
          if (wasLive !== updated.is_live && currentPage.value === 'home') {
            await nextTick();
            initPlayer(updated.playback_url);
          }
        }
      }
    }
  } catch (err) {
    console.error('Core API error:', err);
  }
};

const validateSession = async () => {
  if (!accessToken.value) return;
  try {
    const response = await fetch(`${CORE_API}/api/users/me`, { headers: authenticatedHeaders() });
    if (response.status === 401) {
      handleLogout();
      openAuthModal('login');
      authError.value = 'Your session expired. Please sign in again.';
      return;
    }
    if (!response.ok) throw new Error(`Unable to validate session (${response.status})`);
    profile.value = await response.json();
    streamKey.value = profile.value.stream_key;
    localStorage.setItem('stream_stream_key', streamKey.value);
    currentUser.value = profile.value.username;
    currentUserId.value = profile.value.id;
    await loadSocialData();
  } catch (error) {
    console.error('Unable to validate the current session:', error);
  }
};

// Запуск воспроизведения HLS с оптимизацией низкой задержки (Low Latency)
const initPlayer = (url) => {
  if (!videoElement.value) return;

  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }
  videoElement.value.removeAttribute('src');
  videoElement.value.load();
  hasVideoFrame.value = false;
  if (!currentStream.value?.is_live || !url) {
    playerStatus.value = 'OFFLINE';
    return;
  }
  playerStatus.value = 'CONNECTING • WAITING FOR HLS';

  if (Hls.isSupported()) {
    hlsInstance = new Hls({
      enableWorker: true,
      lowLatencyMode: true,          // Включаем LL-HLS для MediaMTX
      backBufferLength: 10,
      maxBufferLength: 6,
      maxMaxBufferLength: 12,
      liveSyncDurationCount: 1,      // Синхронизация с самым свежим сегментом
      liveMaxLatencyDurationCount: 3,
      maxLiveSyncPlaybackRate: 1.5,
      liveDurationInfinity: true,
      highBufferWatchdogPeriod: 1,
    });

    hlsInstance.loadSource(url);
    hlsInstance.attachMedia(videoElement.value);

    hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
      playerStatus.value = 'LIVE';
      videoElement.value.muted = true;
      const playPromise = videoElement.value.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => console.warn('Autoplay blocked:', err));
      }
    });

    hlsInstance.on(Hls.Events.FRAG_LOADED, () => {
      if (currentStream.value?.is_live) {
        hasVideoFrame.value = true;
        playerStatus.value = 'LIVE';
      }
    });

    hlsInstance.on(Hls.Events.ERROR, (event, data) => {
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
        playerStatus.value = 'CONNECTING • WAITING FOR HLS';
      }
      if (data.fatal) {
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            setTimeout(() => {
              if (hlsInstance) hlsInstance.startLoad();
            }, 1000);
            break;
          case Hls.ErrorTypes.MEDIA_ERROR:
            hlsInstance.recoverMediaError();
            break;
          default:
            hlsInstance.destroy();
            break;
        }
      }
    });
  } else if (videoElement.value.canPlayType('application/vnd.apple.mpegurl')) {
    videoElement.value.src = url;
    videoElement.value.muted = true;
    videoElement.value.play().catch((error) => console.warn('Autoplay is blocked:', error));
  }
};

const forceReloadPlayer = () => {
  if (currentStream.value?.playback_url) {
    initPlayer(currentStream.value.playback_url);
  }
};

const onVideoTimeUpdate = () => {
  if (videoElement.value && videoElement.value.currentTime > 0.1 && currentStream.value?.is_live) {
    hasVideoFrame.value = true;
    playerStatus.value = 'LIVE';
  }
};

const initChat = (streamId) => {
  if (wsInstance) {
    wsInstance.close();
    wsInstance = null;
  }
  clearTimeout(reconnectTimer);

  const token = localStorage.getItem('stream_token');
  const wsUrl = token
    ? `${CHAT_WS_URL}/ws/chat/${streamId}?token=${encodeURIComponent(token)}`
    : `${CHAT_WS_URL}/ws/chat/${streamId}`;

  const socket = new WebSocket(wsUrl);
  wsInstance = socket;

  socket.onopen = () => {
    console.log(`[WS] Connected to stream room: ${streamId}`);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'history') {
        messages.value = data.messages || [];
      } else if (!data.id || !messages.value.some((message) => message.id === data.id)) {
        messages.value.push(data);
      }
      nextTick(() => {
        if (chatScrollContainer.value) {
          chatScrollContainer.value.scrollTop = chatScrollContainer.value.scrollHeight;
        }
      });
    } catch (e) {
      console.error('[WS] Parse error', e);
    }
  };

  socket.onclose = () => {
    if (wsInstance !== socket) return;
    reconnectTimer = setTimeout(() => {
      if (currentStream.value) initChat(currentStream.value.id);
    }, 3000);
  };
};

const markVideoReady = () => {
  if (!currentStream.value?.is_live) return;
  hasVideoFrame.value = true;
  playerStatus.value = 'LIVE';
};

const markVideoWaiting = () => {
  if (!hasVideoFrame.value && currentStream.value?.is_live) {
    playerStatus.value = 'CONNECTING • WAITING FOR HLS';
  }
};

const handleVideoError = () => {
  if (!currentStream.value?.is_live) return;
  hasVideoFrame.value = false;
  playerStatus.value = 'VIDEO ERROR';
};

const selectStream = (st) => {
  currentStream.value = st;
  messages.value = [];
  initChat(st.id);
};

const openChannel = async (stream) => {
  currentPage.value = 'home';
  showLandingPage.value = false;
  selectStream(stream);
  await nextTick();
  initPlayer(stream.playback_url);
};

const handleChannelSelectFromCombobox = async (channel) => {
  if (!channel) return;
  const found = streamsList.value.find((s) => s.id === channel.id);
  const target = found || channel;
  if (!target.playback_url && target.owner) {
    target.playback_url = `http://localhost:8888/live/${target.owner}/index.m3u8`;
  }
  await openChannel(target);
};

const navigate = async (page) => {
  showLandingPage.value = false;
  currentPage.value = page;
  if (page !== 'home' && wsInstance) {
    wsInstance.close();
    wsInstance = null;
    clearTimeout(reconnectTimer);
  }
  if (page === 'following') await loadSocialData();
  if (page === 'profile' && currentUser.value) await loadProfile();
  if (page === 'home') {
    await nextTick();
    if (currentStream.value) {
      initChat(currentStream.value.id);
      initPlayer(currentStream.value.playback_url);
    }
  }
};

const toggleLandingPage = async () => {
  showLandingPage.value = !showLandingPage.value;
  if (!showLandingPage.value) {
    await nextTick();
    if (currentStream.value) {
      initPlayer(currentStream.value.playback_url);
    }
  }
};

const openPlayerFromLanding = async (stream) => {
  showLandingPage.value = false;
  await openChannel(stream);
};

const sendMessage = () => {
  const text = inputMessage.value.trim();
  if (!text || !wsInstance || wsInstance.readyState !== WebSocket.OPEN) return;

  wsInstance.send(JSON.stringify({ text }));
  inputMessage.value = '';
};

const formatMessageTime = (value) => {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const authenticatedHeaders = () => ({
  Authorization: `Bearer ${accessToken.value}`
});

const loadSocialData = async () => {
  if (!accessToken.value) {
    followingIds.value = [];
    subscriptionIds.value = [];
    return;
  }
  const [followsResponse, subscriptionsResponse] = await Promise.all([
    fetch(`${CORE_API}/api/users/me/follows`, { headers: authenticatedHeaders() }),
    fetch(`${CORE_API}/api/users/me/subscriptions`, { headers: authenticatedHeaders() })
  ]);
  if (!followsResponse.ok || !subscriptionsResponse.ok) {
    throw new Error('Unable to load followed channels');
  }
  const [follows, subscriptions] = await Promise.all([followsResponse.json(), subscriptionsResponse.json()]);
  followingIds.value = follows.stream_ids || [];
  subscriptionIds.value = subscriptions.stream_ids || [];
};

const loadProfile = async () => {
  if (!accessToken.value) return;
  const response = await fetch(`${CORE_API}/api/users/me`, { headers: authenticatedHeaders() });
  if (!response.ok) throw new Error('Unable to load your profile');
  profile.value = await response.json();
  streamKey.value = profile.value.stream_key;
  localStorage.setItem('stream_stream_key', streamKey.value);
};

// B6 Feature Flags & Plan Management
const refreshUserFlags = async () => {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`;
    }
    const res = await fetch(`${CORE_API}/api/v1/features/my-flags`, { headers });
    if (res.ok) {
      const data = await res.json();
      userPlan.value = data.plan || 'free';
      userFlags.value = data.effective_flags || {};
    }
  } catch (err) {
    console.error('Failed to load user feature flags:', err);
  }
};

const upgradeToPlan = async (targetPlan) => {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (accessToken.value) {
      headers['Authorization'] = `Bearer ${accessToken.value}`;
    }
    const res = await fetch(`${CORE_API}/api/v1/features/change-plan`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ plan: targetPlan })
    });
    if (res.ok) {
      const data = await res.json();
      userPlan.value = data.plan;
      userFlags.value = data.effective_flags;
    }
  } catch (err) {
    console.error('Failed to update plan:', err);
  }
};

const onPlanChanged = (payload) => {
  if (payload.plan) userPlan.value = payload.plan;
  if (payload.effectiveFlags) userFlags.value = payload.effectiveFlags;
};

const copyStreamKey = async () => {
  try {
    await navigator.clipboard.writeText(streamKey.value);
  } catch (error) {
    console.error('Unable to copy OBS stream key:', error);
    window.alert('Could not copy the stream key. Select and copy it manually.');
  }
};

const toggleRelationship = async (relation, ids) => {
  if (!currentStream.value) return;
  if (!accessToken.value) {
    openAuthModal('login');
    return;
  }
  const streamId = currentStream.value.id;
  const adding = !ids.value.includes(streamId);
  const response = await fetch(
    `${CORE_API}/api/streams/${streamId}/${relation}`,
    { method: adding ? 'POST' : 'DELETE', headers: authenticatedHeaders() }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    window.alert(error.detail || `Unable to update ${relation}`);
    return;
  }
  ids.value = adding ? [...ids.value, streamId] : ids.value.filter((id) => id !== streamId);
};

const toggleFollow = () => toggleRelationship('follow', followingIds);
const toggleSubscription = () => toggleRelationship('subscribe', subscriptionIds);

const askAi = async () => {
  aiAnswer.value = 'Finding active streams…';
  aiRecommendations.value = [];
  try {
    const response = await fetch(`${AI_API_URL}/api/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: aiQuery.value })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'AI guide is unavailable');
    aiAnswer.value = data.answer;
    aiRecommendations.value = data.recommendations || [];
  } catch (error) {
    aiAnswer.value = error instanceof Error ? error.message : 'AI guide is unavailable';
  }
};

const toggleAiModal = () => {
  showAiModal.value = !showAiModal.value;
  if (showAiModal.value) {
    nextTick(() => {
      if (aiScrollContainer.value) {
        aiScrollContainer.value.scrollTop = aiScrollContainer.value.scrollHeight;
      }
    });
  }
};

const sendAiQuickPrompt = (promptText) => {
  aiUserQuery.value = promptText;
  handleAiSubmit();
};

const handleAiSubmit = async () => {
  const query = aiUserQuery.value.trim();
  if (!query || aiIsLoading.value) return;

  aiChatMessages.value.push({
    role: 'user',
    content: query,
    recommendations: [],
    steps: []
  });
  aiUserQuery.value = '';
  aiIsLoading.value = true;

  const assistantMsgIndex = aiChatMessages.value.length;
  aiChatMessages.value.push({
    role: 'assistant',
    content: '',
    recommendations: [],
    steps: [],
    showSteps: true
  });

  const scrollBottom = () => {
    nextTick(() => {
      if (aiScrollContainer.value) {
        aiScrollContainer.value.scrollTop = aiScrollContainer.value.scrollHeight;
      }
    });
  };
  scrollBottom();

  try {
    const response = await fetch(`${AI_API_URL}/api/agent/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        stream_id: currentStream.value?.id || 1
      })
    });

    if (!response.ok || !response.body) {
      throw new Error(`SSE Stream returned HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const ev of events) {
        if (!ev.trim()) continue;
        const lines = ev.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice(6).trim();
          }
        }

        if (dataStr) {
          try {
            const parsed = JSON.parse(dataStr);
            const msg = aiChatMessages.value[assistantMsgIndex];
            if (!msg) continue;

            if (eventType === 'status') {
              msg.steps.push({ type: 'status', text: parsed.message });
            } else if (eventType === 'thinking') {
              msg.steps.push({ type: 'thinking', text: parsed.thought });
            } else if (eventType === 'tool_call') {
              msg.steps.push({
                type: 'tool_call',
                tool: parsed.tool,
                args: parsed.arguments
              });
            } else if (eventType === 'tool_result') {
              msg.steps.push({
                type: 'tool_result',
                tool: parsed.tool,
                result: parsed.result_preview
              });
            } else if (eventType === 'token') {
              msg.content += parsed.token;
            } else if (eventType === 'done') {
              if (parsed.recommendations && parsed.recommendations.length) {
                msg.recommendations = parsed.recommendations;
              }
            }
            scrollBottom();
          } catch (jsonErr) {
            console.error('Failed to parse SSE data:', jsonErr);
          }
        }
      }
    }
  } catch (err) {
    console.warn('Falling back to standard chat endpoint:', err);
    try {
      const res = await fetch(`${AI_API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: query }],
          user: currentUser.value || 'Viewer'
        })
      });
      const data = await res.json();
      const msg = aiChatMessages.value[assistantMsgIndex];
      if (msg) {
        msg.content = data.reply || 'Ось відповідь:';
        msg.recommendations = data.recommendations || [];
      }
    } catch (fallbackErr) {
      const msg = aiChatMessages.value[assistantMsgIndex];
      if (msg) {
        msg.content = `Помилка з'єднання з AI-агентом (${err.message}). Переконайся, що ai-agent працює на порту 8002.`;
      }
    }
  } finally {
    aiIsLoading.value = false;
    scrollBottom();
  }
};

const openChannelFromAi = (stream) => {
  showAiModal.value = false;
  openChannel(stream);
};

const onRecThumbError = (event) => {
  event.target.src = fallbackImage || '/favicon.svg';
};

// Управление авторизацией
const openAuthModal = (mode) => {
  authMode.value = mode;
  authError.value = '';
  showAuthModal.value = true;
};

const submitAuth = async () => {
  authError.value = '';
  const endpoint =
    authMode.value === 'register'
      ? `${CORE_API}/api/v1/auth/register`
      : `${CORE_API}/api/v1/auth/login`;

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(authForm.value)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Authentication failed');
    }

    localStorage.setItem('stream_token', data.access_token);
    localStorage.setItem('stream_user', data.username);
    localStorage.setItem('stream_user_id', String(data.user_id));
    localStorage.setItem('stream_stream_key', data.stream_key);
    currentUser.value = data.username;
    currentUserId.value = data.user_id;
    streamKey.value = data.stream_key;
    profile.value = {
      id: data.user_id,
      username: data.username,
      stream_key: data.stream_key
    };
    showAuthModal.value = false;
    refreshUserFlags().catch((error) => console.error('Unable to refresh user flags:', error));
    loadSocialData().catch((error) => console.error('Unable to load social data:', error));
    if (currentPage.value === 'profile') {
      loadProfile().catch((error) => console.error('Unable to load profile:', error));
    }

    if (currentStream.value) {
      initChat(currentStream.value.id);
    }
  } catch (err) {
    authError.value = err.message;
  }
};

const oauthLoading = ref(false);

const loginWithOAuth = async (provider) => {
  oauthLoading.value = true;
  authError.value = '';
  try {
    const res = await fetch(`${CORE_API}/api/v1/auth/oauth/${provider}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `OAuth authentication with ${provider} failed`);
    }

    localStorage.setItem('stream_token', data.access_token);
    localStorage.setItem('stream_user', data.username);
    localStorage.setItem('stream_user_id', String(data.user_id));
    localStorage.setItem('stream_stream_key', data.stream_key);
    currentUser.value = data.username;
    currentUserId.value = data.user_id;
    streamKey.value = data.stream_key;
    profile.value = {
      id: data.user_id,
      username: data.username,
      stream_key: data.stream_key,
    };
    showAuthModal.value = false;
    refreshUserFlags().catch((error) => console.error('Unable to refresh user flags:', error));
    loadSocialData().catch((error) => console.error('Unable to load social data:', error));
    if (currentPage.value === 'profile') {
      loadProfile().catch((error) => console.error('Unable to load profile:', error));
    }
    if (currentStream.value) {
      initChat(currentStream.value.id);
    }
  } catch (err) {
    authError.value = err.message || 'OAuth error';
  } finally {
    oauthLoading.value = false;
  }
};

const handleLogout = () => {
  localStorage.removeItem('stream_token');
  localStorage.removeItem('stream_user');
  localStorage.removeItem('stream_user_id');
  localStorage.removeItem('stream_stream_key');
  currentUser.value = '';
  currentUserId.value = null;
  streamKey.value = '';
  profile.value = null;
  followingIds.value = [];
  subscriptionIds.value = [];
  userPlan.value = 'free';
  refreshUserFlags().catch((e) => console.error(e));
  if (currentStream.value) {
    initChat(currentStream.value.id);
  }
};

const openStreamModal = (stream = null) => {
  editingStreamId.value = stream?.id ?? null;
  streamForm.value = {
    title: stream?.title ?? '',
    description: stream?.description ?? '',
    thumbnail_url: stream?.thumbnail_url ?? '',
    linked_stream_id: null
  };
  streamError.value = '';
  showStreamModal.value = true;
};

const saveStream = async () => {
  streamError.value = '';
  const isEditing = editingStreamId.value !== null;
  const url = isEditing
    ? `${CORE_API}/api/streams/${editingStreamId.value}`
    : `${CORE_API}/api/streams`;

  try {
    const res = await fetch(url, {
      method: isEditing ? 'PUT' : 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('stream_token')}`
      },
      body: JSON.stringify({
        title: streamForm.value.title,
        description: streamForm.value.description,
        thumbnail_url: streamForm.value.thumbnail_url || null
      })
    });
    const data = res.status === 204 ? null : await res.json();
    if (!res.ok) {
      throw new Error(data?.detail || 'Unable to save stream');
    }

    showStreamModal.value = false;
    await fetchStreams();
    if (!isEditing && data) {
      const createdStream = streamsList.value.find((stream) => stream.id === data.id);
      if (createdStream) await openChannel(createdStream);
    }
  } catch (err) {
    streamError.value = err instanceof Error ? err.message : 'Unable to save stream';
  }
};

const deleteCurrentStream = async () => {
  if (!currentStream.value || !window.confirm(`Delete "${currentStream.value.title}"?`)) return;

  try {
    const res = await fetch(`${CORE_API}/api/streams/${currentStream.value.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('stream_token')}` }
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Unable to delete stream');
    }

    currentStream.value = null;
    await fetchStreams();
  } catch (err) {
    window.alert(err instanceof Error ? err.message : 'Unable to delete stream');
  }
};

const deleteStreamDirect = async (stream) => {
  if (!stream || !window.confirm(`Delete "${stream.title}"?`)) return;

  try {
    const res = await fetch(`${CORE_API}/api/streams/${stream.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('stream_token')}` }
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Unable to delete stream');
    }

    if (currentStream.value?.id === stream.id) {
      currentStream.value = null;
    }
    await fetchStreams();
  } catch (err) {
    window.alert(err instanceof Error ? err.message : 'Unable to delete stream');
  }
};

onMounted(() => {
  // C16 OAuth2 redirect callback handler
  const urlParams = new URLSearchParams(window.location.search);
  const oauthToken = urlParams.get('oauth_token');
  const oauthUsername = urlParams.get('username');
  if (oauthToken && oauthUsername) {
    localStorage.setItem('stream_token', oauthToken);
    localStorage.setItem('stream_user', oauthUsername);
    currentUser.value = oauthUsername;
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  fetchStreams();
  validateSession();
  refreshUserFlags();
  pollTimer = setInterval(fetchStreams, 1500);
  window.addEventListener('click', closeToolsMenuOnOutside);
});

onBeforeUnmount(() => {
  window.removeEventListener('click', closeToolsMenuOnOutside);
  clearInterval(pollTimer);
  clearTimeout(reconnectTimer);
  if (hlsInstance) hlsInstance.destroy();
  if (wsInstance) wsInstance.close();
});
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background-color: #0d0d0d;
  color: #ededed;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  overflow: hidden;
}

.top-nav {
  height: 54px;
  border-bottom: 1px solid #222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #0c0c0c;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: #ffffff;
}

.sub-text {
  font-size: 12px;
  color: #666666;
}

.search-box {
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 440px;
}

.modal-combobox-wrap {
  margin: 10px 0;
  text-align: left;
}

.landing-page-shell {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.auth-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: nowrap;
}

.user-badge {
  height: 32px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  background: #181818;
  border: 1px solid #333333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-sizing: border-box;
  white-space: nowrap;
}

.nav-btn {
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

.nav-btn:hover {
  background: #222222;
  border-color: #666666;
  color: #ffffff;
}

.nav-btn.primary {
  background: #ffffff;
  border-color: #ffffff;
  color: #000000;
  font-weight: 700;
}

.nav-btn.primary:hover {
  background: #cccccc;
  border-color: #cccccc;
  color: #000000;
}

.main-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  border-right: 1px solid #222;
  background: #111;
  display: flex;
  flex-direction: column;
}

.nav-links {
  padding: 16px 0;
  border-bottom: 1px solid #222;
}

.nav-item {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  padding: 8px 20px;
  color: #777;
  font-size: 13px;
  cursor: pointer;
}

.nav-item.active,
.nav-item:hover {
  color: #fff;
  background: #161616;
}

.sidebar-section-title {
  display: flex;
  justify-content: space-between;
  padding: 12px 20px;
  font-size: 11px;
  color: #555;
  letter-spacing: 1px;
}

.stream-list {
  flex: 1;
  overflow-y: auto;
}

.stream-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  gap: 12px;
  cursor: pointer;
  border-left: 2px solid transparent;
}

.stream-item:hover,
.stream-item.active {
  background: #181818;
  border-left-color: #fff;
}

.avatar {
  width: 32px;
  height: 32px;
  background: #252525;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 12px;
  border: 1px solid #333;
}

.avatar.large {
  width: 48px;
  height: 48px;
  font-size: 18px;
}

.stream-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stream-meta .author {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stream-meta .category {
  font-size: 11px;
  color: #666;
}

.live-pill {
  font-size: 10px;
  color: #555;
}

.live-pill.is_live {
  color: #ffffff;
  font-weight: 800;
}

.player-stage {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #090909;
  overflow: auto;
}

.sidebar-empty {
  padding: 0 20px;
  color: #666;
  font-size: 11px;
}

.empty-page {
  margin: auto;
  padding: 32px;
  color: #888;
  text-align: center;
}

.directory-page {
  min-height: 100%;
  padding: 28px;
  overflow-y: auto;
}

.directory-page h1 {
  font-size: 18px;
  margin: 0 0 8px;
}

.directory-page > p {
  color: #888;
  font-size: 12px;
  margin-bottom: 24px;
}

.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.channel-card {
  min-height: 112px;
  padding: 16px;
  background: #121212;
  border: 1px solid #292929;
  color: #eee;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
}

.channel-card:hover {
  border-color: #777;
  background: #181818;
}

.profile-channel-card {
  cursor: default;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.profile-channel-card:hover {
  border-color: #555;
  background: #121212;
}

.channel-card-body {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.channel-card-body:hover strong {
  text-decoration: underline;
}

.channel-card-actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #222;
}

.channel-card span,
.channel-card small,
.profile-hint {
  color: #888;
  font-size: 11px;
}

.profile-panel {
  margin: 20px 0 28px;
  padding: 20px;
  background: #121212;
  border: 1px solid #292929;
}

.profile-panel h2,
.profile-page > h2 {
  font-size: 14px;
}

.profile-panel code {
  color: #ffffff;
  background: #000000;
  border: 1px solid #292929;
  word-break: break-all;
}

.stream-key-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.stream-key-row code {
  padding: 8px 10px;
  background: #090909;
  border: 1px solid #292929;
}

.video-container {
  flex: 1;
  position: relative;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-overlay {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 10;
}

.status-overlay .badge {
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid #333;
  padding: 4px 8px;
  font-size: 11px;
  color: #aaa;
}

.video-feed {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.offline-placeholder {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #444;
  font-weight: 700;
}

.broadcast-footer {
  padding: 16px 24px;
  border-top: 1px solid #222;
  background: #111;
  display: flex;
  align-items: center;
  gap: 18px;
}

.broadcast-footer .info {
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-row h2 {
  font-size: 16px;
  margin: 0;
}

.verified-tag {
  font-size: 11px;
  color: #888;
}

.broadcast-footer p {
  margin: 4px 0 8px;
  font-size: 12px;
  color: #777;
}

.tags {
  display: flex;
  gap: 6px;
}

.tag {
  font-size: 10px;
  background: #1c1c1c;
  border: 1px solid #292929;
  padding: 2px 6px;
  color: #aaa;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-btn {
  height: 32px;
  line-height: 30px;
  padding: 0 14px;
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

.action-btn.sm {
  height: 26px;
  line-height: 24px;
  padding: 0 10px;
  font-size: 10px;
}

.viewers {
  margin-left: 12px;
  display: flex;
  flex-direction: column;
}

.viewers .label {
  font-size: 9px;
  color: #555;
}

.viewers .value {
  font-size: 15px;
  font-weight: 800;
}

.chat-section {
  width: 320px;
  border-left: 1px solid #222;
  background: #111;
  display: flex;
  flex-direction: column;
}

.chat-header {
  height: 48px;
  border-bottom: 1px solid #222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 12px;
  font-weight: 700;
}

.chat-ai-toggle {
  height: 26px;
  line-height: 24px;
  padding: 0 10px;
  background: #181818;
  border: 1px solid #333333;
  color: #ffffff;
  font-family: inherit;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-ai-toggle:hover {
  background: #262626;
  border-color: #666666;
}

.ai-panel {
  padding: 12px;
  border-bottom: 1px solid #292929;
  color: #ddd;
  font-size: 11px;
}

.ai-panel p {
  color: #aaa;
  line-height: 1.5;
}

.ai-result {
  padding: 7px 0;
  color: #ffffff;
  cursor: pointer;
  text-decoration: underline;
}

.ai-input {
  display: flex;
  gap: 5px;
}

.ai-input input {
  min-width: 0;
  flex: 1;
  background: #181818;
  border: 1px solid #333;
  padding: 7px;
  color: #fff;
}

.ai-input button {
  background: #252525;
  color: white;
  border: 1px solid #333;
  cursor: pointer;
}

.sub-only {
  font-size: 10px;
  color: #666;
}

.chat-messages {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-msg {
  font-size: 12px;
  line-height: 1.4;
  word-break: break-word;
}

.chat-msg .time {
  color: #444;
  margin-right: 6px;
}

.author-tag {
  font-weight: 700;
  margin-right: 6px;
  color: #ffffff;
}

.author-tag.SYS {
  color: #777777;
}

.chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid #222;
  display: flex;
  gap: 8px;
}

.chat-input-area input {
  flex: 1;
  background: #181818;
  border: 1px solid #292929;
  padding: 8px 10px;
  color: #fff;
  font-size: 12px;
  outline: none;
}

.chat-input-area button {
  background: #252525;
  border: 1px solid #333;
  color: #fff;
  padding: 0 14px;
  cursor: pointer;
  font-weight: 700;
  font-size: 11px;
}

.app-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.app-modal {
  background: #141414;
  border: 1px solid #333;
  padding: 24px;
  width: 320px;
}

.app-modal h3 {
  margin-top: 0;
  font-size: 14px;
}

.app-modal form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.app-modal input {
  background: #090909;
  border: 1px solid #292929;
  padding: 8px;
  color: #fff;
  outline: none;
}

.app-modal textarea {
  min-height: 90px;
  resize: vertical;
  background: #090909;
  border: 1px solid #292929;
  padding: 8px;
  color: #fff;
  font: inherit;
}

.modal-err {
  color: #ffffff;
  background: #1c1c1c;
  border: 1px solid #444444;
  padding: 6px 10px;
  font-size: 11px;
}

.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* --- AI Assistant Modal --- */
.ai-modal-backdrop {
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.ai-assistant-modal {
  width: min(680px, 92vw);
  height: min(720px, 86vh);
  background: #111;
  border: 1px solid #333;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.95);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-assistant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: #161616;
  border-bottom: 1px solid #222;
}

.ai-header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-avatar-badge {
  font-size: 11px;
  font-weight: 800;
  color: #000;
  background: #fff;
  padding: 3px 6px;
  letter-spacing: 0.5px;
}

.ai-assistant-header h3 {
  margin: 0;
  font-size: 13px;
  letter-spacing: 1px;
  font-weight: 800;
  color: #fff;
}

.ai-status-badge {
  font-size: 10px;
  color: #777;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.ai-close-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
  transition: color 0.15s;
}
.ai-close-btn:hover {
  color: #fff;
}

.ai-quick-prompts {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #0d0d0d;
  border-bottom: 1px solid #1a1a1a;
  overflow-x: auto;
  white-space: nowrap;
}

.quick-chip {
  background: #141414;
  border: 1px solid #2a2a2a;
  color: #888;
  padding: 6px 12px;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.quick-chip:hover {
  background: #222;
  border-color: #666;
  color: #fff;
}

.ai-messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #0d0d0d;
}

.ai-chat-bubble-wrap {
  display: flex;
  gap: 10px;
  max-width: 90%;
}
.ai-chat-bubble-wrap.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.ai-chat-bubble-wrap.assistant {
  align-self: flex-start;
}

.ai-bubble-avatar {
  width: 28px;
  height: 28px;
  background: #1a1a1a;
  border: 1px solid #333;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  flex-shrink: 0;
}
.ai-chat-bubble-wrap.user .ai-bubble-avatar {
  background: #2a2a2a;
  border-color: #444;
}

.ai-bubble-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ai-chat-bubble-wrap.user .ai-bubble-content {
  align-items: flex-end;
}

.ai-bubble-author {
  font-size: 10px;
  color: #666;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.ai-bubble-text {
  background: #141414;
  border: 1px solid #262626;
  padding: 10px 14px;
  color: #ededed;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}
.ai-chat-bubble-wrap.user .ai-bubble-text {
  background: #202020;
  border-color: #444444;
  color: #ffffff;
}

.ai-rec-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-top: 10px;
  width: 100%;
}

.ai-rec-card {
  background: #141414;
  border: 1px solid #282828;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s;
}
.ai-rec-card:hover {
  border-color: #ffffff;
}

.rec-card-thumb {
  position: relative;
  height: 90px;
  background: #000;
}
.rec-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.rec-live-tag {
  position: absolute;
  top: 6px;
  left: 6px;
  font-size: 9px;
  font-weight: 800;
  padding: 2px 6px;
  background: #000;
  color: #888;
  border: 1px solid #333;
}
.rec-live-tag.live {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.rec-card-info {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rec-card-info h4 {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rec-card-info p {
  margin: 0;
  font-size: 10px;
  color: #888;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.3;
}
.rec-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 10px;
  color: #666;
}
.rec-watch-btn {
  background: #ffffff;
  border: 1px solid #ffffff;
  color: #000000;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  cursor: pointer;
}
.rec-watch-btn:hover {
  background: #cccccc;
  border-color: #cccccc;
}

.ai-typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: #181818;
  border: 1px solid #262626;
  width: fit-content;
}
.ai-typing-indicator span {
  width: 6px;
  height: 6px;
  background: #ffffff;
  border-radius: 50%;
  animation: typing-dots 1.4s infinite ease-in-out both;
}
.ai-typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.ai-typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes typing-dots {
  0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}

.ai-input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #141414;
  border-top: 1px solid #222;
}
.ai-input-bar input {
  flex: 1;
  background: #090909;
  border: 1px solid #292929;
  padding: 10px 14px;
  color: #fff;
  font-size: 12px;
  outline: none;
}
.ai-input-bar input:focus {
  border-color: #ffffff;
}

.directory-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
}
.pagination-status {
  display: flex;
  gap: 8px;
}
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
  padding: 16px;
  border-top: 1px solid #222;
}
.page-indicator {
  font-family: monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #fff;
}

/* --- C16 OAuth2 Styles --- */
.oauth-divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 18px 0 14px 0;
  color: #666666;
  font-size: 10px;
  font-family: monospace;
  letter-spacing: 0.05em;
}

.oauth-divider::before,
.oauth-divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid #262626;
}

.oauth-divider span {
  padding: 0 10px;
}

.oauth-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.oauth-action-btn {
  height: 34px;
  background: #111111;
  border: 1px solid #333333;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: all 0.15s ease;
}

.oauth-action-btn:hover:not(:disabled) {
  background: #222222;
  border-color: #ffffff;
}

.oauth-action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.oauth-tag {
  font-family: monospace;
  font-size: 10px;
  color: #888888;
}

/* B6 Premium Page & Gated Views */
.premium-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.premium-badges {
  display: flex;
  gap: 8px;
}

.vip-pill {
  font-family: monospace;
  font-size: 11px;
  padding: 4px 10px;
  border: 1px solid #333;
  background: #141414;
  color: #888;
}

.vip-pill.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
  font-weight: 700;
}

.vip-pill.tier {
  background: #1a1a1a;
  color: #ffffff;
  border-color: #555;
  font-weight: 700;
}

.vip-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.vip-card {
  background: #121212;
  border: 1px solid #282828;
  padding: 18px;
  display: flex;
  flex-direction: column;
}

.vip-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.vip-tag {
  font-family: monospace;
  font-size: 10px;
  color: #888;
  letter-spacing: 0.05em;
}

.vip-indicator.live {
  font-family: monospace;
  font-size: 10px;
  color: #ffffff;
  font-weight: 700;
  border: 1px solid #444;
  padding: 2px 6px;
  background: #181818;
}

.vip-card h3 {
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: #ffffff;
}

.vip-card p {
  font-size: 12px;
  color: #888888;
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.vip-metrics {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 11px;
  font-family: monospace;
  margin-top: auto;
  border-top: 1px solid #202020;
  padding-top: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-item span {
  color: #666;
  font-size: 10px;
}

.metric-item code {
  color: #ffffff;
  background: #0a0a0a;
  padding: 2px 4px;
  border: 1px solid #222;
  font-size: 10px;
  word-break: break-all;
}

.vip-controls-panel {
  background: #101010;
  border: 1px solid #262626;
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.vip-controls-panel .panel-head h3 {
  font-size: 13px;
  margin: 0 0 6px 0;
  color: #ffffff;
}

.vip-controls-panel .panel-head p {
  font-size: 12px;
  margin: 0;
  color: #888888;
  max-width: 600px;
}

.vip-controls-panel .panel-actions {
  display: flex;
  gap: 10px;
}

/* Gated box styling */
.premium-gated-box {
  background: #101010;
  border: 1px solid #333333;
  padding: 32px;
  text-align: center;
  max-width: 840px;
  margin: 30px auto;
}

.gate-lock-badge {
  font-family: monospace;
  font-size: 11px;
  color: #888;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.premium-gated-box h2 {
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 12px 0;
  letter-spacing: 0.05em;
  color: #ffffff;
}

.premium-gated-box p {
  font-size: 13px;
  color: #888888;
  max-width: 640px;
  margin: 0 auto 28px auto;
  line-height: 1.5;
}

.gated-plans-preview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 28px;
  text-align: left;
}

.gate-tier-card {
  background: #141414;
  border: 1px solid #282828;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.gate-tier-card.unlock-card {
  border-color: #ffffff;
  background: #181818;
}

.gate-tier-card h4 {
  font-size: 12px;
  font-weight: 700;
  margin: 0 0 4px 0;
  color: #ffffff;
}

.tier-state {
  font-family: monospace;
  font-size: 10px;
  color: #666;
  margin-bottom: 8px;
}

.tier-state.highlight {
  color: #ffffff;
  font-weight: 700;
}

.gate-tier-card p {
  font-size: 11px;
  color: #888;
  margin: 0 0 14px 0;
  text-align: left;
}

.gate-tier-card .action-btn {
  margin-top: auto;
  width: 100%;
}

.gate-footer-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* C21 AI Workflow & Tool Calling Styles */
.ai-workflow-box {
  background: #0d0d0d;
  border: 1px solid #222222;
  margin-bottom: 12px;
  font-family: monospace;
  font-size: 11px;
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: #141414;
  border-bottom: 1px solid #202020;
  cursor: pointer;
  user-select: none;
}

.workflow-title {
  color: #888888;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.04em;
}

.workflow-toggle {
  color: #aaaaaa;
  font-size: 10px;
}

.workflow-body {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.35;
}

.workflow-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border: 1px solid #333333;
  background: #1a1a1a;
  color: #888888;
  flex-shrink: 0;
}

.workflow-item.thinking .workflow-badge {
  color: #ffffff;
  border-color: #555555;
}

.workflow-item.tool_call .workflow-badge {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.workflow-item.tool_result .workflow-badge {
  color: #cccccc;
}

.workflow-thought {
  color: #999999;
}

.workflow-tool code,
.workflow-res code {
  color: #ffffff;
  background: #080808;
  padding: 1px 4px;
  border: 1px solid #1c1c1c;
  word-break: break-all;
}

/* Tools Dropdown Menu [ = ] */
.tools-menu-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.menu-btn {
  font-family: monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 0 12px;
}

.menu-btn.active {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.tools-dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 290px;
  background: #0e0e0e;
  border: 1px solid #333333;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.95);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  padding: 6px;
  gap: 8px;
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-bottom: 1px solid #202020;
  font-family: monospace;
}

.dropdown-title {
  font-size: 11px;
  font-weight: 700;
  color: #888888;
  letter-spacing: 0.05em;
}

.dropdown-count {
  font-size: 10px;
  color: #ffffff;
  background: #1c1c1c;
  padding: 2px 6px;
  border: 1px solid #333;
}

.dropdown-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-title {
  font-family: monospace;
  font-size: 9px;
  font-weight: 700;
  color: #555555;
  letter-spacing: 0.06em;
  padding: 4px 8px 2px 8px;
}

.dropdown-item {
  width: 100%;
  height: 32px;
  background: #141414;
  border: 1px solid transparent;
  color: #cccccc;
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  cursor: pointer;
  text-align: left;
  transition: all 0.12s ease;
}

.dropdown-item:hover {
  background: #ffffff;
  color: #000000;
  border-color: #ffffff;
}

.item-tag {
  font-size: 9px;
  color: #777777;
  font-weight: 700;
}

.dropdown-item:hover .item-tag {
  color: #000000;
}

.item-name {
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>