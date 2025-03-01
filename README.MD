# Can I Bet On? - Agent

![Can I Bet On? Hero](./docs/canibeton-hero.png)

## Features

- 🤖 Create a betting pool out of anything w/ our custom agents
- 🔄 Automated grading using LangGraph agents
- 🐦 X (Twitter) integration for pool creation
- 💬 Telegram bot interface
- ⛓️ Chainlink Functions integration for decentralized grading
- 📊 Subgraph indexing for frontend display

## Contents

- [./api/twitterapi.py](./api/twitterapi.py) - Tools for querying X
- [./betting_pool_generator.py](./betting_pool_generator.py) - Agent for generating betting pools
- [./telegram_bot.py](./telegram_bot.py) - Telegram interface for creating betting pools
- [./twitter_post.py](./twitter_post.py) - Tools for posting to X
- [./twitter_post.py](./twitter_check.py) - Tools for parsing and handling mentions from X

- [Functionality](#functionality)
- [Deployment](#deployment)
- [Local Development](#local-development)

## Key tech

- [LangChain + LangGraph](https://www.langchain.com/langgraph) - Our agent code for handling the betting pool generation and grading flow
- [Chainlink Functions](https://chain.link/functions) - Has some interoperability with the grading agent for closing pools

## Functionality

### Bet creation flow

1. User mentions @CanIBetOn on X, or our Telegram bot asking it to generate a betting pool. User can optionally provide specific instructions or a general concept for the betting pool.
2. Bot will derive a topic and options for users to bet on. If it cannot derive enough key details from the user's message, it will fetch current events from a news API and use those to generate a betting pool
3. Bot will create a betting pool on the contract with the given topic and options on the contract.
4. The indexer picks up the new betting pool and adds it to the subgraph for rendering in the frontend
4. Bot will respond with a retweet on X, or a reply on Telegram, giving the user a link to the betting pool.

### Bet grading flow

1. Cron job runs every 10 minutes
   1. Fetch all bets that are not graded with bets closed in past from subgraph
   2. If so, run the grading function to simulate what Chainlink Functions will do as a filter (Chainlink Functions is expensive to run)
   3. Grading function:
   4. Small LLM checks the grading instructions for a date and time in which the bet will be graded (we could also extract this with regex if we want to avoid an LLM call).
      1. If there is a date and time and it is in the future return
      1. If there is no date and time OR if the date and time is in the past, CONTINUE
   5. If there is a date and time, check if the date and time is in the future. If so, CONTINUE
   6. If the date and time is in the past, run the grading function
   7. The grading function will return with 0, 1, 2, 3, or 4
      - 0 = is NOT READY TO GRADE
      - 1 = is option A
      - 2 = is option B
      - 3 = is DRAW
      - 4 = is ERROR
   8. Respond to each code with the following:
      - 0 = (NOT READY TO GRADE) do nothing
      - 1 = (Option A) Cache the answer, then call `gradeBet(poolId)` on the contract (this will trigger Chainlink Functions to run)
      - 2 = (Option B) Cache the answer, then call `gradeBet(poolId)` on the contract (this will trigger Chainlink Functions to run)
      - 3 = (DRAW) Cache the answer, then call gradeBet(poolId) on the contract (this will trigger Chainlink Functions to run)
      - 4 = (ERROR) Post error to telegram

### Part 2: Chainlink Functions retrieves grade and closes contract

1. Chainlink Functions is triggered by calling `gradeBet` on the contract
2. Chainlink Functions makes a REST API call to fetch the cached answer from the local run
3. Chainlink Functions takes the response from the grading function and does one of the following:
   - 0 (NOT READY TO GRADE) DO NOTHING (Chainlink Functions will never see this because we will call `gradeBet` on the contract if the grading function returns 0)
   - 1 (Option A), Chainlink Functions will set the selectedOption to 1 and set the status to "CLOSED"
   - 2 (Option B), Chainlink Functions will set the selectedOption to 2 and set the status to "CLOSED"
   - 3 (DRAW), Chainlink Functions will set isDraw to true and the status to "CLOSED"
   - 4 (ERROR) DO NOTHING (Chainlink Functions will never see this because we will call `gradeBet` on the contract if the grading function returns 4)

### Part 3: Backend cron job will send payouts to the winners

1. The backend will periodically poll for pools that are closed that have not been paid out (can get this from the subgraph)
2. Backend will payout the winners

### Deployment setup

- your server/container must have python 3.12 or greater installed
- after the first deploy attempt, run `python3 -m venv .venv` in the project folder
- after the deploy.sh script runs without errors you will need to activate the systemd timers

  ```
  sudo systemctl daemon-reload
  sudo systemctl enable promptbet-agent.timer
  sudo systemctl start promptbet-agent.timer
  ```
