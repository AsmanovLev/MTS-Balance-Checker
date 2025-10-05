import json, sys
from mts_balance_checker import MTSClient, LOCALES

PHONE_NUMBER = "79110001122"
COOKIE_STRING = """JSESSIONID=...; lk_mts_sid=...""" 

client = MTSClient(
    phone_number=PHONE_NUMBER, 
    cookie_string=COOKIE_STRING, 
    locale_func=lambda key: LOCALES['ru'][key]
)

balance_data = client.get_ruble_balance(lambda msg: None)
traffic_data = client.get_traffic_data(lambda msg: None)

full_data = {}
full_data.update(balance_data)
full_data.update(traffic_data)

print(json.dumps(full_data, indent=2, ensure_ascii=False))
