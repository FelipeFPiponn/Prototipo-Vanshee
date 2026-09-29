// BANSHEE - Minimalist Assistant Client Logic
document.addEventListener('DOMContentLoaded', () => {
  const state = {
    ttsEnabled: true,
    wakeWordEnabled: true,
    autostartEnabled: false,
    selectedDeviceIndex: null,
    selectedVoiceId: 'es-ES-ElviraNeural',
    allApps: [],
    activeTab: 'tab-chat',
    websocket: null,
  };

  // DOM Elements
  const chatMessages = document.getElementById('chatMessages');
  const userPromptInput = document.getElementById('userPromptInput');
  const btnSendPrompt = document.getElementById('btnSendPrompt');
  const btnVoiceToggle = document.getElementById('btnVoiceToggle');
  const assistantOrb = document.getElementById('assistantOrb');
  const wakeStatusPill = document.getElementById('wakeStatusPill');
  const wakeStatusText = document.getElementById('wakeStatusText');

  // Settings DOM
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

  // Apps DOM
  const simpleAppsList = document.getElementById('simpleAppsList');
  const appSearchInput = document.getElementById('appSearchInput');
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

  // Update Status Pill UI
  function updateStatus(status, text, isListening = false) {
    if (!wakeStatusPill || !wakeStatusText) return;
    wakeStatusText.textContent = text;
    if (isListening) {
      wakeStatusPill.classList.add('listening');
    } else {
      wakeStatusPill.classList.remove('listening');
    }
  }

  // Append Message to Chat
  function appendMessage(sender, text, actionSummary = null) {
    if (!chatMessages) return;
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    let html = `<div>${text}</div>`;
    if (actionSummary && actionSummary !== 'sin_acciones') {
      html += `<div class="chat-action-tag">⚡ ${actionSummary}</div>`;
    }
    bubble.innerHTML = html;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Execute Command via Natural Language
  // Execute Command via Natural Language
  async function executeCommand(prompt) {
    const clean = prompt.trim();
    if (!clean) return;

    appendMessage('user', clean);
    if (userPromptInput) userPromptInput.value = '';

    updateStatus('thinking', 'Banshee está pensando...', false);

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
        appendMessage('assistant', data.response_text || 'Comando procesado.', data.plan_summary);
      }
      updateStatus('idle', 'Escuchando "Banshee"...', false);
    } catch (err) {
      appendMessage('assistant', 'Hubo un error al procesar tu instrucción.');
      updateStatus('idle', 'Escuchando "Banshee"...', false);
    }
  }

  // Connect WebSocket for Background Wake Word from Python
  function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/live`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'wake_word_command') {
            updateStatus('thinking', `Banshee ejecutando: "${msg.data.command}"`, false);
            appendMessage('user', msg.data.phrase);
          } else if (msg.type === 'wake_word_listening') {
            updateStatus('listening', '¡Banshee te escucha!', true);
            appendMessage('assistant', '¿Dime? Te escucho...');
          } else if (msg.type === 'command_completed') {
            // Solo agregar mensaje si provino de detección de voz en segundo plano (para no duplicar con fetch)
            if (msg.data.source === 'wake_word') {
              appendMessage('assistant', msg.data.response_text, msg.data.plan_summary);
            }
            updateStatus('idle', 'Escuchando "Banshee"...', false);
          }
        } catch (e) {}
      };
      state.websocket = ws;
    } catch (e) {
      console.warn('WebSocket connection error:', e);
    }
  }

  // Load Audio Devices
  async function loadAudioDevices() {
    if (!micSelect) return;
    try {
      const resp = await fetch('/api/audio/devices');
      const data = await resp.json();

      micSelect.innerHTML = '';
      if (!data.devices || data.devices.length === 0) {
        micSelect.innerHTML = '<option value="">No se encontraron micrófonos</option>';
        return;
      }

      data.devices.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.index;
        opt.textContent = `${d.name} ${d.is_default ? '(Predeterminado de Windows)' : ''}`;
        if (d.is_selected) {
          opt.selected = true;
          state.selectedDeviceIndex = d.index;
        }
        micSelect.appendChild(opt);
      });
    } catch (e) {
      micSelect.innerHTML = '<option value="">Error cargando micrófonos</option>';
    }
  }

  // Load Natural Voices
  async function loadVoices() {
    if (!voiceSelect) return;
    try {
      const resp = await fetch('/api/audio/voices');
      const data = await resp.json();

      if (data.voices && data.voices.length > 0) {
        voiceSelect.innerHTML = '';
        data.voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.id;
          opt.textContent = v.name;
          if (v.id === data.current_voice) {
            opt.selected = true;
            state.selectedVoiceId = v.id;
          }
          voiceSelect.appendChild(opt);
        });
      }
    } catch (e) {}
  }

  // Load Autostart Setting
  async function loadAutostart() {
    if (!autostartToggle) return;
    try {
      const resp = await fetch('/api/settings/autostart');
      const data = await resp.json();
      autostartToggle.checked = data.enabled;
      state.autostartEnabled = data.enabled;
    } catch (e) {}
  }

  // Load Apps for Simple Launcher
  async function loadApps(query = '') {
    if (!simpleAppsList) return;
    try {
      const resp = await fetch(`/api/apps?query=${encodeURIComponent(query)}`);
      const data = await resp.json();
      state.allApps = data.apps || [];
      renderSimpleApps(state.allApps);
    } catch (e) {
      simpleAppsList.innerHTML = '<p style="color: var(--text-muted);">Error cargando aplicaciones.</p>';
    }
  }

  function renderSimpleApps(apps) {
    if (!simpleAppsList) return;
    if (apps.length === 0) {
      simpleAppsList.innerHTML = '<p style="color: var(--text-muted); padding: 10px;">No se encontraron aplicaciones.</p>';
      return;
    }

    simpleAppsList.innerHTML = apps.map(app => `
      <div class="simple-app-card" data-target="${app.target}">
        <strong title="${app.name}">${app.name}</strong>
        <button class="btn-open-app">Abrir</button>
      </div>
    `).join('');

    simpleAppsList.querySelectorAll('.simple-app-card').forEach(card => {
      card.addEventListener('click', async () => {
        const target = card.getAttribute('data-target');
        showToast(`Abriendo ${target}...`);
        await fetch('/api/apps/launch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target })
        });
      });
    });
  }

  // Test Microphone Level with 3-Second Recording and Playback
  let recommendedRms = null;

  async function testMicrophoneLevel() {
    if (!btnTestMic) return;
    btnTestMic.disabled = true;
    let secondsLeft = 3;
    btnTestMic.innerHTML = `🔴 Grabando... Habla ahora (${secondsLeft}s)`;
    if (micMeterText) {
      micMeterText.textContent = 'Grabando voz (3s)...';
      micMeterText.style.color = 'var(--warning)';
    }

    const timer = setInterval(() => {
      secondsLeft--;
      if (secondsLeft > 0) {
        btnTestMic.innerHTML = `🔴 Grabando... Habla ahora (${secondsLeft}s)`;
      } else {
        btnTestMic.innerHTML = '⚙️ Analizando y preparando audio...';
      }
    }, 1000);

    const selectedDev = micSelect ? micSelect.value : null;

    try {
      const body = new URLSearchParams();
      body.append('duration', '3.0');
      if (selectedDev !== null && selectedDev !== '') {
        body.append('device_index', selectedDev);
      }

      const resp = await fetch('/api/audio/test_mic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString()
      });
      clearInterval(timer);
      const data = await resp.json();

      btnTestMic.disabled = false;
      btnTestMic.innerHTML = '🎙️ Realizar Otra Prueba de Audio (3s)';

      if (micMeterFill) micMeterFill.style.width = `${data.level_percent}%`;
      if (micMeterText) {
        micMeterText.textContent = `${data.rms} RMS`;
        micMeterText.style.color = data.rms >= 75 ? 'var(--success)' : (data.rms >= 40 ? 'var(--warning)' : 'var(--danger)');
      }

      // Mostrar reproductor y diagnóstico
      if (micPlaybackWrap) {
        micPlaybackWrap.style.display = 'flex';
      }
      if (micAudioPlayer && data.audio_url) {
        micAudioPlayer.src = data.audio_url;
        // Reproducir automáticamente para que el usuario escuche de inmediato cómo suena su micrófono
        try {
          await micAudioPlayer.play();
        } catch (e) {
          console.log('Autoplay bloqueado por el navegador, el usuario puede dar play manual.');
        }
      }
      if (micQualityBadge) {
        micQualityBadge.textContent = data.status;
        micQualityBadge.style.color = data.rms >= 75 ? 'var(--success)' : (data.rms >= 40 ? 'var(--warning)' : 'var(--danger)');
        micQualityBadge.style.background = data.rms >= 75 ? 'rgba(34, 197, 94, 0.15)' : 'rgba(234, 179, 8, 0.15)';
      }
      if (micAdviceBox) {
        micAdviceBox.textContent = `💡 Diagnóstico: ${data.advice}`;
      }

      recommendedRms = data.recommended_threshold;
      if (btnApplyRecommended && recommendedRms) {
        btnApplyRecommended.style.display = 'block';
        btnApplyRecommended.textContent = `⚡ Aplicar Sensibilidad Recomendada (${recommendedRms} RMS)`;
      }

      showToast(`Prueba completada: ${data.rms} RMS. Reproduciendo audio...`);
    } catch (e) {
      clearInterval(timer);
      btnTestMic.disabled = false;
      btnTestMic.innerHTML = '🎙️ Iniciar Prueba de Grabación y Audio (3s)';
      showToast('Error en prueba de micrófono.');
    }
  }

  // Event Listeners
  if (btnSendPrompt && userPromptInput) {
    btnSendPrompt.addEventListener('click', () => executeCommand(userPromptInput.value));
    userPromptInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') executeCommand(userPromptInput.value);
    });
  }

  // Manual Wake Trigger (Mic Button or Orb)
  async function triggerManualWake() {
    updateStatus('listening', '¡Banshee te escucha!', true);
    showToast('Banshee te escucha. Habla tu orden ahora...');
    try {
      await fetch('/api/audio/wake_trigger', { method: 'POST' });
    } catch (e) {}
  }

  if (btnVoiceToggle) {
    btnVoiceToggle.addEventListener('click', triggerManualWake);
  }

  if (assistantOrb) {
    assistantOrb.addEventListener('click', triggerManualWake);
  }

  // Quick Action Chips
  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = btn.getAttribute('data-prompt') || btn.textContent.trim();
      executeCommand(p);
    });
  });

  // Tab Navigation
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => {
      document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      link.classList.add('active');
      const tabId = link.getAttribute('data-tab');
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.classList.add('active');
      state.activeTab = tabId;

      if (tabId === 'tab-settings') {
        loadAudioDevices();
        loadVoices();
        loadAutostart();
      } else if (tabId === 'tab-apps') {
        loadApps();
      }
    });
  });

  // Settings Change Handlers
  if (micSelect) {
    micSelect.addEventListener('change', async (e) => {
      const idx = e.target.value !== '' ? parseInt(e.target.value) : null;
      const optName = e.target.options[e.target.selectedIndex]?.text || '';
      await fetch('/api/audio/devices/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_index: idx, device_name: optName })
      });
      showToast(`Micrófono configurado: ${optName}`);
    });
  }

  if (btnTestMic) {
    btnTestMic.addEventListener('click', testMicrophoneLevel);
  }

  if (btnApplyRecommended) {
    btnApplyRecommended.addEventListener('click', async () => {
      if (!recommendedRms) return;
      if (thresholdSlider) thresholdSlider.value = recommendedRms;
      if (thresholdDisplay) thresholdDisplay.textContent = `${recommendedRms} RMS`;
      await fetch('/api/settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          speak_tts: state.ttsEnabled,
          threshold_rms: recommendedRms
        })
      });
      showToast(`Sensibilidad recomendada guardada: ${recommendedRms} RMS`);
      btnApplyRecommended.style.display = 'none';
    });
  }

  if (thresholdSlider) {
    thresholdSlider.addEventListener('input', (e) => {
      if (thresholdDisplay) thresholdDisplay.textContent = `${e.target.value} RMS`;
    });
    thresholdSlider.addEventListener('change', async (e) => {
      const val = parseFloat(e.target.value);
      await fetch('/api/settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          speak_tts: state.ttsEnabled,
          threshold_rms: val
        })
      });
      showToast(`Sensibilidad guardada: ${val} RMS`);
    });
  }

  if (voiceSelect) {
    voiceSelect.addEventListener('change', async (e) => {
      const vId = e.target.value;
      state.selectedVoiceId = vId;
      await fetch('/api/audio/voices/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_id: vId })
      });
      showToast('Voz de Banshee actualizada.');
    });
  }

  if (btnTestVoice) {
    btnTestVoice.addEventListener('click', async () => {
      btnTestVoice.disabled = true;
      btnTestVoice.innerHTML = '🗣️ Hablando...';
      const vId = voiceSelect ? voiceSelect.value : state.selectedVoiceId;
      await fetch('/api/audio/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `text=${encodeURIComponent('Hola, soy Banshee. Esta es mi voz natural.')}&voice_id=${encodeURIComponent(vId)}`
      });
      btnTestVoice.disabled = false;
      btnTestVoice.innerHTML = '▶ Escuchar Voz de Prueba';
    });
  }

  if (ttsToggle) {
    ttsToggle.addEventListener('change', async (e) => {
      state.ttsEnabled = e.target.checked;
      await fetch('/api/settings/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          speak_tts: state.ttsEnabled,
          threshold_rms: thresholdSlider ? parseFloat(thresholdSlider.value) : 180.0
        })
      });
      showToast(state.ttsEnabled ? 'Voz de respuesta activada.' : 'Voz de respuesta silenciada.');
    });
  }

  if (wakeWordToggle) {
    wakeWordToggle.addEventListener('change', async (e) => {
      state.wakeWordEnabled = e.target.checked;
      await fetch('/api/settings/wakeword', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: state.wakeWordEnabled })
      });
      updateStatus(
        state.wakeWordEnabled ? 'idle' : 'muted',
        state.wakeWordEnabled ? 'Escuchando "Banshee"...' : 'Activación por voz desactivada'
      );
      showToast(state.wakeWordEnabled ? 'Escucha de "Banshee" activada.' : 'Activación por voz pausada.');
    });
  }

  if (autostartToggle) {
    autostartToggle.addEventListener('change', async (e) => {
      const en = e.target.checked;
      const resp = await fetch('/api/settings/autostart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: en })
      });
      const data = await resp.json();
      showToast(data.enabled ? 'Banshee se iniciará con Windows.' : 'Inicio automático desactivado.');
    });
  }

  // App Search
  if (appSearchInput) {
    appSearchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      renderSimpleApps(state.allApps.filter(a => a.name.toLowerCase().includes(q)));
    });
  }

  async function loadInitialStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (data.threshold_rms && thresholdSlider) {
        thresholdSlider.value = data.threshold_rms;
        if (thresholdDisplay) thresholdDisplay.textContent = `${data.threshold_rms} RMS`;
      }
    } catch (e) {}
  }

  // Initialize
  loadInitialStatus();
  loadAudioDevices();
  loadVoices();
  loadAutostart();
  connectWebSocket();
});
