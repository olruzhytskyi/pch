import aiohttp
import asyncio
import async_timeout
import concurrent
import dbm
import dryscrape
import json
import telepot

from bs4 import BeautifulSoup
from lxml import etree

TG_BOT_TOKEN = '350060259:AAGXwhskIaiPFBVlKwop_atIcKFY62dZSLs'
FETCH_INTERVAL = 5 # seconds
CACHE_FILE = 'cache.dbm'

url_1 = 'http://sports.williamhill.com/bet/en-gb/betting/e/10810406/UEFA+Champions+League+-+To+Reach+The+Final.html'
url_2 = 'http://www.paddypower.com/football/euro-football/champions-league'
url_3 = 'https://www.21bet.co.uk/sportsbook/SOCCER/EU_CL/269006/'
url_4 = 'https://www.spreadex.com/sports/en-GB/spread-betting/Football-European/Champions-League/Champions-League-2016-17/p461635'
url_5 = 'http://www.sportsbet.com.au/betting/soccer/uefa-competitions/uefa-champions-league/Champions-League-Outright-2016-17-2710742.html'
url_6 = 'http://sports.coral.co.uk/football/uefa-club-comps/champions-league/outrights?body_only=Y'
url_7 = 'http://sports.titanbet.com/en/t/19161/UEFA-Champions-League?mkt_sort=X086'
url_8 = 'https://mobile.bet365.com/V6/sport/coupon/coupon.aspx?zone=9&isocode=UA&tzi=1&key=1-172-1-29101630-2-0-0-0-2-0-0-4063-0-0-1-0-0-0-0-0-0&ip=0&gn=0&cid=1&lng=1&ct=195&clt=9996&ot=1'
url_9 = 'https://sports.betstars.com/sportsbook/v1/api/getRegionalOutrights?sport=SOCCER&channelId=6&locale=en-gb&siteId=1'

command_mappings = {
    'BayernMunich': ['B.Munich', 'BayernMunich', 'Bayern Munich'],
    'Monaco': ['Monaco', 'ASMonaco'],
    'Juventus': ['Juventus'],
    'Leicester': ['Leicester', 'LeicesterCity'],
    'Barcelona': ['Barcelona'],
    'RealMadrid': ['RealMadrid', 'Real Madrid'],
    'AtleticoMadrid': ['AtleticoMadrid', 'Atletico Madrid'],
    'Dortmund': ['Dortmund', 'B.Dortmund', 'BorussiaDortmund', 'Borussia Dortmund'],
}

urls = [
    url_1, # 'div', 'eventselection', 'eventprice'
    url_2, # 'span', 'odds-label', 'odds-value'
    url_3, # 'span', 'app--market__entry__name', 'app--market__entry__value' --> need to be run with dryscrape
    url_4, # Fucking doesn't show what needed
    url_5, # 'span', 'team-name', 'odd-val' (no slash values)
    url_6, # 'div', 'span', 'outrights-betting-title', 'odds-fractional'
    url_7, # 'span', 'span', 'seln-name', 'price frac' Gives more, but possible to select
    url_8, # 'span', 'span', 'opp', 'odds' JSON should be parsed
]

pages_with_data_in_html = {
    url_1: ('div', 'div', 'eventselection', 'eventprice'),
    url_2: ('span', 'span', 'odds-label', 'odds-value'),
    url_5: ('span', 'span', 'team-name', 'odd-val'),
    url_6: ('div', 'span', 'outrights-betting-title', 'odds-fractional'),
    url_7: ('span', 'span', 'seln-name', 'price frac'),
}

pages_to_run_js = {
    url_3: ('span', 'span', 'app--market__entry__name', 'app--market__entry__value'),
    url_8: ('span', 'span', 'opp', 'odds'),
}

pages_to_run_selenium = {
    url_4,
}

pages_with_json = {
    url_9,
}

def get_fqdn(url):
    return url.split('//')[1].split('/')[0]

