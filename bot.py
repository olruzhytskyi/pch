import aiohttp
import asyncio
import async_timeout
import concurrent
import dryscrape
import json
import telepot

from bs4 import BeautifulSoup
from lxml import etree

TG_BOT_TOKEN = '350060259:AAGXwhskIaiPFBVlKwop_atIcKFY62dZSLs'

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
    'RealMadrid': ['RealMadrid'],
    'AtleticoMadrid': ['AtleticoMadrid'],
    'Dortmund': ['Dortmund', 'B.Dortmund', 'BorussiaDortmund'],
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

urls_with_data_in_html = {
    url_1: ('div', 'div', 'eventselection', 'eventprice'),
    url_2: ('span', 'span', 'odds-label', 'odds-value'),
    url_5: ('span', 'span', 'team-name', 'odd-val'),
    url_6: ('div', 'span', 'outrights-betting-title', 'odds-fractional'),
    url_7: ('span', 'span', 'seln-name', 'price frac'),
}

pages_to_run_js = {
    url_3: ('span', 'span', 'app--market__entry__name', 'app--market__entry__value'),
    url_8: ('div', 'div', 'eventselection', 'eventprice'),
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
        try:
            site_odds[site] = get_normalized_odds(odds)
        except KeyError as e:
            print ('Error on {}: {}'.format(site, e))

        driver.close()
        vdisplay.stop()

        return parsed_html

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

def send_odss_to_telegram_chat(odds, telepot_bot):
    print(telepot_bot.getMe())
    updates = telepot_bot.getUpdates()
    print(updates)
    ids = set(map(lambda x: x['message']['chat']['id'], updates))
    print(ids)
    for chat_id in ids:
        telepot_bot.sendMessage(chat_id, json.dumps(odds))


async def get_odds_by_classnames(parsed_html, comm_tag, odd_tag, command_class, odd_class):
    odds = []
    commands = []
    for elem in parsed_html.body.findAll(odd_tag, attrs={'class':odd_class}):
        odd = ''.join(elem.text.split())
        odds.append(odd)

    for elem in parsed_html.body.findAll(comm_tag, attrs={'class':command_class}):
        command = ''.join(elem.text.split())
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

async def main(loop):
    tp_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    #for url, tags in urls_with_data_in_html.items():
    # for url, tags in pages_to_run_js.items():
    coros = []
    for url, tags in urls_with_data_in_html.items():
        coros.append(get_odds_from_html(url, tags))
    for url, tags in pages_to_run_js.items():
        coros.append(get_odds_from_dryscape(url, tags, tp_executor))

    results = await asyncio.gather(*coros)
    site_odds = {}
    for result in results:
        site_odds.update(result)

#    site_odds = await get_odds_with_selenium(url_4, tp_executor)

    print(site_odds)

    # print(site_odds)
    # bot = telepot.Bot(TG_BOT_TOKEN)
    # send_odss_to_telegram_chat(site_odds, bot)

    # tg_bot = TelegramBot()
    # chat_ids = await tg_bot.get_bot_updates()
    # print(chat_ids)
    # for chat_id in chat_ids:
    #     await tg_bot.send_odds_to_telegram('blabla', chat_id)

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))