import requests
import json
import time
import argparse
from datetime import datetime
import sys

# --- Localization Data (L10N) ---
LOCALES = {
    'ru': {
        # Logging & Errors
        'getting_traffic': "Получение остатков трафика...",
        'traffic_step_1_error': "Traffic Step 1 Error:",
        'waiting_task': "Ожидание запуска задачи (3 сек)...",
        'checking_status': "Проверка статуса задачи (попытка {i}/{max_i})...",
        'task_running': "Задача выполняется, ожидание (2 сек)...",
        'traffic_received': "Данные о трафике получены.",
        'traffic_non_json': "Traffic Step 2: Non-JSON response received. Status: {status}",
        'task_timeout': "Traffic: Задача не завершилась вовремя.",
        'getting_balance': "Получение денежного баланса...",
        'balance_received': "Денежный баланс получен: {amount:.2f}",
        'balance_not_found': "Balance: Поле 'remainingValue' не найдено.",
        'error_fatal_cookie': "FATAL: Ошибка при загрузке Cookie: {e}",
        'error_loading_cookie': "Ошибка при загрузке Cookie",
        'error_no_cookies': "Cookie file was successfully read, but no valid cookies found.",
        'error_decoding_json': "Error decoding JSON cookie file:",
        'error_traffic_step_2': "Traffic Step 2 Error:",
        'error_balance': "Balance Error:",
        'error_summary': "❌ Сбор данных завершен с ошибками:",
        'data_header': "ДАННЫЕ ПО СЧЕТУ МТС ({phone})",
        'data_header_hidden_placeholder': "СКРЫТО", # New placeholder
        'data_not_available': "Н/Д",
        
        # Human Output Labels
        'label_balance': "Баланс (руб.)",
        'label_deadline': "Обновление пакета",
        'label_internet': "Интернет",
        'label_minutes': "Минуты",
        'label_sms': "SMS",
        
        # Units and Formatting
        'unit_rub': "руб.",
        'unit_kb': "КБ",
        'unit_mb': "МБ",
        'unit_gb': "ГБ",
        'unit_min': "мин",
        'unit_count': "шт",
        'format_from': " (из {total} {total_unit})",
    },
    'en': {
        # Logging & Errors
        'getting_traffic': "Fetching traffic counters...",
        'traffic_step_1_error': "Traffic Step 1 Error:",
        'waiting_task': "Waiting for task start (3 sec)...",
        'checking_status': "Checking task status (attempt {i}/{max_i})...",
        'task_running': "Task running, waiting (2 sec)...",
        'traffic_received': "Traffic data received.",
        'traffic_non_json': "Traffic Step 2: Non-JSON response received. Status: {status}",
        'task_timeout': "Traffic: Task did not complete within the timeout.",
        'getting_balance': "Fetching monetary balance...",
        'balance_received': "Monetary balance received: {amount:.2f}",
        'balance_not_found': "Balance: Could not find 'remainingValue' in GraphQL response.",
        'error_fatal_cookie': "FATAL: Error loading Cookie: {e}",
        'error_loading_cookie': "Error loading Cookie",
        'error_no_cookies': "Cookie file was successfully read, but no valid cookies found.",
        'error_decoding_json': "Error decoding JSON cookie file:",
        'error_traffic_step_2': "Traffic Step 2 Error:",
        'error_balance': "Balance Error:",
        'error_summary': "❌ Data collection completed with errors:",
        'data_header': "MTS ACCOUNT DATA ({phone})",
        'data_header_hidden_placeholder': "HIDDEN", # New placeholder
        'data_not_available': "N/A",

        # Human Output Labels
        'label_balance': "Balance (RUB)",
        'label_deadline': "Package Renewal",
        'label_internet': "Internet",
        'label_minutes': "Minutes",
        'label_sms': "SMS",
        
        # Units and Formatting
        'unit_rub': "RUB",
        'unit_kb': "KB",
        'unit_mb': "MB",
        'unit_gb': "GB",
        'unit_min': "min",
        'unit_count': "items",
        'format_from': " (out of {total} {total_unit})",
    }
}

# --- MTS Client Class ---

