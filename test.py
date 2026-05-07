from bs4 import BeautifulSoup

with open("scielo_debug.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

# Print all unique div classes in the page
div_classes = set()
for div in soup.find_all("div", class_=True):
    for cls in div["class"]:
        div_classes.add(cls)

print(sorted(div_classes))

for art in soup.select("div.results div.item")[:1]:  # just first article
    for div in art.find_all("div"):
        print(repr(div.get("class")), "|", div.get_text(strip=True)[:80])