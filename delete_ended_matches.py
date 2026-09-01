# DEPRECATED: superseded by sync_matches.py (livescore/json_sync).
# Ended-match cleanup is now handled internally by JsonSyncService's updater loop
# (freeze-time / wall-clock / orphan detection), so a separate cleanup service is
# no longer needed. This file is retained for reference only and is no longer
# wired into deployment (systemds/ / devops/deploy.sh).
import schedule
import time
import asyncio
from livescore.utils import delete_ended_matches

if __name__ == "__main__":

    schedule.every(5).minutes.do(delete_ended_matches)
    # Init
    delete_ended_matches()

    while 1:
        schedule.run_pending()
        time.sleep(1)
