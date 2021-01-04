
from modules.fool.models.article_info import ArticleInfo
from modules.fool.models.article import Article

import requests
import os
import warnings

from urllib.parse import urljoin

from datetime import datetime, date, timedelta
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
import dateutil.parser

import urllib.request
import re
import pytz



class Fetcher(object):
    SCROLL_PAUSE_TIME = 0.15
    base_url = "https://www.fool.com"
    news_portal = "fool"

    articles_selector = '.list-content article'
    text_selector = '.article-content > p'
    timezone = pytz.timezone('US/Eastern')

    sources = [{
            "article_selector": articles_selector.format("Press Releases")
        },
    ]

    def __init__(self, api_key=None):
        if api_key:
            self.api_key =  api_key       
        else:
            self.api_key = self.load_apikey()

        self.headers = { "X-Api-Key" : self.api_key}
        
        self.conn = sql.connect(dbname='finan', user='postgres', 
                        password='postgres', host='database', port=5432)
        self.cursor = self.conn.cursor()

        self.cursor.execute("CREATE TABLE IF NOT EXISTS {} (company text, news_portal text, title text, date timestamp with time zone, link text, brief text, author text, text text);".format(self.news_portal))
        self.conn.commit()

    def get_endpoint(self, endpoint):
        return requests.get(urljoin(self.base_url, endpoint), headers = self.headers)

    def get_endpoint_path(self, endpoint):
        return urljoin(self.base_url, endpoint)

    def get_date_(self, content):
        base_link = content.find_element_by_css_selector('a').get_attribute('href')
        response = requests.get(base_link).text
        parser = BeautifulSoup(response, "html.parser")
        print(base_link)
        try:
            datetime_info = parser.select('.publication-date')[-1].text.replace("Published:", "")
            datetime_info = dateutil.parser.parse(datetime_info).replace(tzinfo=self.timezone)
        except:
            print("Wanr: Only update date")
        return  datetime_info


    def get_stream(self, company, stream_id, update = True, offset=1, limit=10,from_date=None, to_date=None, stock_type=''):
        if update:
            get_last_date = ('SELECT date FROM {} ORDER BY date DESC LIMIT 1').format(
                self.news_portal
            )
            self.cursor.execute(get_last_date)
            row = self.cursor.fetchone()
            if row and len(row) == 1:
                from_date = row[0]

        for source in self.sources:
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
            print(self.get_endpoint_path("quote/{}".format((stock_type+'/' if stock_type!='' else '') +company+'/'+stream_id)))
            driver.get(self.get_endpoint_path("quote/{}".format((stock_type+'/' if stock_type!='' else '') +company)))
            time.sleep(self.SCROLL_PAUSE_TIME)

            counter = 0
            content_size = 0
            content_list = driver.find_elements_by_css_selector(article_selector)

            while len(content_list) > content_size:
                driver.execute_script("""
                window.scrollTo(0, {0}*window.scrollHeight);

                tab = document.querySelector('#load-more');
                tab.click();
                """.format(counter))

                time.sleep(self.SCROLL_PAUSE_TIME)
                counter += 1
                print(counter, len(driver.find_elements_by_css_selector(article_selector)))
                if counter % 10 == 0:
                    content_size = len(content_list)
                    content_list = driver.find_elements_by_css_selector(article_selector)
                    if from_date and content_size > 0:
                        current_date = self.get_date_(content_list[-1])
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
                    try:
                        med = self.get_date_(content_list[med_index])
                    except:
                        continue
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
                        continue

                    print(base_link)
                    
                    header_base = content.find_element_by_css_selector('h4').text
                    brief = header_base



                    text_list = []

                    response = requests.get(base_link).text
                    parser = BeautifulSoup(response, "html.parser")
                    try:
                        if not header_base:
                             header_base = parser.select_one('h1').text
                             brief = header_base
                        text_list = parser.select(self.text_selector)
                        author = parser.select_one('.author-name').text
                        try:
                            datetime_info = parser.select('.publication-date')[-1].text.replace("Published:", "")
                            datetime_info = dateutil.parser.parse(datetime_info).replace(tzinfo=self.timezone)
                        except:
                            print("Wanr: Only update date")
                            continue
                        print(datetime_info)
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
