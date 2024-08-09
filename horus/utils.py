import json
import re
import math
import asyncio
from horus.enums import Game, RISKS, BetTime
import horus.apis as apis
from dateutil.parser import parse, parserinfo
from horus.config import X8_LIVE_FOOTBALL, X8_BASE_URL, TEMP_FOLDER, logger
from operator import itemgetter


class MyParser(parserinfo):
    def __init__(self):
        super(MyParser, self).__init__()
        self._formats = [
            '%d-%m-%Y',
            '%d %b %Y',
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m/%d/%y',
            '%d/%m/%Y',
            '%d/%m/%y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B, %Y',
            '%d %b, %Y',
            '%b %d %Y',
            '%B %d %Y',
            '%d %B %Y',
        ]


def round_up(n, decimals=0):
    multiplier = 10**decimals
    return math.ceil(n * multiplier) / multiplier


def round_down(n, decimals=0):
    multiplier = 10**decimals
    return math.floor(n * multiplier) / multiplier


def parse_date(input_date_str):
    # parse the input string with the custom parser object
    parsed_date = parse(input_date_str, parserinfo=MyParser())

    # get the format of the parsed date
    parsed_format = parsed_date.strftime('%Y-%m-%d')

    # print the format of the parsed date
    return parsed_format


def is_date(string, fuzzy=True):
    """
    Return whether the string can be interpreted as a date.

    :param string: str, string to check for date
    :param fuzzy: bool, ignore unknown tokens in string if True
    """
    try:
        parse(string, fuzzy=fuzzy)
        return True

    except ValueError:
        return False

#
# def extract_events_history(events):
#     new_dict = []
#     map_key = {
#         'champ_id': 'champ_id',
#         'champ_name': 'champ_name',
#         'main_game_id': 'main_game_id',
#         'game_id': 'game_id',
#         'game_name': 'game_name',
#         'game_status': 'game_status',
#         'is_finished': 'is_finished'
#     }
#     for e in events:
#         event = {}
#         for k in map_key:
#             if '.' in k:
#                 ak = re.split(r"[.]", k)
#                 value = e
#                 for e in ak:
#                     value = value.get(e)
#             else:
#                 value = e.get(k)
#             event[map_key.get(k)] = value
#         new_dict.append(event)
#     return new_dict
#
#
# def extract_bet_history(bets):
#     new_dict = []
#     map_key = {
#         'BetId'      : 'bet_id',
#         'BetStatus'  : 'status',
#         'BetSum'     : 'bet_amount',
#         'WinSum'     : 'win_amount',
#         'Events'     : 'events'
#     }
#     """
#     {
#       "id": 38028961713,
#       "date": 1685972433,
#       "coef": 1.1,
#       "coef_view": "1.1",
#       "status": 1,
#       "type": 0,
#       "type_title": "Single",
#       "system_type": 1,
#       "formatted_system_type": null,
#       "can_be_returned": false,
#       "can_sell": true,
#       "can_insure": true,
#       "can_print": true,
#       "can_show_sale_logs": false,
#       "is_used_promo_code": false,
#       "currency_code": "VND",
#       "sum": 200000,
#       "win_sum": null,
#       "win_sum_with_tax": null,
#       "possible_win_sum": 220000,
#       "possible_win_sum_with_tax": null,
#       "payout_sum": null,
#       "max_payout": null,
#       "out_sum": null,
#       "to_prepayment_sum": null,
#       "prepayment_sum": null,
#       "closed_prepayment_sum": null,
#       "old_sale_sum": null,
#       "auto_sale_sum": null,
#       "cashout_sum": null,
#       "insurance_sum": null,
#       "insurance_percent": null,
#       "insurance_status": null,
#       "max_sum_increasing_request_status": null,
#       "auto_sale_status": null,
#       "skks_hash": null,
#       "has_alternative_info": false,
#       "events": [
#         {
#           "additional_game_info": "",
#           "calculation_date": null,
#           "event_type_id": 10,
#           "event_type_title": "Total Under (0.5)",
#           "event_type_small_group_id": 4,
#           "event_type_small_group_name": "Total",
#           "game_start_date": 1685970000,
#           "sport_id": 1,
#           "sport_name": "Football",
#           "sport_name_en": null,
#           "champ_id": 40053,
#           "champ_name": "Armenia. Premier League",
#           "champ_name_en": null,
#           "champ_image": null,
#           "main_game_id": 456167777,
#           "const_id": 173088470,
#           "game_id": 456167779,
#           "game_name": "Lernayin Artsakh - Shirak 1 Half",
#           "game_kind": 1,
#           "game_status": 3,
#           "game_type_title": null,
#           "game_vid_title": null,
#           "period_name": "1 Half",
#           "is_home_away_game": false,
#           "is_live_game_in_live": true,
#           "live_game_time_sec": 2456,
#           "coef": 1.1,
#           "coef_view": "1.1",
#           "score": "0:0 (0:0)",
#           "is_score_json": false,
#           "result_type": null,
#           "returned_bet_event_status_id": null,
#           "returned_bet_event_status_name": null,
#           "returned_bet_event_reason_name": null,
#           "is_finished": false,
#           "player_name": null,
#           "opp1_id": 2736663,
#           "opp1_name": "Lernayin Artsakh",
#           "opp1_name_en": null,
#           "opp1_images": [
#             "00cf4a5da925cf82fc5bee70214a9a27.png"
#           ],
#           "opp2_id": 2448,
#           "opp2_name": "Shirak",
#           "opp2_name_en": null,
#           "opp2_images": [
#             "2448.png"
#           ],
#           "block_level": null,
#           "block_sum": null,
#           "block_coef": null,
#           "block_result": null,
#           "statId": "62e013d8f75a663f69e2b430",
#           "has_translation": true,
#           "translation_id": "",
#           "is_cyber": false,
#           "param": "0.5",
#           "groupId": 17
#         }
#       ],
#       "taxBet": null,
#       "isPowerBet": false
#     }
#     """
#     for b in bets:
#         bet = {}
#         for k in map_key:
#             if '.' in k:
#                 ak = re.split(r"[.]", k)
#                 value = b
#                 for e in ak:
#                     value = value.get(e)
#             else:
#                 value = b.get(k)
#             if map_key.get(k) == 'events':
#                 bet[map_key.get(k)] = extract_events_history(value)
#             else:
#                 bet[map_key.get(k)] = value
#
#         new_dict.append(bet)
#     return new_dict
#
#
# def get_from_to_history(d=None, ts='timestamp'):
#     if d and is_date(d):
#         date = datetime.strptime(parse_date(d), "%Y-%m-%d")
#         h_from = datetime(date.year, date.month, date.day, 0, 0, 0)
#         h_to = datetime(date.year, date.month, date.day + 1, 23, 59, 59)
#     else:
#         h_from = datetime(datetime.now().year, datetime.now().month, datetime.now().day, 0, 0, 0)
#         h_to = datetime(datetime.now().year, datetime.now().month, datetime.now().day + 1, 23, 59, 59)
#     # convert from datetime to timestamp
#     if ts == 'timestamp':
#         return round(datetime.timestamp(h_from)), round(datetime.timestamp(h_to))
#     else:
#         return h_from, h_to
#
#
# def get_history_results(d=None):
#     results = []
#     h_from, h_to = get_from_to_history(d)
#     res = apis.get_history_results(h_from, h_to)
#     if res is not None:
#         results = extract_bet_history(res.get('BetInfos'))
#     return results
#
#
# def count_bets(d=None):
#     results = get_history_results(d)
#     if results:
#         f, t = get_from_to_history(d, 'date')
#         return f"bets: {len(results)} ({f} - {t})"
#
#
# def bet_reports(d=None):
#     results = get_history_results(d)
#     unsettled_list = []
#     wins_list = []
#     losses_list = []
#     unknown_list = []
#     if results:
#         if len(results) > 0:
#             for r in results:
#                 if r.get('status') == BetStatuses.Unsettled.value:
#                     unsettled_list.append(r)
#                 elif r.get('status') == BetStatuses.Win.value:
#                     wins_list.append(r)
#                 elif r.get('status') == BetStatuses.Loss.value:
#                     losses_list.append(r)
#                 else:
#                     unknown_list.append(r)
#     return unsettled_list, wins_list, losses_list, unknown_list
#
#
# def is_even(num):
#     if num % 2 == 0:
#         return True
#     return False
#
#
# def minimize_matches(matches, objs):
#     new_matches = []
#     for m in matches:
#         tem_m = {}
#         for i in m:
#             if i in objs:
#                 tem_m.update({i: m.get(i)})
#         new_matches.append(tem_m)
#     return new_matches


