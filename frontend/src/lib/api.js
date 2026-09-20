import axios from 'axios';

/**
 * Single axios instance for the FastAPI backend. Vite proxies /api to :8000 in
 * development, so no base URL is needed there.
 */
const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

const TOKEN_KEY = 'rishforge_token';
const USER_KEY = 'rishforge_user';

export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  user: () => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  },
  save: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

client.interceptors.request.use((config) => {
  const token = auth.token();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      // Expired or rejected session — drop it so the router falls back to login
      // rather than looping on requests that will keep failing.
      auth.clear();
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    const detail = error.response?.data?.detail;
    error.friendlyMessage =
      typeof detail === 'string'
        ? detail
        : status === 403
          ? 'Your role does not permit this action.'
          : status === 503
            ? 'The risk engine has no computed results yet. Run the pipeline first.'
            : error.code === 'ECONNABORTED'
              ? 'The request timed out.'
              : 'Could not reach the risk engine.';
    return Promise.reject(error);
  }
);

export const api = {
  login: (email, password, rememberMe) =>
    client.post('/api/v1/auth/login', { email, password, remember_me: rememberMe }).then((r) => r.data),
  me: () => client.get('/api/v1/auth/me').then((r) => r.data),

  dashboard: () => client.get('/api/v1/dashboard').then((r) => r.data),

  riskAnalysis: () => client.get('/api/v1/risk/analysis').then((r) => r.data),
  businessUnits: () => client.get('/api/v1/risk/business-units').then((r) => r.data),
  lossCurve: () => client.get('/api/v1/risk/loss-curve').then((r) => r.data),

  vulnerabilities: (params) =>
    client.get('/api/v1/threats/vulnerabilities', { params }).then((r) => r.data),
  threatActors: (params) => client.get('/api/v1/threats/actors', { params }).then((r) => r.data),

  scenarioControls: () => client.get('/api/v1/scenarios/controls').then((r) => r.data),
  precomputedScenarios: () =>
    client.get('/api/v1/scenarios/precomputed').then((r) => r.data),
  simulate: (controlIds) =>
    client.post('/api/v1/scenarios/simulate', { control_ids: controlIds }).then((r) => r.data),

  compliance: () => client.get('/api/v1/compliance').then((r) => r.data),

  optimize: (budget) =>
    client.post('/api/v1/investment/optimize', { budget }).then((r) => r.data),
  frontier: () => client.get('/api/v1/investment/frontier').then((r) => r.data),

  network: (limit = 120) =>
    client.get('/api/v1/network', { params: { limit } }).then((r) => r.data),

  remediation: (limit = 25) =>
    client.get('/api/v1/remediation', { params: { limit } }).then((r) => r.data),
  remediationBacklog: () => client.get('/api/v1/remediation/backlog').then((r) => r.data),

  reports: () => client.get('/api/v1/reports').then((r) => r.data),
  generateReport: (reportType, format = 'markdown') =>
    client.post('/api/v1/reports/generate', { report_type: reportType, format }).then((r) => r.data),

  ask: (question) => client.post('/api/v1/ask', { question }).then((r) => r.data),
  recommendations: () => client.get('/api/v1/recommendations').then((r) => r.data),
  insightHistory: (limit = 25) =>
    client.get('/api/v1/insights/history', { params: { limit } }).then((r) => r.data),

  alerts: (unacknowledgedOnly = false) =>
    client
      .get('/api/v1/alerts', { params: { unacknowledged_only: unacknowledgedOnly } })
      .then((r) => r.data),
  ackAlert: (id) => client.post(`/api/v1/alerts/${id}/ack`).then((r) => r.data),

  pipelineStatus: () => client.get('/api/v1/pipeline/status').then((r) => r.data),
  recompute: (mode = 'incremental') =>
    client.post('/api/v1/pipeline/recompute', null, { params: { mode, force: true } }).then((r) => r.data),
  auditLog: () => client.get('/api/v1/pipeline/audit-log').then((r) => r.data),
};

export default client;
