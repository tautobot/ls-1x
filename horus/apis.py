import requests
import json
import http.client
import time
from horus.config import logger, \
    X8_DOMAIN, \
    X8_BASE_URL, \
    X8_COOKIE, \
    X8_BET_HISTORY, \
    X8_AUTH, \
    X8_NUM_GAMES, \
    X8_LIVE_1, \
    X8_LIVE_1_PARAM, \
    X8_OPEN_BET, \
    X8_BALANCE


payload = {}
headers = {
  'authority': X8_DOMAIN,
  'accept': 'application/json, text/plain, */*',
  'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
  'content-type': 'application/json',
  'if-modified-since': 'Sat, 06 Jan 2024 11:06:54 GMT',
  'cookie': X8_COOKIE,
  'referer': X8_BASE_URL + '/en/live',
  'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"macOS"',
  'sec-fetch-dest': 'empty',
  'sec-fetch-mode': 'cors',
  'sec-fetch-site': 'same-origin',
  'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'x-requested-with': 'XMLHttpRequest'
}


def call_common_api(endpoint, payload=''):
    try:
        conn = http.client.HTTPSConnection(X8_DOMAIN)
        headers = {
            'authority'         : X8_DOMAIN,
            'accept'            : 'application/json, text/plain, */*',
            'accept-language'   : 'en-US,en;q=0.9,vi;q=0.8',
            'content-type'      : 'application/json;charset=UTF-8',
            'cookie'            : '_ym_uid=1597485927209928584; is_rtl=1; _ga=GA1.2.1106221113.1645201799; sh.session_be98639c=2da53792-3fb7-42f1-8dd7-7b07a082cf89; typeBetNames=full; pushfree_status=canceled; lng=en; flaglng=en; _ym_d=2823407981; right_side=right; che_g=fa4c72fa-abef-6410-7d40-ae6520ef27ea; app_mode=mobile; bettingView=1; uhash=e9cadaae93548a92c74abd7a0006695e; cur=VND; cfdata=%251%25; dnb=1; fast_coupon=true; _gid=GA1.2.1075956682.1655223384; iscbpdck=false; coefview=0; only_betting=0; automax=false; when_change_coef=1; auid=LYd6cGKqCSMH72IDBFVXAg==; tzo=7; promo_points=1; v3frm=1; regular_user=1; lite_version=0; _ym_isad=2; ggru=195; SESSION=019377b9a772968175652eda057fcb9a; visit=7-2c7348db619da63fa41f4db042d4d686; funnycookie=0218fa26fb17f9fbbe8fd4bb5b0fda28; _ym_visorc=b; _gat_gtag_UA_131019888_1=1; _glhf=1655815341; auid=LYd6cGJvoVYUzyLbEdJzAg==; cur=VND; funnycookie=cc3ae644e1425f2798ad37080bb6490d; is_rtl=1; tzo=7; uhash=e9cadaae93548a92c74abd7a0006695e',
            'origin'            : X8_BASE_URL,
            'referer'           : X8_BASE_URL + '/en/live/football',
            'sec-ch-ua'         : '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile'  : '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest'    : 'empty',
            'sec-fetch-mode'    : 'cors',
            'sec-fetch-site'    : 'same-origin',
            'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
            'x-requested-with'  : 'XMLHttpRequest'
        }
        conn.request("GET", endpoint, payload, headers)
        res = conn.getresponse()

        if res.status == 200:
            data = res.read()
            return json.loads(data.decode("utf-8"))
        else:
            print("Error code: ", res.status)
            return None

    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print('RequestException:', e)
    except ConnectionResetError:
        print('ConnectionResetError')
    return None


