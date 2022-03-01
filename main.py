import datetime
import os
import time
import requests
import sqlite3
from lxml import html


API_URL = 'https://schpincer.sch.bme.hu/api/open/upcoming-openings?token=%s'

# [
#   {
#       "name":"Vödör",
#       "orderStart":1645376400000,
#       "openingStart":1645466400000,
#       "icon":"https://schpincer.sch.bme.hu/cdn/logos/0000016e-5132-d10f-814e-c2e2eba089f2.png",
#       "feeling":"sosem késő",
#       "available":0,
#       "outOf":52,
#       "banner":"https://schpincer.sch.bme.hu/image/blank-pr.jpg",
#       "day":"Hétfő",
#       "comment":"Hétfő 16:00-ig rendelhető",
#       "circleUrl":"https://schpincer.sch.bme.hu/p/vodor",
#       "circleColor":"purple2"
#   },
#   {
#       "name":"Americano",
#       "orderStart":1645383600000,
#       "openingStart":1645556400000,
#       "icon":"https://schpincer.sch.bme.hu/cdn/logos/0000016e-7a0c-b385-23f2-9cf8b8e75e03.png",
#       "feeling":"",
#       "available":25,
#       "outOf":120,
#       "banner":"https://schpincer.sch.bme.hu/cdn/pr/0000017f-1897-4054-3dfb-9963cd551796.png",
#       "day":"Kedd",
#       "comment":"Kedd 16:00-ig rendelhető",
#       "circleUrl":"https://schpincer.sch.bme.hu/p/americano",
#       "circleColor":"orange"
#   }
# ]


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
  "content": "FYI, @here",
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
  "content": "FYI, @here",
  "embeds": [
    {
      "title": "%(feeling)s",
      "description": "%(comment)s",
      "url": "%(provider_link)s",
      "color": %(color)s,
      "timestamp": "%(start_of_order_iso)s",
      "fields": [
        {
          "name": "Rendelés kezdete:",
          "value": "%(start_of_order)s"
        },
        {
          "name": "Nyitás kezdete:",
          "value": "%(start_of_opening)s",
          "inline": true
        },
        {
          "name": "Ennyi adagot készítünk:",
          "value": "%(max_orders)s",
          "inline": true
        }
      ],
      "author": {
        "name": "%(circle_name)s",
        "url": "%(provider_link)s",
        "icon_url": "%(circle_logo_url)s"
      },
      "image": {
        "url": "%(pr_url)s"
      },
      "thumbnail": {
        "url": "%(circle_logo_url)s"
      }
    }
  ]
}'''

con = sqlite3.connect('sent.db')
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
        openings = requests.get(API_URL % os.environ['SCHPINCER_TOKEN']).json()
    except:
        print('Problem while fetching pincer api')
        time.sleep(300)
        continue

    for opening in openings:
        if not cur.execute("select * from sent where id=:id", {"id": opening['openingStart']}).fetchone() and \
                (datetime.datetime.fromtimestamp(opening['orderStart']/1000) - datetime.datetime.now()).total_seconds() < 3600:
            if opening['name'] == 'Vödör' or 'vodor' in opening['circleUrl']:
                content = simple_template % {
                    "feeling": 'Mai cuki állatos kép',
                    "comment": 'Töltődj fel hétfőre ezzel a cuki állatos képpel!',
                    'pr_url': get_cute_animal()
                }
            else:
                content = template % {
                    "feeling": opening['feeling'] or 'Új nyitást írtak ki',
                    "comment": opening['comment'],
                    'pr_url': opening['banner'],
                    "circle_logo_url": opening['icon'],
                    "circle_name": opening['name'],
                    "provider_link": opening['circleUrl'],
                    "start_of_opening": str(datetime.datetime.fromtimestamp(opening['openingStart']/1000)),
                    "start_of_order": str(datetime.datetime.fromtimestamp(opening['orderStart']/1000)),
                    'start_of_order_iso': str(datetime.datetime.utcfromtimestamp(opening['orderStart']/1000).isoformat()) + '.000Z',
                    'max_orders': opening['outOf'],
                    'color': colors.get(opening['circleColor']) or colors['white']
                }
            print(content, flush=True)
            resp = requests.post(os.environ['WEBHOOK_URL'], data=content.encode('utf-8'), headers={'Content-Type': 'application/json'})
            print(resp.content)
            cur.execute("insert into sent values (:id)", {"id": opening['openingStart']})
            con.commit()
    time.sleep(60)