def recorrect_url(url):
    rep = {"ö": "o", "ä": "a", "ü": "u", "ß": "s", "ó": "o", "í": "i", "é": "e", "è": "e", "т": "t"}
    # use these three lines to do the replacement
    rep = dict((re.escape(k), v) for k, v in rep.items())
    # Python 3 renamed dict.iteritems to dict.items so use rep.items() for latest versions
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], url)


def matches_data(json_response):
    if json_response and json_response['Value']:
        return json_response['Value']
    return None


def extract_matches_info(data):
    ori_dict = matches_data(data)
    if not ori_dict:
        return None
    new_dict = []
    map_key = {
        'I'       : 'match_id',
        'SC.CP'   : 'half',
        'SC.TS'   : 'time_second',
        'LI'      : 'league_id',
        'LE'      : 'league',
        'O1E'     : 'team1',
        'O2E'     : 'team2',
        'SC.FS.S1': 'team1_score',
        'SC.FS.S2': 'team2_score',
        'SC.I'    : 'penalties',  # 'Videoreview' info
        'SC.S'    : 'additional_info',
        'SC.ST'   : 'main_info',
        'AE'      : 'games',
        'S'       : 'kickoff'
    }
    for o in ori_dict:
        # Skip amateur, indoor, short football
        if o.get('CID') == 1 and 'MIO' in o:
            # MaF: Match formats that are different with normal football match, e.g 2x5
            if 'MaF' not in o['MIO']:
                match = {}
                for k in map_key:
                    if '.' in k:
                        ak = re.split(r"[.]", k)
                        value = o
                        for e in ak:
                            value = value.get(e)
                    else:
                        value = o.get(k)
                    if map_key.get(k) == 'penalties':
                        match[map_key.get(k)] = value or None
                    else:
                        match[map_key.get(k)] = value or 0
                # Add current time of the match
                tm = convert_timestamp_to_timematch(match.get('time_second'))
                match['time_match'] = tm
                league_name = remove_special_str_excepted_spaces(match.get('league').lower())
                # Add prediction from games obj - AE.ME
                match['prediction'] = 0
                match['cur_prediction'] = 0
                match['scores'] = []
                games = match.get('games')
                # Check if 'games' key exists in 'match' and it is of list type
                if isinstance(games, list):

                    # Loop through each element of the list
                    for game in games:

                        # Check if the game dictionary contains keys 'G' and 'ME'
                        if all(key in game for key in ['G', 'ME']):

                            # Check if the value of the 'G' key is 17
                            if game.get('G') == 17:

                                # Loop through each element of 'ME' list
                                for cg in game.get('ME'):

                                    # Check if the dictionary 'cg' has keys 'CE', 'G', 'T', and 'P'
                                    if all(key in cg for key in ['CE', 'G', 'T', 'P']):

                                        # Check if the 'CE', 'G', and 'T' keys have expected values
                                        if cg.get('CE') == 1 and cg.get('G') == 17 and cg.get('T') == 9:

                                            time_sec = match.get('time_second')
                                            cur_prediction = cg.get('P')
                                            # If match appeared before first 10 minutes, prediction is good to consider
                                            if time_sec <= 600:
                                                # Calculate the new prediction value and store it in 'prediction' key
                                                match['prediction'] = cur_prediction

                                            # Store 'P' value in 'cur_prediction' key
                                            match['cur_prediction'] = cur_prediction
                match.pop('games', None)

                # Red card info
                main_info = match.get('main_info')[0].get('Value') if match.get('main_info') else None
                if isinstance(main_info, list):
                    # for mi in main_info:
                    #     if mi.get('Key') == 'IRedCard1' and mi.get('Value') != "0":
                    #         match['team1_redcard'] = mi.get('Value')
                    #     if mi.get('Key') == 'IRedCard2' and mi.get('Value') != "0":
                    #         match['team2_redcard'] = mi.get('Value')
                    for mi in main_info:
                        if mi.get('ID') == 71:  # 71 is read card info
                            match['team1_redcard'] = mi.get('S1')
                            match['team2_redcard'] = mi.get('S2')
                match.pop('main_info', None)

                # Additional Time
                add_info = match.get('additional_info')
                if isinstance(add_info, list):
                    for ai in add_info:
                        if ai.get('Key') == 'AddTime':
                            match['add_time'] = ai.get('Value')
                            break
                match.pop('additional_info', None)

                # Add match's URL
                match['url'] = recorrect_url(
                    f"{X8_BASE_URL}/{X8_LIVE_FOOTBALL}/{match.get('league_id')}-{league_name}/{match.get('match_id')}")

                new_dict.append(match)
    return new_dict


