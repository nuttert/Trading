
__appname__ = "pyft"
__version__ = "0.1"

from modules.barrons.models.article_info import ArticleInfo
from modules.barrons.models.article import Article

import requests
import os
import warnings

from urllib.parse import urljoin

from datetime import datetime, date, time
import timestring
import json
import time 

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from pyvirtualdisplay import Display

import psycopg2 as sql
from bs4 import BeautifulSoup

import urllib.request

import pytz
import dateutil.parser
import re

class Fetcher(object):
    SCROLL_PAUSE_TIME = 0.5
    base_url = "https://www.barrons.com"
    news_portal = "barrons"

    articles_selector = '#barronsNews .news-columns > li'
    window_selector = '#barrons-news-infinite'
    text_selector_mw = '[class*="article"] p'
    timezone = pytz.timezone('US/Eastern')

    sources = [{
            "window_selector": window_selector,
            "article_selector": articles_selector
        },
    ]

    def __init__(self, api_key=None):
        if api_key:
            self.api_key =  api_key       
        else:
            self.api_key = self.load_apikey()

        self.headers = { "X-Api-Key" : self.api_key}
        
        self.conn = sql.connect(dbname='finan', user='postgres', 
                        password='postgres', host='database')
        self.cursor = self.conn.cursor()
        
        days = ""
        days_amount = 30
        for day in range(1,days_amount+1):
            days += "global_{}_day float".format(day)
            if day != days_amount:
                days += ","

        hours = ""
        hours_amount = 7
        for hour in range(1,hours_amount+1):
            hours += "local_{}_hour float".format(hour)
            if hour != hours_amount:
                hours += ","

        (self.cursor.execute("CREATE TABLE IF NOT EXISTS {} (company text, news_portal text, title text, date timestamp with time zone, link text, brief text, author text, text text, {}, {});".
            format(self.news_portal,
            days,
            hours
        )))
        self.conn.commit()

    def get_endpoint(self, endpoint):
        return requests.get(urljoin(self.base_url, endpoint), headers = self.headers)

    def get_endpoint_path(self, endpoint):
        return urljoin(self.base_url, endpoint)

    def get_date_(self):
        parser = BeautifulSoup(self.page_driver.page_source, "html.parser")
        
        datetime_info = parser.select_one('time').text.replace("ET", "")
        
        indexies = re.search(r'\b(Original)\b', datetime_info)
        if indexies:
            datetime_info = datetime_info[indexies.end():]

        datetime_info = dateutil.parser.parse(datetime_info).replace(tzinfo=self.timezone)
        return datetime_info


    def get_stream(self, company, stream_id, update=True, offset=1, limit=10,from_date=None, to_date=None, stock_type='stock'):
        if update:
            get_last_date = ('SELECT date FROM {} ORDER BY date DESC LIMIT 1').format(
                self.news_portal
            )
            self.cursor.execute(get_last_date)
            row = self.cursor.fetchone()
            if row and len(row) == 1:
                from_date = row[0]
        for source in self.sources:
            window_selector = source['window_selector']
            article_selector = source['article_selector']
            
            articles = []

            if from_date and to_date and from_date > to_date:
                raise RuntimeError("from date > to date")

            chromedriver = "/usr/local/bin/chromedriver"
            op = webdriver.ChromeOptions()
            op.add_argument('headless')
            op.add_argument('--no-sandbox')
            op.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(chromedriver, options=op)
            self.page_driver = webdriver.Chrome(chromedriver, options=op)
            
            driver.get(self.get_endpoint_path("quote/stock/{}".format(stream_id)))

            counter = 0
            content_size = 0
            content_list = driver.find_elements_by_css_selector(article_selector)

            while len(content_list) > content_size:
                driver.execute_script("""
                sub_window = document.querySelector('{0}');
                sub_window.scrollTo(0, {1}*sub_window.scrollHeight);""".format(window_selector, counter))
                time.sleep(self.SCROLL_PAUSE_TIME)
                counter += 1
                print(counter, len(driver.find_elements_by_css_selector(article_selector)))
                if counter % 10 == 0:
                    content_size = len(content_list)
                    content_list = driver.find_elements_by_css_selector(article_selector)
                    if from_date and content_size > 0:
                        base_link = content_list[-1].find_element_by_css_selector('a').get_attribute('href')
                        self.page_driver.get(base_link)
                        current_date = self.get_date_()
                        if current_date < from_date:
                            break


            print("Found {} articles without filters".format(len(content_list)))
            
            result_index = -1
            if from_date:
                start_index = 0
                last_index = len(content_list)-1
                result_index = None
                
                while(start_index <= last_index):
                    med_index = int((start_index+last_index)/2)
                    base_link = content_list[med_index].find_element_by_css_selector('a').get_attribute('href')
                    self.page_driver.get(base_link)
                    med = self.get_date_()

                    if not med:
                        continue
                    if from_date < med:
                        start_index = med_index+1
                    elif from_date > med:
                        last_index = med_index-1
                    else:
                        break
                result_index = med_index

            for content in content_list[:result_index][::-1]:
                try:
                    try:
                        base_link = content.find_element_by_css_selector('a').get_attribute('href')
                    except:
                        base_link = None
                        pass

                    print(base_link)
                    
                    header_base = content.find_element_by_css_selector('a').text
                    brief = header_base

                    text_list = []
                    datetime_info = None
                    author = None

                    if base_link:
                        self.page_driver.get(base_link)
                        
                        parser = BeautifulSoup(self.page_driver.page_source, "html.parser")
                        try:
                            datetime_info = parser.select_one('time').text.replace("ET", "")
                            
                            indexies = re.search(r'\b(Original)\b', datetime_info)
                            if indexies:
                                datetime_info = datetime_info[indexies.end():]

                            datetime_info = dateutil.parser.parse(datetime_info).replace(tzinfo=self.timezone)
                        
                            if not datetime_info:
                                continue
                            try:
                                author = parser.select_one('.author .name').text
                            except:
                                pass
                            text_list = parser.select(self.text_selector_mw)
                        except Exception as e:
                                print("ERROR can't find article(perhaps, captcha)", str(e))


                    text = ""
                    for text_p in text_list:
                        text += text_p.text + " "


                    article_info = ArticleInfo(company, self.news_portal, header_base, datetime_info, base_link, brief, author)
                    article = Article(text, article_info)

                    articles.append(article)


                    dict_article = article.get_dict()

                    insert = ('INSERT INTO {} ({}) VALUES ({})').format(
                        self.news_portal,
                        ",".join(list(dict_article.keys())),
                        ",".join(list(dict_article.values()))
                    )

                    self.cursor.execute(insert)
                    self.conn.commit()
                except Exception as e:
                    print("ERROR", str(e))
                    continue

        
    def load_apikey(self):
        return ""
