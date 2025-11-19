import json

def load_articles():
    with open("sourcebox_blog.json", "r") as f:
        data = json.load(f)
    return data

articles = load_articles()
print(articles)