def extract_match_info(data, match_id=None, game1h_id=None, game2h_id=None):
    original_match = matches_data(data)
    if not original_match:
        return None
    map_key = {
        'I'       : 'match_id',
        'SC.CP'   : 'half',
        'SC.CPS'  : 'half_text',
        'SC.TS'   : 'time_second',
        'LI'      : 'league_id',
        'LE'      : 'league',
        'O1E'     : 'team1',
        'O2E'     : 'team2',
        'SC.FS.S1': 'team1_score',
        'SC.FS.S2': 'team2_score',
        'SC.I'    : 'penalties',
        'SG'      : 'halfs',
        'SC.PS'   : 'match_score_obj',
        'GE'      : 'event_odds'
    }
    match = {}
    for k in map_key:
        if '.' in k:
            ak = re.split(r"[.]", k)
            value = original_match
            for e in ak:
                value = value.get(e)
        else:
            value = original_match.get(k)
        if map_key.get(k) == 'penalties':
            match[map_key.get(k)] = value or None
        else:
            match[map_key.get(k)] = value or 0
    # Add current time of the match
    tm = convert_timestamp_to_timematch(match.get('time_second'))
    match['time_match'] = tm
    league_name = remove_special_str_excepted_spaces(match.get('league').lower())
    # Add prediction from games obj - AE.ME
    match['full_time_game_id'] = match['match_id'] if match_id is None else match_id
    match['1half_game_id'] = game1h_id
    match['2half_game_id'] = game2h_id

    if not game1h_id and not game2h_id and isinstance(match['halfs'], list):
        for g in match['halfs']:
            if 'PN' in g and 'TG' not in g and g['P'] == 1 and g['PN'].lower() == '1 half':
                match['1half_game_id'] = g['I']
            if 'PN' in g and 'TG' not in g and g['P'] == 2 and g['PN'].lower() == '2 half':
                match['2half_game_id'] = g['I']
    match.pop('halfs', None)
    # TODO: From current half, can find all available events, odds for bet
    event_obj = []
    event_odds = match.get('event_odds')
    if isinstance(event_odds, list):
        for item in match.get('event_odds'):
            for gs in item.get('E'):
                for obj in gs:
                    if obj.get('T') in [Game.X.value, Game.TOTAL_UNDER.value, Game.TOTAL_EVEN_YES.value,
                                        Game.TOTAL_EVEN_NO.value, Game.CORRECT_SCORE.value, Game.EUROPEAN_HANDICAP_X.value]:
                        coef = obj.get('C')
                        type = obj.get('T')
                        param = obj.get('P')
                        game = obj.get('G')
                        event_obj.append({'game_type': type, 'coef': coef, 'param': param})
    match['events'] = event_obj

    # Add match's URLs
    match['full_time_url'] = build_game_url(match.get('match_id'), match.get('league_id'), league_name)
    if match['1half_game_id']:
        match['1half_url'] = build_game_url(match['1half_game_id'], match.get('league_id'), league_name)
    if match['2half_game_id']:
        match['2half_url'] = build_game_url(match['2half_game_id'], match.get('league_id'), league_name)
    return match


