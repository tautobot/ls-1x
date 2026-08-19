# DEPRECATED: superseded by sync_matches.py (horus/json_sync).
# The legacy fetch loop wrote to tmp/matches.json via a stale remote json-server
# endpoint that nothing reads anymore. The new in-process sync service
# (sync_matches.py) discovers live matches AND deletes ended ones, writing
# directly into horus/jsondb.py's db.json. This file is retained for reference
# only and is no longer wired into deployment (systemds/ / devops/deploy.sh).
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