def get_normalized_odds(odds):
    normalized_odds = {}
    for key in command_mappings:
        for map_key in command_mappings[key]:
            try:
                normalized_odds[key] = odds[map_key]
            except KeyError:
                continue
            else:
                break
        # Key should be populated now
        if not key in normalized_odds:
            raise KeyError(key)
    return normalized_odds

async def get_html_with_dryscape(url, executor):
    loop = asyncio.get_event_loop()
    def get_html(url):
        session = dryscrape.Session()
        session.visit(url)
        response = session.body()
        parsed_html = BeautifulSoup(response, 'lxml')
        return parsed_html

    result = await loop.run_in_executor(executor, get_html, url)
    return result

async def get_odds_with_selenium(url, executor):
    loop = asyncio.get_event_loop()

    def get_html(url):
        from selenium import webdriver
        from xvfbwrapper import Xvfb
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        import selenium.webdriver.support.expected_conditions as EC
        import selenium.webdriver.support.ui as ui
        # start xvfb
        vdisplay = Xvfb()
        vdisplay.start()
        # return True if element is visible within 5 seconds, otherwise False
        def wait_until_is_visible(locator, timeout=5):
            try:
                ui.WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CLASS_NAME, locator)))
                return True
            except TimeoutException:
                return False
        driver = webdriver.Firefox()
        driver.get(url)
        driver.find_element_by_class_name("buttonlist").find_element_by_class_name("fixedodds").click()
        wait_until_is_visible("dref")
        elements = driver.find_element_by_class_name("panel").find_elements_by_tag_name("tr")
        odds = {}
        for element in elements:
            value = element.text.split("\n")
            odds[value[0]] = value[1]

        site = get_fqdn(url)
        print(odds)
        site_odds = {}
        try:
            site_odds[site] = get_normalized_odds(odds)
        except KeyError as e:
            print ('Error on {}: {}'.format(site, e))

        driver.close()
        vdisplay.stop()

        return site_odds

    result = await loop.run_in_executor(executor, get_html, url)
    return result

async def fetch(session, url):
    with async_timeout.timeout(10):
        async with session.get(url) as response:
            return await response.text()

async def post(session, url, data):
    with async_timeout.timeout(10):
        async with session.post(url, data=data) as response:
            return await response.text()

async def get_parsed_html(url):
    async with aiohttp.ClientSession(loop=loop) as session:
        html = await fetch(session, url)
        parsed_html = BeautifulSoup(html, 'lxml')
        return parsed_html

def get_updates_from_bot(telepot_bot, offset=0):
    print(telepot_bot.getMe())
    # with dbm.open(CACHE_FILE, 'c') as chat_ids_store:
    #     existing_ids = json.loads(chat_ids_store.get('ids', b'[]').decode())
    updates = telepot_bot.getUpdates(offset=offset)
    print(updates)
    offset = max(map(int, [u['update_id'] for u in updates])) + 1 if updates else 0
    print(offset)
    ids_from_updates = list(map(lambda x: x['message']['chat']['id'], updates))
    messages = list(map(lambda x: x['message']['text'], updates))
    ids_msg = list(zip(ids_from_updates, messages))
#    ids = list(set(existing_ids + ids_from_updates))
#    chat_ids_store['ids'] = json.dumps(ids)
    ids = list(set(ids_from_updates))
    subscribes = set([i for i, msg in ids_msg if msg == 'start'])
    unsubscribes = set([i for i, msg in ids_msg if msg == 'stop'])
    print ("Subscribes: {}".format(subscribes))
    print ("Unsubscribes: {}".format(unsubscribes))

    print(ids)

    return (offset, subscribes, unsubscribes)

async def get_odds_by_classnames(parsed_html, comm_tag, odd_tag, command_class, odd_class):
    odds = []
    commands = []
    for elem in parsed_html.body.findAll(odd_tag, attrs={'class':odd_class}):
        elem = elem.replace_with('')
        odd = ''.join(elem.text.strip().split())
        odds.append(odd)

    for elem in parsed_html.body.findAll(comm_tag, attrs={'class':command_class}):
        elem = elem.replace_with('')
        command = ''.join(elem.text.strip().split())
        commands.append(command)

    return dict(zip(commands, odds))