def build_game_url(match_id, league_id, league_name):
    return f"{X8_LIVE_FOOTBALL}/{league_id}-{league_name}/{match_id}"


# def extract_matches_tracking(origin_matches):
#     new_dict = []
#     map_key = {
#         'I'       : 'match_id',
#         'SC.FS.S1': 'team1_score',
#         'SC.FS.S2': 'team2_score',
#     }
#     for o in origin_matches:
#         match = {}
#         for k in map_key:
#             if '.' in k:
#                 ak = re.split(r"[.]", k)
#                 value = o
#                 for e in ak:
#                     value = value.get(e)
#             else:
#                 value = o.get(k)
#             match[map_key.get(k)] = value or 0
#         new_dict.append(match)
#     return new_dict


def get_live_matches_1xbet():
    num_games = get_num_live_matches()
    res = apis.get_live_matches_1xbet(num_games)
    live_matches = extract_matches_info(res)
    return live_matches


def get_live_match_1xbet(match_id):
    res = apis.get_live_match_1xbet(match_id)
    live_match = extract_match_info(res)
    if not live_match:
        return None
    # print(f"event happened in half: {live_match.get('half')}")
    # if live_match.get('half') == 1:
    #     print(f"recall get live match for half 1")
    #     res = apis.get_live_match_1xbet(live_match.get('1half_game_id'))
    #     if res.get('Success') or not res.get('Value'):
    #         live_match = extract_match_info(res, match_id, live_match.get('1half_game_id'), live_match.get('2half_game_id'))

    return live_match


def get_num_live_matches(sport="Football", num_games=50):
    res = apis.get_number_live_sports()
    if res is not None:
        if 'Value' in res:
            sports = res.get('Value')
            for s in sports:
                if s['N'] == sport:
                    num_games = int(s['C']) if int(s['C']) > num_games else num_games
    return num_games


# def get_live_match_ids():
#     ids = []
#     live_matches = get_live_matches_1xbet()
#     for m in live_matches:
#         if m['match_id']:
#             ids.append(m['match_id'])
#     return ids
#
#
# def get_num_live_sports(json_object, sport):
#     if 'Value' in json_object:
#         sports = json_object.get('Value')
#         for s in sports:
#             if s['N'] == sport:
#                 return int(s['C'])
#     return 50
#
#
# def extract_red_cards_info(pen_str):
#     if 'Penalties' in pen_str:
#         red_cards = pen_str.split()[1]
#         red_cards_t1 = red_cards.split('-')[0]
#         red_cards_t2 = red_cards.split('-')[1]
#         return red_cards, int(red_cards_t1), int(red_cards_t2)
#     return None, None, None
#
#
# def convert_game_obj(json_object):
#     converted_object = {
#         "full_time": {},
#         "half1"    : {},
#         "half2": {}
#     }
#
#     for item in json_object:
#         key = item["Key"]
#         value = item["Value"]
#
#         if key == 1:
#             converted_object["half1"]["team1score"] = value.get("S1", 0)
#             converted_object["half1"]["team2score"] = value.get("S2", 0)
#
#         if key == 2:
#             converted_object["half2"]["team1score"] = value.get("S1", 0)
#             converted_object["half2"]["team2score"] = value.get("S2", 0)
#
#     # Convert the final object to JSON string
#     result = json.dumps(converted_object, indent=4)
#     print(result)


def is_integer(n):
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()


# def is_int(n):
#     try:
#         return float(n).is_integer()
#     except AttributeError:
#         return False
#     except ValueError:
#         return False
#
#
# def is_json(data):
#     try:
#         json.loads(data)
#         return True
#     except json.JSONDecodeError:
#         return False
#
#
# def read_json():
#     # Opening JSON file
#     f = open(f'{config.CODE_HOME}/src/report/matches.json')
#
#     # returns JSON object as
#     # a dictionary
#     data = json.load(f)
#
#     # Closing file
#     f.close()
#     return data


def read_json_w_file_path(file_path):
    # Opening JSON file
    f = open(file_path)
    # returns JSON object as
    # a dictionary
    data = json.load(f)
    # Closing file
    f.close()
    return data


# def read_and_clear_json_w_file_path(file_path):
#     # Opening JSON file
#     f = open(file_path)
#     # returns JSON object as
#     # a dictionary
#     data = json.load(f)
#     # Closing file
#     f.close()
#     with open(file_path, 'w') as outfile:
#         json.dump({}, outfile)
#     outfile.close()
#     return data


