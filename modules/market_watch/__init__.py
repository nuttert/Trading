
__appname__ = "pyft"
__version__ = "0.1"

from modules.market_watch.models.article_info import ArticleInfo
from modules.market_watch.models.article import Article

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

class Fetcher(object):
    SCROLL_PAUSE_TIME = 0.2
    base_url = "https://www.marketwatch.com"
    news_portal = "market_watch"
    # articles_selector_mw = '[data-tab-pane="MarketWatch"] .collection__elements [data-guid]'
    # window_selector = '[data-tab-pane="MarketWatch"]'
    articles_selector_mw = '[data-tab-pane="{}"] .collection__elements [data-guid]'
    window_selector = '.element__body [data-tab-pane="{}"] mw-scrollable-news-v2'
    text_selector_mw = '#js-article__body p'

    tab_press_releases = '.tabs [data-tab-pane="Press Releases"]'
    # tab_dow_jones = '.tabs [data-tab-pane="Dow Jones"]'
    tab_dmerketwatch = '.tabs [data-tab-pane="MarketWatch"]'
    # tab_other_news = '.tabs [data-tab-pane="Other News"]'

    sources = [{
            "tab": tab_press_releases,
            "window_selector": window_selector.format("Press Releases"),
            "article_selector": articles_selector_mw.format("Press Releases")
        },
        {
            "tab": tab_dmerketwatch,
            "window_selector": window_selector.format("MarketWatch"),
            "article_selector": articles_selector_mw.format("MarketWatch")
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

        self.cursor.execute("CREATE TABLE IF NOT EXISTS {} (company text, news_portal text, title text, date timestamp with time zone, link text, brief text, author text, text text);".format(self.news_portal))
        self.conn.commit()

    def get_endpoint(self, endpoint):
        return requests.get(urljoin(self.base_url, endpoint), headers = self.headers)

    def get_endpoint_path(self, endpoint):
        return urljoin(self.base_url, endpoint)

    def get_date_(self, content):
        datetime_info = content.get_attribute('data-timestamp')
        if not datetime_info:
            return None
        datetime_info = int(datetime_info)//1000
        datetime_info = datetime.fromtimestamp(datetime_info)
        return  datetime_info


    def get_stream(self, company, stream_id, update=True, offset=1, limit=10,from_date=None, to_date=None, stock_type='stock'):
        if update:
            get_last_date = ('SELECT date FROM {} ORDER BY date DESC LIMIT 1').format(
                self.news_portal
            )
            self.cursor.execute(get_last_date)
            row = self.cursor.fetchone()
            if row and len(row) == 1:
                from_date = timestring.Date(row[0])
        for source in self.sources:
            tab = source['tab']
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
            
            driver.get(self.get_endpoint_path("investing/{}/{}".format(stock_type, stream_id)))
            print(self.get_endpoint_path("investing/{}/{}".format(stock_type, stream_id)))

            try:
                driver.execute_script("""
                    tab = document.querySelector('{0}');
                    tab.click();
                """.format(tab))
                time.sleep(self.SCROLL_PAUSE_TIME)
            except:
                print("Warning: couldn't find tab: press releases")
                continue

            counter = 0
            content_size = 0
            content_list = driver.find_elements_by_css_selector(article_selector)

            while len(content_list) > content_size:
                driver.execute_script("""
                sub_window = document.querySelector('{0}');
                sub_window.scrollTo(0, {1}*sub_window.scrollHeight);""".format(window_selector, counter))
                time.sleep(self.SCROLL_PAUSE_TIME)
                counter += 1
                
                if counter % 300 == 0:
                    content_size = len(content_list)
                    content_list = driver.find_elements_by_css_selector(article_selector)
                    print(counter, len(content_list))
                    if from_date and content_size > 0:
                        current_date = timestring.Date(self.get_date_(content_list[-1]))
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
                    med = timestring.Date(self.get_date_(content_list[med_index]))
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
                    try:
                        author = content.find_element_by_css_selector('.article__author').text.replace("by ","")
                    except:
                        author = None
                        pass

                    print(base_link)
                    
                    header_base = content.find_element_by_css_selector('h3').text
                    brief = header_base

                    datetime_info = content.get_attribute('data-timestamp')
                    if not datetime_info:
                        continue
                    datetime_info = int(datetime_info)//1000
                    datetime_info = str(datetime.fromtimestamp(datetime_info))
                    print(datetime_info)

                    text_list = []

                    if base_link:
                        response = requests.get(base_link).text
                        parser = BeautifulSoup(response, "html.parser")
                        try:
                            text_list = parser.select(self.text_selector_mw)
                        except Exception as e:
                                print("ERROR can't find article(perhaps, captcha)",str(e))
                    
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
