import path from 'path';
import fs from 'fs';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const projectRoot = path.resolve(__dirname, '..');

export default defineConfig(({ mode }) => {
  // Load from repo root (local dev) and from frontend dir (Docker: .env mounted at /app/.env)
  const fileEnv = { ...loadEnv(mode, projectRoot, ''), ...loadEnv(mode, __dirname, '') };
  // Merge process.env so Docker env_file vars are available when no .env file is present
  const env: Record<string, string> = { ...fileEnv };
  for (const key of Object.keys(process.env)) {
    if (key.startsWith('VITE_')) env[key] = process.env[key] ?? '';
  }
  const apiTarget = env.VITE_PROXY_TARGET || process.env.VITE_PROXY_TARGET || 'http://localhost:8000';
  return {
    root: __dirname,
    envDir: projectRoot,
    publicDir: 'public',
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
    plugins: [
      react(),
      {
        name: 'favicon-ico',
        configureServer(server) {
          server.middlewares.use((req, res, next) => {
            if (req.url === '/favicon.ico' && req.method === 'GET') {
              const svgPath = path.join(__dirname, 'public', 'favicon.svg');
              if (fs.existsSync(svgPath)) {
                res.setHeader('Content-Type', 'image/svg+xml');
                res.end(fs.readFileSync(svgPath));
                return;
              }
            }
            next();
          });
        },
      },
    ],
    envPrefix: ['VITE_'],
    // Do not bake backend API keys (e.g. Gemini) into the frontend bundle; the API is the only consumer.
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
  };
});