def write_json(data):
    write_json_w_path(data, f'{TEMP_FOLDER}/matches.json')


def write_json_w_path(data, file_path):
    with open(file_path, 'w') as outfile:
        json.dump(data, outfile)
    outfile.close()


# def insert_items_json_w_path(items, file_path):
#     data = read_json_w_file_path(file_path) or []
#     for i in items:
#         data.append(i)
#     with open(file_path, 'w') as outfile:
#         json.dump(data, outfile)
#     outfile.close()
#
#
# def remove_items_json_w_path(items, file_path):
#     data = read_json_w_file_path(file_path) or []
#     for i in items:
#         data.remove(i)
#     with open(file_path, 'w') as outfile:
#         json.dump(data, outfile)
#     outfile.close()
#
#
# def insert_item_json_w_path(item, file_path):
#     data = read_json_w_file_path(file_path)
#     data.append(item)
#     with open(file_path, 'w') as outfile:
#         json.dump(data, outfile)
#     outfile.close()
#
#
# def remove_item_json_w_path(item, file_path):
#     data = read_json_w_file_path(file_path) or []
#     data.remove(item)
#     with open(file_path, 'w') as outfile:
#         json.dump(data, outfile)
#     outfile.close()
#
#
# def ssh_scp_file(start, destination):
#     import subprocess
#     subprocess.run(["scp", start, destination])
#
#
# def write_txt(data):
#     try:
#         with open(f'{config.CODE_HOME}/src/report/messages.txt', 'w') as outfile:
#             outfile.write(data)
#         outfile.close()
#     except Exception:
#         print('File does not exist')
#
#
# def write_txt_w_path(data, file_path):
#     try:
#         with open(file_path, 'w') as outfile:
#             outfile.write(data)
#         outfile.close()
#     except Exception:
#         print('File does not exist')
#
#
# def read_txt(file):
#     try:
#         with open(file, 'r') as f:
#             data = f.read()
#             f.close()
#             return data
#     except Exception:
#         print('File does not exist')
#
#
# def write_auth_code(data):
#     gg_auth_code_file = config.get_gg_auth_code()
#     userhost = config.userhost
#     if config.tele_env == 'server':
#         try:
#             ssh_scp_file(data, f'{userhost}:{gg_auth_code_file}')
#         except:
#             print("Can't connect to server")
#     elif config.tele_env == 'local':
#         write_txt_w_path(data, gg_auth_code_file)
#
#
# def read_auth_code():
#     gg_auth_code_file = config.gg_auth_code
#     userhost = config.userhost
#     if config.tele_env == 'server':
#         try:
#             ssh_scp_file(f'{userhost}:{gg_auth_code_file}', gg_auth_code_file)
#         except:
#             print("Can't connect to server")
#
#     with open(str(gg_auth_code_file), 'r') as f:
#         data = f.read()
#         f.close()
#     # After read data, clear it immediately
#     with open(str(gg_auth_code_file), 'w') as outfile:
#         outfile.write("")
#     outfile.close()
#     return data


def convert_timematch_to_seconds(time_match):
    if not is_integer(time_match[:2]):
        return 0
    if not is_integer(time_match[-2:]):
        return 0
    min_tm = int(time_match[:2])
    sec_tm = int(time_match[-2:])
    return min_tm * 60 + sec_tm


# def convert_uptotime_to_seconds(up_to_time):
#     return round(up_to_time) * 60


def convert_timestamp_to_timematch(timestamp):
    ctm = str(round(divmod(timestamp, 60)[0])).zfill(2)
    cts = str(round(divmod(timestamp, 60)[1])).zfill(2)
    ct = f"{ctm}:{cts}"
    return ct


def remove_special_str_excepted_spaces(league_str):
    final_str = ""
    for character in league_str:
        if character == " ":
            # checking character is space and if yes concat
            final_str = final_str + character
        else:
            if character.isalnum():
                final_str = final_str + character
    final_str = final_str.replace(" ", "-").replace("é", "e")
    return final_str


# def run_bash_script_file(file_path):
#     from subprocess import call
#     with open(file_path, 'rb') as file:
#         script = file.read()
#     rc = call([script, "12345"])
#
#
# def convert_auth_code_to_base64(auth_code):
#     if auth_code is None:
#         auth_code = input("Please enter auth code: ")
#     hash = str(base64.b64encode(bytes(f"{auth_code}", 'utf-8')))[2:10]
#     print(hash)
#     return hash
#
#
# def hash_password(password):
#     # uuid is used to generate a random number
#     salt = uuid.uuid4().hex
#     return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt
#
#
# # md5, sha1, sha224, sha256, sha384, sha512
# def check_password(hashed_password, user_password):
#     password, salt = hashed_password.split(':')
#     return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()
#
#
# def create_bets_json(new_match):
#     with open(f'{config.CODE_HOME}/src/report/bets.json', 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     data.append(new_match)
#     with open(f'{config.CODE_HOME}/src/report/bets.json', 'w', encoding='utf-8') as outfile:
#         json.dump(data, outfile, ensure_ascii=False)
#
#
# def generate_guid():
#     import uuid
#     return str(uuid.uuid4())
#
#
# def convert_timestamp_to_datetime(timestamp):
#     # Example timestamp value (Unix timestamp in seconds)
#     # Convert the timestamp to a datetime object
#     datetime_obj = datetime.fromtimestamp(timestamp)
#     # Print the datetime object
#     return datetime_obj


