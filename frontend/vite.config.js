import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Bind all interfaces, not just IPv6 [::1]. Without this the dev server is
    // reachable on localhost but not 127.0.0.1, and not from another machine —
    // which the endpoint-agent demo needs.
    host: true,
    proxy: {
      // Everything goes through the Java gateway on :8080, which serves the
      // platform's own resources under /api/v1/platform and transparently
      // relays every other /api/v1 route to the Python engine on :8000.
      // Pointing this straight at :8000 still works, but bypasses the gateway.
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
