import os
import aiohttp
import asyncio
import json
import logging
from config import logger
from database import cur, db, get_flag_by_country_name

LZT_BASE_URL = "https://api.lzt.market"

# Comprehensive Country Name to ISO 3166-1 alpha-2 mapping with all aliases
COUNTRY_TO_LZT = {
    'USA/Canada': 'us', 'USA': 'us', 'United States': 'us', 'United States of America': 'us',
    'Russia': 'ru', 'Russian Federation': 'ru',
    'UK': 'gb', 'United Kingdom': 'gb', 'Great Britain': 'gb', 'Britain': 'gb', 'England': 'gb',
    'India': 'in', 'Indonesia': 'id', 'Brazil': 'br', 'Brasil': 'br',
    'Pakistan': 'pk', 'Bangladesh': 'bd', 'Nigeria': 'ng', 'Philippines': 'ph',
    'Egypt': 'eg', 'Vietnam': 'vn', 'Viet Nam': 'vn', 'Turkey': 'tr', 'Turkiye': 'tr',
    'Iran': 'ir', 'Thailand': 'th', 'Germany': 'de', 'France': 'fr', 'Italy': 'it',
    'South Africa': 'za', 'Myanmar': 'mm', 'Burma': 'mm', 'South Korea': 'kr', 'Korea': 'kr',
    'Colombia': 'co', 'Spain': 'es', 'Argentina': 'ar', 'Algeria': 'dz', 'Ukraine': 'ua',
    'Iraq': 'iq', 'Afghanistan': 'af', 'Poland': 'pl', 'Canada': 'ca', 'Morocco': 'ma',
    'Saudi Arabia': 'sa', 'Uzbekistan': 'uz', 'Peru': 'pe', 'Angola': 'ao', 'Malaysia': 'my',
    'Mozambique': 'mz', 'Ghana': 'gh', 'Yemen': 'ye', 'Nepal': 'np', 'Venezuela': 've',
    'Madagascar': 'mg', 'Cameroon': 'cm', 'Ivory Coast': 'ci', 'North Korea': 'kp',
    'Australia': 'au', 'Taiwan': 'tw', 'Sri Lanka': 'lk', 'Kazakhstan': 'kz', 'Chile': 'cl',
    'Zambia': 'zm', 'Romania': 'ro', 'Chad': 'td', 'Somalia': 'so', 'Senegal': 'sn',
    'Netherlands': 'nl', 'Ecuador': 'ec', 'Guatemala': 'gt', 'Zimbabwe': 'zw',
    'Cambodia': 'kh', 'Rwanda': 'rw', 'Benin': 'bj', 'Burundi': 'bi', 'Tunisia': 'tn',
    'Bolivia': 'bo', 'Belgium': 'be', 'Haiti': 'ht', 'Cuba': 'cu', 'South Sudan': 'ss',
    'Dominican Republic': 'do', 'Czech Republic': 'cz', 'Czechia': 'cz', 'Greece': 'gr',
    'Jordan': 'jo', 'Portugal': 'pt', 'Azerbaijan': 'az', 'Sweden': 'se', 'Honduras': 'hn',
    'UAE': 'ae', 'United Arab Emirates': 'ae', 'Hungary': 'hu', 'Tajikistan': 'tj',
    'Belarus': 'by', 'Austria': 'at', 'Papua New Guinea': 'pg', 'Serbia': 'rs',
    'Israel': 'il', 'Switzerland': 'ch', 'Togo': 'tg', 'Sierra Leone': 'sl', 'Hong Kong': 'hk',
    'Laos': 'la', 'Paraguay': 'py', 'Bulgaria': 'bg', 'Libya': 'ly', 'Lebanon': 'lb',
    'Nicaragua': 'ni', 'Kyrgyzstan': 'kg', 'El Salvador': 'sv', 'Turkmenistan': 'tm',
    'Singapore': 'sg', 'Denmark': 'dk', 'Finland': 'fi', 'Congo': 'cg', 'Slovakia': 'sk',
    'Norway': 'no', 'Oman': 'om', 'Costa Rica': 'cr', 'Liberia': 'lr', 'Ireland': 'ie',
    'New Zealand': 'nz', 'Kuwait': 'kw', 'Panama': 'pa', 'Croatia': 'hr', 'Georgia': 'ge',
    'Eritrea': 'er', 'Uruguay': 'uy', 'Bosnia and Herzegovina': 'ba', 'Mongolia': 'mn',
    'Armenia': 'am', 'Jamaica': 'jm', 'Qatar': 'qa', 'Albania': 'al', 'Lithuania': 'lt',
    'Namibia': 'na', 'Gambia': 'gm', 'Botswana': 'bw', 'Gabon': 'ga', 'Lesotho': 'ls',
    'Slovenia': 'si', 'Latvia': 'lv', 'Bahrain': 'bh', 'North Macedonia': 'mk',
    'Trinidad and Tobago': 'tt', 'Estonia': 'ee', 'Mauritius': 'mu', 'Cyprus': 'cy',
    'Eswatini': 'sz', 'Djibouti': 'dj', 'Fiji': 'fj', 'Comoros': 'km', 'Guyana': 'gy',
    'Bhutan': 'bt', 'Solomon Islands': 'sb', 'Luxembourg': 'lu', 'Montenegro': 'me',
    'Suriname': 'sr', 'Cape Verde': 'cv', 'Malta': 'mt', 'Belize': 'bz', 'Brunei': 'bn',
    'Bahamas': 'bs', 'Maldives': 'mv', 'Iceland': 'is', 'Vanuatu': 'vu', 'Barbados': 'bb',
    'Sao Tome and Principe': 'st', 'Samoa': 'ws', 'Saint Lucia': 'lc', 'Kiribati': 'ki',
    'Micronesia': 'fm', 'Grenada': 'gd', 'Tonga': 'to', 'Seychelles': 'sc',
    'Saint Vincent and the Grenadines': 'vc', 'Antigua and Barbuda': 'ag', 'Andorra': 'ad',
    'Dominica': 'dm', 'Saint Kitts and Nevis': 'kn', 'Monaco': 'mc', 'Liechtenstein': 'li',
    'San Marino': 'sm', 'Palau': 'pw', 'Tuvalu': 'tv', 'Nauru': 'nr'
}