def sort_json(data, keys=itemgetter('remark_coef'), reverse=True):
    # Sort the data by name
    return sorted(data, key=keys, reverse=reverse)


# async def bot_send_message(bot_token, title, msg):
#     try:
#         msg = f"<b>{title}</b>\n<code>----------------</code>\n" + msg
#         # print(msg)
#         # sending message using telegram bot
#         bot = Bot(bot_token)
#         bot.sendMessage(chat_id=1654808760, text=msg, parse_mode='HTML')
#
#     except Exception as ex:
#         print(ex)
#
#
# # TODO: This is not a todo, just want to highlight to separate important section
# #   1XBET COMMON FUNC(s)
# def format_tele_msg(league, team1, team2, red_cards, scores, half, time_min, html_match_url, prediction, live_prediction):
#     msg = f"<code>{team1} - {team2}\n" \
#           f"{red_cards if red_cards else ''}" \
#           f"{scores} {half} {time_min}</code> {html_match_url}\n" \
#           f"PREDICTION: {prediction}\n" \
#           f"LIVE PREDICTION: {live_prediction}\n" \
#           f"<code>----------------------------\n" \
#           f"{league}</code>"
#
#     return msg
#
#
# def tag_bet_now_msg(url):
#     return f"<a href='{url}'><b>BET NOW</b></a>"
#
#
# def tag_bet_risk_msg(url):
#     return f"<a href='{url}'><b>BET WITH HIGH RISK</b></a>"
#
#
# def tag_link_msg(url):
#     return f"<a href='{url}'><b>LINK</b></a>"
#
#
# def extract_balances(ori_bal):
#     main_bal_mapping = {
#         'money': 'money'
#     }
#     bonus_bal_mapping = {
#         'id'          : 'id',
#         'idBonus'     : 'bonus_id',
#         'money'       : 'money',
#         'bonus_start' : 'bonus_start',
#         'bonus_fact'  : 'total_amount_bet',
#         'bonus_finish': 'target_amount',
#         'closing_time': 'expired_time'
#     }
#
#     main_acc_obj = {}
#     bonus_acc_obj = {}
#     if 'balance' in ori_bal:
#         balance_obj = ori_bal.get('balance')[0]
#         for k in main_bal_mapping:
#             if '.' in k:
#                 ak = re.split(r"[.]", k)
#                 value = balance_obj
#                 for e in ak:
#                     value = value.get(e)
#             else:
#                 value = balance_obj.get(k)
#             main_acc_obj[main_bal_mapping.get(k)] = value or 0
#     if 'bonus' in ori_bal:
#         bonus_obj = ori_bal.get('bonus')
#         if len(bonus_obj) > 0:
#             for k in bonus_bal_mapping:
#                 if '.' in k:
#                     ak = re.split(r"[.]", k)
#                     value = bonus_obj
#                     for e in ak:
#                         value = value.get(e)
#                 else:
#                     value = bonus_obj[0].get(k)
#                 if bonus_bal_mapping.get(k) == 'expired_time':
#                     bonus_acc_obj[bonus_bal_mapping.get(k)] = str(convert_timestamp_to_datetime(value)) or None
#                 else:
#                     bonus_acc_obj[bonus_bal_mapping.get(k)] = value or 0
#
#             bonus_acc_obj['pct_completed'] = round(
#                 (bonus_acc_obj.get('total_amount_bet') + bonus_acc_obj.get('money') - bonus_acc_obj.get('bonus_start')) * 100 / bonus_acc_obj.get('target_amount'), 2
#             )
#
#     return main_acc_obj, bonus_acc_obj
#
#
# async def get_pct_completed():
#     _, bonus_acc_obj = extract_balances(await apis.get_balance())
#     return bonus_acc_obj.get('pct_completed')
#
#
# async def get_specific_balance(bal='main'):
#
#     main_acc_obj, bonus_acc_obj = extract_balances(await apis.get_balance())
#     if bal == 'main':
#         return main_acc_obj.get('money')
#     elif bal == 'bonus':
#         return bonus_acc_obj.get('money')
#
#
# def get_bets():
#     return count_bets()
#
#
# def get_reports(d=None):
#     return bet_reports(d)
#
#
# def get_amount_bet(max_bet):
#     """
#     Get the maximum amount bet based on configuration and user input.
#
#     :param max_bet: (float) The maximum amount bet allowed
#     :return: (float) The maximum amount bet that can be used
#     """
#     # Get the default amount from the configuration
#     amount_bet = float(config.amount_bet)
#
#     # Get the amount from the user input file
#     jarxis_amount = read_txt(f"{config.CODE_HOME}/src/report/amount_bet")
#
#     if isinstance(jarxis_amount, float):
#         amount_bet = jarxis_amount
#
#     if max_bet and isinstance(max_bet, float):
#         if max_bet < amount_bet:
#             return max_bet
#     return amount_bet
#
#
# def send_email_smtp(receiver_emails):
#     import smtplib
#     from email.mime.multipart import MIMEMultipart
#     from email.mime.text import MIMEText
#
#     # Email configuration
#     sender_email, password = config.get_smtp()
#     subject = 'Subject of your email'
#     message = 'Body of your email'
#
#     msg = MIMEMultipart()
#     msg['From'] = sender_email
#     msg['To'] = ', '.join(receiver_emails)
#     msg['Subject'] = subject
#
#     msg.attach(MIMEText(message, 'plain'))
#
#     # Connect to Office 365 SMTP server
#     server = smtplib.SMTP('smtp.office365.com', 587)
#     server.starttls()
#
#     # Login to your email account
#     server.login(sender_email, password)
#
#     # Send the email
#     server.sendmail(sender_email, receiver_emails, msg.as_string())
#
#     # Close the connection
#     server.quit()
#
#
# def send_email(receiver_email, subject, message):
#     import smtplib
#     # Set the SMTP server and port
#     smtp_server = 'smtp.office365.com'
#     smtp_port = 587  # Default port for SMTP
#     sender_email = 'sender@example.com'
#     sender_password = 'send_password'
#
#     try:
#         # Create a SMTP session
#         with smtplib.SMTP(smtp_server, smtp_port) as server:
#             # Start a secure connection
#             server.starttls()
#
#             # Login to your email account
#             server.login(sender_email, sender_password)
#
#             # Create the email message
#             email_message = f"Subject: {subject}\n\n{message}"
#
#             # Send the email
#             server.sendmail(sender_email, receiver_email, email_message)
#
#         print("Email sent successfully!")
#     except Exception as e:
#         print(f"Error: {str(e)}")


