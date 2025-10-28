#!/bin/bash
# 0 0 * * * ${pwd}/periodic_task.sh >> /home/ubuntu/cron.log 2>&1
docker exec -i app sh -c 'uv run python run_agent.py'