Bet grading flow:

1. Cron job runs every 10 minutes
    1. Fetch all bets that are not graded with bets closed in past from subgraph
    2. If so, run the grading function to simulate what Chainlink Functions will do as a filter (Chainlink Functions is expensive to run)
    3. Grading function:
    1. Small LLM checks the grading instructions for a date and time in which the bet will be graded (we could also extract this with regex if we want to avoid an LLM call).
        1. If there is a date and time and it is in the future return
        1. If there is no date and time OR if the date and time is in the past, CONTINUE
    2. If there is a date and time, check if the date and time is in the future. If so, CONTINUE
    3. If the date and time is in the past, run the grading function
    4. The grading function will return with 0, 1, 2, 3, or 4
        - 0 = is NOT READY TO GRADE
        - 1 = is option A
        - 2 = is option B
        - 3 = is DRAW
        - 4 = is ERROR
    5. Respond to each code with the following:
        - 0 = (NOT READY TO GRADE) do nothing
        - 1 = (Option A) Cache the answer, then mark the contract as ready for grading (this will trigger Chainlink Functions to run)
        - 2 = (Option B) Cache the answer, then mark the contract as ready for grading (this will trigger Chainlink Functions to run)
        - 3 = (DRAW) Cache the answer, then mark the contract as ready for grading (this will trigger Chainlink Functions to run) <or do we want to do something here? Maybe wait until we get 3 draws in a row?>
        - 4 = (ERROR) Post error to telegram

Part 2: Chainlink Functions retrieves grade and closes contract

1. Chainlink functions detects that a pool is ready for grading by seeing which pools are marked as ready for grading
2. Chainlink functions makes a REST API call to fetch the cached answer from the local run
3. Chainlink functions takes the response from the grading function and does one of the following:
    - 0 (NOT READY TO GRADE) DO NOTHING (Chainlink functions will never see this because we will never mark the contract as ready for grading if the grading function returns 0)
    - 1 (Option A), Chainlink functions will set the selectedOption to 1 and set the status to "CLOSED" (further down the line the backend will send payouts to the winners)
    - 2 (Option B), Chainlink functions will set the selectedOption to 2 and set the status to "CLOSED" (further down the line the backend will send payouts to the winners)
    - 3 (DRAW), Chainlink Functions will set isDraw to true and the status to "CLOSED"
    - 4 (ERROR) DO NOTHING (Chainlink Functions will never see this because we will never mark the contract as ready for grading if the grading function returns 4)

Part 3: Backend cron job will send payouts to the winners

1. The backend will periodically poll for pools that are closed that have not been paid out (can get this from the subgraph)
2. Backend will payout the winners
