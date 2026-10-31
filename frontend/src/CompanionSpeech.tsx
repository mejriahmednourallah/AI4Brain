import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Pause, Play, Square, Volume2 } from 'lucide-react';
import { speechExcerpt } from './speechExcerpt';
import type { CompanionCheckpointSignal } from './companionCheckpoint';
export type { CompanionCheckpointSignal as CompanionCheckpointSpeech } from './companionCheckpoint';

type SpeechMode = 'fast_local' | 'bella' | 'muted';
type LocalSpeechEngine = 'browser' | 'windows_sapi' | null;
type SpeechSettings = { mode: SpeechMode; enabled: boolean; voice: string; speed: number; auto: boolean };
type SpeechStatus = { engine: string; model: string; loaded: boolean; voices?: string[] };
export type CompanionSpeechPhase = 'idle' | 'preparing' | 'playing' | 'paused' | 'error';
type Props = {
  sessionId: string | null; text: string; quiet: boolean; titleId: string; visible?: boolean;
  onPhaseChange?: (phase: CompanionSpeechPhase) => void;
  onStop?: () => void;
  replyKey?: string; autoSpokenOwner?: { current: string };
  ownershipKey?: string;
  speechContext?: { evidenceRevision?: string; subject?: string };
  checkpoint?: CompanionCheckpointSignal | null;
};
const DEFAULTS: SpeechSettings = { mode: 'fast_local', enabled: false, voice: 'Bella', speed: 1, auto: true };
const localKey = (sessionId: string | null) => `ai4brain.speech.${sessionId ?? 'local'}`;
const autoKey = (sessionId: string | null) => `ai4brain.speech.auto.${sessionId ?? 'local'}`;
const checkpointKey = (sessionId: string) => `ai4brain.speech.checkpoints.${sessionId}`;
const localEngineKey = (sessionId: string | null) => `ai4brain.speech.fast-local-engine.${sessionId ?? 'local'}`;
const englishLocal = (voice: SpeechSynthesisVoice) => voice.localService === true && /^en(?:-|$)/i.test(voice.lang);
function prefersWindowsSapi(sessionId: string | null): boolean {
  try { return localStorage.getItem(localEngineKey(sessionId)) === 'windows_sapi'; } catch { return false; }
}

function readLocal(sessionId: string | null): SpeechSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(localKey(sessionId)) ?? 'null') as Partial<SpeechSettings> | null;
    const mode = saved?.mode === 'bella' || saved?.mode === 'muted' ? saved.mode : 'fast_local';
    return { mode, enabled: saved?.enabled === true, voice: typeof saved?.voice === 'string' ? saved.voice : 'Bella',
      speed: typeof saved?.speed === 'number' && saved.speed >= .6 && saved.speed <= 1.4 ? saved.speed : 1,
      auto: localStorage.getItem(autoKey(sessionId)) !== 'false' };
  } catch { return DEFAULTS; }
}

