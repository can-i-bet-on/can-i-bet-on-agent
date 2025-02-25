#! /bin/bash

project_dir="/home/ubuntu/promptbet-agent"

source "$project_dir/.env"
"$project_dir/.venv/bin/python3" "$project_dir/twitter_check.py"
