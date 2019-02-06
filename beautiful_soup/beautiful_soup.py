# import libraries
import requests
from bs4 import BeautifulSoup

# specify the url
quote_page = "http://www.oughton.io"

page = requests.get(quote_page)

soup = BeautifulSoup(page.content, 'html.parser')

#print(soup.prettify())

#print(list(soup.children))

#print([type(item) for item in list(soup.children)])

# html = list(soup.children)[2]

# body = list(html.children)[3]

# print(list(body.children))

print(soup.find_all('p')[0].get_text())