export function CompanionSpeech({ sessionId, text, quiet, titleId, visible = true, onPhaseChange, onStop, replyKey = '', autoSpokenOwner, ownershipKey = '', speechContext, checkpoint }: Props) {
  const [settings, setSettings] = useState<SpeechSettings>(() => readLocal(sessionId));
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [status, setStatus] = useState<SpeechStatus | null>(null);
  const [phase, setPhase] = useState<'idle' | 'preparing' | 'playing' | 'paused' | 'error'>('idle');
  const [activeLocalEngine, setActiveLocalEngine] = useState<LocalSpeechEngine>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [preferenceNote, setPreferenceNote] = useState('');
  const [controlsHost, setControlsHost] = useState<HTMLElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const localEngineRef = useRef<LocalSpeechEngine>(null);
  const windowsAudioReady = useRef<{ key: string; source: 'reply' | 'checkpoint' | 'manual' } | null>(null);
  const requestRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const lastAutoReply = useRef('');
  const lastCheckpoint = useRef('');
  const lastCheckpointAt = useRef(0);
  const seenCheckpoints = useRef(new Set<string>());
  const settingsRevision = useRef(0);
  const spokenKey = useRef(replyKey);
  const settingsRef = useRef(settings);
  const sessionRef = useRef(sessionId);
  const replyKeyRef = useRef(replyKey);
  const ownershipRef = useRef(ownershipKey);
  settingsRef.current = settings;
  sessionRef.current = sessionId;
  replyKeyRef.current = replyKey;
  ownershipRef.current = ownershipKey;

  useEffect(() => { onPhaseChange?.(phase); }, [phase, onPhaseChange]);
  useEffect(() => {
    setControlsHost(visible ? document.querySelector<HTMLElement>('.companion-card') : null);
  }, [visible]);
  useEffect(() => {
    let active = true;
    const revision = ++settingsRevision.current;
    setSettings(readLocal(sessionId));
    setPreferenceNote('');
    if (!sessionId) return () => { active = false; };
    fetch(`/api/companion/speech/preferences?session_id=${encodeURIComponent(sessionId)}`, { credentials: 'omit' })
      .then(async response => response.ok ? response.json() : null)
      .then(body => {
        if (!active || revision !== settingsRevision.current || !body?.preferences) return;
        const saved = body.preferences;
        const mode: SpeechMode = saved.mode === 'bella' || saved.mode === 'muted' ? saved.mode : 'fast_local';
        const next = { mode, enabled: saved.enabled === true, voice: typeof saved.voice === 'string' ? saved.voice : 'Bella',
          speed: Number(saved.speed) >= .6 && Number(saved.speed) <= 1.4 ? Number(saved.speed) : 1,
          auto: localStorage.getItem(autoKey(sessionId)) !== 'false' };
        setSettings(next); localStorage.setItem(localKey(sessionId), JSON.stringify(next));
      }).catch(() => { if (active && revision === settingsRevision.current) setPreferenceNote('Voice preference could not be loaded from this session; this tab uses its saved setting.'); });
    return () => { active = false; };
  }, [sessionId]);
  useEffect(() => {
    seenCheckpoints.current = new Set();
    if (!sessionId) return;
    try {
      const prior = JSON.parse(sessionStorage.getItem(checkpointKey(sessionId)) ?? '[]');
      if (Array.isArray(prior)) seenCheckpoints.current = new Set(prior.filter((item): item is string => typeof item === 'string').slice(-64));
    } catch { /* Session storage is optional; audio remains opt-in. */ }
  }, [sessionId]);
  useEffect(() => {
    const refresh = () => {
      const found = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis.getVoices().filter(englishLocal) : [];
      setVoices(found);
    };
    refresh();
    const synthesis = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
    synthesis?.addEventListener?.('voiceschanged', refresh);
    if (synthesis && !synthesis.addEventListener) synthesis.onvoiceschanged = refresh;
    return () => { synthesis?.removeEventListener?.('voiceschanged', refresh); if (synthesis?.onvoiceschanged === refresh) synthesis.onvoiceschanged = null; };
  }, []);
  useEffect(() => {
    let active = true;
    fetch('/api/companion/speech/status', { credentials: 'omit' }).then(r => r.ok ? r.json() : null).then(body => { if (active && body) setStatus(body); }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const stop = useCallback(() => {
    requestRef.current += 1;
    abortRef.current?.abort('stopped'); abortRef.current = null;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    const audio = audioRef.current;
    if (audio) { audio.onended = null; audio.onerror = null; audio.onpause = null; audio.pause(); audio.src = ''; audioRef.current = null; }
    if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = null; }
    localEngineRef.current = null; windowsAudioReady.current = null; setActiveLocalEngine(null);
    setPhase('idle');
  }, []);
  useEffect(() => { stop(); }, [sessionId, stop]);
  useEffect(() => { stop(); }, [ownershipKey, stop]);
  useEffect(() => { if (!visible) stop(); }, [visible, stop]);
  useEffect(() => { if (spokenKey.current !== replyKey) { spokenKey.current = replyKey; stop(); } }, [replyKey, stop]);
  useEffect(() => { if (quiet || document.visibilityState === 'hidden') stop(); }, [quiet, stop]);
  useEffect(() => {
    const onVisibility = () => { if (document.visibilityState === 'hidden') stop(); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [stop]);
  useEffect(() => () => stop(), [stop]);

  const persist = useCallback(async (next: SpeechSettings) => {
    setSettings(next); settingsRef.current = next;
    if (sessionId) localStorage.setItem(localKey(sessionId), JSON.stringify(next));
    localStorage.setItem(autoKey(sessionId), String(next.auto));
    const revision = ++settingsRevision.current;
    if (!sessionId) { setPreferenceNote('Start a consented session to save voice preferences.'); return false; }
    try {
      const response = await fetch('/api/companion/speech/preferences', { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, mode: next.mode, enabled: next.enabled, voice: next.mode === 'fast_local' ? 'Bella' : next.voice, speed: next.speed }) });
      if (!response.ok) throw new Error(`Preference save failed (${response.status}).`);
      if (revision === settingsRevision.current) setPreferenceNote('Voice preference saved for this session.');
      return true;
    } catch (error) {
      if (revision === settingsRevision.current) setPreferenceNote(error instanceof Error ? `${error.message} The choice is kept in this tab.` : 'Voice preference could not be saved; the choice is kept in this tab.');
      return false;
    }
  }, [sessionId]);

  const playWindowsLocal = useCallback(async (short: string, key: string,
    source: 'reply' | 'checkpoint' | 'manual', token: number, controller: AbortController) => {
    if (!sessionId) {
      if (token === requestRef.current) { setDetail('Start a consented session to use Windows local speech. The written reply remains available.'); setPhase('error'); }
      return;
    }
    if (token === requestRef.current) {
      setPhase('preparing'); setDetail('Using the local Windows voice…');
    }
    try {
      const response = await fetch('/api/companion/speech/fast-local', { method: 'POST', credentials: 'omit',
        headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ text: short, session_id: sessionId,
          ...(speechContext?.evidenceRevision ? { evidence_revision: speechContext.evidenceRevision } : {}),
          ...(speechContext?.subject ? { subject: speechContext.subject } : {}) }) });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Windows local speech failed (${response.status}).`);
      }
      const blob = await response.blob();
      if (!blob.size || (blob.type && blob.type !== 'audio/wav')) throw new Error('Windows local speech returned invalid audio.');
      if (token !== requestRef.current) return;
      try { localStorage.setItem(localEngineKey(sessionId), 'windows_sapi'); } catch { /* Current fallback still works without persistence. */ }
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      const url = URL.createObjectURL(blob); urlRef.current = url;
      const audio = new Audio(url); audioRef.current = audio;
      windowsAudioReady.current = { key, source };
      localEngineRef.current = 'windows_sapi'; setActiveLocalEngine('windows_sapi');
      audio.onended = () => { if (token === requestRef.current) stop(); };
      audio.onerror = () => { if (token === requestRef.current) { setDetail('Windows local audio could not be played. Read the written reply or press Play reply to retry.'); setPhase('error'); } };
      try {
        await audio.play();
        if (token === requestRef.current) {
          setDetail(null); setPhase('playing');
          if (source === 'reply') { lastAutoReply.current = key; if (autoSpokenOwner) autoSpokenOwner.current = key; }
        }
      } catch {
        if (token === requestRef.current) { setDetail('Windows local audio is ready. Press Play reply to start it.'); setPhase('error'); }
      }
    } catch (error) {
      if (controller.signal.aborted || token !== requestRef.current) return;
      // Do not pin a session to SAPI when it is unavailable (for example in a
      // non-Windows deployment); the browser local path remains selectable.
      try { localStorage.removeItem(localEngineKey(sessionId)); } catch { /* Capability memory is optional. */ }
      setDetail(error instanceof Error ? error.message : 'Windows local voice is unavailable. The written reply still works.');
      setPhase('error');
    }
  }, [autoSpokenOwner, sessionId, speechContext?.evidenceRevision, speechContext?.subject, stop]);

  const speak = useCallback(async (value: string, key: string, source: 'reply' | 'checkpoint' | 'manual' = 'manual') => {
    const current = settingsRef.current;
    if (!value.trim() || quiet || !current.enabled || current.mode === 'muted') return;
    const short = speechExcerpt(value);
    stop(); const token = requestRef.current; const controller = new AbortController(); abortRef.current = controller;
    setPhase('preparing'); setDetail(null);
    
    try {
      if (current.mode === 'fast_local') {
        if (prefersWindowsSapi(sessionId)) {
          await playWindowsLocal(short, key, source, token, controller);
          return;
        }
        if (!('speechSynthesis' in window)) {
          await playWindowsLocal(short, key, source, token, controller);
          return;
        }
        const voice = voices.find(item => item.voiceURI === current.voice && englishLocal(item)) ?? voices.find(englishLocal);
        if (!voice) {
          await playWindowsLocal(short, key, source, token, controller);
          return;
        }
        const utterance = new SpeechSynthesisUtterance(short); utterance.voice = voice; utterance.rate = current.speed; utterance.lang = voice.lang;
        localEngineRef.current = 'browser'; setActiveLocalEngine('browser');
        utterance.onstart = () => { if (token === requestRef.current) setPhase('playing'); };
        utterance.onend = () => { if (token === requestRef.current) { setPhase('idle'); setActiveLocalEngine(null); localEngineRef.current = null; abortRef.current = null; } };
        utterance.onerror = event => { if (token === requestRef.current && event.error !== 'canceled' && event.error !== 'interrupted') {
          setDetail(`Browser local voice failed (${event.error}); trying the local Windows voice.`);
          void playWindowsLocal(short, key, source, token, controller);
        } };
        window.speechSynthesis.speak(utterance);
        if (source === 'reply') { lastAutoReply.current = key; if (autoSpokenOwner) autoSpokenOwner.current = key; }
        if (source === 'manual' && key === 'enable') { setPhase('playing'); setDetail('Fast local English voice enabled.'); }
        return;
      }
      const response = await fetch('/api/companion/speech', { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ text: short, voice: current.voice, speed: current.speed, session_id: sessionId,
          ...(speechContext?.evidenceRevision ? { evidence_revision: speechContext.evidenceRevision } : {}), ...(speechContext?.subject ? { subject: speechContext.subject } : {}) }) });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail ?? `Bella speech failed (${response.status}).`); }
      const url = URL.createObjectURL(await response.blob());
      if (token !== requestRef.current) { URL.revokeObjectURL(url); return; }
      urlRef.current = url; const audio = new Audio(url); audioRef.current = audio;
      audio.onended = () => { if (token === requestRef.current) stop(); };
      audio.onerror = () => { if (token === requestRef.current) { stop(); setDetail('Bella audio could not be decoded. The written reply is still available.'); setPhase('error'); } };
      await audio.play(); if (token === requestRef.current) { if (source === 'reply') { lastAutoReply.current = key; if (autoSpokenOwner) autoSpokenOwner.current = key; } setPhase('playing'); }
    } catch (error) {
      if (controller.signal.aborted || token !== requestRef.current) return;
      if (current.mode === 'fast_local') {
        await playWindowsLocal(short, key, source, token, controller);
        return;
      }
      setDetail(error instanceof Error ? error.message : 'Voice unavailable. The written reply still works.'); setPhase('error');
    }
  }, [autoSpokenOwner, playWindowsLocal, quiet, sessionId, speechContext?.evidenceRevision, speechContext?.subject, stop, voices]);

  useEffect(() => {
    if (!settings.enabled || !settings.auto || settings.mode === 'muted' || quiet || !text.trim() || !replyKey || lastAutoReply.current === replyKey || autoSpokenOwner?.current === replyKey) return;
    void speak(text, replyKey, 'reply');
  }, [settings.enabled, settings.auto, settings.mode, quiet, text, replyKey, speak, autoSpokenOwner]);
  useEffect(() => {
    if (!checkpoint || !settings.enabled || !settings.auto || settings.mode === 'muted' || quiet || lastCheckpoint.current === checkpoint.id || seenCheckpoints.current.has(checkpoint.id)) return;
    const now = Date.now();
    // A user-requested assistance checkpoint follows a canonical save and is
    // directly relevant to the hint just exposed. Let it speak even when a
    // nearby ready/checkpoint announcement used the proactive cooldown. The
    // per-checkpoint ID/session dedupe above still prevents repeat speech.
    if (now - lastCheckpointAt.current < 30000
        && checkpoint.kind !== 'completed'
        && checkpoint.kind !== 'assistance') return;
    lastCheckpoint.current = checkpoint.id; lastCheckpointAt.current = now;
    seenCheckpoints.current.add(checkpoint.id);
    if (sessionId) {
      try { sessionStorage.setItem(checkpointKey(sessionId), JSON.stringify([...seenCheckpoints.current].slice(-64))); } catch { /* Dedup still applies for this mount. */ }
    }
    void speak(checkpoint.text, checkpoint.id, 'checkpoint');
  }, [checkpoint, settings.enabled, settings.auto, settings.mode, quiet, speak, sessionId]);

  const persistSelection = (mode: SpeechMode) => {
    if (mode !== settings.mode || mode === 'muted') stop();
    void persist({ ...settings, mode, enabled: false });
  };
  const enable = () => {
    if (settings.mode === 'muted') return;
    const next = { ...settings, enabled: true, auto: true };
    const saved = persist(next);
    if (settings.mode === 'fast_local') {
      setPreferenceNote('Fast local is enabled for new replies. Use Play reply for the current answer when you are ready.');
      if (sessionId) {
        void saved.then(ok => {
          if (!ok) return null;
          return fetch('/api/companion/speech/fast-local/warm', { method: 'POST', credentials: 'omit',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId }) });
        }).then(async response => response?.ok ? response.json() : null)
          .then(result => {
            if (!result?.accepted) return;
            try { localStorage.setItem(localEngineKey(sessionId), 'windows_sapi'); } catch { /* Capability memory is optional. */ }
            setPreferenceNote('Fast local voice is preparing in the background.');
          })
          .catch(() => undefined);
      }
    }
    else if (sessionId) {
      void saved.then(ok=>{
        if(!ok)throw new Error('Save the Bella preference before warmup.');
        return fetch('/api/companion/speech/warm', { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId }) });
      })
        .then(response=>{if(!response.ok)throw new Error(`Bella warmup failed (${response.status}).`);return response.json();})
        .then(() => setPreferenceNote('Bella is warming in the background. Use Play reply after it is ready.'))
        .catch(e => setPreferenceNote(e instanceof Error ? e.message : 'Bella warmup is unavailable.'));
    }
  };
  const localVoices = voices;
  const currentVoice = localVoices.find(item => item.voiceURI === settings.voice) ?? localVoices[0];
  const manualPlay = () => {
    const playWindowsAudio = () => {
      const ready = windowsAudioReady.current;
      const audio = audioRef.current;
      const token = requestRef.current;
      const ownerSession = sessionId;
      const ownerReplyKey = replyKey;
      const ownerContext = ownershipKey;
      if (!audio || !ready) return;
      const stillOwnsPlayback = () => token === requestRef.current
        && sessionRef.current === ownerSession
        && replyKeyRef.current === ownerReplyKey
        && ownershipRef.current === ownerContext
        && audioRef.current === audio
        && windowsAudioReady.current?.key === ready.key
        && windowsAudioReady.current?.source === ready.source;
      void audio.play().then(() => {
        if (!stillOwnsPlayback()) return;
        setDetail(null); setPhase('playing');
        if (ready?.source === 'reply') { lastAutoReply.current = ready.key; if (autoSpokenOwner) autoSpokenOwner.current = ready.key; }
      }).catch(() => {
        if (!stillOwnsPlayback()) return;
        setDetail('Windows local audio is ready. Click Play reply to try again.'); setPhase('error');
      });
    };
    if (phase === 'playing') {
      if (settings.mode === 'fast_local' && localEngineRef.current === 'browser') { window.speechSynthesis.pause(); setPhase('paused'); }
      else { audioRef.current?.pause(); setPhase('paused'); }
    } else if (phase === 'paused') {
      if (settings.mode === 'fast_local' && localEngineRef.current === 'browser') { window.speechSynthesis.resume(); setPhase('playing'); }
      else {
        const audio = audioRef.current;
        const token = requestRef.current;
        const ownerSession = sessionId;
        const ownerReplyKey = replyKey;
        const ownerContext = ownershipKey;
        if (audio) void audio.play().then(() => {
          if (token === requestRef.current && sessionRef.current === ownerSession
              && replyKeyRef.current === ownerReplyKey && ownershipRef.current === ownerContext
              && audioRef.current === audio) setPhase('playing');
        }).catch(() => {
          if (token === requestRef.current && sessionRef.current === ownerSession
              && replyKeyRef.current === ownerReplyKey && ownershipRef.current === ownerContext
              && audioRef.current === audio) {
            setDetail('Audio playback was blocked. Click Play reply again after interacting with this page.'); setPhase('error');
          }
        });
      }
    } else if (activeLocalEngine === 'windows_sapi' && windowsAudioReady.current) playWindowsAudio();
    else void speak(text, replyKey, 'manual');
  };

  const controls = <section className="companion-speech" aria-label="Companion audio settings">
    <label htmlFor={`${titleId}-speech-mode`}>Companion audio</label>
    <select id={`${titleId}-speech-mode`} value={settings.mode} onChange={event => persistSelection(event.target.value as SpeechMode)}>
      <option value="fast_local">Fast local</option><option value="bella">Bella quality</option><option value="muted">Muted</option>
    </select>
    {settings.mode !== 'muted' && !settings.enabled && <button type="button" onClick={enable}><Volume2 size={14} aria-hidden="true"/>Enable companion audio</button>}
    {settings.mode === 'fast_local' && settings.enabled && <>
      <label htmlFor={`${titleId}-fast-voice`}>Local English voice</label>
      <select id={`${titleId}-fast-voice`} value={currentVoice?.voiceURI ?? ''} onChange={event => { stop(); try { localStorage.removeItem(localEngineKey(sessionId)); } catch { /* Capability memory is optional. */ } const next={...settings,voice:event.target.value};void persist(next); }}>
        {localVoices.map(voice=><option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} · {voice.lang} · local</option>)}
      </select>
      {!localVoices.length && <p role="status">Waiting for an installed local English voice. Remote voices are not used by Fast local.</p>}
    </>}
    {settings.mode === 'bella' && settings.enabled && <>
      <label htmlFor={`${titleId}-bella-voice`}>Bella voice</label>
      <select id={`${titleId}-bella-voice`} value={settings.voice} onChange={event=>void persist({...settings,voice:event.target.value})}>{(status?.voices?.length?status.voices:['Bella','Jasper','Luna','Bruno','Rosie','Hugo','Kiki','Leo']).map(voice=><option key={voice} value={voice}>{voice}</option>)}</select>
      <label htmlFor={`${titleId}-bella-speed`}>Speaking speed</label>
      <select id={`${titleId}-bella-speed`} value={String(settings.speed)} onChange={event=>void persist({...settings,speed:Number(event.target.value)})}><option value="0.8">Slower</option><option value="1">Normal</option><option value="1.2">Faster</option></select>
    </>}
    {settings.enabled && settings.mode !== 'muted' && <label><input type="checkbox" checked={settings.auto} onChange={event=>void persist({...settings,auto:event.target.checked})}/> Speak new replies and safe checkpoints automatically</label>}
    <div className="companion-speech-actions">
      <button type="button" onClick={manualPlay} disabled={!text.trim() || quiet || settings.mode==='muted' || !settings.enabled || phase==='preparing'}>{phase==='playing'?<Pause size={14}/>:<Play size={14}/>} {phase==='playing'?'Pause':phase==='paused'?'Resume':'Play reply'}</button>
      <button type="button" onClick={()=>{stop();onStop?.();}} disabled={phase==='idle' || phase==='error'}><Square size={14}/> Stop</button>
    </div>
    <p className="companion-speech-note" role="status" aria-live="polite">{quiet?'Audio is paused during a scored or timed response window.':phase==='preparing'?detail??'Preparing the selected voice…':phase==='playing'?settings.mode==='fast_local'?(activeLocalEngine==='windows_sapi'?'Speaking with the local Windows voice.':`Speaking with local English voice ${currentVoice?.name??''}.`):'Speaking with Bella.':phase==='paused'?'Paused.':phase==='error'?detail??'Voice unavailable. The complete written reply remains available.':settings.mode==='muted'?'Muted. Replies remain written.':settings.enabled?settings.mode==='bella'?`Bella quality · ${status?.model??'local model'}${status&&!status.loaded?' · first use may take longer':''}`:`Fast local · ${currentVoice?.name??'waiting for a local English voice'}`:'Audio is off until you explicitly enable it.'}</p>
    {preferenceNote && <p role="status">{preferenceNote}</p>}
  </section>;
  return visible && controlsHost ? createPortal(controls, controlsHost) : null;
}
