from betting_pool_core import (
    call_payout_bets_contract,
    fetch_bets_for_pool,
    fetch_pending_pools,
    grade_pool_with_langgraph_agent,
    post_close_market_tweets,
    store_pool_grade,
    call_grade_pool_contract,
)
from betting_idea_grader import betting_pool_idea_grader_agent
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
FRONTEND_URL_PREFIX = os.getenv("FRONTEND_URL_PREFIX")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("grade_pools.log"), logging.StreamHandler()],
)


def grade_pending_pools():
    """
    Cron job to grade pending pools:
    1. Fetch all pending pools
    2. Grade each pool
    3. Store the grades in Redis
    """
    try:
        # Fetch pending pools
        logging.info("Fetching pending pools...")
        pending_pools = fetch_pending_pools()
        logging.info(f"Found {len(pending_pools)} pending pools")

        # for testing
        # pending_pools = [pending_pools[0]]
        # pending_pools = [pool for pool in pending_pools if pool['id'] == '0x24']
        print(f"pending_pools: {pending_pools}")

        graded_pools = {}
        # Process each pool
        for pool in pending_pools:
            pool_close_at = int(pool["betsCloseAt"])

            print(f"pool_close_at: {pool_close_at}, time.time(): {time.time()}")
            if pool_close_at <= time.time():
                retry_count = 0
                pool_id = pool["id"]
                while True:
                    try:

                        logging.info(f"Processing pool {pool_id}")

                        # Grade the pool
                        grade_result = grade_pool_with_langgraph_agent(
                            betting_pool_idea_grader_agent, pool
                        )
                        logging.info(
                            f"Pool {pool_id} graded with result: {grade_result}"
                        )

                        # Set pool data to grade_result for processing
                        grade_result["pool_data"] = pool

                        # for testing
                        # grade_result['result_code'] = 1

                        # Store the grade in Redis
                        if grade_result["result_code"] != 4:  # 4 = "error"
                            if (
                                grade_result["result_code"] == 0
                            ):  # 0 = "not yet resolved"
                                logging.info(f"Pool {pool_id} is not yet resolved")
                            else:
                                # call the contract to update the pool
                                print(f"Pool {pool_id} is resolved, updating pool {pool_id} with result {grade_result['result_code']}")
                                call_grade_pool_contract(
                                    # pool_id is "#" (Ex: "3"). Although technically a bigint in contract, we're not realistically going to hit the cap of int32, so cast to int here.
                                    int(pool_id), grade_result["result_code"]
                                )
                                graded_pools[pool_id] = grade_result
                            break
                        else:
                            # TODO: Print the reason here
                            logging.error(
                                f"Error grading pool {pool_id}. Trying again..."
                            )
                            retry_count += 1

                    except Exception as e:
                        logging.error(
                            f"Error processing pool {pool_id}: {str(e)}. Trying again..."
                        )
                        retry_count += 1
                    finally:
                        if retry_count > 2:
                            logging.error(
                                f"Error processing pool {pool_id}: {str(e)}. Giving up."
                            )
                            break

        return graded_pools

    except Exception as e:
        logging.error(f"Error in grade_pending_pools: {str(e)}")


def pay_out_bets(graded_pools):
    """
    Pay out bets for each pool
    """
    bets_to_pay_out = []
    for pool_id in graded_pools:
        bets = fetch_bets_for_pool(int(pool_id))
        for bet in bets:
            bets_to_pay_out.append(int(bet["betIntId"]))

    print(f"bets_to_pay_out: {bets_to_pay_out}")
    if bets_to_pay_out:
        call_payout_bets_contract(bets_to_pay_out)


if __name__ == "__main__":
    logging.info("Starting pools grading cron job")
    graded_pools = grade_pending_pools()
    logging.info("Finished pools grading cron job")

    logging.info(f"Graded pools: {graded_pools}")

    if graded_pools:
        print(f"graded_pools: {graded_pools}")
        time.sleep(1 * 60)
        logging.info(f"Starting paying out bets")
        pay_out_bets(list(graded_pools.keys()))
        logging.info(f"Finished paying out bets")

        logging.info("Tweeting for the graded pools")
        post_close_market_tweets(graded_pools, FRONTEND_URL_PREFIX)
