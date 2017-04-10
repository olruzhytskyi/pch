import dryscrape
from bs4 import BeautifulSoup

my_url = 'https://www.21bet.co.uk/sportsbook/SOCCER/EU_CL/269006/'
url_4 = 'https://www.spreadex.com/sports/en-GB/spread-betting/Football-European/Champions-League/Champions-League-2016-17/p461635'
url_6 = 'http://sports.coral.co.uk/football/uefa-club-comps/champions-league'
url_8 = 'https://mobile.bet365.com/#type=Coupon;key=1-172-1-29101630-2-0-0-0-2-0-0-4063-0-0-1-0-0-0-0-0-0;ip=0;lng=1;anim=1'

session = dryscrape.Session()
session.visit(url_8)
response = session.body()
print (response)
#soup = BeautifulSoup(response)
