s=$BASH_SOURCE ; s=$(dirname "$s") ; s=$(cd "$s" && pwd) ; SCRIPT_HOME="$s"  # get SCRIPT_HOME=executed script's path, containing folder, cd & pwd to get container path
a="$SCRIPT_HOME/.."; a=$(cd "$a" && pwd); APP_HOME=$a; ROOT="$APP_HOME/../"; ROOT=$(cd "$ROOT" && pwd)

ONEXBET_SYNC_SERVICE=/etc/systemd/system/1xbet.sync.service

# Retire the legacy services (fetch + clean). They are superseded by 1xbet.sync,
# which discovers new live matches AND deletes ended ones in a single process.
if [ -f /etc/systemd/system/1xbet.service ]; then
  sudo systemctl stop 1xbet 2>/dev/null; sudo systemctl disable 1xbet 2>/dev/null
  sudo rm -f /etc/systemd/system/1xbet.service; echo "Removed legacy service: 1xbet.service"
fi
if [ -f /etc/systemd/system/1xbet.clean.service ]; then
  sudo systemctl stop 1xbet.clean 2>/dev/null; sudo systemctl disable 1xbet.clean 2>/dev/null
  sudo rm -f /etc/systemd/system/1xbet.clean.service; echo "Removed legacy service: 1xbet.clean.service"
fi

# Resolve the real deploy path + poetry virtualenv python, then render the unit
# from the template (its __APP_HOME__/__VENV_PYTHON__ placeholders) so the service
# always points at this actual clone rather than a hardcoded path.
VENV_PYTHON="$(cd "$APP_HOME" && poetry run which python 2>/dev/null || echo "$APP_HOME/.venv/bin/python")"
sudo sed -e "s|__APP_HOME__|$APP_HOME|g" -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
  "$APP_HOME/systemds/1xbet.sync.service" | sudo tee "$ONEXBET_SYNC_SERVICE" >/dev/null
sudo systemctl enable "$ONEXBET_SYNC_SERVICE"; echo "Installed service: $ONEXBET_SYNC_SERVICE (WorkingDirectory=$APP_HOME, python=$VENV_PYTHON)"

# Stop the sync service before pulling
sudo systemctl stop 1xbet.sync

# Checkout master and pull master
git stash && git checkout master && git pull

# sync
#pipenv sync
poetry install

# Reload all services
sudo systemctl daemon-reload
# Start the sync service
sudo systemctl start 1xbet.sync

# Check status
sudo systemctl status 1xbet.sync --no-pager
