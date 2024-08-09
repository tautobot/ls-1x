from enum import Enum, EnumMeta


class EnumDirectValueMeta(EnumMeta):
    def __getattribute__(cls, name):
        value = super().__getattribute__(name)
        if isinstance(value, cls):
            value = value.value
        return value


class BaseEnum(Enum, metaclass=EnumDirectValueMeta):
    @classmethod
    def all(cls, except_list=None):
        if except_list is None:
            except_list = []
        return [c.value for c in cls if c.value not in except_list]

    @classmethod
    def keys(cls):
        return [k.name for k in cls]

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


###  Static class values should be stored in here

class BotEnv(BaseEnum):
    UAT        = 'uat'
    PRODUCTION = 'production'


class BotTypes:
    SCORES = 'scores'
    MOS = 'mos'
    OTHERS = 'others'


class LoginTypes(BaseEnum):
    ID = ''
    MOBILE = '+84'


class RISKS(BaseEnum):
    LOW         = 0
    MEDIUM      = 1
    HIGH        = 2
    HIGHEST     = 3
    EXT_HIGHEST = 4


class BetTime(Enum):
    MIN33 = 1980  # 33
    MIN34 = 2040  # 34
    MIN35 = 2100  # 35
    MIN36 = 2160  # 36
    MIN37 = 2220  # 37
    MIN38 = 2280  # 38
    MIN39 = 2340  # 39
    MIN40 = 2400  # 40
    MIN41 = 2460  # 41
    MIN42 = 2520  # 42

    MIN83 = 4980  # 83
    MIN84 = 5040  # 84
    MIN85 = 5100  # 85
    MIN86 = 5160  # 86
    MIN87 = 5220  # 87
    MIN88 = 5280  # 88
    MIN89 = 5340  # 89
    MIN90 = 5400  # 90


class BetStatuses(Enum):
    Unsettled = 1
    Loss      = 2
    Unknown   = 3
    Win       = 4


class OneXBetErrors(Enum):
    UNAUTHORIZATION             = 403
    ODDS_HAVE_CHANGED           = 130
    FAILED_TO_CHECK_EVENT       = 104
    GAME_IS_TEMPORARILY_BLOCKED = 133
    THE_MAX_AMOUNT_BET          = 109
    NO_LONGER_AVAILABLE         = 158150

    def get_key(value):
        for key, member in OneXBetErrors.__members__.items():
            if member.value == value:
                return key
        return None


