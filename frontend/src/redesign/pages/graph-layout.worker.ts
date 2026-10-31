import type { EvidenceGraphEdge, EvidenceGraphNode } from './EvidencePage';

type Position = { x: number; y: number };
type LayoutMessage = {
  type: 'layout'; requestId: number; nodes: EvidenceGraphNode[]; edges: EvidenceGraphEdge[];
  previous?: Record<string, Position>; reducedMotion?: boolean;
};
type WorkerMessage = { type: 'positions'; requestId: number; positions: Record<string, Position> };
const previousPositions = new Map<string, Position>();
let activeRequest = 0;

function hash(text: string): number {
  let result = 2166136261;
  for (let i = 0; i < text.length; i += 1) result = Math.imul(result ^ text.charCodeAt(i), 16777619);
  return result >>> 0;
}

self.onmessage = (event: MessageEvent<LayoutMessage>) => {
  const message = event.data;
  if (message.type !== 'layout') return;
  activeRequest = message.requestId;
  const requestId = activeRequest;
  const nodes = message.nodes.slice(0, 5000);
  const nodeIds = nodes.map(node => node.id);
  const indices = new Map(nodeIds.map((id, index) => [id, index]));
  const count = nodes.length;
  const x = new Float32Array(count); const y = new Float32Array(count);
  const vx = new Float32Array(count); const vy = new Float32Array(count);
  const pinned = new Uint8Array(count);
  for (let i = 0; i < count; i += 1) {
    const node = nodes[i];
    const previous = message.previous?.[node.id] ?? previousPositions.get(node.id);
    if (previous && Number.isFinite(previous.x) && Number.isFinite(previous.y)) {
      x[i] = previous.x; y[i] = previous.y; pinned[i] = 1;
    } else {
      const angle = i * 2.399963229728653 + (hash(node.id) % 997) / 997;
      const radius = 60 + Math.sqrt((i + .5) / Math.max(1, count)) * 440;
      x[i] = 600 + Math.cos(angle) * radius;
      y[i] = 450 + Math.sin(angle) * radius * .72;
    }
  }
  const links: Array<[number, number]> = [];
  for (const edge of message.edges.slice(0, 30000)) {
    const source = indices.get(edge.source); const target = indices.get(edge.target);
    if (source !== undefined && target !== undefined && source !== target) links.push([source, target]);
  }
  const iterations = message.reducedMotion ? 18 : 54;
  let iteration = 0;
  const step = () => {
    if (requestId !== activeRequest) return;
    const buckets = new Map<string, number[]>();
    for (let i = 0; i < count; i += 1) {
      const key = `${Math.floor(x[i] / 90)},${Math.floor(y[i] / 90)}`;
      const bucket = buckets.get(key); if (bucket) bucket.push(i); else buckets.set(key, [i]);
    }
    const fx = new Float32Array(count); const fy = new Float32Array(count);
    for (let i = 0; i < count; i += 1) {
      if (pinned[i]) continue;
      fx[i] += (600 - x[i]) * .0018; fy[i] += (450 - y[i]) * .0018;
      const cx = Math.floor(x[i] / 90); const cy = Math.floor(y[i] / 90);
      for (let dx = -1; dx <= 1; dx += 1) for (let dy = -1; dy <= 1; dy += 1) {
        const peers = buckets.get(`${cx + dx},${cy + dy}`) ?? [];
        for (const j of peers) {
          if (j <= i) continue;
          let ax = x[i] - x[j]; let ay = y[i] - y[j];
          const distance2 = ax * ax + ay * ay;
          if (distance2 === 0 || distance2 > 8100) continue;
          const distance = Math.sqrt(distance2); const force = 1550 / distance2;
          ax = ax / distance * force; ay = ay / distance * force;
          fx[i] += ax; fy[i] += ay; fx[j] -= ax; fy[j] -= ay;
        }
      }
    }
    for (const [a, b] of links) {
      let dx = x[b] - x[a]; let dy = y[b] - y[a];
      const distance = Math.max(1, Math.hypot(dx, dy));
      const force = (distance - 210) * .0045;
      dx = dx / distance * force; dy = dy / distance * force;
      if (!pinned[a]) { fx[a] += dx; fy[a] += dy; }
      if (!pinned[b]) { fx[b] -= dx; fy[b] -= dy; }
    }
    const cooling = 1 - iteration / iterations;
    for (let i = 0; i < count; i += 1) {
      if (pinned[i]) continue;
      vx[i] = (vx[i] + fx[i] * cooling) * .78;
      vy[i] = (vy[i] + fy[i] * cooling) * .78;
      x[i] = Math.max(40, Math.min(1160, x[i] + vx[i]));
      y[i] = Math.max(40, Math.min(860, y[i] + vy[i]));
    }
    iteration += 1;
    if (iteration < iterations) { setTimeout(step, 0); return; }
    const positions: Record<string, Position> = {};
    for (let i = 0; i < count; i += 1) {
      const pos = { x: x[i], y: y[i] }; positions[nodeIds[i]] = pos; previousPositions.set(nodeIds[i], pos);
    }
    postMessage({ type: 'positions', requestId, positions } satisfies WorkerMessage);
  };
  step();
};