async def get_odds_from_html(url, tags):
    parsed_html = await get_parsed_html(url)
    odds = await get_odds_by_classnames(parsed_html, *tags)
    site = get_fqdn(url)
    site_odds = {}
    try:
        site_odds[site] = get_normalized_odds(odds)
    except KeyError as e:
        print ('Error on {}: {}'.format(site, e))
    return site_odds

async def get_odds_from_dryscape(url, tags, tp_executor):
    parsed_html = await get_html_with_dryscape(url, tp_executor)
    odds = await get_odds_by_classnames(parsed_html, *tags)
    site = get_fqdn(url)
    site_odds = {}
    try:
        site_odds[site] = get_normalized_odds(odds)
    except KeyError as e:
        print ('Error on {}: {}'.format(site, e))
    return site_odds

async def get_odds_from_json(url):
    async with aiohttp.ClientSession(loop=loop) as session:
        json_resp = await fetch(session, url)
        parsed_json = json.loads(json_resp)

        lc_index = next(index for (index, d) in enumerate(parsed_json) if d["categoryName"] == "Champions League")
        teams = parsed_json[lc_index]['event'][0]['markets'][1]['selection']
        odds = {team['name']:team['odds']['dec'] for team in teams}

        site = get_fqdn(url)
        site_odds = {}
        try:
            site_odds[site] = get_normalized_odds(odds)
        except KeyError as e:
            print ('Error on {}: {}'.format(site, e))
        return site_odds

def uk2eu(uk_odd):
    # convert uk odds type e.g. "1/5" to euro odds type e.g. 1.20
    values = uk_odd.split("/")
    values = list(map(int, values))
    euro = values[0] / values[1] + 1
    return "{:.2f}".format(euro)

def format_odds(site_odds):
    """Returns str in format:
    Site -> Command:odd|Command:odd|

    """
    formatted_odds = ''
    for site, odds in site_odds.items():
        formatted_site_odds = '{} -> '.format(site)
        for key, val in odds.items():
            try:
                val = float(val)
            except ValueError:
                val = uk2eu(val)
            site_odds[site][key] = val

            formatted_odd = ':'.join([key, str(val)])
            formatted_site_odds = '|'.join([formatted_site_odds, formatted_odd])
        formatted_odds = '\n'.join([formatted_odds, formatted_site_odds])
    return formatted_odds

async def main(loop):
    tp_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    bot = telepot.Bot(TG_BOT_TOKEN)
    tp_updates_offset = 0
    subscribed = set()

    while True:
        coros = [
            get_odds_from_html(url, tags)
            for url, tags in pages_with_data_in_html.items()
        ] + [
            get_odds_from_dryscape(url, tags, tp_executor)
            for url, tags in pages_to_run_js.items()
        ] + [
            get_odds_with_selenium(url_4, tp_executor),
            get_odds_from_json(url_9),
        ]

        results = await asyncio.gather(*coros)
        site_odds = {}
        for result in results:
            site_odds.update(result)

#        site_odds = await get_odds_from_dryscape(url_8, pages_to_run_js[url_8], tp_executor)
#        site_odds = await get_odds_with_selenium(url_4, tp_executor)
        # js_odds = await get_odds_from_json(url_9)
        # print(format_odds(js_odds))
        print (format_odds(site_odds))

        # print(format_odds(site_odds))
        tp_updates_offset, sub, unsub = get_updates_from_bot(bot, offset=tp_updates_offset)
        subscribed |= sub
        subscribed -= unsub

        print('Subscribed: {}'.format(subscribed))

        for chat_id in subscribed:
            print ("Sending: {}".format(site_odds))
            telepot_bot.sendMessage(chat_id, format_odds(site_odds))

        # chat_ids = await tg_bot.get_bot_updates()
        # print(chat_ids)
        # for chat_id in chat_ids:
        #     await tg_bot.send_odds_to_telegram('blabla', chat_id)

        await asyncio.sleep(FETCH_INTERVAL)
    # print(site_odds)
loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))