def get_history_results(ts_from, ts_to):

    url = X8_BASE_URL + X8_BET_HISTORY

    # payload = "{\n    \"timestamp_from\": HISTORY_FROM,\n    \"timestamp_to\": HISTORY_TO,\n    \"account_id\": 17721013,\n    \"coef_view\": 0,\n    \"feed_types\": [\n        0,\n        1\n    ],\n    \"bet_common_statuses\": [\n        1,\n        2,\n        3,\n        4,\n        5,\n        7,\n        8\n    ],\n    \"bet_types\": [\n        0,\n        1,\n        9,\n        7,\n        3,\n        8,\n        4,\n        5,\n        6,\n        2\n    ],\n    \"is_calculated_date_type\": false,\n    \"include_terminal_bets\": false,\n    \"sort_type\": 1\n}"
    # payload = payload.replace('HISTORY_FROM', str(h_from)).replace('HISTORY_TO', str(h_to))
    payload = json.dumps({
        "DateFrom"           : ts_from,
        "DateTo"             : ts_to,
        "CfView"             : 0,
        "BetTypes"           : [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8
        ],
        "BetStatuses"        : [
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8
        ],
        "SortType"           : 1,
        "BonusUserId"        : 17721013,
        "PartnerGroupId"     : 820,
        "PartnerId"          : 1,
        "Language"           : "en",
        "Count"              : 300,
        "CalculateSaleInfo"  : True,
        "ByBetSettlingDates" : False,
        "OnlyBetsForSale"    : False,
        "UseArchive"         : False,
        "IncludeTerminalBets": False
    })
    # headers = {
    #     'authority'         : X8_BASE_URL,
    #     'accept'            : 'application/json, text/plain, */*',
    #     'accept-language'   : 'en-US,en;q=0.9,vi;q=0.8',
    #     'content-type'      : 'application/json;charset=UTF-8',
    #     'cookie'            : X8_COOKIE,
    #     'origin'            : X8_BASE_URL,
    #     'referer'           : X8_BASE_URL + '/en/office/history',
    #     'sec-ch-ua'         : '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
    #     'sec-ch-ua-mobile'  : '?0',
    #     'sec-ch-ua-platform': '"macOS"',
    #     'sec-fetch-dest'    : 'empty',
    #     'sec-fetch-mode'    : 'cors',
    #     'sec-fetch-site'    : 'same-origin',
    #     'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    #     'x-requested-with'  : 'XMLHttpRequest',
    #     'x-auth'            : X8_AUTH
    # }
    headers = {
        'authority'         : X8_DOMAIN,
        'accept'            : 'application/json, text/plain, */*',
        'accept-language'   : 'en-US,en;q=0.9,vi;q=0.8',
        'content-type'      : 'application/json',
        'cookie'            : X8_COOKIE,
        'is-srv'            : 'false',
        'origin'            : X8_BASE_URL,
        'referer'           : X8_BASE_URL + '/en/office/history',
        'sec-ch-ua'         : '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile'  : '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest'    : 'empty',
        'sec-fetch-mode'    : 'cors',
        'sec-fetch-site'    : 'same-origin',
        'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'x-requested-with'  : 'XMLHttpRequest',
        'x-auth'            : X8_AUTH
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Request failed with status code: {response.status_code}")
            # Access the error message, if available
            error_message = response.text
            logger.error(error_message)
    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')
    return None


def get_number_live_sports():
    url = X8_BASE_URL + X8_NUM_GAMES
    payload = {}
    try:
        # # Start the timer
        # start_time = time.time()

        response = requests.request("GET", url, headers=headers, data=payload)

        # # Calculate the elapsed time
        # elapsed_time = time.time() - start_time
        # logger.info(f"Elapsed Time: {elapsed_time} seconds")

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.error("Result not found!")
        else:
            logger.error(f"Request failed with status code: {response.status_code}")
            # Access the error message, if available
            error_message = response.text
            logger.error(error_message)
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')

    return None


def get_num_live_matches(sport="Football", num_games=50):
    res = get_number_live_sports()
    if res is not None:
        if 'Value' in res:
            sports = res.get('Value')
            for s in sports:
                if s['N'] == sport:
                    num_games = int(s['C']) if int(s['C']) > num_games else num_games
    return num_games


def get_live_matches_1xbet(num_games=50):

    # num_games = get_number_live_sports()
    time.sleep(1)
    # if num_games > 170:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=170&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    # elif num_games > 150:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=150&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    # elif num_games > 120:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=120&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    # elif num_games > 100:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=100&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    # elif num_games > 70:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=70&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    # else:
    #     url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?sports=1&count=50&lng=en&gr=819&mode=4&country=43&getEmpty=true&virtualSports=true&noFilterBlockEvent=true"
    url = X8_BASE_URL + "/service-api/LiveFeed/Get1x2_VZip?count=50&lng=en&gr=819&antisports=2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,94,95,96,97,98,99,100,101,102,103,105,106,107,109,110,111,112,113,114,115,116,117,118,119,120,121,122,125,126,128,129,130,131,132,133,135,136,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,256,257,258,259,260,261,262,263,264,265,266,268,269,270,271,272,273,274,275,276,277,278,279,280,281,282,283,284,286,287,288,289,291,292,293,294,295,296,297,298,299,300&mode=4&country=43&virtualSports=true&noFilterBlockEvent=true"
    # url = config.live_all_api
    try:
        # # Start the timer
        # start_time = time.time()

        response = requests.request("GET", url, headers=headers, data=payload)
        json_response = {}
        # # Calculate the elapsed time
        # elapsed_time = time.time() - start_time
        # logger.info(f"Elapsed Time: {elapsed_time} seconds")

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.error("Result not found!")
        else:
            logger.error(f"Request failed with status code: {response.status_code}")
            # Access the error message, if available
            error_message = response.text
            logger.error(error_message)
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')

    return None


def get_live_match_1xbet(match_id):

    url = f"{X8_BASE_URL}{X8_LIVE_1}?id={match_id}{X8_LIVE_1_PARAM}"

    try:
        # Start the timer
        # start_time = time.time()
        response = requests.request("GET", url, headers=headers, data=payload)
        # Calculate the elapsed time
        # elapsed_time = time.time() - start_time
        # logger.info(f"Elapsed Time: {elapsed_time} seconds")

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.error("Result not found!")
        else:
            logger.error("Request failed with status code:", response.status_code)
            # Access the error message, if available
            error_message = response.text
            logger.error(error_message)
        return None

    except requests.exceptions.RequestException as e:  # This is the correct syntax
        logger.error('RequestException: ', e)
    except ConnectionResetError:
        logger.error('ConnectionResetError')

    return None


def open_bet(match_id):
    endpoint = X8_OPEN_BET
    data = {
        "Events"        : [
            {
                "GameId"      : match_id,
                "Type"        : 731,
                "Coef"        : 1.39,
                "Param"       : 1.001,
                "PV"          : None,
                "PlayerId"    : 0,
                "Kind"        : 1,
                "InstrumentId": 0,
                "Seconds"     : 0,
                "Price"       : 0,
                "Expired"     : 0,
                "PlayersDuel" : []
            }
        ],
        "Vid": 1,
        "partner": 1,
        "Lng": "en",
        "CfView": 0,
        "CalcSystemsMin": False,
        "IsNeedUpdatePromoCode": True,
        "Group": 820,
        "Country": 43,
        "Currency": 91,
        "SaleBetId": 0,
        "IsPowerBet": False
    }
    payload = json.dumps(data)
    try:
        conn = http.client.HTTPSConnection(X8_DOMAIN)
        headers = {
            'authority'         : X8_BASE_URL,
            'accept'            : 'application/json, text/plain, */*',
            'accept-language'   : 'en-US,en;q=0.9,vi;q=0.8',
            'content-type'      : 'application/json;charset=UTF-8',
            'cookie'            : X8_COOKIE,
            'origin'            : X8_BASE_URL,
            'referer'           : X8_BASE_URL,
            'sec-ch-ua'         : '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile'  : '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest'    : 'empty',
            'sec-fetch-mode'    : 'cors',
            'sec-fetch-site'    : 'same-origin',
            'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
            'x-requested-with'  : 'XMLHttpRequest'
        }
        conn.request("POST", endpoint, payload, headers)
        res = conn.getresponse()

        print(f"response code: {res.status}")
        if res.status == 200:
            json_response = json.loads(res.read().decode("utf-8"))
            return json.dumps(json_response, indent=4)

            # if not json_response['Success'] and json_response['Value'] is None:
            #     print("The match ended")
            #     return None
            # else:
            #     match_json = extract_match_info(json_response['Value'])
            #     return json.dumps(match_json, indent=4)
        elif res.status == 404:
            print("Result not found!")
            return None

    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    except ConnectionResetError:
        print('ConnectionResetError')
        return None


def login_w_tele():
    url = "https://oauth.telegram.org/auth/request?bot_id=704253235&origin=https%3A%2F%2Fxoauth.top&embed=1&return_to=https%3A%2F%2Fxoauth.top%2Foauth%2Ftelegram%3Fbot%3DXbetWebBot"
    payload = 'phone=84938846797'
    try:
        headers = {
            'authority'         : 'oauth.telegram.org',
            'accept'            : '*/*',
            'accept-language'   : 'en-US,en;q=0.9',
            'content-type'      : 'application/x-www-form-urlencoded',
            'cookie'            : 'stel_ssid=b888edb5ecc1427652_4868843735856565507',
            'origin'            : 'https://oauth.telegram.org',
            'referer'           : 'https://oauth.telegram.org/auth?bot_id=704253235&origin=https%3A%2F%2Fxoauth.top&embed=1&return_to=https%3A%2F%2Fxoauth.top%2Foauth%2Ftelegram%3Fbot%3DXbetWebBot',
            'sec-ch-ua'         : '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile'  : '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest'    : 'empty',
            'sec-fetch-mode'    : 'cors',
            'sec-fetch-site'    : 'same-origin',
            'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
            'x-requested-with'  : 'XMLHttpRequest'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        print('response.text of tele login', response.text)

        if response.text == 'true':
            return True
        elif response.text == 'false':
            return False
        else:
            return None
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    except ConnectionResetError:
        print('ConnectionResetError')
        return None


def check_tele_w_login():
    url = "https://oauth.telegram.org/auth/login?bot_id=704253235&origin=https%3A%2F%2Fxoauth.top&embed=1&return_to=https%3A%2F%2Fxoauth.top%2Foauth%2Ftelegram%3Fbot%3DXbetWebBot"
    payload = {}
    headers = {
        'authority'         : 'oauth.telegram.org',
        'accept'            : '*/*',
        'accept-language'   : 'en-US,en;q=0.9',
        'content-length'    : '0',
        'content-type'      : 'application/x-www-form-urlencoded',
        'cookie'            : 'stel_ssid=1ec1bb161b45026d3d_6116402916473840746; stel_tsession_84938846797=SzDlfepA9yZEzjUAocR7wtRn; stel_tsession=SzDlfepA9yZEzjUAocR7wtRn',
        'origin'            : 'https://oauth.telegram.org',
        'referer'           : 'https://oauth.telegram.org/auth?bot_id=704253235&origin=https%3A%2F%2Fxoauth.top&embed=1&return_to=https%3A%2F%2Fxoauth.top%2Foauth%2Ftelegram%3Fbot%3DXbetWebBot',
        'sec-ch-ua'         : '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
        'sec-ch-ua-mobile'  : '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest'    : 'empty',
        'sec-fetch-mode'    : 'cors',
        'sec-fetch-site'    : 'same-origin',
        'user-agent'        : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'x-requested-with'  : 'XMLHttpRequest'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        print('response.text of check tele login', response.text)

        if response.text == 'true':
            return True
        elif response.text == 'false':
            return False
        else:
            return None
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        raise SystemExit(e)
    except ConnectionResetError:
        print('ConnectionResetError')
        return None


async def get_balance():
    url = X8_BASE_URL + X8_BALANCE

    # Create the payload dictionary
    # Convert the payload dictionary to a JSON string

    response = requests.request("POST", url, headers=headers, data=payload)

    """
        {
          "balance": [
            {
              "id": 17721013,
              "money": 2984097.84,
              "lineRestrict": "0",
              "liveRestrict": "1",
              "BetVivaroBalance": 0,
              "fantasy_virt_balance": 0,
              "idCurrecy": 91,
              "kode": "VND",
              "HasPromoStavka": 1,
              "firstdep": null,
              "firstdepbonus": null,
              "hasbonus": 0,
              "refID": 1,
              "PointsBalance": 0,
              "idException": 105497,
              "TypeAccount": 0,
              "line_type": 0,
              "need_ban": 0,
              "Bonus": 0,
              "typ": 0,
              "alias": "",
              "MinOutDeposite": 8000,
              "MinOutElectronDeposite": 35000,
              "MinInElectronDeposite": 15000,
              "freespins": null,
              "AccountName": "Main account",
              "summ_unplaced_bets": 0,
              "active": true
            },
            {
              "id": 20572257,
              "money": 2509093.14,
              "lineRestrict": "0",
              "liveRestrict": "1",
              "BetVivaroBalance": 0,
              "fantasy_virt_balance": 0,
              "idCurrecy": 91,
              "kode": "VND",
              "HasPromoStavka": 0,
              "firstdep": null,
              "firstdepbonus": null,
              "hasbonus": 1,
              "refID": 1,
              "PointsBalance": 0,
              "idException": 106545,
              "TypeAccount": 2,
              "line_type": 0,
              "need_ban": 0,
              "Bonus": 1,
              "typ": 13,
              "alias": "",
              "MinOutDeposite": 8000,
              "MinOutElectronDeposite": 35000,
              "MinInElectronDeposite": 15000,
              "freespins": null,
              "AccountName": "1xGames bonus account",
              "summ_unplaced_bets": 0,
              "active": false
            }
          ],
          "bonus": [
            {
              "id": 331116645,
              "idBonus": 203,
              "promoaction_id": 19,
              "TypeBonus": 6,
              "BonusName": "Beat 1xBet Offer",
              "Trslt_BonusName": "Beat 1xBet Offer",
              "bonus_start": 2499093.14,
              "bonus_finish": 74972794.2,
              "bonus_fact": 40000,
              "BonusClosed": 0,
              "closing_time": 1684853402,
              "currency_code": "VND",
              "money": 2509093.14,
              "leftMilliseconds": 19087305
            }
          ],
          "all_accounts": [
            {
              "id": 17721013,
              "typ": 0,
              "name": "Main account",
              "idException": 105497,
              "money": 2984097.84,
              "BonusName": "Main account",
              "IdForTranslate": 105497,
              "dt": 1490761331,
              "Bonus": 0,
              "Currenty": 91,
              "activate": 1,
              "idBonus": null,
              "Temporary": null,
              "kode": "VND",
              "HasStavki": 1
            },
            {
              "id": 20264929,
              "typ": 1,
              "name": "Bonus account",
              "idException": 105503,
              "money": 2899518.49,
              "BonusName": "\"Lucky Friday\" Offer",
              "IdForTranslate": 106445,
              "dt": 1496996541,
              "Bonus": 1,
              "Currenty": 91,
              "activate": 0,
              "idBonus": 155,
              "Temporary": 1,
              "kode": "VND",
              "HasStavki": 1
            },
            {
              "id": 20572257,
              "typ": 1,
              "name": "1xGames bonus account",
              "idException": 106545,
              "money": 2509093.14,
              "BonusName": "\"Beat 1xBet\" Offer",
              "IdForTranslate": 106557,
              "dt": 1684767002,
              "Bonus": 1,
              "Currenty": 91,
              "activate": 1,
              "idBonus": 203,
              "Temporary": 1,
              "kode": "VND",
              "HasStavki": 1
            },
            {
              "id": 21145169,
              "typ": 1,
              "name": "Bonus account",
              "idException": 105503,
              "money": 0,
              "BonusName": "\"x2 Wednesday\" Promotion",
              "IdForTranslate": 106583,
              "dt": 1499243457,
              "Bonus": 1,
              "Currenty": 91,
              "activate": 0,
              "idBonus": 156,
              "Temporary": 1,
              "kode": "VND",
              "HasStavki": 1
            }
          ],
          "has_bets": true,
          "is_available_first_deposit_bonus": false,
          "success": true
        }
    """
    if response.status_code == 200:
        return response.json()
    return None


def get_json_sports():
    url = "http://localhost:8080/matches"
    payload = {}
    try:
        # # Start the timer
        # start_time = time.time()

        response = requests.request("GET", url, headers=headers, data=payload)

        # # Calculate the elapsed time
        # elapsed_time = time.time() - start_time
        # logger.info(f"Elapsed Time: {elapsed_time} seconds")

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.error("Result not found!")
        else:
            logger.error(f"Request failed with status code: {response.status_code}")
            # Access the error message, if available
            error_message = response.text
            logger.error(error_message)
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')

    return None


if __name__ == "__main__":
    # Example usage
    import asyncio
    res = get_json_sports()
    # res = get_live_matches_1xbet(72)
    # res = asyncio.run(get_balance())
    # res = get_number_live_sports()
    # res = open_bet(495436207)
    print(res)
