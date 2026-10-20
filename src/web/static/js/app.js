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
    isMicListening: true,
    isTestingMic: false,
    testMeterPollInterval: null,
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
  const micBtnIcon = document.getElementById('micBtnIcon');
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
  const btnRefreshMics = document.getElementById('btnRefreshMics');
  const btnTestMic = document.getElementById('btnTestMic');
  const btnTestMicText = document.getElementById('btnTestMicText');
  const micLiveVerdictBadge = document.getElementById('micLiveVerdictBadge');
  const floatingMicTestPill = document.getElementById('floatingMicTestPill');
  const floatingPillVerdict = document.getElementById('floatingPillVerdict');
  const floatingPillMeterFill = document.getElementById('floatingPillMeterFill');
  const btnFloatingPauseTest = document.getElementById('btnFloatingPauseTest');
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

  // Toggle Chat Open state
  function setChatOpen(open) {
    state.isChatOpen = open;
    if (chatbotContainer) {
      chatbotContainer.style.display = open ? 'flex' : 'none';
    }
  }

  // ==========================================================================
  // Window Drag & Interactive Isolation
  // ==========================================================================
  // Evitar que hacer clic en los botones del header active el arrastre
  const headerInteractives = document.querySelectorAll(
    '.header-actions, .header-action-btn, #btnCollapseChat, #btnCloseChat, #btnPinWindow, #btnOpenApps, #btnOpenSettings, .bot-tag'
  );
  headerInteractives.forEach((el) => {
    el.addEventListener('mousedown', (e) => {
      e.stopPropagation();
    });
  });

  // Arrastre ultra-fluido de la ventana a cualquier parte de la pantalla
  const headerElement = document.querySelector('.chat-header');
  if (headerElement) {
    let isMoving = false;
    let initialClientX = 0;
    let initialClientY = 0;

    headerElement.addEventListener('mousedown', (e) => {
      if (e.target.closest('button, input, textarea, a, .header-action-btn')) {
        return;
      }
      isMoving = true;
      initialClientX = e.clientX;
      initialClientY = e.clientY;

      const handleMouseMove = (moveEv) => {
        if (!isMoving) return;
        const newX = moveEv.screenX - initialClientX;
        const newY = moveEv.screenY - initialClientY;
        if (window.pywebview && window.pywebview._jsApiCallback) {
          window.pywebview._jsApiCallback('pywebviewMoveWindow', [newX, newY], 'move');
        }
      };

      const handleMouseUp = () => {
        isMoving = false;
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    });
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
  function updateMicUI(isListening) {
    state.isMicListening = isListening;
    if (btnVoiceToggle) {
      if (isListening) {
        btnVoiceToggle.classList.add('listening');
        btnVoiceToggle.classList.remove('paused');
        btnVoiceToggle.title = 'Micrófono activo (escuchando) · Haz clic para pausar';
        if (micBtnIcon) micBtnIcon.textContent = '🎙️';
        updateStatus('idle', '● Escuchando tu voz', false);
      } else {
        btnVoiceToggle.classList.remove('listening');
        btnVoiceToggle.classList.add('paused');
        btnVoiceToggle.title = 'Micrófono pausado · Haz clic para activar escucha';
        if (micBtnIcon) micBtnIcon.textContent = '🔇';
        updateStatus('paused', '⏸️ Micrófono en pausa', false);
      }
    }
  }

  function updateStatus(status, text, isListening = false) {
    state.isListeningVoice = isListening;
    if (wakeStatusText) {
      wakeStatusText.textContent = text;
      if (isListening) {
        wakeStatusText.style.color = '#fb7185';
      } else if (!state.isMicListening) {
        wakeStatusText.style.color = '#f87171';
      } else {
        wakeStatusText.style.color = '#34d399';
      }
    }
    if (launcherBadge) {
      if (isListening) {
        launcherBadge.textContent = '🎙️ Escuchando';
        launcherBadge.style.background = 'var(--danger)';
      } else if (!state.isMicListening) {
        launcherBadge.textContent = '🔇 Pausado';
        launcherBadge.style.background = '#64748b';
      } else {
        launcherBadge.textContent = 'Online';
        launcherBadge.style.background = 'var(--success)';
      }
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

  // Toggle Microphone Listening / Pause
  if (btnVoiceToggle) {
    btnVoiceToggle.addEventListener('click', async () => {
      try {
        btnVoiceToggle.disabled = true;
        const resp = await fetch('/api/audio/listen_toggle', { method: 'POST' });
        const data = await resp.json();
        const listening = (data.is_listening === true);
        updateMicUI(listening);
        if (listening) {
          showToast('🎙️ Escucha activada. ¡Vanshee te escucha!');
        } else {
          showToast('🔇 Escucha pausada. Micrófono silenciado.');
        }
      } catch (err) {
        console.warn('Error toggling mic listening:', err);
      } finally {
        btnVoiceToggle.disabled = false;
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
    btnCloseSettings.addEventListener('click', () => {
      settingsDrawer.classList.remove('open');
      updateMicUI(state.isMicListening !== false);
    });
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
          } else if (msg.type === 'stt_ready') {
            updateMicUI(true);
          } else if (msg.type === 'wake_word_listening') {
            setChatOpen(true);
            updateStatus('listening', '¡Vanshee te escucha!', true);
            if (state.isMicListening && btnVoiceToggle) {
              btnVoiceToggle.classList.add('listening');
            }
          } else if (msg.type === 'mic_state_changed') {
            const listening = (msg.data && msg.data.is_listening === true);
            updateMicUI(listening);
          } else if (msg.type === 'mic_test_meter') {
            updateLiveMeterUI(msg.data);
          } else if (msg.type === 'mic_test_state') {
            if (msg.data && msg.data.is_testing === false) {
              onTestStoppedUI(msg.data.result);
            }
          } else if (msg.type === 'command_completed') {
            if (msg.data.source === 'wake_word') {
              appendMessage('assistant', msg.data.response_text, msg.data.plan_summary);
            }
            if (state.isMicListening) {
              updateStatus('idle', '● Escuchando tu voz', false);
            } else {
              updateStatus('paused', '⏸️ Micrófono en pausa', false);
            }
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
  // Load Audio Devices & Voices (Filtered to available devices only)
  // ==========================================================================
  async function loadAudioDevices(isRefresh = false) {
    if (!micSelect) return;
    if (isRefresh && btnRefreshMics) {
      btnRefreshMics.classList.add('refreshing');
      btnRefreshMics.disabled = true;
    }

    try {
      const url = isRefresh ? '/api/audio/devices?refresh=true' : '/api/audio/devices';
      const resp = await fetch(url);
      const data = await resp.json();
      micSelect.innerHTML = '';

      const devs = data.devices || [];
      if (devs.length === 0) {
        const opt = document.createElement('option');
        opt.value = '-1';
        opt.textContent = 'Predeterminado de Windows (Automático)';
        micSelect.appendChild(opt);
      } else {
        // Opción 1: Predeterminado de Windows
        const defOpt = document.createElement('option');
        defOpt.value = '-1';
        const defLabel = data.default_name ? ` (${data.default_name})` : '';
        defOpt.textContent = `🎙️ Predeterminado de Windows${defLabel}`;
        if (data.selected_index === null || data.selected_index === -1) {
          defOpt.selected = true;
        }
        micSelect.appendChild(defOpt);

        // Dispositivos físicos disponibles filtrados
        devs.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d.index;
          opt.textContent = `${d.name} ${d.is_default ? '(Predeterminado)' : ''}`;
          if (d.is_selected && data.selected_index !== null && data.selected_index !== -1) {
            opt.selected = true;
          }
          micSelect.appendChild(opt);
        });
      }

      if (isRefresh) {
        showToast('✅ Dispositivos de audio actualizados');
      }
    } catch (err) {
      console.warn('Error loading audio devices:', err);
      if (isRefresh) showToast('Error al actualizar micrófonos');
    } finally {
      if (isRefresh && btnRefreshMics) {
        btnRefreshMics.classList.remove('refreshing');
        btnRefreshMics.disabled = false;
      }
    }
  }

  if (btnRefreshMics) {
    btnRefreshMics.addEventListener('click', () => {
      loadAudioDevices(true);
    });
  }

  if (micSelect) {
    micSelect.addEventListener('change', async () => {
      const val = micSelect.value;
      const idx = (val === '' || val === '-1') ? null : parseInt(val, 10);
      const selOpt = micSelect.options[micSelect.selectedIndex];
      const devName = selOpt ? selOpt.textContent : '';
      try {
        const resp = await fetch('/api/audio/devices/select', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_index: idx, device_name: devName })
        });
        const data = await resp.json();
        const listening = (data.is_listening !== false);
        updateMicUI(listening);
        showToast('Micrófono de entrada seleccionado.');
      } catch (e) {
        console.warn('Error selecting mic:', e);
      }
    });
  }

  // ==========================================================================
  // Live Microphone Testing & Real-Time Truthful Detection Controller
  // ==========================================================================
  function updateLiveMeterUI(meterData) {
    if (!state.isTestingMic) return;
    const rms = meterData.rms || 0;
    const pct = Math.min(meterData.level_percent || 0, 100);

    if (micMeterFill) micMeterFill.style.width = pct + '%';
    if (floatingPillMeterFill) floatingPillMeterFill.style.width = pct + '%';

    const verdict = meterData.verdict || '';
    const statusType = meterData.status_type || 'silence';

    if (micMeterText) {
      micMeterText.textContent = `Volumen: ${rms} RMS · ${verdict}`;
    }

    if (micLiveVerdictBadge) {
      micLiveVerdictBadge.style.display = 'flex';
      micLiveVerdictBadge.className = `live-verdict-badge ${statusType}`;
      micLiveVerdictBadge.textContent = verdict;
    }

    if (floatingPillVerdict) {
      floatingPillVerdict.textContent = verdict;
      floatingPillVerdict.style.color = (statusType === 'clear') ? '#34d399' : ((statusType === 'moderate') ? '#fbbf24' : '#94a3b8');
    }

    const pillDot = document.getElementById('floatingPillDot') || document.querySelector('.pill-pulse-dot');
    if (pillDot) {
      pillDot.className = `pill-pulse-dot ${statusType}`;
    }
  }

  function onTestStoppedUI(data) {
    state.isTestingMic = false;
    if (state.testMeterPollInterval) {
      clearInterval(state.testMeterPollInterval);
      state.testMeterPollInterval = null;
    }

    if (btnTestMic) {
      btnTestMic.classList.remove('testing');
      if (btnTestMicText) {
        btnTestMicText.textContent = 'Probar Detección de Micrófono';
      } else {
        btnTestMic.textContent = '🎙️ Probar Detección de Micrófono';
      }
    }

    if (micLiveVerdictBadge) {
      micLiveVerdictBadge.style.display = 'none';
    }

    if (data) {
      const vol = data.volume_rms !== undefined ? data.volume_rms : (data.max_rms || 0);
      const hasSound = data.has_sound === true;
      const verdict = data.quality_verdict || (hasSound ? 'Se escucha fuerte y claro' : 'No se escucha al no percibir sonido alguno');

      if (micMeterFill) micMeterFill.style.width = Math.min(vol * 1.5, 100) + '%';
      if (micMeterText) micMeterText.textContent = `Resultado: ${vol} RMS · ${verdict}`;

      if (floatingPillVerdict) {
        floatingPillVerdict.textContent = (hasSound ? '✅ ' : '❌ ') + verdict;
        floatingPillVerdict.style.color = hasSound ? '#34d399' : '#f87171';
      }
      const pillDot = document.getElementById('floatingPillDot') || document.querySelector('.pill-pulse-dot');
      if (pillDot) {
        pillDot.className = `pill-pulse-dot ${hasSound ? 'clear' : 'silence'}`;
      }

      // Mantener el flotante visible 3.5 segundos con el resultado verídico final antes de retirarse
      if (state.floatingPillTimer) clearTimeout(state.floatingPillTimer);
      state.floatingPillTimer = setTimeout(() => {
        if (!state.isTestingMic && floatingMicTestPill) {
          floatingMicTestPill.style.display = 'none';
        }
      }, 3500);

      if (micPlaybackWrap && micAudioPlayer && data.audio_url) {
        micPlaybackWrap.style.display = 'block';
        micAudioPlayer.src = data.audio_url;
        micAudioPlayer.play().catch(() => {});
      }

      if (micQualityBadge) {
        micQualityBadge.textContent = (hasSound ? '✅ ' : '❌ ') + verdict;
        micQualityBadge.className = hasSound ? 'badge-optimal' : 'badge-silence';
      }

      if (micAdviceBox) micAdviceBox.textContent = data.advice;

      if (btnApplyRecommended && data.recommended_threshold) {
        btnApplyRecommended.onclick = async () => {
          if (thresholdSlider) thresholdSlider.value = data.recommended_threshold;
          if (thresholdDisplay) thresholdDisplay.textContent = `${data.recommended_threshold} RMS`;
          await saveThresholdSetting(data.recommended_threshold);
          showToast(`Sensibilidad aplicada: ${data.recommended_threshold} RMS`);
        };
      }

      if (hasSound) {
        showToast(`🎙️ ${verdict}`);
      } else {
        showToast('⚠️ No se percibe sonido alguno en el micrófono.');
      }
    } else {
      if (floatingMicTestPill) floatingMicTestPill.style.display = 'none';
      if (micMeterText) micMeterText.textContent = 'Prueba finalizada.';
    }
  }

  async function startMicTest() {
    if (state.floatingPillTimer) {
      clearTimeout(state.floatingPillTimer);
      state.floatingPillTimer = null;
    }
    state.isTestingMic = true;

    if (btnTestMic) {
      btnTestMic.classList.add('testing');
      if (btnTestMicText) {
        btnTestMicText.textContent = 'Pausar Detección (Escuchando en vivo...)';
      } else {
        btnTestMic.textContent = '⏸️ Pausar Detección (Escuchando...)';
      }
    }

    if (micLiveVerdictBadge) {
      micLiveVerdictBadge.style.display = 'flex';
      micLiveVerdictBadge.className = 'live-verdict-badge silence';
      micLiveVerdictBadge.textContent = '🔇 No se escucha al no percibir sonido alguno (Habla al micrófono...)';
    }

    if (floatingMicTestPill) {
      floatingMicTestPill.style.display = 'flex';
      if (floatingPillVerdict) {
        floatingPillVerdict.textContent = '🔇 No se escucha al no percibir sonido alguno';
        floatingPillVerdict.style.color = '#94a3b8';
      }
      if (floatingPillMeterFill) floatingPillMeterFill.style.width = '0%';
      const pillDot = document.getElementById('floatingPillDot') || document.querySelector('.pill-pulse-dot');
      if (pillDot) pillDot.className = 'pill-pulse-dot silence';
    }

    if (micPlaybackWrap) micPlaybackWrap.style.display = 'none';
    if (micMeterText) micMeterText.textContent = 'Analizando señal de sonido en vivo...';
    if (micMeterFill) micMeterFill.style.width = '0%';

    try {
      const devIdx = micSelect ? micSelect.value : null;
      const resp = await fetch('/api/audio/test/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_index: (devIdx && devIdx !== '-1') ? parseInt(devIdx, 10) : null })
      });
      const data = await resp.json();
      if (!data || data.status === 'error') {
        showToast('⚠️ No se pudo acceder al micrófono seleccionado.');
        onTestStoppedUI(null);
        return;
      }

      // Polling de respaldo constante cada 80ms para garantizar animación visual fluida
      if (state.testMeterPollInterval) clearInterval(state.testMeterPollInterval);
      state.testMeterPollInterval = setInterval(async () => {
        if (!state.isTestingMic) {
          clearInterval(state.testMeterPollInterval);
          return;
        }
        try {
          const mResp = await fetch('/api/audio/test/meter');
          const mData = await mResp.json();
          if (mData && mData.is_testing) {
            updateLiveMeterUI(mData);
          }
        } catch (e) {}
      }, 80);

    } catch (err) {
      console.warn('Error starting mic test:', err);
      onTestStoppedUI(null);
    }
  }

  async function stopMicTest() {
    if (state.testMeterPollInterval) {
      clearInterval(state.testMeterPollInterval);
      state.testMeterPollInterval = null;
    }
    state.isTestingMic = false;

    if (btnTestMicText) {
      btnTestMicText.textContent = 'Deteniendo detección...';
    }
    if (floatingPillVerdict) {
      floatingPillVerdict.textContent = 'Analizando señal de voz...';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const resp = await fetch('/api/audio/test/stop', {
        method: 'POST',
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      const data = await resp.json();
      onTestStoppedUI(data.result || data);
    } catch (err) {
      clearTimeout(timeoutId);
      console.warn('Mic test stop timed out or failed:', err);
      onTestStoppedUI(null);
    }
  }

  function toggleMicTest() {
    if (state.isTestingMic) {
      stopMicTest();
    } else {
      startMicTest();
    }
  }

  if (btnTestMic) {
    btnTestMic.addEventListener('click', toggleMicTest);
  }

  if (btnFloatingPauseTest) {
    btnFloatingPauseTest.addEventListener('click', stopMicTest);
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
      saveThresholdSetting(thresholdSlider ? parseFloat(thresholdSlider.value) : 45);
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
      if (thresholdSlider) thresholdSlider.value = data.threshold_rms || 45;
      if (thresholdDisplay) thresholdDisplay.textContent = `${data.threshold_rms || 45} RMS`;
      if (voiceSelect && data.selected_voice) voiceSelect.value = data.selected_voice;
      if (wakeWordToggle) wakeWordToggle.checked = data.wakeword_enabled !== false;
      if (autostartToggle) autostartToggle.checked = !!data.autostart_enabled;
      if (ttsToggle) ttsToggle.checked = data.speak_tts_enabled !== false;
      state.ttsEnabled = data.speak_tts_enabled !== false;
      state.isMicListening = data.mic_listening !== false;
      updateMicUI(state.isMicListening);
    } catch (e) {}
  }

  // Initialize
  loadAudioDevices();
  initStatus();
  connectWebSocket();
});
