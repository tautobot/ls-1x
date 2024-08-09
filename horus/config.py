import logging
import os
import sys
import json
import logging
import pytz
from horus.custom_logger import CustomFormatter
from dotenv import load_dotenv


load_dotenv()
TIMEZONE    = os.environ.get('TIMEZONE') and pytz.timezone(os.environ.get('TIMEZONE')) or pytz.timezone('UTC')
env = None
score_env = None
tele_env = None
gg_auth_code = None
userhost = None
autobet_folder = None
jarxis = None

# 1xbet config
amount_bet = 0
hash1xbet = None
cookie1xbet = None
auth_token = None
domain = None
base_url_1xbet = None
num_games_api = None
live_football_api = None
live_all_api = None
live_1_api = None
live_1_param = None
open_bet_api = None
bet_history_api = None
balance_api = None
bonus_id_1xgames = None

DEBUG = False
CODE_HOME           = os.path.abspath(os.path.dirname(__file__) + '/..')
TEMP_FOLDER = f'{CODE_HOME}/tmp'
os.makedirs(TEMP_FOLDER, exist_ok=True)

TEMP_AUTH_FOLDER    = '/tmp/auth'
TEMP_AUTOBET_FOLDER = '/tmp/autobet'
logger = None

# zeromq
ZERO_HOST   = None
ZERO_PORT1  = None
ZERO_PORT2  = None

# 8X
X8_DOMAIN        = os.environ.get('X8_DOMAIN')
X8_BASE_URL      = os.environ.get('X8_BASE_URL')
X8_LIVE_FOOTBALL = os.environ.get('X8_LIVE_FOOTBALL')
X8_LIVE_1        = os.environ.get('X8_LIVE_1')
X8_LIVE_1_PARAM  = os.environ.get('X8_LIVE_1_PARAM')
X8_NUM_GAMES     = os.environ.get('X8_NUM_GAMES')
X8_OPEN_BET      = os.environ.get('X8_OPEN_BET')
X8_BET_HISTORY   = os.environ.get('X8_BET_HISTORY')
X8_BALANCE       = os.environ.get('X8_BALANCE')
X8_COOKIE        = os.environ.get('X8_COOKIE')
X8_AUTH          = os.environ.get('X8_AUTH')

JSON_SERVER_BASE_URL = os.environ.get('JSON_SERVER_BASE_URL')
#region MAIN@load config
def load_config_file(file_path):
    global logger
    global config
    global env
    global score_env
    global tele_env
    global gg_auth_code
    global userhost
    global autobet_folder
    global tele_auth_bot
    global jarxis
    # 1xbet
    global domain
    global base_url_1xbet
    global num_games_api
    global live_football_api
    global live_all_api
    global live_1_api
    global live_1_param
    global open_bet_api
    global bet_history_api
    global balance_api
    global amount_bet
    global hash1xbet
    global cookie1xbet
    global auth_token
    global bonus_id_1xgames
    global ZERO_HOST
    global ZERO_PORT1
    global ZERO_PORT2

    logger = logging.getLogger("autobet_app")
    logger.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)


def load_test_config():
    logger.info('[CONFIG] Using test configuration')
    test_config_path = os.path.join(os.path.dirname(__file__), os.pardir, 'config.test.json')
    if not os.path.exists(test_config_path):
        raise Exception('File not found config.test.json - please create one e.g. cp config.sample.json config.test.json')
    else:
        load_config_file(test_config_path)


def set_log_level():
    if not DEBUG:
        env_log_level = config['settings']['logLevel']
        if env_log_level == 'DEBUG': config['settings']['logLevel'] = logging.DEBUG
        if env_log_level == 'INFO':  config['settings']['logLevel'] = logging.INFO


load_config_file(CODE_HOME + '/config.json')


# if hasattr(sys, '_called_from_test'):
#     load_test_config()
#     set_log_level()
# else:
#     #TODO use Utils.get_config_path()
#     if 'BOT_CONFIG_FILE_PATH' in os.environ:
#         logger.info('[CONFIG] Using user-defined configuration')
#         load_config_file(CODE_HOME + 'config.json')
#         set_log_level()
#     else:
#         logger.error('[CONFIG] Not in test and BOT_CONFIG_FILE_PATH not set in .env')
#         sys.exit()
#endregion MAIN@load config


# # put alias to config for sentinel authentication url
# AUTH_URL = config['AUTH_URL'] = config['sentinel']['gc']
# GC_URL = config['AUTH_URL'] = config['website_url']['gc']
# GC_APP_URL = config['AUTH_URL'] = config['website_url']['gc_app']


#region access log config
# TODO move this to external config file e.g. config.dev.json so that can be changed easily
# https://gigacover.slack.com/archives/C7A3RK8Q0/p1530753060000071
#endregion


def custom_logger():
    # create logger with 'spam_application'
    logger = logging.getLogger("autobet_app")
    logger.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    # logger.debug("debug message")
    # logger.info("info message")
    # logger.warning("warning message")
    # logger.error("error message")
    # logger.critical("critical message")
    return logger

def get_telegram_bots():
    try:    return config['telegram_bots']
    except:
        logger.error("No definition for config['telegram_bots']")
        return None


def get_telegram_clients():
    try:    return config['telegram_clients']
    except:
        logger.error("No definition for config['telegram_clients']")
        return None


def get_path_files():
    try:    return config['path_files']
    except:
        logger.error("No definition for config['path_files']")
        return None


def get_chrome_driver_config():
    try:    return config['chrome_driver_config']
    except:
        logger.error("No definition for config['path_files']")
        return None


def get_autobet_folder():
    try:    return config['path_files']['autobet_folder']
    except:
        logger.error("No definition for config['path_files']['autobet_folder']")
        return None


def get_tmp_autobet_folder():
    try:    return config['path_files']['tmp_autobet_folder']
    except:
        logger.error("No definition for config['path_files']['tmp_autobet_folder']")
        return None


def get_1xbet_account():
    try:    return config['accounts']['1xbet']
    except:
        logger.error("No definition for config['accounts']['1xbet']")
        return None


def get_gg_auth_code():
    try:    return config['path_files']['gg_auth_code']
    except:
        logger.error("No definition for config['path_files']['gg_auth_code']")
        return None


def get_features():
    try:    return config['features']
    except:
        logger.error("No definition for config['features']")
        return None


def get_amount_bet():
    try:    return config['bets']['amount_bet']
    except:
        logger.error("No definition for config['bets']")
        return None

def set_amount_bet(amount):
    try:
        amount = config['bets']['amount_bet'] = amount
        return amount
    except:
        logger.error("No definition for config['bets']")
        return None

def get_smtp():
    try:    return config['smtp']['sender'], config['smtp']['password']
    except:
        logger.error("No definition for config['smtp']")
        return None
