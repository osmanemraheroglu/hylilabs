#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp /var/www/hylilabs/api/data/talentflow.db /var/www/hylilabs/backups/talentflow_$DATE.db
find /var/www/hylilabs/backups -name "*.db" -mtime +7 -delete
echo "Backup completed: $DATE" >> /var/www/hylilabs/backups/backup.log
