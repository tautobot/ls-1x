import schedule
import time
import asyncio
from horus.utils import delete_ended_matches

if __name__ == "__main__":

    schedule.every(5).minutes.do(delete_ended_matches)
    # Init
    delete_ended_matches()

    while 1:
        schedule.run_pending()
        time.sleep(1)
