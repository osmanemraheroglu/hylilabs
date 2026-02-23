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
