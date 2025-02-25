from betting_pool_core import fetch_pending_pools, grade_pool_with_langgraph_agent, store_pool_grade, call_grade_pool_contract
from betting_idea_grader import betting_pool_idea_grader_agent
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('grade_pools.log'),
        logging.StreamHandler()
    ]
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
        # pending_pools = [pending_pools[3]]

        # Process each pool
        for pool in pending_pools:
            pool_id_hex = pool['id']
            pool_close_at = int(pool['betsCloseAt'])
            
            print(f"pool_close_at: {pool_close_at}, time.time(): {time.time()}")
            if pool_close_at <= time.time():
                retry_count = 0
                while True:
                    try:
                        
                        logging.info(f"Processing pool {pool['id']}")

                        # Grade the pool
                        grade_result = grade_pool_with_langgraph_agent(betting_pool_idea_grader_agent, pool)
                        logging.info(f"Pool {pool_id_hex} graded with result: {grade_result}")

                        # Store the grade in Redis
                        if grade_result['result_code'] not in [4]: # 0 = "not yet resolved", 4 = "error"
                            if grade_result['result_code'] == 0:
                                logging.info(f"Pool {pool_id_hex} is not yet resolved")
                            else:
                                store_pool_grade(pool_id_hex, grade_result['result_code'])
                                logging.info(f"Stored grade for pool {pool_id_hex}")

                                # call the contract to update the pool
                                call_grade_pool_contract(int(pool_id_hex, 16))
                            
                            break
                        else:
                            logging.error(f"Error grading pool {pool_id_hex}. Trying again...")
                            retry_count += 1

                    except Exception as e:
                        logging.error(f"Error processing pool {pool_id_hex}: {str(e)}. Trying again...")
                        retry_count += 1
                    finally:
                        if retry_count > 3:
                            logging.error(f"Error processing pool {pool_id_hex}: {str(e)}. Giving up.")
                            break

    except Exception as e:
        logging.error(f"Error in grade_pending_pools: {str(e)}")

if __name__ == "__main__":
    logging.info("Starting pools grading cron job")
    grade_pending_pools()
    logging.info("Finished pools grading cron job") 