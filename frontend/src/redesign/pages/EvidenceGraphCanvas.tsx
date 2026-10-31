import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent, WheelEvent } from 'react';
import type { EvidenceGraphEdge, EvidenceGraphNode } from './EvidencePage';

type Point = { x: number; y: number };
type Camera = { x: number; y: number; scale: number };
type Props = {
  nodes: EvidenceGraphNode[]; edges: EvidenceGraphEdge[]; selectedId: string | null;
  reduceMotion: boolean; onSelect: (id: string) => void;
};
const WORLD = { width: 1200, height: 900 };

function nodeColor(node: EvidenceGraphNode): string {
  const properties = node.properties ?? {};
  if (properties.brain === 'knowledge') return '#7892b2';
  const dimension = String(properties.dimension ?? properties.dimension_id ?? '');
  if (dimension === 'reasoning') return '#dfa644';
  if (dimension === 'planning') return '#4b9b85';
  if (dimension === 'working_memory') return '#688bd2';
  if (dimension === 'flexibility') return '#a17bc2';
  if (dimension === 'attention_inhibition') return '#d87962';
  return '#4f83db';
}

export function EvidenceGraphCanvas({ nodes, edges, selectedId, reduceMotion, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const positionsRef = useRef<Record<string, Point>>({});
  const cameraRef = useRef<Camera>({ x: 0, y: 0, scale: 1 });
  const pointerRef = useRef<{ id: number; mode: 'pan' | 'node'; nodeId?: string; lastX: number; lastY: number; moved: boolean } | null>(null);
  const pinnedRef = useRef(new Set<string>());
  const hoverRef = useRef<string | null>(null);
  const nodeMapRef = useRef(new Map<string, EvidenceGraphNode>());
  const nodeMap = useMemo(() => new Map(nodes.map(node => [node.id, node])), [nodes]);
  const edgesRef = useRef(edges);
  const adjacency = useMemo(() => {
    const neighbors = new Map<string, Set<string>>();
    for (const edge of edges) {
      if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
      if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
      neighbors.get(edge.source)!.add(edge.target);
      neighbors.get(edge.target)!.add(edge.source);
    }
    return neighbors;
  }, [edges]);
  const [layoutRevision, setLayoutRevision] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [announcement, setAnnouncement] = useState('Graph ready. Use the node list below for keyboard selection.');
  const drawFrameRef = useRef<number | null>(null);
  nodeMapRef.current = nodeMap;
  edgesRef.current = edges;

  useEffect(() => {
    const worker = new Worker(new URL('./graph-layout.worker.ts', import.meta.url), { type: 'module' });
    const requestId = Date.now();
    worker.onmessage = (event: MessageEvent<{ type: string; requestId: number; positions: Record<string, Point> }>) => {
      if (event.data.requestId !== requestId) return;
      positionsRef.current = { ...positionsRef.current, ...event.data.positions };
      pinnedRef.current.clear();
      setLayoutRevision(value => value + 1);
      setAnnouncement(`Layout ready: ${nodes.length.toLocaleString()} nodes and ${edges.length.toLocaleString()} relationships.`);
    };
    worker.postMessage({ type: 'layout', requestId, nodes, edges, previous: positionsRef.current, reducedMotion: reduceMotion });
    return () => { worker.terminate(); };
  }, [nodes, edges, reduceMotion]);

  const fit = useCallback(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const bounds = canvas.getBoundingClientRect();
    const scale = Math.min(bounds.width / WORLD.width, bounds.height / WORLD.height) * .92;
    cameraRef.current = { x: (bounds.width - WORLD.width * scale) / 2, y: (bounds.height - WORLD.height * scale) / 2, scale };
    setZoom(scale);
    setLayoutRevision(value => value + 1);
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const bounds = canvas.getBoundingClientRect(); const ctx = canvas.getContext('2d'); if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(bounds.width * dpr) || canvas.height !== Math.round(bounds.height * dpr)) {
      canvas.width = Math.round(bounds.width * dpr); canvas.height = Math.round(bounds.height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, bounds.width, bounds.height);
    const camera = cameraRef.current;
    ctx.save(); ctx.translate(camera.x, camera.y); ctx.scale(camera.scale, camera.scale);
    const selected = selectedId; const hover = hoverRef.current;
    const focus = hover ?? selected;
    const related = new Set<string>(); if (focus) related.add(focus);
    if (focus) for (const neighbor of adjacency.get(focus) ?? []) related.add(neighbor);
    // Edges in each visual state share one path and one stroke. This avoids
    // tens of thousands of individual Canvas stroke calls on large maps.
    const coldEdgesPath = new Path2D();
    const hotEdgesPath = focus ? new Path2D() : null;
    let hasColdEdges = false; let hasHotEdges = false;
    for (const edge of edgesRef.current) {
      const a = positionsRef.current[edge.source]; const b = positionsRef.current[edge.target]; if (!a || !b) continue;
      if (focus && (edge.source === focus || edge.target === focus)) {
        hotEdgesPath!.moveTo(a.x, a.y); hotEdgesPath!.lineTo(b.x, b.y); hasHotEdges = true;
      } else {
        coldEdgesPath.moveTo(a.x, a.y); coldEdgesPath.lineTo(b.x, b.y); hasColdEdges = true;
      }
    }
    if (hasColdEdges) {
      ctx.strokeStyle = '#526d84'; ctx.globalAlpha = focus ? .16 : .34;
      ctx.lineWidth = 1.2; ctx.stroke(coldEdgesPath);
    }
    if (hasHotEdges) { ctx.strokeStyle = '#c88a2e'; ctx.globalAlpha = .78; ctx.lineWidth = 2.4; ctx.stroke(hotEdgesPath!); }
    ctx.globalAlpha = 1;
    const labelNodes = nodes.length <= 40;
    for (const node of nodes) {
      const position = positionsRef.current[node.id]; if (!position) continue;
      const active = node.id === selected || node.id === hover;
      const dim = focus && !related.has(node.id) && node.id !== selected;
      ctx.globalAlpha = dim ? .2 : 1;
      // Ordinary records stay compact so every canonical node remains part of
      // the live graph. The focused record borrows the reference's ivory/brass
      // medallion treatment without adding illustrative or synthetic nodes.
      if (active) {
        const radius = 39 / camera.scale;
        ctx.save(); ctx.shadowColor = '#142e423d'; ctx.shadowBlur = 15 / camera.scale; ctx.shadowOffsetY = 4 / camera.scale;
        ctx.beginPath(); ctx.arc(position.x, position.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = '#fff8e8'; ctx.fill(); ctx.strokeStyle = '#b78331'; ctx.lineWidth = 2.2 / camera.scale; ctx.stroke();
        ctx.restore();
        ctx.beginPath(); ctx.arc(position.x, position.y, 31 / camera.scale, 0, Math.PI * 2);
        ctx.fillStyle = '#fffdf7'; ctx.fill(); ctx.strokeStyle = '#e5c77f'; ctx.lineWidth = 1 / camera.scale; ctx.stroke();
        ctx.beginPath(); ctx.arc(position.x, position.y, 3.6 / camera.scale, 0, Math.PI * 2);
        ctx.fillStyle = nodeColor(node); ctx.fill();
        // Four small brass points echo the approved medallions at any zoom.
        for (const [dx, dy] of [[0, -36], [36, 0], [0, 36], [-36, 0]]) {
          const x = position.x + dx / camera.scale; const y = position.y + dy / camera.scale;
          ctx.save(); ctx.translate(x, y); ctx.rotate(Math.PI / 4);
          ctx.fillStyle = '#c39142'; ctx.fillRect(-2.3 / camera.scale, -2.3 / camera.scale, 4.6 / camera.scale, 4.6 / camera.scale); ctx.restore();
        }
        const title = node.label.length > 18 ? node.label.trim().split(/\s+/)[0] : node.label;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#253147';
        ctx.font = `700 ${9 / camera.scale}px system-ui, sans-serif`;
        ctx.fillText(title, position.x, position.y - 7 / camera.scale, 56 / camera.scale);
        ctx.font = `${6 / camera.scale}px system-ui, sans-serif`; ctx.fillStyle = '#647184';
        const typeLabel = String(node.properties?.dimension ?? node.properties?.dimension_id ?? node.type)
          .replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
        const subtitle = typeLabel.toLowerCase() === title.toLowerCase() ? 'selected record' : typeLabel;
        ctx.fillText(subtitle, position.x, position.y + 7 / camera.scale, 56 / camera.scale);
        ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      } else {
        ctx.beginPath(); ctx.arc(position.x, position.y, 8.5 / camera.scale, 0, Math.PI * 2);
        ctx.fillStyle = '#fff9eb'; ctx.fill(); ctx.strokeStyle = '#bd8a38'; ctx.lineWidth = 1.25 / camera.scale; ctx.stroke();
        ctx.beginPath(); ctx.arc(position.x, position.y, 5.2 / camera.scale, 0, Math.PI * 2);
        ctx.fillStyle = nodeColor(node); ctx.fill();
      }
      if ((labelNodes && !active) || (!active && hover && related.has(node.id))) {
        const label = node.label.length > 26 ? `${node.label.slice(0, 25)}…` : node.label;
        ctx.font = `600 ${10 / camera.scale}px system-ui, sans-serif`;
        const textWidth = ctx.measureText(label).width; const x = position.x + 12 / camera.scale; const y = position.y - 7 / camera.scale;
        ctx.fillStyle = '#fffaf0ed'; ctx.beginPath(); ctx.roundRect(x - 3 / camera.scale, y - 10 / camera.scale, textWidth + 7 / camera.scale, 14 / camera.scale, 4 / camera.scale); ctx.fill();
        ctx.strokeStyle = '#c391424d'; ctx.lineWidth = .65 / camera.scale; ctx.stroke();
        ctx.fillStyle = '#253147'; ctx.fillText(label, x, y);
      }
    }
    ctx.globalAlpha = 1; ctx.restore();
  }, [nodes, selectedId, layoutRevision, adjacency]);

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const observer = new ResizeObserver(() => { fit(); draw(); }); observer.observe(canvas);
    draw(); return () => observer.disconnect();
  }, [draw, fit]);
  useEffect(() => { draw(); }, [draw, layoutRevision, selectedId]);

  const scheduleDraw = useCallback(() => {
    if (drawFrameRef.current !== null) return;
    drawFrameRef.current = requestAnimationFrame(() => { drawFrameRef.current = null; draw(); });
  }, [draw]);

  useEffect(() => () => { if (drawFrameRef.current !== null) cancelAnimationFrame(drawFrameRef.current); }, []);

  const toWorld = (clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect(); if (!rect) return { x: 0, y: 0 };
    const camera = cameraRef.current;
    return { x: (clientX - rect.left - camera.x) / camera.scale, y: (clientY - rect.top - camera.y) / camera.scale };
  };
  const hitTest = (clientX: number, clientY: number) => {
    const point = toWorld(clientX, clientY); let best: string | null = null; let bestDistance = 17 / cameraRef.current.scale;
    for (const node of nodes) {
      const pos = positionsRef.current[node.id]; if (!pos) continue;
      const distance = Math.hypot(pos.x - point.x, pos.y - point.y);
      if (distance < bestDistance) { best = node.id; bestDistance = distance; }
    }
    return best;
  };
  const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const nodeId = hitTest(event.clientX, event.clientY);
    pointerRef.current = { id: event.pointerId, mode: nodeId ? 'node' : 'pan', nodeId: nodeId ?? undefined,
      lastX: event.clientX, lastY: event.clientY, moved: false };
    if (nodeId) onSelect(nodeId);
    setAnnouncement(nodeId ? `Selected ${nodeMapRef.current.get(nodeId)?.label ?? nodeId}. Drag to pin and move.` : 'Panning graph.');
  };
  const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    const pointer = pointerRef.current;
    if (!pointer) { hoverRef.current = hitTest(event.clientX, event.clientY); scheduleDraw(); return; }
    const dx = event.clientX - pointer.lastX; const dy = event.clientY - pointer.lastY;
    if (Math.abs(dx) + Math.abs(dy) > 2) pointer.moved = true;
    pointer.lastX = event.clientX; pointer.lastY = event.clientY;
    if (pointer.mode === 'pan') { cameraRef.current.x += dx; cameraRef.current.y += dy; }
    else if (pointer.nodeId) {
      const pos = toWorld(event.clientX, event.clientY); positionsRef.current[pointer.nodeId] = pos; pinnedRef.current.add(pointer.nodeId);
    }
    scheduleDraw();
  };
  const onPointerUp = (event: PointerEvent<HTMLCanvasElement>) => {
    const pointer = pointerRef.current; if (!pointer || pointer.id !== event.pointerId) return;
    if (!pointer.moved && pointer.mode === 'node' && pointer.nodeId) onSelect(pointer.nodeId);
    pointerRef.current = null; scheduleDraw();
  };
  const onWheel = (event: WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault(); const rect = event.currentTarget.getBoundingClientRect();
    const px = event.clientX - rect.left; const py = event.clientY - rect.top; const camera = cameraRef.current;
    const worldX = (px - camera.x) / camera.scale; const worldY = (py - camera.y) / camera.scale;
    const next = Math.max(.25, Math.min(3.2, camera.scale * (event.deltaY < 0 ? 1.12 : .89)));
    camera.x = px - worldX * next; camera.y = py - worldY * next; camera.scale = next; setZoom(next); scheduleDraw();
  };
  const zoomBy = (multiplier: number) => {
    const canvas = canvasRef.current; if (!canvas) return;
    const rect = canvas.getBoundingClientRect(); const camera = cameraRef.current; const px = rect.width / 2; const py = rect.height / 2;
    const worldX = (px - camera.x) / camera.scale; const worldY = (py - camera.y) / camera.scale;
    const next = Math.max(.25, Math.min(3.2, camera.scale * multiplier));
    camera.x = px - worldX * next; camera.y = py - worldY * next; camera.scale = next; setZoom(next); scheduleDraw();
  };
  return <div className="evidence-graph-viewport">
    <canvas ref={canvasRef} className="evidence-graph-canvas" aria-label={`Interactive evidence map. ${nodes.length} visible nodes. Use the accessible node list to select records.`}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onWheel={onWheel} />
    <div className="evidence-graph-zoom" role="group" aria-label="Graph zoom controls">
      <button type="button" onClick={() => zoomBy(1.2)} aria-label="Zoom in">+</button>
      <span>{Math.round(zoom * 100)}%</span>
      <button type="button" onClick={() => zoomBy(.83)} aria-label="Zoom out">−</button>
      <button type="button" onClick={fit}>Fit</button>
    </div>
    <span className="evidence-sr-only" aria-live="polite">{announcement}</span>
  </div>;
}
