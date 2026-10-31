// Explicit isolated-QA instrumentation. Imported only by vite.luna.qa.config.mjs.
// It never changes application data or runs in the production bundle.
import http from 'node:http';
import { createHash } from 'node:crypto';

export function qaFaults(target = 'http://127.0.0.1:8031') {
  const upstream = new URL(target);
  if (upstream.hostname !== '127.0.0.1' || upstream.port !== '8031') throw new Error('QA target must be the owned isolated API');
  let armed = [];
  const hits = [];
  const requests = [];
  return {
    name: 'isolated-qa-faults',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/__qa/faults') {
          if (req.method === 'GET') {
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ armed, hits, requests }));
            return;
          }
          if (req.method !== 'POST') { res.statusCode = 405; res.end(); return; }
          let raw = '';
          req.on('data', chunk => { raw += chunk; if (raw.length > 10000) req.destroy(); });
          req.on('end', () => {
            try {
              const body = JSON.parse(raw);
              if (!Array.isArray(body.faults)) throw new Error('faults must be an array');
              armed = body.faults.map(item => {
                if (!['GET', 'POST'].includes(item.method) || !String(item.path).startsWith('/api/')) throw new Error('invalid QA route');
                if (!['reject', 'drop_after_accept', 'delay'].includes(item.action)) throw new Error('invalid QA fault');
                return { id: String(item.id), method: item.method, path: item.path, action: item.action,
                  remaining: Math.max(1, Math.min(10, Number(item.count ?? 1))), delayMs: Math.max(0, Math.min(10000, Number(item.delayMs ?? 1500))) };
              });
              if (body.clearHits) { hits.length = 0; requests.length = 0; }
              res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ armed }));
            } catch (error) { res.statusCode = 400; res.end(JSON.stringify({ detail: error.message })); }
          });
          return;
        }
        if (req.url.startsWith('/api/')) {
          const receipt = { method: req.method, path: req.url, at: new Date().toISOString() };
          requests.push(receipt); if (requests.length > 500) requests.shift();
          if (req.method === 'POST') {
            const digest = createHash('sha256'); let bytes = 0;
            req.on('data', chunk => { digest.update(chunk); bytes += chunk.length; });
            req.on('end', () => { receipt.bodySha256 = digest.digest('hex'); receipt.bodyBytes = bytes; });
          }
          res.on('finish', () => { receipt.status = res.statusCode; });
        }
        const fault = armed.find(item => item.remaining > 0 && item.method === req.method && req.url.startsWith(item.path));
        if (!fault) return next();
        fault.remaining -= 1;
        const hit = { id: fault.id, method: req.method, path: req.url, action: fault.action, at: new Date().toISOString() };
        hits.push(hit); if (hits.length > 200) hits.shift();
        if (fault.action === 'reject') {
          res.statusCode = 503; res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ detail: `Isolated QA injected failure: ${fault.id}` })); return;
        }
        if (fault.action === 'delay') { setTimeout(next, fault.delayMs); return; }
        const forwarded = http.request({ hostname: upstream.hostname, port: upstream.port, path: req.url,
          method: req.method, headers: { ...req.headers, host: upstream.host } }, response => {
          hit.backendStatus = response.statusCode;
          let bytes = 0; response.on('data', chunk => { bytes += chunk.length; });
          response.on('end', () => { hit.backendBytes = bytes; hit.backendCompleted = true; res.destroy(); });
        });
        forwarded.on('error', () => { hit.upstreamError = true; res.destroy(); });
        req.pipe(forwarded);
      });
    },
  };
}
