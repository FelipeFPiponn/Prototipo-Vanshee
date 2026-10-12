// ==========================================================================
// VANSHEE - Modern AI Chatbot Client Controller (Fin / Intercom Style)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  const state = {
    isChatOpen: true,
    isPinned: false,
    ttsEnabled: true,
    wakeWordEnabled: true,
    autostartEnabled: false,
    selectedDeviceIndex: null,
    selectedVoiceId: 'es-ES-ElviraNeural',
    allApps: [],
    websocket: null,
    isListeningVoice: false,
  };

  // DOM Elements - Launcher & Chat Container
  const floatingLauncherBtn = document.getElementById('floatingLauncherBtn');
  const chatbotContainer = document.getElementById('chatbotContainer');
  const btnCollapseChat = document.getElementById('btnCollapseChat');
  const btnCloseChat = document.getElementById('btnCloseChat');
  const btnPinWindow = document.getElementById('btnPinWindow');
  const pinIcon = document.getElementById('pinIcon');
  const launcherBadge = document.getElementById('launcherBadge');
  const wakeStatusText = document.getElementById('wakeStatusText');

  // Chat DOM
  const chatMessages = document.getElementById('chatMessages');
  const chatBody = document.getElementById('chatBody');
  const userPromptInput = document.getElementById('userPromptInput');
  const btnSendPrompt = document.getElementById('btnSendPrompt');
  const btnVoiceToggle = document.getElementById('btnVoiceToggle');
  const btnToggleChips = document.getElementById('btnToggleChips');
  const quickChipsTray = document.getElementById('quickChipsTray');
  const voiceListeningBanner = document.getElementById('voiceListeningBanner');
  const welcomeCard = document.getElementById('welcomeCard');

  // Drawers DOM
  const btnOpenSettings = document.getElementById('btnOpenSettings');
  const btnCloseSettings = document.getElementById('btnCloseSettings');
  const settingsDrawer = document.getElementById('settingsDrawer');

  const btnOpenApps = document.getElementById('btnOpenApps');
  const btnCloseApps = document.getElementById('btnCloseApps');
  const appsDrawer = document.getElementById('appsDrawer');
  const simpleAppsList = document.getElementById('simpleAppsList');
  const appSearchInput = document.getElementById('appSearchInput');

  // Settings Controls DOM
  const micSelect = document.getElementById('micSelect');
  const btnTestMic = document.getElementById('btnTestMic');
  const micMeterFill = document.getElementById('micMeterFill');
  const micMeterText = document.getElementById('micMeterText');
  const micPlaybackWrap = document.getElementById('micPlaybackWrap');
  const micQualityBadge = document.getElementById('micQualityBadge');
  const micAudioPlayer = document.getElementById('micAudioPlayer');
  const micAdviceBox = document.getElementById('micAdviceBox');
  const btnApplyRecommended = document.getElementById('btnApplyRecommended');
  const thresholdSlider = document.getElementById('thresholdSlider');
  const thresholdDisplay = document.getElementById('thresholdDisplay');
  const voiceSelect = document.getElementById('voiceSelect');
  const btnTestVoice = document.getElementById('btnTestVoice');
  const ttsToggle = document.getElementById('ttsToggle');
  const wakeWordToggle = document.getElementById('wakeWordToggle');
  const autostartToggle = document.getElementById('autostartToggle');
  const toastBox = document.getElementById('toastBox');

  // Toast Helper
  function showToast(message) {
    if (!toastBox) return;
    toastBox.textContent = message;
    toastBox.style.display = 'block';
    setTimeout(() => {
      toastBox.style.display = 'none';
    }, 3200);
  }

  // ==========================================================================
  // Window Visibility Controls (Minimize / Close)
  // ==========================================================================
  if (btnCollapseChat) {
    btnCollapseChat.addEventListener('click', async () => {
      try {
        await fetch('/api/window/hide_chat', { method: 'POST' });
      } catch (e) {
        console.warn('Error hiding chat:', e);
      }
    });
  }

  if (btnCloseChat) {
    btnCloseChat.addEventListener('click', async () => {
      showToast('Cerrando Vanshee por completo...');
      if (chatbotContainer) chatbotContainer.style.opacity = '0';
      try {
        await fetch('/api/system/shutdown', { method: 'POST' });
      } catch (e) {}
      setTimeout(() => {
        try { window.close(); } catch (e) {}
      }, 250);
    });
  }

  // ==========================================================================
  // Always-On-Top Pin Toggle (Superpuesto a otras aplicaciones en Windows)
  // ==========================================================================
  if (btnPinWindow) {
    btnPinWindow.addEventListener('click', async () => {
      state.isPinned = !state.isPinned;
      try {
        const resp = await fetch('/api/window/pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topmost: state.isPinned })
        });
        const res = await resp.json();
        if (state.isPinned) {
          btnPinWindow.classList.add('active-pinned');
          showToast('📌 Chat fijado: siempre visible sobre otras aplicaciones');
        } else {
          btnPinWindow.classList.remove('active-pinned');
          showToast('📌 Modo superpuesto desactivado');
        }
      } catch (err) {
        console.warn('Pin window API error:', err);
      }
    });
  }

  // ==========================================================================
  // Status Indicator
  // ==========================================================================
  function updateStatus(status, text, isListening = false) {
    state.isListeningVoice = isListening;
    if (wakeStatusText) {
      wakeStatusText.textContent = text;
      if (isListening) {
        wakeStatusText.style.color = '#fb7185';
      } else {
        wakeStatusText.style.color = '#34d399';
      }
    }
    if (launcherBadge) {
      launcherBadge.textContent = isListening ? '🎙️ Escuchando' : 'Online';
      launcherBadge.style.background = isListening ? 'var(--danger)' : 'var(--success)';
    }
    if (voiceListeningBanner) {
      voiceListeningBanner.style.display = isListening ? 'flex' : 'none';
      if (isListening && chatBody) {
        chatBody.scrollTop = chatBody.scrollHeight;
      }
    }
  }

  // ==========================================================================
  // Messages Stream (Intercom / Fin Style)
  // ==========================================================================
  function appendMessage(sender, text, actionSummary = null) {
    if (!chatMessages) return;

    // Ocultar tarjeta de bienvenida una vez que empieza el chat
    if (welcomeCard) welcomeCard.style.display = 'none';

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${sender === 'user' ? 'user-msg' : 'bot-msg'}`;

    let html = '';
    if (sender !== 'user') {
      html += `<div class="msg-avatar">⚡</div>`;
    }

    html += `<div class="msg-content-wrap">
      <div class="msg-bubble">${escapeHtml(text)}</div>`;

    if (actionSummary && actionSummary !== 'sin_acciones' && actionSummary !== 'sin_plan') {
      html += `<div class="action-pill-tag">⚡ ${escapeHtml(actionSummary)}</div>`;
    }

    html += `<span class="msg-meta">${sender === 'user' ? 'Tú' : 'Vanshee · AI Agent'} · ${timeStr}</span>
    </div>`;

    msgDiv.innerHTML = html;
    chatMessages.appendChild(msgDiv);

    if (chatBody) {
      chatBody.scrollTop = chatBody.scrollHeight;
    }
  }

  function escapeHtml(unsafe) {
    return (unsafe || '')
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ==========================================================================
  // Execute Command via Natural Language
  // ==========================================================================
  async function executeCommand(prompt) {
    const clean = prompt.trim();
    if (!clean) return;

    // Asegurar que el chat esté desplegado
    setChatOpen(true);

    appendMessage('user', clean);
    if (userPromptInput) {
      userPromptInput.value = '';
      userPromptInput.style.height = 'auto';
    }

    updateStatus('thinking', 'Vanshee pensando...', false);

    try {
      const resp = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: clean,
          speak_tts: state.ttsEnabled
        })
      });

      const data = await resp.json();
      if (data.plan_summary !== 'omitido_duplicado') {
        appendMessage('assistant', data.response_text || 'Instrucción ejecutada.', data.plan_summary);
      }
      updateStatus('idle', '● Escuchando tu voz', false);
    } catch (err) {
      appendMessage('assistant', 'Hubo un error al procesar tu instrucción.');
      updateStatus('idle', '● Escuchando tu voz', false);
    }
  }

  // Enviar mensaje con botón o Enter
  if (btnSendPrompt && userPromptInput) {
    btnSendPrompt.addEventListener('click', () => {
      executeCommand(userPromptInput.value);
    });

    userPromptInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        executeCommand(userPromptInput.value);
      }
    });

    // Auto-ajuste de altura de textarea
    userPromptInput.addEventListener('input', () => {
      userPromptInput.style.height = 'auto';
      userPromptInput.style.height = Math.min(userPromptInput.scrollHeight, 90) + 'px';
    });
  }

  // Manual Voice Listen Trigger
  if (btnVoiceToggle) {
    btnVoiceToggle.addEventListener('click', async () => {
      try {
        btnVoiceToggle.classList.add('listening');
        updateStatus('listening', '¡Vanshee te escucha!', true);
        await fetch('/api/audio/wake_trigger', { method: 'POST' });
        setTimeout(() => {
          btnVoiceToggle.classList.remove('listening');
        }, 3000);
      } catch (err) {
        console.warn('Wake trigger error:', err);
      }
    });
  }

  // Quick Chips Buttons
  document.querySelectorAll('.chip-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const prompt = btn.dataset.prompt;
      if (prompt) executeCommand(prompt);
    });
  });

  if (btnToggleChips && quickChipsTray) {
    btnToggleChips.addEventListener('click', () => {
      quickChipsTray.style.display = (quickChipsTray.style.display === 'none') ? 'flex' : 'none';
    });
  }

  // ==========================================================================
  // Drawers Toggle (Settings & Apps)
  // ==========================================================================
  if (btnOpenSettings && settingsDrawer) {
    btnOpenSettings.addEventListener('click', () => settingsDrawer.classList.add('open'));
  }
  if (btnCloseSettings && settingsDrawer) {
    btnCloseSettings.addEventListener('click', () => settingsDrawer.classList.remove('open'));
  }

  if (btnOpenApps && appsDrawer) {
    btnOpenApps.addEventListener('click', () => {
      appsDrawer.classList.add('open');
      loadAppsList();
    });
  }
  if (btnCloseApps && appsDrawer) {
    btnCloseApps.addEventListener('click', () => appsDrawer.classList.remove('open'));
  }

  // ==========================================================================
  // WebSocket Live Sync for Background Wake Word
  // ==========================================================================
  function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/live`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'wake_word_command') {
            setChatOpen(true);
            updateStatus('thinking', `Ejecutando: "${msg.data.command}"`, false);
            appendMessage('user', msg.data.phrase);
          } else if (msg.type === 'wake_word_listening') {
            setChatOpen(true);
            updateStatus('listening', '¡Vanshee te escucha!', true);
          } else if (msg.type === 'command_completed') {
            if (msg.data.source === 'wake_word') {
              appendMessage('assistant', msg.data.response_text, msg.data.plan_summary);
            }
            updateStatus('idle', '● Escuchando tu voz', false);
          }
        } catch (e) {}
      };
      ws.onclose = () => {
        setTimeout(connectWebSocket, 3000);
      };
      state.websocket = ws;
    } catch (e) {
      console.warn('WebSocket connection error:', e);
    }
  }

  // ==========================================================================
  // Load Audio Devices & Voices
  // ==========================================================================
  async function loadAudioDevices() {
    if (!micSelect) return;
    try {
      const resp = await fetch('/api/audio/devices');
      const data = await resp.json();
      micSelect.innerHTML = '';
      (data.devices || []).forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.index;
        opt.textContent = `${d.name} ${d.is_default ? '(Predeterminado)' : ''}`;
        if (d.is_selected) opt.selected = true;
        micSelect.appendChild(opt);
      });
    } catch (err) {}
  }

  if (micSelect) {
    micSelect.addEventListener('change', async () => {
      const idx = parseInt(micSelect.value, 10);
      const selOpt = micSelect.options[micSelect.selectedIndex];
      await fetch('/api/audio/devices/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_index: idx, device_name: selOpt ? selOpt.textContent : '' })
      });
      showToast('Micrófono actualizado.');
    });
  }

  // Mic 3s Recording Test with Audio Player
  if (btnTestMic) {
    btnTestMic.addEventListener('click', async () => {
      btnTestMic.disabled = true;
      btnTestMic.textContent = '🔴 Grabando tu voz (3s)... Habla ahora';
      if (micMeterText) micMeterText.textContent = 'Grabando...';
      if (micMeterFill) micMeterFill.style.width = '60%';
      if (micPlaybackWrap) micPlaybackWrap.style.display = 'none';

      try {
        const devIdx = micSelect ? micSelect.value : null;
        const resp = await fetch('/api/audio/mic_record_test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_index: devIdx ? parseInt(devIdx, 10) : null,
            duration_seconds: 3.0
          })
        });
        const data = await resp.json();
        btnTestMic.disabled = false;
        btnTestMic.textContent = '🎙️ Realizar Otra Prueba de Audio';

        if (data.status === 'ok') {
          if (micMeterFill) micMeterFill.style.width = Math.min(data.volume_rms * 1.5, 100) + '%';
          if (micMeterText) micMeterText.textContent = `Volumen: ${data.volume_rms} RMS (${data.quality_verdict})`;
          if (micPlaybackWrap && micAudioPlayer) {
            micPlaybackWrap.style.display = 'block';
            micAudioPlayer.src = data.audio_url;
            micAudioPlayer.play().catch(() => {});
          }
          if (micQualityBadge) {
            micQualityBadge.textContent = data.quality_verdict;
            micQualityBadge.className = data.quality_verdict.includes('Óptimo') || data.quality_verdict.includes('Excelente') ? 'badge-optimal' : 'badge-optimal';
          }
          if (micAdviceBox) micAdviceBox.textContent = data.advice;
          if (btnApplyRecommended) {
            btnApplyRecommended.onclick = async () => {
              if (thresholdSlider) thresholdSlider.value = data.recommended_threshold;
              if (thresholdDisplay) thresholdDisplay.textContent = `${data.recommended_threshold} RMS`;
              await saveThresholdSetting(data.recommended_threshold);
              showToast(`Sensibilidad aplicada: ${data.recommended_threshold} RMS`);
            };
          }
        }
      } catch (err) {
        btnTestMic.disabled = false;
        btnTestMic.textContent = '🎙️ Iniciar Prueba de Grabación (3s)';
      }
    });
  }

  async function saveThresholdSetting(val) {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          speak_tts: state.ttsEnabled,
          threshold_rms: val
        })
      });
    } catch (e) {}
  }

  if (thresholdSlider) {
    thresholdSlider.addEventListener('input', () => {
      if (thresholdDisplay) thresholdDisplay.textContent = `${thresholdSlider.value} RMS`;
    });
    thresholdSlider.addEventListener('change', () => {
      saveThresholdSetting(parseFloat(thresholdSlider.value));
    });
  }

  // Voice Test
  if (btnTestVoice && voiceSelect) {
    btnTestVoice.addEventListener('click', async () => {
      const v = voiceSelect.value;
      const formData = new FormData();
      formData.append('text', 'Hola, soy Vanshee. Tu asistente de Windows configurada y lista.');
      formData.append('voice_id', v);
      await fetch('/api/audio/tts', { method: 'POST', body: formData });
    });
  }

  // Toggles
  if (ttsToggle) {
    ttsToggle.addEventListener('change', () => {
      state.ttsEnabled = ttsToggle.checked;
      saveThresholdSetting(thresholdSlider ? parseFloat(thresholdSlider.value) : 100);
      showToast(state.ttsEnabled ? 'Voz hablada activada.' : 'Voz hablada silenciada.');
    });
  }
  if (wakeWordToggle) {
    wakeWordToggle.addEventListener('change', async () => {
      state.wakeWordEnabled = wakeWordToggle.checked;
      await fetch('/api/settings/wakeword', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: state.wakeWordEnabled })
      });
      showToast(state.wakeWordEnabled ? 'Activación por voz activada.' : 'Activación por voz desactivada.');
    });
  }
  if (autostartToggle) {
    autostartToggle.addEventListener('change', async () => {
      state.autostartEnabled = autostartToggle.checked;
      await fetch('/api/settings/autostart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: state.autostartEnabled })
      });
      showToast(state.autostartEnabled ? 'Inicio con Windows activado.' : 'Inicio con Windows desactivado.');
    });
  }

  // Load Indexed Apps
  async function loadAppsList() {
    if (!simpleAppsList) return;
    try {
      const resp = await fetch('/api/apps');
      const data = await resp.json();
      state.allApps = data.apps || [];
      renderApps(state.allApps);
    } catch (e) {}
  }

  function renderApps(apps) {
    if (!simpleAppsList) return;
    simpleAppsList.innerHTML = '';
    apps.slice(0, 50).forEach(app => {
      const card = document.createElement('div');
      card.className = 'app-compact-card';
      card.innerHTML = `
        <div class="app-compact-info">
          <span class="app-compact-name">${escapeHtml(app.name)}</span>
          <span class="app-compact-type">${escapeHtml(app.type || 'app')}</span>
        </div>
        <span style="color: var(--primary); font-size: 14px;">▶</span>
      `;
      card.addEventListener('click', () => {
        executeCommand(`Abre ${app.name}`);
        if (appsDrawer) appsDrawer.classList.remove('open');
      });
      simpleAppsList.appendChild(card);
    });
  }

  if (appSearchInput) {
    appSearchInput.addEventListener('input', () => {
      const q = appSearchInput.value.toLowerCase().trim();
      const filtered = state.allApps.filter(a => a.name.toLowerCase().includes(q));
      renderApps(filtered);
    });
  }

  // Load Initial Status
  async function initStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (thresholdSlider) thresholdSlider.value = data.threshold_rms || 100;
      if (thresholdDisplay) thresholdDisplay.textContent = `${data.threshold_rms || 100} RMS`;
      if (voiceSelect && data.selected_voice) voiceSelect.value = data.selected_voice;
      if (wakeWordToggle) wakeWordToggle.checked = data.wakeword_enabled !== false;
      if (autostartToggle) autostartToggle.checked = !!data.autostart_enabled;
      if (ttsToggle) ttsToggle.checked = data.speak_tts_enabled !== false;
      state.ttsEnabled = data.speak_tts_enabled !== false;
    } catch (e) {}
  }

  // Initialize
  loadAudioDevices();
  initStatus();
  connectWebSocket();
});