# Reverse mapping: code -> Country name
LZT_TO_COUNTRY = {v: k for k, v in COUNTRY_TO_LZT.items()}

def get_lzt_code(country_name):
    if not country_name:
        return None
    clean = str(country_name).strip()
    if clean in COUNTRY_TO_LZT:
        return COUNTRY_TO_LZT[clean]
    clean_lower = clean.lower()
    for k, v in COUNTRY_TO_LZT.items():
        if k.lower() == clean_lower:
            return v
    if len(clean) == 2 and clean.isalpha():
        return clean.lower()
    return None

def get_country_from_lzt(code):
    if not code: return "Unknown"
    return LZT_TO_COUNTRY.get(code.lower(), code.upper())

DC_IPS = {
    1: '149.154.175.50',
    2: '149.154.167.51',
    3: '149.154.175.100',
    4: '149.154.167.91',
    5: '91.108.56.130'
}

def extract_telethon_string_session(item_dict):
    """Robustly extracts Telethon StringSession from any LZT item representation."""
    if not isinstance(item_dict, dict):
        return None
    try:
        import struct, socket, base64
        login_data = item_dict.get('loginData') or {}
        raw = login_data.get('raw') or item_dict.get('raw') or ''
        auth_key_hex = None
        dc_id = None
        
        # Method 1: from loginData['login'] (512-hex auth key) and password/telegram_dc_id
        login_val = str(login_data.get('login') or '').strip()
        if len(login_val) == 512:
            auth_key_hex = login_val
            dc_val = login_data.get('password') or item_dict.get('telegram_dc_id') or 2
            try: dc_id = int(str(dc_val).strip())
            except: dc_id = 2
            
        # Method 2: from raw string if login wasn't 512 hex
        if not auth_key_hex and raw:
            raw_clean = raw.replace('%3A', ':')
            if ':' in raw_clean:
                k_hex, d_str = raw_clean.split(':', 1)
                if len(k_hex.strip()) == 512:
                    auth_key_hex = k_hex.strip()
                    try: dc_id = int(d_str.strip())
                    except: dc_id = 2
                    
        if not auth_key_hex:
            return None
            
        auth_key_bytes = bytes.fromhex(auth_key_hex)
        ip_str = DC_IPS.get(dc_id, '149.154.167.51')
        ip_bytes = socket.inet_aton(ip_str)
        port = 443
        packed = struct.pack('>B4sH', dc_id, ip_bytes, port) + auth_key_bytes
        return '1' + base64.urlsafe_b64encode(packed).decode('ascii')
    except Exception as e:
        logger.error(f"Error extracting telethon session: {e}")
        return None

