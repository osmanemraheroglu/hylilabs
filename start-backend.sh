#!/bin/bash
cd /var/www/hylilabs/api
exec uvicorn main:app --host 0.0.0.0 --port 8000