class Game(Enum):
    W1 = 1
    X = 2
    W2 = 3
    X1 = 4
    W12 = 5
    X2 = 6
    HANDICAP1 = 7
    HANDICAP2 = 8
    TOTAL_OVER = 9
    TOTAL_UNDER = 10
    TOTAL_1_OVER = 11
    TOTAL_1_UNDER = 12
    TOTAL_2_OVER = 13
    TOTAL_2_UNDER = 14
    TOTAL_EVEN_YES = 182
    TOTAL_EVEN_NO = 183
    CORRECT_SCORE = 731
    INDIVIDUAL_TOTAL_1_EVEN_YES = 755
    INDIVIDUAL_TOTAL_1_EVEN_NO = 757
    INDIVIDUAL_TOTAL_2_EVEN_YES = 766
    INDIVIDUAL_TOTAL_2_EVEN_NO = 767
    INTERVALS_YES = 812
    INTERVALS_NO = 813
    INTERVALS_TOTAL_IN_MINUTE_YES = 1197  # (Over 4.5 In 85 Minute) param: 450.085
    INTERVALS_TOTAL_IN_MINUTE_NO = 1198   # (Under 4.5 In 85 Minute) param: 450.085
    EUROPEAN_HANDICAP_W1 = 424
    EUROPEAN_HANDICAP_X = 425
    EUROPEAN_HANDICAP_W2 = 426
    ASIAN_HANDICAP1 = 3829
    ASIAN_HANDICAP2 = 3830
    YELLOW_CARD = 10
    DOUBLE_CHANGE_AND_TOTAL_UNDER = 1558
    ANY_TEAM_TO_WIN_BY_X_GOAL = 4850
    """
            1. Click on Place a Bet and check if the bet is placed successfully
            2. In case the bet is placed failed -> Clarify issue and retry or change game before retry
            3. Advanced feature, check with API if it is possible to bet before Place a Bet
            Find on postman https://1xbet.mobi/LiveUtil/UpdateCoupon
            - Type 1: W1
            - Type 2: X
            - Type 3: W2
            - Type 4: 1X
            - Type 5: 12
            - Type 6: 2X
            - Type 7: Handicap 1
            - Type 8: Handicap 2
            - Type 9: Total Over
            - Type 10: Total Under
            - Type 11: Total 1 Over
            - Type 12: Total 1 Under
            - Type 13: Total 2 Over
            - Type 14: Total 2 Under
            - Type 182: Total Even Yes
            - Type 183: Total Even No
            - Type 731: Correct Score
            - Type 755: Individual Total 1 Even Yes
            - Type 757: Individual Total 1 Even No
            - Type 766: Individual Total 2 Even Yes
            - Type 767: Individual Total 2 Even No
            - Type 812: Intervals Yes, param=60.004, Coef=1.33 (Goal 4 Up to 60 Min - Yes)
            - Type 813: Intervals No , param=60.004, Coef=1.33 (Goal 4 Up to 60 Min - No)
            - Type 1197: Intervals Total In Minute Over (Over 4.5 In 85 Minute) param: 450.085
            - Type 1198: Intervals Total In Minute Under (Under 4.5 In 85 Minute) param: 450.085
            - Type 424: European Handicap 1:0 W1 
            - Type 425: European Handicap 1:0 X 
            - Type 426: European Handicap 1:0 W2 
            - Type 4850: Any team to win by 1 Goal(s) Yes
            - Type 4851: Any team to win by 1 Goal(s) No
            'payload': {
                "Events": [
                    {
                        "GameId": 413049395,  // Regular Time (Full), 1 Half, 2 Half
                        "Type": 10,           // Game type 
                        "Coef": 1.296,        // Odds 
                        "Param": 6.5,         // Use in games having choices like Total Over/Under
                        "PV": null,
                        "PlayerId": 0,
                        "Kind": 1,
                        "InstrumentId": 0,
                        "Seconds": 0,
                        "Price": 0,
                        "Expired": 0
                    }
                ],
                "NeedUpdateLine": false,
                "Lng": "en",
                "CfView": 0,
                "Vid": 0,
                "partner": 1,
                "group": 54,
                "UserId": 17461013
            }
            'response': {
                "Error": "",
                "ErrorCode": 0,
                "Guid": "2c6be9c4-dec5-40a0-b3bf-a3957e0dcbb6",
                "Id": 0,
                "Success": true,
                "Value": {
                    "AntiExpressCoef": 17.4,
                    "BetStep": 50.00,
                    "BonusCode": null,
                    "CfView": 0,
                    "CheckCf": 0,
                    "Code": 0,
                    "Coef": 17.400,
                    "CoefView": "",
                    "CustomerId": null,
                    "DebitFrom": null,
                    "Events": [
                        {
                            "Block": false,
                            "CV": null,
                            "ChampId": 2062693,
                            "Coef": 17.4,
                            "Expired": 0,
                            "ExtraKind": 0,
                            "FS1": 0,
                            "FS2": 0,
                            "Finish": false,
                            "FullName": null,
                            "FullScore": 0,
                            "GameConstId": 0,
                            "GameId": 413070285,
                            "GameTypeId": 1,
                            "InstrumentId": 0,
                            "IsBlock": false,
                            "IsRelation": 0,
                            "Kind": 1,
                            "MS1": 0,
                            "MS2": 0,
                            "PS": null,
                            "PV": null,
                            "Param": 0.001,
                            "ParamMobile": "0.001",
                            "PeriodName": "",
                            "PeriodScores": null,
                            "PlayerId": 0,
                            "Price": 0,
                            "Score": 0,
                            "Seconds": 0,
                            "SpecialCoef": 0,
                            "SportId": 1,
                            "Start": 1668839400,
                            "TimeDirection": 0,
                            "TimeSec": 2183,
                            "Type": 731
                        }
                    ],
                    "EventsIndexes": null,
                    "ExpresCoef": 0,
                    "Groups": null,
                    "GroupsSumms": null,
                    "InitialBet": 150.00,
                    "IsMatchOfDay": false,
                    "Kind": 0,
                    "Lng": "en",
                    "ManagerId": null,
                    "MinBetSystem": null,
                    "NeedUpdateLine": false,
                    "ResultCoef": 17.400,
                    "ResultCoefView": "",
                    "SaleBetId": 0,
                    "Source": 0,
                    "Sport": 0,
                    "Summ": 0,
                    "TerminalCode": null,
                    "TerminalCodeWeb": null,
                    "Top": 0,
                    "UserId": 17461013,
                    "UserIdBonus": 0,
                    "Vid": 0,
                    "WithLobby": false,
                    "avanceBet": false,
                    "betGUID": null,
                    "changeCf": false,
                    "exceptionText": null,
                    "expressNum": 0,
                    "fcountry": 0,
                    "maxBet": 960,
                    "minBet": 10.00,
                    "notLogin": false,
                    "notWait": false,
                    "partner": 1,
                    "promo": null,
                    "promoCodes": null
                }
            }
            """

    def get_key(value):
        for key, member in Game.__members__.items():
            if member.value == value:
                return key
        return None


class Events(Enum):
    COLLECT_LIVE_MATCH_IDS  = '_task1'
    COLLECT_LIVE_MATCHES = '_task1'

    def get_key(value):
        for key, member in OneXBetErrors.__members__.items():
            if member.value == value:
                return key
        return None