class MTSClient:
    """
    Client to fetch monetary balance and traffic counters from MTS using two different API methods.
    """
    
    TRAFFIC_START_URL = 'https://lk.mts.ru/api/sharing/counters?overwriteCache=false'
    TRAFFIC_CHECK_BASE_URL = 'https://lk.mts.ru/api/longtask/check/' 
    RUBLE_BALANCE_URL = 'https://federation.mts.ru/graphql'
    
    # GraphQL Query for Ruble Balance
    GRAPHQL_QUERY = {
        "operationName": "GetBalanceBaseQueryInput",
        "variables": {},
        "query": "query GetBalanceBaseQueryInput { balances { nodes { ... on BalanceInfo { remainingValue { amount currency __typename } __typename } ... on BalanceError { error { message code __typename } __typename } __typename } __typename } }"
    }

    def __init__(self, phone_number, cookie_string, locale_func):
        """Initializes the client with authentication details and localization function."""
        self.phone_number = phone_number
        self.cookie_string = cookie_string
        # self._ is now a callable function
        self._ = locale_func 
        
        self.HEADERS = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
            'Cookie': self.cookie_string,
            'Referer': 'https://lk.mts.ru/',
            'x-login': self.phone_number,
        }

    def _parse_netscape_cookies(self, file_path: str) -> str:
        """
        Reads a cookie file in Netscape format and converts it into a simple
        HTTP header string (key=value; key2=value2;...).
        """
        cookies = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Netscape format is usually tab-separated
                    parts = line.split('\t')
                    # A valid line has at least 7 parts
                    if len(parts) >= 7:
                        # parts[5] is the name, parts[6] is the value
                        name, value = parts[5], parts[6]
                        if name and value:
                            cookies[name] = value
            
            # Combine into the required string format for the HTTP header
            if not cookies:
                 raise ValueError(self._('error_no_cookies'))
                 
            return '; '.join([f"{name}={value}" for name, value in cookies.items()])
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: Cookie file not found at: {file_path}")
        except Exception as e:
            raise Exception(f"{self._('error_loading_cookie')}: {e}")
            
    def _parse_json_cookies(self, file_path: str) -> str:
        """
        Reads a cookie file in JSON format (key-value dictionary or array of objects)
        and converts it into an HTTP header string.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cookies = {}
            if isinstance(data, dict):
                # Assume simple key-value object: {"name": "value", ...}
                cookies = {k: v for k, v in data.items() if isinstance(v, str)}
            elif isinstance(data, list):
                # Attempt to parse common list of cookie objects: 
                # [{"name": "key", "value": "val"}, ...]
                for item in data:
                    if isinstance(item, dict) and 'name' in item and 'value' in item:
                        cookies[item['name']] = item['value']
            
            if not cookies:
                 raise ValueError(self._('error_no_cookies'))
                 
            return '; '.join([f"{name}={value}" for name, value in cookies.items()])
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: Cookie file not found at: {file_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"{self._('error_decoding_json')} {e}")
        except Exception as e:
            raise Exception(f"{self._('error_loading_cookie')}: {e}")


    def _format_deadline(self, iso_date_str):
        """Converts an ISO date string to DD.MM.YYYY format."""
        try:
            # Handle empty string or None for deadline date
            if not iso_date_str:
                return self._('data_not_available')
            date_part = iso_date_str.split('T')[0]
            dt = datetime.strptime(date_part, '%Y-%m-%d')
            return dt.strftime('%d.%m.%Y')
        except Exception:
            return self._('data_not_available')

    def _parse_traffic_data(self, data):
        """
        Extracts raw remaining/total traffic data in base units (KB, seconds, items).
        Returns raw data suitable for JSON/custom parsing.
        """
        
        # Initialize results with raw data fields (0.0 means N/A)
        results = { 
            'deadline_date': self._('data_not_available'),
            'remaining_internet_kb': 0.0,
            'total_internet_kb': 0.0,
            'remaining_minutes_sec': 0.0,
            'total_minutes_sec': 0.0,
            'remaining_sms_count': 0.0,
            'total_sms_count': 0.0,
        }

        counters = data.get('data', {}).get('counters', [])
        
        for counter in counters:
            # Set deadline date from the Main package group, if available
            if counter.get('packageGroup') == 'Main' and results['deadline_date'] == self._('data_not_available'):
                results['deadline_date'] = self._format_deadline(counter.get('deadlineDate'))
                 
            package_type = counter.get('packageType')
            unit_type = counter.get('unitType')

            # The remaining amount is in parts[2].amount ('NonUsed')
            non_used_amount = counter.get('parts', [{},{},{}])[2].get('amount', 0.0)
            total_amount = counter.get('totalAmount', 0.0)
            
            # Internet (KByte)
            if package_type == 'Internet' and unit_type == 'KByte':
                results['remaining_internet_kb'] = non_used_amount
                results['total_internet_kb'] = total_amount
            
            # Minutes (Second)
            elif package_type == 'Calling' and unit_type == 'Second':
                results['remaining_minutes_sec'] = non_used_amount
                results['total_minutes_sec'] = total_amount
                
            # SMS (Item)
            elif package_type == 'Messaging' and unit_type == 'Item':
                results['remaining_sms_count'] = non_used_amount
                results['total_sms_count'] = total_amount
                
        # Remove fields that remained 0.0 (no data for this counter)
        results_cleaned = {k: v for k, v in results.items() if v != 0.0 or k == 'deadline_date'}
        
        # Ensure deadline_date key exists even if empty
        if 'deadline_date' not in results_cleaned:
            results_cleaned['deadline_date'] = self._('data_not_available')
            
        return results_cleaned

    def get_traffic_data(self, log_info):
        """Executes the two-step REST API request for traffic data."""
        log_info(self._('getting_traffic'))
        
        # 1. START TASK
        try:
            response_start = requests.get(self.TRAFFIC_START_URL, headers=self.HEADERS, timeout=10)
            response_start.raise_for_status()
            task_id = response_start.text.strip().replace('"', '') 
        except requests.exceptions.RequestException as e:
            return {'error': f"{self._('traffic_step_1_error')} {e}"}

        # 2. CHECK TASK
        check_url = f"{self.TRAFFIC_CHECK_BASE_URL}{task_id}?for=api/sharing/counters"
        log_info(self._('waiting_task'))
        time.sleep(3) # Wait for server processing
        
        for i in range(5):
            try:
                log_info(self._('checking_status').format(i=i+1, max_i=5))
                response_check = requests.get(check_url, headers=self.HEADERS, timeout=10)
                response_check.raise_for_status()
                response_text = response_check.text 
                
                if response_text.startswith('{'):
                    data = json.loads(response_text)
                    if data.get('data'):
                        log_info(self._('traffic_received'))
                        # Returns raw data dict
                        return self._parse_traffic_data(data)
                    elif data.get('status') == 'Running':
                        log_info(self._('task_running'))
                        time.sleep(2)
                        continue
                else:
                    return {'error': self._('traffic_non_json').format(status=response_text[:30] + '...') if len(response_text) > 30 else response_text}

            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                 return {'error': f"{self._('error_traffic_step_2')} {e}"}

        return {'error': self._('task_timeout')}
    
    def get_ruble_balance(self, log_info):
        """Executes the GraphQL POST request for the monetary balance."""
        log_info(self._('getting_balance')) 
        headers = self.HEADERS.copy()
        headers.update({
            'Content-Type': 'application/json',
            'x-apollo-operation-name': 'GetBalanceBaseQueryInput',
            'x-client-id': 'LK',
            'Sec-Fetch-Site': 'same-site' # Required for federation.mts.ru
        })
        
        try:
            response = requests.post(self.RUBLE_BALANCE_URL, headers=headers, json=self.GRAPHQL_QUERY, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse GraphQL response for the amount
            balance_node = data.get('data', {}).get('balances', {}).get('nodes', [{}])
            if balance_node and 'remainingValue' in balance_node[0]:
                amount = balance_node[0]['remainingValue']['amount']
                log_info(self._('balance_received').format(amount=amount))
                # Return raw number
                return {'ruble_balance_raw': amount}
            
            return {'error': self._('balance_not_found')}

        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            return {'error': f"{self._('error_balance')} {e}"}


# --- CLI Main Function ---

def main():
    # --- Localization Setup (Pre-Parsing) ---
    # We set a default dict just for arg parsing, then fix to a function later
    locale_dict_pre = LOCALES['ru'] 
    
    parser = argparse.ArgumentParser(
        description="MTS Balance and Traffic Checker CLI Utility.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Cookie source
    group_cookie = parser.add_mutually_exclusive_group(required=True)
    group_cookie.add_argument('--cookies', type=str, help=locale_dict_pre.get('label_cookies_string', 'Полная строка cookie (напр., "key1=val1; key2=val2")'))
    group_cookie.add_argument('--cookies-file', type=str, help=locale_dict_pre.get('label_cookies_file', 'Путь к файлу с cookie.'))

    # Cookie format
    group_format = parser.add_mutually_exclusive_group()
    group_format.add_argument('--netscape', action='store_true', help='Использовать парсер формата Netscape для --cookies-file.')
    group_format.add_argument('--json', action='store_true', help='Использовать парсер формата JSON для --cookies-file.')

    parser.add_argument('--phone', type=str, required=True, help='Ваш номер телефона МТС (напр., 79XXXXXXXXX).')
    
    parser.add_argument(
        '--mode', 
        type=str, 
        default='all', 
        choices=['bal', 'traf', 'all'],
        help='Данные для получения: "bal" (только баланс), "traf" (только трафик), "all" (оба).'
    )

    # Logging
    parser.add_argument('--verbose', action='store_true', help='Показывать подробные логи получения данных в stderr.')

    # Localization
    parser.add_argument('--lang', type=str, default='ru', choices=LOCALES.keys(), 
                        help='Язык вывода: "ru" (Русский) или "en" (English).')

    # Data output formatting and units
    parser.add_argument('--human', action='store_true', 
                        help='Отображать вывод в человекочитаемом формате (напр., "100.5 руб.", "10 ГБ").')
    
    # Flag to hide phone number
    parser.add_argument('--hide-phone', action='store_true', 
                        help='Скрывать номер телефона в человекочитаемом выводе (будет показано "СКРЫТО" / "HIDDEN").')

    group_units = parser.add_mutually_exclusive_group()
    group_units.add_argument('--kilo', action='store_true', help='Отображать интернет-трафик в КБ (только для --human).')
    group_units.add_argument('--mega', action='store_true', help='Отображать интернет-трафик в МБ (только для --human).')
    group_units.add_argument('--giga', action='store_true', help='Отображать интернет-трафик в ГБ (только для --human).')
    
    parser.add_argument(
        '--output', 
        type=str, 
        default='parse', # Default to machine-readable parse
        choices=['parse', 'json'],
        help='Формат машиночитаемого вывода:\n'
             '  parse: Строка, разделенная key=value (по умолчанию)\n'
             '  json: Чистый вывод JSON'
    )
    
    args = parser.parse_args()

    # --- Final Localization Setup: Create the Callable Function ---
    try:
        locale_dict = LOCALES[args.lang]
    except KeyError:
        # Fallback to Russian if invalid language is provided
        locale_dict = LOCALES['ru']
        print(f"Warning: Invalid language code '{args.lang}'. Defaulting to Russian ('ru').", file=sys.stderr)

    # THIS IS THE FIX: Define the callable translation function
    def _(key):
        return locale_dict.get(key, f"MISSING_KEY:{key}")

    # --- Unicode Fix and Conditional Logging Setup ---
    # Fix UnicodeEncodeError: ensure stdout/stderr use UTF-8
    try:
        # Reconfigure streams to use UTF-8 encoding
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older Python versions
        pass

    # Helper function to print verbose logs to stderr
    def log_info(message):
        if args.verbose:
            print(f"INFO: {message}", file=sys.stderr)

    # --- 1. Load Cookies ---
    cookie_string = ""
    try:
        # Pass the callable function '_' to the temporary client
        client_temp = MTSClient(args.phone, "", _)
        
        if args.cookies:
            cookie_string = args.cookies
        elif args.cookies_file:
            if args.netscape and args.json:
                # Use a specific error string from the locale function
                # Note: This error message is technically wrong but preserves original CLI structure
                raise ValueError(_('error_decoding_json')) 
            elif args.netscape:
                cookie_string = client_temp._parse_netscape_cookies(args.cookies_file)
            elif args.json:
                cookie_string = client_temp._parse_json_cookies(args.cookies_file)
            else:
                with open(args.cookies_file, 'r', encoding='utf-8') as f:
                    cookie_string = f.read().strip()
    except Exception as e:
        print(_('error_fatal_cookie').format(e=e), file=sys.stderr)
        sys.exit(1)

    # --- 2. Initialize and Collect Data ---
    # Pass the callable function '_' to the main client
    client = MTSClient(args.phone, cookie_string, _)
    
    raw_data = {}
    
    if args.mode in ('all', 'bal'):
        # The fix for the original error: now passing a callable log_info function
        balance_res = client.get_ruble_balance(log_info) 
        raw_data.update(balance_res)
    
    if args.mode in ('all', 'traf'):
        traffic_res = client.get_traffic_data(log_info) 
        raw_data.update(traffic_res)

    # --- 3. Check for Errors ---
    errors = {k: v for k, v in raw_data.items() if k.endswith('error')}
    
    if errors:
        print(f"\n{_('error_summary')}", file=sys.stderr)
        for k, v in errors.items():
            print(f"   [{k.split('_')[0].upper()}]: {v}", file=sys.stderr)
        if not args.human and args.output != 'json':
            # Exit only if machine-readable parse output is expected and errors occurred
            sys.exit(1)
            
    # Remove error keys for cleaner output
    clean_data = {k: v for k, v in raw_data.items() if not k.endswith('error')}
    
    # --- 4. Process for Output Formats ---

    # --- 4A. Define Machine-Readable Data (JSON/Parse) ---
    machine_data = {}
    # NOTE: Machine-readable keys are intentionally kept in English/Latin for consistency/parsing ease.
    if 'ruble_balance_raw' in clean_data:
        machine_data['balance_rub'] = round(clean_data['ruble_balance_raw'], 2)
        
    if 'deadline_date' in clean_data and clean_data['deadline_date'] != _('data_not_available'):
        machine_data['deadline_date'] = clean_data['deadline_date'] 

    # Internet 
    if 'remaining_internet_kb' in clean_data and 'total_internet_kb' in clean_data:
        machine_data['remaining_internet_mb'] = round(clean_data['remaining_internet_kb'] / 1024, 2)
        machine_data['total_internet_gb'] = round(clean_data['total_internet_kb'] / (1024 * 1024), 2)
    
    # Minutes
    if 'remaining_minutes_sec' in clean_data and 'total_minutes_sec' in clean_data:
        machine_data['remaining_minutes_min'] = int(clean_data['remaining_minutes_sec'] / 60)
        machine_data['total_minutes_min'] = int(clean_data['total_minutes_sec'] / 60)
        
    # SMS 
    if 'remaining_sms_count' in clean_data and 'total_sms_count' in clean_data:
        machine_data['remaining_sms_count'] = int(clean_data['remaining_sms_count'])
        machine_data['total_sms_count'] = int(clean_data['total_sms_count'])


    if not args.human:
        # Machine-readable output requested

        if args.output == 'json':
            # Include errors in JSON if they exist
            if errors:
                machine_data['errors'] = errors
            print(json.dumps(machine_data, ensure_ascii=False, indent=2))
        
        elif args.output == 'parse':
            # Line separated key=value (default machine output)
            for key, value in machine_data.items():
                print(f"{key}={value}")
        return

    # --- 4B. Human Readable Output (if --human is set) ---
    
    def format_internet_traffic(remaining_kb, total_kb, args, _):
        """Formats Internet traffic based on CLI unit flags for human output with smart scaling."""
        if total_kb == 0:
            return _('data_not_available')

        GIGA_THRESHOLD = 1024 * 1024 # 1 GB in KB

        # Check if any explicit unit flag is set
        if args.kilo or args.mega or args.giga:
            # Explicit flags: use the same unit for both remaining and total
            divisor = 1
            unit = _('unit_kb')
            
            if args.mega:
                divisor = 1024
                unit = _('unit_mb')
            elif args.giga:
                divisor = GIGA_THRESHOLD
                unit = _('unit_gb')
            
            remaining = round(remaining_kb / divisor, 2)
            total = round(total_kb / divisor, 2)
            return f"{remaining} {unit}{_('format_from').format(total=total, total_unit=unit)}"
        
        else:
            # Smart auto-scaling logic (user request):
            # If total or remaining is >= 1 GB, use GB for both.
            if remaining_kb >= GIGA_THRESHOLD or total_kb >= GIGA_THRESHOLD:
                remaining_gb = round(remaining_kb / GIGA_THRESHOLD, 2)
                total_gb = round(total_kb / GIGA_THRESHOLD, 2)
                unit = _('unit_gb')
                return f"{remaining_gb} {unit}{_('format_from').format(total=total_gb, total_unit=unit)}"
            else:
                # Otherwise (both are < 1GB, but total is package size), use MB remaining vs GB total format
                remaining_mb = int(remaining_kb / 1024)
                total_gb = round(total_kb / GIGA_THRESHOLD, 2) 
                unit_rem = _('unit_mb')
                unit_tot = _('unit_gb')
                return f"{remaining_mb} {unit_rem}{_('format_from').format(total=total_gb, total_unit=unit_tot)}"

    def format_minutes_traffic(remaining_sec, total_sec, _):
        remaining_min = int(remaining_sec / 60)
        total_min = int(total_sec / 60)
        unit = _('unit_min')
        return f"{remaining_min} {unit}{_('format_from').format(total=total_min, total_unit=unit)}"

    def format_sms_traffic(remaining_count, total_count, _):
        remaining_sms = int(remaining_count)
        total_sms = int(total_count)
        unit = _('unit_count')
        return f"{remaining_sms} {unit}{_('format_from').format(total=total_sms, total_unit=unit)}"

    # Handle phone display for header (FIXED: now uses hiding placeholder)
    phone_display = args.phone
    if args.hide_phone:
        # If the user wants to hide the phone number, replace it with a placeholder
        phone_display = _('data_header_hidden_placeholder') 
    
    # Prepare final human-readable data
    final_human_data = {}
    
    if 'ruble_balance_raw' in clean_data:
        final_human_data[_('label_balance')] = f"{clean_data['ruble_balance_raw']:.2f} {_('unit_rub')}"
    
    if 'deadline_date' in clean_data:
        final_human_data[_('label_deadline')] = clean_data['deadline_date']

    if 'remaining_internet_kb' in clean_data:
        final_human_data[_('label_internet')] = format_internet_traffic(
            clean_data['remaining_internet_kb'],
            clean_data['total_internet_kb'],
            args,
            _
        )

    if 'remaining_minutes_sec' in clean_data:
        final_human_data[_('label_minutes')] = format_minutes_traffic(
            clean_data['remaining_minutes_sec'],
            clean_data['total_minutes_sec'],
            _
        )

    if 'remaining_sms_count' in clean_data:
        final_human_data[_('label_sms')] = format_sms_traffic(
            clean_data['remaining_sms_count'],
            clean_data['total_sms_count'],
            _
        )
    
    # Print human readable table
    SEPARATOR = "==============================="
    header_text = _('data_header').format(phone=phone_display)
    
    # Calculate padding for centered output
    padding_size = (len(SEPARATOR) - len(header_text)) // 2
    padding = ' ' * padding_size
    
    print(f"\n{SEPARATOR}")
    print(f"{padding}{header_text}{padding}")
    print(f"{SEPARATOR}")

    # Find max key length for clean alignment
    max_key_len = max(len(key) for key in final_human_data.keys()) if final_human_data else 0
    
    for key, value in final_human_data.items():
        # Align the key and add colon separator
        print(f"{key.ljust(max_key_len)}: {value}")
        
    print(f"{SEPARATOR}")


if __name__ == '__main__':
    main()
