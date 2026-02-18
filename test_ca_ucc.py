
import os
import sys
import logging
from dotenv import load_dotenv

# Ensure safe import paths
sys.path.insert(0, os.getcwd())

from src.queue.api import enqueue_window
from src.queue.store import TaskStore
from src.queue.worker import run_task
import sys
import io

class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode, encoding='utf-8')
        self.stdout = sys.stdout
        sys.stdout = self
    def __del__(self):
        sys.stdout = self.stdout
        self.file.close()
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
    def flush(self):
        self.file.flush()
        self.stdout.flush()

sys.stdout = Tee('log.txt', 'w')
sys.stderr = sys.stdout

import src.queue.worker
src.queue.worker.MAX_ATTEMPTS = 1

# Load .env for credentials (SHEETS_ID, etc.)
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_ca_ucc")

def main():
    logger.info("Starting CA UCC integration test...")

    # Enqueue a small task: 5 records, early 2026 window
    db_path = "data/test_queue.db"  # Use separate DB for test
    task_id = enqueue_window(
        site_id="20",
        date_start="01/20/2026",
        date_end="01/25/2026",
        max_records=5,
        db_path=db_path
    )
    
    logger.info(f"Enqueued task {task_id}")

    # Run the task
    store = TaskStore(db_path)
    task = store.get_next_pending()
    
    if not task:
        logger.error("Failed to retrieve task!")
        return

    logger.info(f"Running task {task.id} (site={task.site_id})")
    try:
        run_task(task, store)
        # Check final status
        final_task = [t for t in store.list_tasks() if t.id == task_id][0]
        logger.info(f"Task finished with status: {final_task.status}")
        if final_task.status == "completed":
            logger.info(f"Cursor: {final_task.cursor}")
        else:
            logger.error(f"Error: {final_task.last_error}")
            import os
            logging.info(f"Saving error to {os.getcwd()}/final_error.txt")
            with open("final_error.txt", "w", encoding="utf-8") as f:
                f.write(str(final_task.last_error))
            
    except Exception as e:
        logger.error(f"Execution failed: {e}")
    finally:
        store.close()
        # Cleanup test DB if desired, but keeping it for debugging might be useful
        # os.remove(db_path)

if __name__ == "__main__":
    main()