def lzt_raw_to_string_session(raw_str):
    """Convert LZT auth key string (hex:dc_id) into a valid Telethon StringSession."""
    return extract_telethon_string_session({'raw': raw_str})

class LZTClient:
    def __init__(self):
        pass

    def get_token(self):
        res = cur.execute("SELECT value FROM settings WHERE key='lzt_api_key'").fetchone()
        return res[0] if res and res[0] else os.getenv("LZT_API_KEY", "")

    def get_headers(self):
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Numbott/1.0"
        }

    async def check_connection(self):
        """Check if API key is valid and get user info / balance."""
        token = self.get_token()
        if not token:
            return False, "❌ LZT API Key not configured."
        
        url = f"{LZT_BASE_URL}/user"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        user = data.get("user", {})
                        username = user.get("username", "Unknown")
                        balance = user.get("balance", 0)
                        currency = user.get("currency", "RUB")
                        return True, f"✅ Connected to LZT!\n👤 User: <b>{username}</b>\n💰 Balance: <b>{balance} {currency}</b>"
                    else:
                        try:
                            err_data = await resp.json()
                            errors = err_data.get("errors", [])
                            err_str = ", ".join(errors) if isinstance(errors, list) else str(errors)
                            return False, f"❌ LZT Error: {err_str}"
                        except:
                            text = await resp.text()
                            return False, f"⚠️ LZT Error (Status {resp.status}): {text[:100]}"
        except Exception as e:
            logger.error(f"LZT check connection error: {e}")
            return False, f"❌ Network error connecting to LZT: {str(e)}"

    async def get_available_countries(self):
        """Fetch available telegram countries from LZT."""
        url = f"{LZT_BASE_URL}/telegram"
        params = {
            "order_by": "price_to_up",
            "parse_sticky_items": "0"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), params=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        country_counts = {}
                        for item in items:
                            c_code = (item.get("telegram_country") or item.get("country") or "").lower()
                            if c_code:
                                c_name = get_country_from_lzt(c_code)
                                country_counts[c_name] = country_counts.get(c_name, 0) + 1
                        return country_counts
        except Exception as e:
            logger.error(f"LZT get countries error: {e}")
        return {}

    async def get_balance_info(self):
        """Fetch balance details including account balance_id, RUB balance, and USD balance."""
        url = f"{LZT_BASE_URL}/user"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        user = data.get("user", {})
                        balances = user.get("balances", [])
                        balance_id = None
                        balance_rub = 0.0
                        balance_usd = 0.0
                        for b in balances:
                            if b.get("type") == "account":
                                balance_id = b.get("balance_id")
                                balance_rub = float(b.get("balance", 0))
                                balance_usd = float(b.get("convertedBalance", 0))
                                break
                        if not balance_id:
                            balance_usd = float(user.get("balance", 0))
                            balance_rub = balance_usd * 84.0
                        return balance_id, balance_rub, balance_usd
        except Exception as e:
            logger.error(f"Error fetching LZT balance info: {e}")
        return None, 0.0, 0.0

    async def get_balance_rub(self):
        """Fetch current LZT account/market balance in RUB."""
        _, bal_rub, _ = await self.get_balance_info()
        return bal_rub

    async def search_items(self, country_name, year=None, limit=20, mode='bulk'):
        """Search available Telegram accounts for a country and optional year, filtered by available balance and mode."""
        c_code = get_lzt_code(country_name)
        if not c_code or len(c_code) != 2:
            logger.warning(f"No valid 2-letter ISO country code mapped for '{country_name}'")
            return []

        url = f"{LZT_BASE_URL}/telegram"
        balance_id, balance_rub, balance_usd = await self.get_balance_info()
        
        params = {
            "country[]": c_code.upper(),
            "order_by": "price_to_up",
            "parse_sticky_items": "0"
        }
        if mode == 'nonspam':
            params["spamblock"] = "0"
        elif mode == 'spam':
            params["spamblock"] = "1"

        if balance_rub > 0:
            params["pmax"] = int(balance_rub)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), params=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        results = []
                        import datetime
                        for item in items:
                            # 1. STRICT COUNTRY ENFORCEMENT
                            item_c = (item.get("telegram_country") or item.get("country") or "").strip().upper()
                            if item_c != c_code.upper():
                                continue

                            # Filter checks by mode
                            sb = item.get("telegram_spam_block")
                            if mode == 'nonspam' and sb == 1:
                                continue

                            has_mail = bool(item.get("mail") or item.get("email_type") in ("native", "domain", "temporary"))
                            if mode == 'no_email' and has_mail:
                                continue
                            elif mode == 'with_email' and not has_mail:
                                continue

                            is_prem = bool(item.get("telegram_premium") or item.get("premium"))
                            if mode == 'premium' and not is_prem:
                                continue

                            stars_cnt = int(item.get("telegram_stars") or item.get("stars") or 0)
                            if mode == 'stars' and stars_cnt <= 0:
                                continue

                            dc_val = item.get("telegram_dc") or item.get("dc")
                            if mode == 'dc5' and str(dc_val) != '5':
                                continue

                            price_rub = item.get("rub_price")
                            if price_rub is None:
                                price_rub = float(item.get("price", 0))
                            else:
                                price_rub = float(price_rub)

                            # Strictly ensure price is within our LZT wallet balance
                            if balance_rub > 0 and price_rub > balance_rub:
                                continue

                            created_ts = item.get("telegram_session_created_at") or item.get("telegram_register_date") or item.get("register_date") or 0
                            if created_ts and created_ts > 1000000:
                                try: item_year = datetime.datetime.fromtimestamp(created_ts).year
                                except: item_year = 2026
                            elif created_ts and 1900 < created_ts < 2100:
                                item_year = int(created_ts)
                            else:
                                item_year = 2026
                                
                            if year is not None and int(year) != int(item_year):
                                continue
                                
                            pwd_val = item.get("telegram_password_value") or item.get("telegram_password") or item.get("password") or "None"
                            has_pwd = bool(pwd_val and str(pwd_val) not in ("0", "None", "False"))
                            
                            if mode == 'no_2fa' and has_pwd:
                                continue
                            elif mode == 'with_2fa' and not has_pwd:
                                continue
                            
                            results.append({
                                "item_id": item.get("item_id"),
                                "price_rub": price_rub,
                                "price_usd": float(item.get("price", 0)),
                                "price_str": str(item.get("price", "0.1")),
                                "balance_id": balance_id,
                                "phone": item.get("telegram_phone") or item.get("phone") or "Hidden",
                                "year": item_year,
                                "title": item.get("title", ""),
                                "has_2fa": has_pwd,
                                "twofa_pass": str(pwd_val) if has_pwd else "None"
                            })
                        return results
        except Exception as e:
            logger.error(f"LZT search items error for {country_name}: {e}")
        return []

    async def fast_buy(self, item_id, price_str, balance_id=None):
        """Perform fast-buy for an item on LZT with balance_id."""
        url = f"{LZT_BASE_URL}/{item_id}/fast-buy"
        if balance_id is None:
            bid, _, _ = await self.get_balance_info()
            balance_id = bid

        payload = {"price": str(price_str)}
        if balance_id:
            payload["balance_id"] = balance_id
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.get_headers(), json=payload, timeout=25) as resp:
                    data_json = await resp.json()
                    if resp.status == 200 and not data_json.get("errors"):
                        item = data_json.get("item", {})
                        phone = item.get("telegram_phone") or item.get("phone") or ""
                        str_sess = extract_telethon_string_session(item)
                        
                        pwd = item.get("telegram_password_value") or item.get("telegram_password") or item.get("password") or item.get("twofa") or "None"
                        return True, {
                            "item_id": item_id,
                            "phone": phone,
                            "string_session": str_sess,
                            "twofa": str(pwd) if (pwd and str(pwd) not in ("0", "None", "False")) else "None",
                            "item_data": item
                        }
                    else:
                        errors = data_json.get("errors", ["Failed to purchase"])
                        err = errors[0] if isinstance(errors, list) and errors else str(errors)
                        return False, f"{err}"
        except Exception as e:
            logger.error(f"LZT fast_buy error for {item_id}: {e}")
            return False, f"Network error during purchase: {str(e)}"

    async def get_otp_code(self, item_id):
        """Fetch incoming SMS / Telegram login OTP code for the purchased item."""
        url = f"{LZT_BASE_URL}/{item_id}/code"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        code = data.get("code") or data.get("sms_code") or data.get("telegram_code")
                        if code:
                            return str(code).strip()
        except Exception as e:
            logger.error(f"LZT get_otp_code error for {item_id}: {e}")
        return None

lzt_client = LZTClient()
