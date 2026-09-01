from livescore.config import logger
from livescore import jsondb


def convert_data_types(data):
    converted_data = []
    for item in data:
        converted_item = {}
        for key, value in item.items():
            if isinstance(value, str) and value.isdigit():
                converted_item[key] = int(value)
            elif isinstance(value, list):
                converted_item[key] = value
            elif isinstance(value, str) and value.replace(".", "", 1).isdigit():
                converted_item[key] = float(value)
            else:
                converted_item[key] = value
        converted_data.append(converted_item)
    return converted_data


def parse_filters(filters):
    # '?risk=0&risk=-1&status=on_going_h1' -> {'risk': ['0', '-1'], 'status': ['on_going_h1']}
    # None or '' -> {}. Values are kept as strings (json-server compares as strings).
    parsed = {}
    if not filters:
        return parsed
    query = filters[1:] if filters.startswith('?') else filters
    for pair in query.split('&'):
        if not pair:
            continue
        if '=' not in pair:
            logger.error(f'skipping malformed filter segment: {pair}')
            continue
        key, value = pair.split('=', 1)
        parsed.setdefault(key, []).append(value)
    return parsed


def make_predicate(filters):
    # AND across fields, OR within a field, string-coerced equality. Missing field = no match.
    parsed = filters if isinstance(filters, dict) else parse_filters(filters)
    if not parsed:
        return lambda record: True

    def predicate(record):
        for field, values in parsed.items():
            if field not in record:
                return False
            if str(record[field]) not in values:
                return False
        return True
    return predicate


class _FakeResponse(object):
    # Minimal, requests.Response-compatible shim: exposes .status_code and .json().
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class JsonServerProcessor(object):

    def __init__(self, source, params, **kwargs):
        self.source = source
        self.params = params

    def get_all_matches(self, filters=None):
        try:
            data = jsondb.query_collection(self.source, make_predicate(filters))
            return {
                'success': True,
                'data'   : data if self.params.get('skip_convert_data_types') else convert_data_types(data),
            }
        except Exception as e:
            logger.error(f'get_all_matches failed: {e}')
            return {'success': False, 'data': []}

    def get_match(self):
        try:
            record = jsondb.get_record(self.source, self.params.get('id'))
            if record is None:
                return {'success': False, 'data': None}
            data = record if self.params.get('skip_convert_data_types') else convert_data_types([record])[0]
            return {'success': True, 'data': data}
        except Exception as e:
            logger.error(f'get_match failed: {e}')
            return {'success': False, 'data': None}

    def post_match(self):
        try:
            record = jsondb.insert_record(self.source, self.params)
            return _FakeResponse(201, record)
        except ValueError as e:
            logger.error(f'post_match conflict: {e}')
            return _FakeResponse(409, {'error': str(e)})
        except Exception as e:
            logger.error(f'post_match failed: {e}')
            return _FakeResponse(500, {'error': str(e)})

    def put_match(self):
        try:
            record = jsondb.update_record(self.source, self.params.get('id'), self.params)
            if record is None:
                return _FakeResponse(404, {})
            return _FakeResponse(200, record)
        except Exception as e:
            logger.error(f'put_match failed: {e}')
            return _FakeResponse(500, {'error': str(e)})

    def delete_match(self):
        try:
            removed = jsondb.delete_record(self.source, self.params.get('id'))
            return _FakeResponse(200 if removed else 404, {})
        except Exception as e:
            logger.error(f'delete_match failed: {e}')
            return _FakeResponse(500, {'error': str(e)})


if __name__ == "__main__":
    # Example usage
    import json
    res_ = JsonServerProcessor(source='1x', params={}).get_all_matches()
    print(json.dumps(res_.get('data', {}), indent=4))

    # res_ = JsonServerProcessor(source='8x', params=new_data).post_match()
    # res_ = JsonServerProcessor(source='8x', params={'id': "3347160"}).delete_match()
    # print(res_)
