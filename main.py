import datetime
import os
import time

import requests
import sqlite3
from lxml import html
import logging
from bs4 import BeautifulSoup


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

colors = {
    'red': 0xcc0202,
    'green': 0x5e8705,
    'orange': 0xea9b1c,
    'purple2': 0x6d1878,
    'blue': 0x0271d1,
    'yellow': 0xf4cf3b,
    'white': 0xffffff,
}


simple_template = '''{
  "content": "%(message)s",
  "embeds": [
    {
      "title": "%(feeling)s",
      "description": "%(comment)s",
      "image": {
        "url": "%(pr_url)s"
      }
    }
  ]
}'''

template = '''{
  "content": "%(message)s",
  "embeds": [
    {
      "title": "%(feeling)s",
      "url": "%(provider_link)s",
      "color": %(color)s,
      "fields": [
        {
          "name": "Nyitás kezdete:",
          "value": "%(start_of_opening)s",
          "inline": true
        }
      ],
      "author": {
        "name": "%(circle_name)s",
        "url": "%(provider_link)s"
      }
    }
  ]
}'''

con = sqlite3.connect('db/sent.db')
cur = con.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS sent (id int)''')


def get_cute_animal(depth=10):
    if depth == 0:
        return ''

    page = requests.get('http://animalemails.com/')
    tree = html.fromstring(page.content)
    for img in tree.xpath("//img[@class='img-responsive']/@src"):
        response = requests.get(img)
        if response.status_code == 200:  # some pics are broken
            return img

    return get_cute_animal(depth-1)  # recursion if all pics are broken :(


while True:
    try:
        doc = BeautifulSoup(requests.get('https://schpincer.sch.bme.hu/').content, 'html.parser')
        openings = []
        for tr in doc.find(class_='circles-table').find_all('tr'):
            circle_id = str(tr.find(class_='arrow').find('a')['href']).split('/')[2]
            items = list(requests.get('https://schpincer.sch.bme.hu/api/items/?circle=' + circle_id).json())
            openings.append({
                'name': tr.find('a').contents[0],
                'circleUrl': 'https://schpincer.sch.bme.hu' + tr.find('a')['href'],
                'circleColor': tr['class'][0],
                'openingStart': int(datetime.datetime.strptime(tr.find(class_='date').contents[0], '%H:%M (%y-%m-%d)').timestamp())*1000,
                'feeling': dict(enumerate(tr.find(class_='feeling').contents)).get(0),
                'orderable': any(list(map(lambda a: a['orderable'] and not a['outOfStock'], items)))
            })
    except:
        logging.error('Problem while fetching pincer api')
        time.sleep(300)
        continue

    for opening in openings:
        if opening['orderable'] and not cur.execute("select * from sent where id=:id", {"id": opening['openingStart']}).fetchone():
            if opening['name'] == 'Vödör' or 'vodor' in opening['circleUrl']:
                content = simple_template % {
                    'message': "FYI, @&" + os.environ['MENTIONED_ROLE'],
                    "feeling": 'Mai cuki állatos kép',
                    "comment": 'Töltődj fel hétfőre ezzel a cuki állatos képpel!',
                    'pr_url': get_cute_animal()
                }
            else:
                content = template % {
                    'message': "FYI, @&" + os.environ['MENTIONED_ROLE'],
                    "feeling": opening['feeling'] or 'Új nyitást írtak ki',
                    "circle_name": opening['name'],
                    "provider_link": opening['circleUrl'],
                    "start_of_opening": str(datetime.datetime.fromtimestamp(opening['openingStart']/1000)),
                    'color': colors.get(opening['circleColor']) or colors['white']
                }
            logging.debug(content)
            resp = requests.post(os.environ['WEBHOOK_URL'], data=content.encode('utf-8'), headers={'Content-Type': 'application/json'})
            logging.debug(resp.content)
            cur.execute("insert into sent values (:id)", {"id": opening['openingStart']})
            con.commit()
    time.sleep(60)