def check_scores(old_match, new_match):
    team_score = 0
    if old_match['match_id'] == new_match['match_id']:
        if old_match['team1_score'] < new_match['team1_score']:
            team_score = 1
        elif old_match['team1_score'] > new_match['team1_score']:
            team_score = -1
        elif old_match['team2_score'] < new_match['team2_score']:
            team_score = 2
        elif old_match['team2_score'] > new_match['team2_score']:
            team_score = -2
    return team_score


async def check_rules(start_prediction, current_prediction, score_team1, score_team2, half, time_sec):
    # Check risk for betting under
    total_score = score_team1 + score_team2
    diff_score = abs(score_team1 - score_team2)
    if half == 1:
        # TODO:
        #  #1 Add win-lose prediction into total scores prediction
        #  #2 Check red cards into prediction
        #  #3 total scores prediction in 2nd half go to reduced more than 50% from start prediction
        #     Bet over total scores
        # start_prediction < 3: The match is predicted low scores
        if 0 < start_prediction <= 3 or (start_prediction == 0 and total_score*2 < current_prediction):
            # The situation seems going exact start prediction until close to the end of half
            if total_score < start_prediction:
                # The score happens after 36th minute
                if time_sec >= BetTime.MIN36.value:
                    return RISKS.LOW
                # The score happens from 33rd to 36th minute
                # TODO: Add indicators to check
                #   If low scores, skip check odds increased continuously and win team prediction after the score
                elif BetTime.MIN34.value <= time_sec <= BetTime.MIN36.value:
                    return RISKS.MEDIUM
            # The situation seems going wrong start prediction until close to the end of half
            elif total_score >= start_prediction:
                # The score happens after 37th minute
                if time_sec >= BetTime.MIN37.value:
                    return RISKS.MEDIUM
                else:
                    return RISKS.HIGH
        # start_prediction == 3: The match is predicted medium scores
        elif start_prediction == 3.5:
            # The situation seems going exact start prediction until close to the end of half
            if total_score <= 3:
                # The score happens after 37th minute
                if time_sec > BetTime.MIN37.value:
                    return RISKS.LOW
                # The score happens from 34th to 36th minute
                elif BetTime.MIN35.value <= time_sec <= BetTime.MIN37.value:
                    return RISKS.MEDIUM
            elif total_score == 4:
                # The score happens after 39th minute
                if time_sec > BetTime.MIN39.value:
                    return RISKS.MEDIUM
                # The score happens from 36th to 39th minute
                elif BetTime.MIN36.value <= time_sec <= BetTime.MIN39.value:
                    return RISKS.HIGH
            return RISKS.HIGHEST
        return RISKS.HIGHEST
    elif half == 2:
        # start_prediction < 3: The match is predicted low scores
        if total_score <= 4:
            if 0 < start_prediction <= 3.5:
                if diff_score == 1:
                    # The score happens after 86th minute
                    if time_sec > BetTime.MIN85.value:
                        return RISKS.LOW
                    elif BetTime.MIN84.value <= time_sec <= BetTime.MIN85.value:
                        return RISKS.MEDIUM
                    else:
                        return RISKS.HIGH
                elif diff_score == 2:
                    # The score happens after 84th minute
                    if time_sec > BetTime.MIN84.value:
                        return RISKS.LOW
                    # The score happens from 82nd to 84th minute
                    elif BetTime.MIN83.value <= time_sec <= BetTime.MIN84.value:
                        return RISKS.MEDIUM
                    else:
                        return RISKS.HIGH
                elif diff_score == 3:
                    # The score happens after 86th minute
                    if time_sec > BetTime.MIN86.value:
                        return RISKS.LOW
                    elif BetTime.MIN84.value <= time_sec <= BetTime.MIN86.value:
                        return RISKS.MEDIUM
                    else:
                        return RISKS.HIGH
                elif diff_score == 0:
                    # The score happens after 86th minute
                    if time_sec > BetTime.MIN88.value:
                        return RISKS.LOW
                    elif BetTime.MIN86.value <= time_sec <= BetTime.MIN88.value:
                        return RISKS.MEDIUM
                    else:
                        return RISKS.HIGH
                else:
                    return RISKS.HIGHEST
            return RISKS.HIGHEST
        return RISKS.HIGHEST
    else:
        return RISKS.HIGHEST


