export function createTTSController({ state, el, showToast, adjacentChapterNo, openChapter }) {
  let bound = false;
  let activeChapterKey = '';

  function chapterIdentity() {
    return `${state.currentSlug || ''}:${state.currentChapterNo || 0}`;
  }

  function hashText(text) {
    let hash = 2166136261;
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(36);
  }

  function audioCacheKey(idx, text, speed) {
    return `${chapterIdentity()}:${state.tts.voice}:${speed}:${idx}:${hashText(text)}`;
  }

  function clearAudioCache() {
    for (const url of Object.values(state.tts.audioBlobs || {})) {
      if (typeof url === 'string' && url.startsWith('blob:')) URL.revokeObjectURL(url);
    }
    state.tts.audioBlobs = {};
  }

  function stopCurrentPlayback() {
    if (state.tts.audioElement) {
      state.tts.audioElement.pause();
      state.tts.audioElement = null;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function clearParagraphHighlight() {
    el.readerContent?.querySelectorAll('p.reading-active').forEach(node => {
      node.classList.remove('reading-active');
    });
  }

  function highlightParagraph(idx) {
    clearParagraphHighlight();
    const paragraph = el.readerContent?.querySelector(`p[data-p-idx="${idx}"]`);
    if (!paragraph) return;
    paragraph.classList.add('reading-active');
    paragraph.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function browserSpeech(text, speed, onEnd) {
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') {
      showToast('เบราว์เซอร์นี้ไม่รองรับระบบอ่านออกเสียง', 'error');
      return false;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'th-TH';
    utterance.rate = speed;
    utterance.onend = onEnd;
    utterance.onerror = event => {
      if (event.error !== 'interrupted' && event.error !== 'canceled') {
        console.warn('Browser TTS error:', event);
      }
    };
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function initTTS() {
    if (el.ttsVoice) {
      const validOptions = Array.from(el.ttsVoice.options).map(option => option.value);
      if (!validOptions.includes(state.tts.voice)) {
        state.tts.voice = 'edge-tts/th-TH-NiwatNeural';
        localStorage.setItem('nc_tts_voice', state.tts.voice);
      }
      el.ttsVoice.value = state.tts.voice;
    }
    if (el.ttsSpeed) {
      state.tts.speed = Number.parseFloat(el.ttsSpeed.value) || 1.0;
    }
    if (bound) return;
    bound = true;

    el.ttsVoice?.addEventListener('change', () => {
      state.tts.voice = el.ttsVoice.value;
      localStorage.setItem('nc_tts_voice', state.tts.voice);
      clearAudioCache();
      if (state.tts.speaking) speakCurrentParagraph();
    });
    el.ttsSpeed?.addEventListener('change', () => {
      state.tts.speed = Number.parseFloat(el.ttsSpeed.value) || 1.0;
      clearAudioCache();
      if (state.tts.speaking) speakCurrentParagraph();
    });
    el.btnReaderTTS?.addEventListener('click', toggleTTS);
    el.btnTTSPlayPause?.addEventListener('click', togglePlayPauseTTS);
    el.btnTTSNext?.addEventListener('click', nextTTSParagraph);
    el.btnTTSPrev?.addEventListener('click', prevTTSParagraph);
    el.btnTTSClose?.addEventListener('click', stopTTS);
  }

  function toggleTTS() {
    if (state.tts.speaking) stopTTS();
    else startTTS();
  }

  function startTTS() {
    const chapter = state.currentChapterData;
    if (!chapter) return;
    const paragraphs = chapter.translatedText?.length
      ? chapter.translatedText
      : (chapter.sourceText || []);
    if (!paragraphs.length) {
      showToast('ไม่มีเนื้อหาสำหรับอ่านเสียง', 'warning');
      return;
    }

    const chapterKey = chapterIdentity();
    if (activeChapterKey !== chapterKey) {
      clearAudioCache();
      activeChapterKey = chapterKey;
    }
    state.tts.paragraphs = paragraphs;
    state.tts.currentIdx = 0;
    state.tts.speaking = true;
    state.tts.paused = false;
    el.ttsPlayerBar?.classList.remove('hidden');
    if (el.btnTTSPlayPause) el.btnTTSPlayPause.innerText = '⏸️ หยุด';
    speakCurrentParagraph();
  }

  function stopTTS() {
    stopCurrentPlayback();
    state.tts.speaking = false;
    state.tts.paused = false;
    clearParagraphHighlight();
    clearAudioCache();
    el.ttsPlayerBar?.classList.add('hidden');
  }

  function togglePlayPauseTTS() {
    if (!state.tts.speaking) {
      startTTS();
      return;
    }
    const nextPaused = !state.tts.paused;
    if (state.tts.voice === 'browser') {
      if (!window.speechSynthesis) return;
      if (nextPaused) window.speechSynthesis.pause();
      else window.speechSynthesis.resume();
    } else if (state.tts.audioElement) {
      if (nextPaused) state.tts.audioElement.pause();
      else state.tts.audioElement.play().catch(error => console.warn(error));
    } else if (!nextPaused) {
      speakCurrentParagraph();
    }
    state.tts.paused = nextPaused;
    if (el.btnTTSPlayPause) {
      el.btnTTSPlayPause.innerText = nextPaused ? '▶️ เล่นต่อ' : '⏸️ หยุด';
    }
  }

  function advanceAfterSpeech(idx) {
    if (!state.tts.speaking || state.tts.paused || state.tts.currentIdx !== idx) return;
    state.tts.currentIdx += 1;
    speakCurrentParagraph();
  }

  async function speakCurrentParagraph() {
    if (state.tts.currentIdx >= state.tts.paragraphs.length) {
      const nextChapter = adjacentChapterNo(state.currentChapterNo, 1);
      if (nextChapter) {
        const current = state.currentChapterNo;
        stopTTS();
        showToast(`จบตอน ${current} — อ่านเสียงต่อตอน ${nextChapter}... 📖`, 'info');
        await openChapter(state.currentSlug, nextChapter);
        startTTS();
        return;
      }
      stopTTS();
      showToast('อ่านเสียงจบทั้งเรื่องแล้ว 🎉', 'success');
      return;
    }

    stopCurrentPlayback();
    const idx = state.tts.currentIdx;
    const text = state.tts.paragraphs[idx];
    const speed = Number.parseFloat(el.ttsSpeed?.value || state.tts.speed || '1') || 1.0;
    state.tts.speed = speed;
    const requestChapterKey = chapterIdentity();
    highlightParagraph(idx);
    if (el.ttsStatus) {
      el.ttsStatus.innerText = `อ่านย่อหน้า ${idx + 1}/${state.tts.paragraphs.length}`;
    }
    prefetchNextAudio(idx + 1);

    if (state.tts.voice === 'browser') {
      browserSpeech(text, speed, () => advanceAfterSpeech(idx));
      return;
    }

    const key = audioCacheKey(idx, text, speed);
    try {
      let audioBlobUrl = state.tts.audioBlobs[key];
      if (!audioBlobUrl) {
        const response = await fetch('/api/audio/speech', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice: state.tts.voice, speed }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        audioBlobUrl = URL.createObjectURL(blob);
        state.tts.audioBlobs[key] = audioBlobUrl;
      }

      if (!state.tts.speaking || state.tts.currentIdx !== idx || chapterIdentity() !== requestChapterKey) {
        return;
      }
      const audio = new Audio(audioBlobUrl);
      audio.playbackRate = speed;
      state.tts.audioElement = audio;
      audio.onended = () => advanceAfterSpeech(idx);
      audio.onerror = event => {
        console.warn('Audio playback error:', event);
        advanceAfterSpeech(idx);
      };
      await audio.play();
    } catch (err) {
      console.warn('Neural TTS failed, falling back to browser speech:', err);
      browserSpeech(text, speed, () => advanceAfterSpeech(idx));
    }
  }

  async function prefetchNextAudio(nextIdx) {
    if (state.tts.voice === 'browser' || !state.tts.speaking) return;
    if (nextIdx >= state.tts.paragraphs.length) return;
    const text = state.tts.paragraphs[nextIdx];
    const speed = state.tts.speed || 1.0;
    const key = audioCacheKey(nextIdx, text, speed);
    if (state.tts.audioBlobs[key]) return;
    const requestChapterKey = chapterIdentity();
    try {
      const response = await fetch('/api/audio/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: state.tts.voice, speed }),
      });
      if (!response.ok || !state.tts.speaking || chapterIdentity() !== requestChapterKey) return;
      const blob = await response.blob();
      if (!state.tts.speaking || chapterIdentity() !== requestChapterKey) return;
      state.tts.audioBlobs[key] = URL.createObjectURL(blob);
    } catch {
      // Prefetch is best-effort; foreground playback handles fallback.
    }
  }

  function nextTTSParagraph() {
    if (state.tts.currentIdx >= state.tts.paragraphs.length - 1) return;
    state.tts.currentIdx += 1;
    speakCurrentParagraph();
  }

  function prevTTSParagraph() {
    if (state.tts.currentIdx <= 0) return;
    state.tts.currentIdx -= 1;
    speakCurrentParagraph();
  }

  return {
    initTTS,
    stopTTS,
    clearAudioCache,
  };
}
