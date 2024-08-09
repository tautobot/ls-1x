import schedule
import time
from horus.utils import fetch_matches_data

if __name__ == "__main__":

    schedule.every(10).seconds.do(fetch_matches_data)
    # Init
    fetch_matches_data()

    while 1:
        schedule.run_pending()
        time.sleep(1)
