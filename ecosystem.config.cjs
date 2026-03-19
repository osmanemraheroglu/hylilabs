/**
 * PM2 ENV CACHE UYARISI
 * ====================
 * PM2, process baslatildiginda .env dosyasini CACHE'ler.
 * ENV degisikligi yapildiginda "pm2 restart" YETMEZ!
 *
 * Cozum: ./scripts/pm2-reload-env.sh kullan
 * veya:  pm2 delete <app> && pm2 start ecosystem.config.cjs --only <app>
 *
 * Detay: CLAUDE.md Kural #20
 */
module.exports = {
  apps: [
    {
      name: 'hylilabs-frontend',
      script: 'npx',
      args: 'vite preview --port 3000 --host',
      cwd: '/var/www/hylilabs',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000
    },
    {
      name: 'hylilabs-backend',
      script: 'uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000',
      cwd: '/var/www/hylilabs/api',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        PYTHONPATH: '/var/www/hylilabs/api/core:/var/www/hylilabs/api'
      }
    }
  ]
}
