/**
 * Standalone mock of the Java gateway, for developing or demoing the frontend
 * without running the Java and Python services. Serves the real pipeline output
 * from RiskEngine/outputs when present.
 *
 *   node mock-server.mjs      then    npm run dev
 */
import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, '..', 'RiskEngine', 'outputs');
const PORT = 8080;

const read = (f) => (existsSync(join(OUT, f)) ? JSON.parse(readFileSync(join(OUT, f), 'utf8')) : null);

const server = createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const send = (code, body) => {
    res.writeHead(code, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    });
    res.end(JSON.stringify(body));
  };

  if (req.method === 'OPTIONS') return send(204, {});

  const graph = read('graph_data.json');
  const p = url.pathname;

  if (p === '/api/v1/auth/login') {
    return send(200, { accessToken: 'mock-token', tokenType: 'Bearer', role: 'ADMIN', expiresInMinutes: 60 });
  }
  if (p === '/api/v1/riskengine/dashboard') {
    return graph ? send(200, graph) : send(503, { message: 'graph_data.json not generated yet' });
  }
  if (p === '/api/v1/riskengine/business-units') {
    return send(200, graph?.business_unit_risk?.by_business_unit ?? []);
  }
  if (p === '/api/v1/riskengine/scenarios') {
    return send(200, graph?.what_if_scenarios ?? []);
  }
  if (p === '/api/v1/riskengine/attack-paths') {
    return send(200, graph?.attack_paths ?? {});
  }
  if (p === '/api/v1/riskengine/compliance/report') {
    return send(200, read('compliance_report.json') ?? { message: 'not generated' });
  }
  if (p === '/api/v1/riskengine/ask') {
    return send(200, {
      answer: 'Mock server: run the Python engine for real answers.',
      mode: 'deterministic',
      context_used: [],
    });
  }
  return send(404, { message: `No mock route for ${p}` });
});

server.listen(PORT, () => console.log(`Mock gateway on http://localhost:${PORT}`));
