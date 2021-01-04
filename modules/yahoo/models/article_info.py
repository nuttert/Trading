import json

class ArticleInfo:
    def __init__(self, company, news_portal, title, date, link, brief, author=None):
        self._company = company.replace("'","\"") if company else None
        self._news_portal = news_portal.replace("'","\"") if news_portal else None
        self._title = title.replace("'","\"") if title else None
        self._date = date
        self._link = link
        self._brief = brief.replace("'","\"") if brief else None
        self._author = author.replace("'","\"") if author else None
    
    def get_company(self):
        return self._company

    def get_news_portal(self):
        return self._news_portal

    def get_date(self):
        return self._date

    def get_title(self):
        return self._title

    def get_link(self):
        return self._link

    def get_brief(self):
        return self._brief

    def get_author(self):
        return self._author

    def set_author(self, author):
        self._author = author

    def __str__(self):
        dict_res = self.get_dict()
        return json.dumps(dict_res, indent=2)

    def get_dict(self):
        dict_res = {
            "company":  "'{}'".format(self._company) if self._company else "null",
            "news_portal":  "'{}'".format(self._news_portal) if self._news_portal else "null",
            "title": "'{}'".format(self._title) if self._title else "null",
            "date": "'{}'".format(str(self._date)) if str(self._date) else "null",
            "link": "'{}'".format(self._link) if self._link else "null",
            "brief": "'{}'".format(self._brief) if self._brief else "null",
            "author": "'{}'".format(self._author) if self._author else "null",
        }
        return dict_res