import { useEffect, useState } from 'react';
import memoryScene from './assets/scene34.png';
import reasoningScene from './assets/scene35.png';
import attentionScene from './assets/scene36.png';
import flexibilityScene from './assets/scene37.png';
import planningScene from './assets/scene38.png';
import memoryPlain from './assets/prepared/memory-tile-plain.png';
import memoryGold from './assets/prepared/memory-tile-gold.png';
import memoryTeal from './assets/prepared/memory-tile-teal.png';
import attentionLens from './assets/prepared/attention-porthole.png';
import attentionDais from './assets/prepared/attention-dais.png';
import reasoningPlaque from './assets/prepared/reasoning-plaque-square.png';
import reasoningCrystal from './assets/prepared/reasoning-crystal-cutout.png';
import flexibilityA from './assets/prepared/flexibility-plaque-a.png';
import flexibilityB from './assets/prepared/flexibility-plaque-b.png';
import flexibilityWide from './assets/prepared/flexibility-plaque-wide.png';
import parcel from './assets/prepared/hybrid-parcel.png';
import tray from './assets/prepared/hybrid-tray.png';
import boatBlue from './assets/prepared/harbor-boat-blue.png';
import boatRed from './assets/prepared/harbor-boat-red.png';
import harborGate from './assets/prepared/harbor-gate.png';
import archiveSlab from './assets/prepared/reasoning-slab.png';
import archiveBracket from './assets/prepared/reasoning-bracket.png';
import archiveCrystal from './assets/prepared/reasoning-crystal-blue.png';

const ART: Record<string, readonly string[]> = {
  'EX-01': [memoryScene, memoryPlain, memoryGold, memoryTeal],
  'EX-02': [reasoningScene, reasoningPlaque, reasoningCrystal],
  'EX-03': [attentionScene, attentionLens, attentionDais],
  'EX-04': [flexibilityScene, flexibilityA, flexibilityB, flexibilityWide],
  'EX-05': [planningScene],
  'HY-02': [attentionScene, attentionLens, attentionDais],
  'HY-01': [planningScene],
  'HY-03': [flexibilityScene, memoryTeal, parcel, tray],
  'HY-04': [attentionScene, boatBlue, boatRed, harborGate],
  'HY-05': [reasoningScene, archiveSlab, archiveBracket, archiveCrystal],
  'HY-06': [planningScene, attentionDais],
};
const decoded = new Map<string, Promise<void>>();

/** Decode local approved art before mounting a task's cue/timing state machine. */
function prepare(url: string): Promise<void> {
  const cached = decoded.get(url);
  if (cached) return cached;
  const promise = new Promise<void>((resolve, reject) => {
    const asset = new Image();
    const timer = window.setTimeout(() => fail(), 20000);
    const fail = () => { window.clearTimeout(timer); decoded.delete(url); reject(new Error('Local scene artwork could not be loaded.')); };
    asset.onerror = fail;
    asset.onload = () => {
      void asset.decode().then(() => { window.clearTimeout(timer); resolve(); }, fail);
    };
    asset.src = url;
  });
  decoded.set(url, promise);
  return promise;
}

export function useGameArt(activityId: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ id: string; status: 'loading' | 'ready' | 'error' }>({ id: activityId, status: 'loading' });
  useEffect(() => {
    let live = true;
    setState({ id: activityId, status: 'loading' });
    void Promise.all((ART[activityId] ?? []).map(prepare)).then(
      () => { if (live) setState({ id: activityId, status: 'ready' }); },
      () => { if (live) setState({ id: activityId, status: 'error' }); },
    );
    return () => { live = false; };
  }, [activityId, attempt]);
  return { status: state.id === activityId ? state.status : 'loading', retry: () => setAttempt(value => value + 1) } as const;
}
