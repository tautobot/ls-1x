import requests
from horus.config import logger, JSON_SERVER_BASE_URL


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


class JsonServerProcessor(object):

    def __init__(self, source, params, **kwargs):
        self.source = source
        self.params = params
        self.headers = {
            'accept': 'application/json, text/plain, */*',
        }

    def _get(self, url, params):
        response = {}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                data = {
                    'success': True,
                    'data'   : convert_data_types(response.json()) if not self.params.get('skip_convert_data_types') else response.json(),
                }
                return data
            else:
                logger.error(f"Request failed with status code: {response.status_code}")
                # Access the error message, if available
                error_message = response.text
                logger.error(error_message)
        except requests.exceptions.RequestException as e:
            logger.error(f'RequestException: {e}')
        except ConnectionResetError:
            logger.error('ConnectionResetError')
        data = {
            'success': False,
            'data'   : response,
        }

        return data

    def get_all_matches(self):
        url = f"{JSON_SERVER_BASE_URL}/{self.source}"
        # return response
        res_ = self._get(url, {})

        return res_

    def get_match(self):
        url = f"{JSON_SERVER_BASE_URL}/{self.source}/{self.params.get('id')}"
        # return response
        data = self._get(url, {})

        return data

    def post_match(self):
        # data = self.params

        url = f"{JSON_SERVER_BASE_URL}/{self.source}"
        # return response
        resp_ = requests.post(url, headers=self.headers, data=self.params)

        return resp_

    def put_match(self):
        url = f"{JSON_SERVER_BASE_URL}/{self.source}/{self.params.get('id')}"
        # return response
        resp_ = requests.put(url, headers=self.headers, data=self.params)

        return resp_

    def delete_match(self):
        url = f"{JSON_SERVER_BASE_URL}/{self.source}/{self.params.get('id')}"
        # return response
        resp_ = requests.delete(url, headers=self.headers, data={})

        return resp_


if __name__ == "__main__":
    # Example usage
    import json
    res_ = JsonServerProcessor(source='1x', params={}).get_all_matches()
    print(json.dumps(res_.get('data', {}), indent=4))

    # res_ = JsonServerProcessor(source='8x', params=new_data).post_match()
    # res_ = JsonServerProcessor(source='8x', params={'id': "3347160"}).delete_match()
    # print(res_)
