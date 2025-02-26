#!/bin/bash

deploy_acct="${DEPLOYMENT_USER}@${DEPLOYMENT_SERVER}"
deploy_path="/home/${DEPLOYMENT_USER}/promptbet-agent/"

# TODO We're hosting everything on my existing server, but should swap out domain names in this script when we lock a project name
# Step 1: SCP everything that isn't in .gitignore and .git to the remote server
rsync -avz --exclude-from='.gitignore' --exclude='.git' --include='.env' --delete ./ "$deploy_acct:$deploy_path"

# Below is example of also syncing a second project
# (cd ../pvpvai-eliza-starter && rsync -avz --exclude-from='.gitignore' --exclude='.git' --include='.env'  --delete ./ root@pvpvai.com:/root/pvpvai-eliza)

#rsync doesn't always get the .env file for some reason, so we'll just copy it manually
scp .env "$deploy_acct:$deploy_path/.env"

# The server will need to have python and pip installed

# ## Step 2: SSH into the remote server, navigate to the directory, rename .envrc.prod to .envrc and run the docker commands
ssh "$deploy_acct" <<ENDSSH
	echo "$deploy_path foo"
  cd "$deploy_path"
	pwd
  source .venv/bin/activate
  pip install -r requirements.txt
	sudo cp deploy/promptbet-agent.service /etc/systemd/system/promptbet-agent.service
	sudo cp deploy/promptbet-agent.timer /etc/systemd/system/promptbet-agent.timer
	sudo cp deploy/promptbet-agent-grader.service /etc/systemd/system/promptbet-agent-grader.service
	sudo cp deploy/promptbet-agent-grader.timer /etc/systemd/system/promptbet-agent-grader.timer
	sudo systemctl daemon-reload
ENDSSH

# docker compose down
# docker compose up -d
