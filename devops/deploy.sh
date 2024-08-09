s=$BASH_SOURCE ; s=$(dirname "$s") ; s=$(cd "$s" && pwd) ; SCRIPT_HOME="$s"  # get SCRIPT_HOME=executed script's path, containing folder, cd & pwd to get container path
a="$SCRIPT_HOME/.."; a=$(cd "$a" && pwd); APP_HOME=$a; ROOT="$APP_HOME/../"; ROOT=$(cd "$ROOT" && pwd)

ONEXBET_SERVICE=/etc/systemd/system/1xbet.service
ONEXBET_CLEAN_SERVICE=/etc/systemd/system/1xbet.clean.service

# Add new service if not existing and enable service
[ ! -f "$ONEXBET_SERVICE" ] && sudo cp "$APP_HOME/systemds/1xbet.service" "$ONEXBET_SERVICE"; sudo systemctl enable "$ONEXBET_SERVICE"; echo "Created new service: $ONEXBET_SERVICE"
[ ! -f "$ONEXBET_CLEAN_SERVICE" ] && sudo cp "$APP_HOME/systemds/1xbet.clean.service" "$ONEXBET_CLEAN_SERVICE"; sudo systemctl enable "$ONEXBET_CLEAN_SERVICE"; echo "Created new service: $ONEXBET_CLEAN_SERVICE"

# Stop all services
#sudo systemctl stop live-sports
sudo systemctl stop 1xbet
sudo systemctl stop 1xbet.clean

# Checkout master and pull master
git stash && git checkout master && git pull

# sync
#pipenv sync
poetry install

# Reload all services
sudo systemctl daemon-reload
# Start all services
#sudo systemctl start live-sports
sudo systemctl start 1xbet
sudo systemctl start 1xbet.clean

# Check status all services
#Will replace for history
#sudo systemctl status live-sports --no-pager
sudo systemctl status 1xbet --no-pager
sudo systemctl status 1xbet.clean --no-pager