async def compare_matches(matches, new_matches):
    # TODO: New logic - loop new matches to check current scores with existing matches
    """
    If found any existing match, pop() it out after check score
    New matches will be included new scores, and time that are stored into matches json
    pop() a match from list matches['matches'].pop(matches['matches'].index(m))
    """
    bet_coros = []
    tele_coros = []
    # Loop through each element of 'matches' list
    for match in matches:
        # Loop through each element of 'new_matches' list
        for new_match in new_matches:
            # Check if the 'match_id' keys in both dictionaries have the same value
            if match['match_id'] == new_match['match_id']:
                # Update prediction to new match
                new_match['prediction'] = match['prediction']
                new_match['scores'] = []
                if 'scores' in match:
                    new_match['scores'] = match['scores']
                # Check if is there any score happened
                team_score = check_scores(match, new_match)
                if team_score != 0:
                    # TODO
                    #  1. Create telegram msg here with type to send it to telebot accordingly
                    #  2. If meet matrix rules -> bet
                    match_id = new_match.get('match_id')
                    league = new_match.get('league')
                    prediction = new_match.get('prediction')
                    cur_prediction = new_match.get('cur_prediction')
                    team1 = new_match.get('team1')
                    team2 = new_match.get('team2')
                    team1_score = new_match.get('team1_score')
                    team2_score = new_match.get('team2_score')
                    half = new_match.get('half')
                    time_second = new_match.get('time_second')
                    time_match = new_match.get('time_match')
                    penalties = new_match.get('penalties')
                    team1_redcard = new_match.get('team1_redcard')
                    team2_redcard = new_match.get('team2_redcard')
                    url = new_match.get('url')
                    scores = new_match.get('scores')

                    matched_rule = await check_rules(prediction, cur_prediction, team1_score,
                                                     team2_score, half, time_second)

                    # store time of the last score
                    scores.insert(0, time_match)
                    new_match['scores'] = scores

                break
        # If the inner loop completes without the 'break' statement, remove the current 'match' from 'matches' list
        # else:
        #     matches.remove(match)
    # TODO: Start bet with asyncio here, refer /async_sample.py
    await asyncio.gather(*bet_coros, *tele_coros)
    if len(new_matches) > 0:
        write_json(new_matches)
    return new_matches


async def delete_matches(matches):
    logger.info('run deleting ended matches')
    for match in matches:
        res_ = get_live_match_1xbet(match.get('match_id'))
        if not res_ or not res_.get('Success'):
            matches.remove(match)


def fetch_matches_data():
    last_matches = read_json_w_file_path(f'{TEMP_FOLDER}/matches.json')
    live_matches = get_live_matches_1xbet()
    logger.info(f'Popular live matches: {len(live_matches)}')

    # # last_matches is not correct format, create last matches with live_matches
    # if not isinstance(last_matches, list):
    #     if len(live_matches) > 0:
    #         utils.write_json(live_matches)
    asyncio.run(compare_matches(last_matches, live_matches))


def delete_ended_matches():
    last_matches = read_json_w_file_path(f'{TEMP_FOLDER}/matches.json')
    asyncio.run(delete_matches(last_matches))
    # live_matches = utils.get_live_matches_1xbet()
    # logger.info(f'Popular live matches: {len(live_matches)}')
    #
    # # # last_matches is not correct format, create last matches with live_matches
    # # if not isinstance(last_matches, list):
    # #     if len(live_matches) > 0:
    # #         utils.write_json(live_matches)
    # asyncio.run(compare_matches(last_matches, live_matches))


def pagination(array, page, limit):
    start_index = (page - 1) * limit
    end_index = page * limit

    return array[start_index:end_index]


if __name__ == "__main__":
    # Example usage
    # import asyncio
    #
    # print(f"Completed 1xgames bonus: {asyncio.run(get_pct_completed())}%")

    # print(get_history_results('2024-01-07'))
    # print(asyncio.run(get_specific_balance()))
    # print(get_reports('2023-12-08'))
    # print(get_num_live_matches())
    # print(get_live_match_ids())
    # print(get_live_match_1xbet(501161552))
    # print(asyncio.run(bet.get_games_to_bet(501166333)))

    # res = asyncio.run(get_pct_completed())
    # print(res)

    # send_email("trieu.truong@gigacover.com, kytrieu.truong@gmail.com", "Test subject", "Test content")
    # send_email_smtp(['trieutruong.dev@gmail.com', 'kytrieu.truong@gmail.com'])

    pass

