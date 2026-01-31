import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  integrations: [react(), tailwind()],
  output: 'static',
  server: {
    port: 4321, // Changed from 3000 to avoid conflict with FalkorDB
    host: true,
  },
  vite: {
    optimizeDeps: {
      include: ['react-markdown', 'remark-parse', 'unified'],
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path,
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path,
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.log('WebSocket proxy error:', err.message);
            });
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log('Proxying WebSocket request:', req.url);
            });
            proxy.on('open', (proxySocket) => {
              console.log('WebSocket proxy connection opened');
              proxySocket.on('error', (err) => {
                console.error('WebSocket proxy socket error:', err.message);
              });
            });
          },
        },
      },
    },
    ssr: {
      noExternal: ['@tanstack/react-query'],
    },
    build: {
      // Production optimizations
      minify: 'esbuild',
      cssMinify: true,
      rollupOptions: {
        output: {
          manualChunks: {
            // Vendor chunking for better caching
            'react-vendor': ['react', 'react-dom'],
            'd3-vendor': ['d3'],
            'ui-vendor': ['lucide-react', 'zustand'],
          },
        },
      },
    },
  },
  // Production build configuration
  compressHTML: true,
  build: {
    inlineStylesheets: 'auto',
  },
});
