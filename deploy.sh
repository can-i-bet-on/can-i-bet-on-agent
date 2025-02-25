#!/bin/bash

# TODO We're hosting everything on my existing server, but should swap out domain names in this script when we lock a project name
# Step 1: SCP everything that isn't in .gitignore and .git to the remote server
rsync -avz --exclude-from='.gitignore' --exclude='.git' --include='.env' --delete ./ root@pvpvai.com:/root/promptbet-agent/

# Below is example of also syncing a second project
# (cd ../pvpvai-eliza-starter && rsync -avz --exclude-from='.gitignore' --exclude='.git' --include='.env'  --delete ./ root@pvpvai.com:/root/pvpvai-eliza)

#rsync doesn't always get the .env file for some reason, so we'll just copy it manually
scp .env root@pvpvai.com:/root/promptbet-agent/.env

# ## Step 2: SSH into the remote server, navigate to the directory, rename .envrc.prod to .envrc and run the docker commands
# ssh root@pvpvai.com << 'ENDSSH'
#   cd /root/promptbet-agent/
#   echo "HI"
# #   docker image build -t promptbet-agent .
#   source venv/bin/activate
#   pip install -r requirements.txt
#   docker compose down
#   langgraph build -t promptbet-agent
#   docker build -t promptbet-telegram-bot -f Dockerfile.telegram . 
#   docker compose up -d
# ENDSSH

# docker compose down
# docker compose up -d
