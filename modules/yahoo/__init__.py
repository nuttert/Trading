
__appname__ = "pyft"
__version__ = "0.1"

from modules.yahoo.models.article_info import ArticleInfo
from modules.yahoo.models.article import Article

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


# Метод отправки API запроса прямо в плагин
# Например для инициализации API ключа сервиса anti-captcha.com, необходимый для работы плагина
# Работает только на действующей HTML страничке,
# в нашем случае на https://antcpt.com/blank.html
# на страницах вроде about:blank запрос не пройдет
def acp_api_send_request(driver, message_type, data={}):
    message = {
        # всегда указывается именно этот получатель API сообщения
        'receiver': 'antiCaptchaPlugin',
        # тип запроса, например setOptions
        'type': message_type,
        # мерджим с дополнительными данными
        **data
    }
    # выполняем JS код на странице
    # а именно отправляем сообщение стандартным методом window.postMessage
    return driver.execute_script("""
    return window.postMessage({});
    """.format(json.dumps(message)))

class Fetcher(object):
    SCROLL_PAUSE_TIME = 0.1
    base_url = "https://finance.yahoo.com"
    news_portal = "yahoo"

    def __init__(self, api_key=None):
        if api_key:
            self.api_key =  api_key       
        else:
            self.api_key = self.load_apikey()

        self.headers = { "X-Api-Key" : self.api_key}
        
        self.conn = sql.connect(dbname='finan', user='postgres', 
                        password='postgres', host='database')
        self.cursor = self.conn.cursor()

        self.cursor.execute("CREATE TABLE IF NOT EXISTS yahoo (company text, news_portal text, title text, date timestamp with time zone, link text, brief text, author text, text text);")
        self.conn.commit()

    def get_endpoint(self, endpoint):
        return requests.get(urljoin(self.base_url, endpoint), headers = self.headers)

    def get_endpoint_path(self, endpoint):
        return urljoin(self.base_url, endpoint)


    def get_date_(self, content):
        base_link = content.find_element_by_css_selector('a').get_attribute('href')

        if not base_link.startswith(self.base_url):
            return None
        self.page_driver.get(base_link)
        datetime_info = self.page_driver.find_element_by_css_selector('time').get_attribute('datetime')
        return  timestring.Date(datetime_info)


    def get_stream(self, company, stream_id, update= True, offset=1, limit=10,from_date=None, to_date=None, stock_type='index'):
        articles = []
        if update:
            get_last_date = ('SELECT date FROM {} ORDER BY date DESC LIMIT 1').format(
                self.news_portal
            )
            self.cursor.execute(get_last_date)
            row = self.cursor.fetchone()
            if row and len(row) == 1:
                from_date = row[0]

        if from_date and to_date and from_date > to_date:
            raise RuntimeError("from date > to date")

        chromedriver = "/usr/local/bin/chromedriver"
        op = webdriver.ChromeOptions()
        op.add_argument('headless')
        op.add_argument('--no-sandbox')
        op.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(chromedriver, options=op)
        self.page_driver = webdriver.Chrome(chromedriver, options=op)

        driver.get(self.get_endpoint_path("quote/{0}/news?p={0}".format(stream_id,stream_id)))
        # self.page_driver.add_extension("buster_captcha_solver_for_humans-0.6.0.xpi")
        # self.page_driver.set_preference("security.fileuri.strict_origin_policy", False)
        print(self.get_endpoint_path("quote/{0}/news?p={0}".format(stream_id,stream_id)))


        counter = 0
        content_size = 0
        content_list = driver.find_elements_by_css_selector('#latestQuoteNewsStream-0-Stream > ul > li, #quoteNewsStream-0-Stream > ul > li')
        time.sleep(self.SCROLL_PAUSE_TIME)

        while len(content_list) > content_size:
            driver.execute_script("window.scrollTo(0, {0}*document.body.scrollHeight);".format(counter))
            time.sleep(self.SCROLL_PAUSE_TIME)
            counter += 1
            print(counter, len(driver.find_elements_by_css_selector('#latestQuoteNewsStream-0-Stream > ul > li, #quoteNewsStream-0-Stream > ul > li')))
            if counter % 10 == 0:
                content_size = len(content_list)
                content_list = driver.find_elements_by_css_selector('#latestQuoteNewsStream-0-Stream > ul > li, #quoteNewsStream-0-Stream > ul > li')
                if from_date and content_size > 0:
                      current_date = self.get_date_(content_list[-1])
                      if current_date < from_date:
                          break


        print("Found {} articles without filters".format(len(content_list)))
        
        if from_date:
            start_index = 0
            last_index = len(content_list)-1
            result_index = None
            
            while(start_index <= last_index):
                med_index = int((start_index+last_index)/2)
                med = self.get_date_(content_list[med_index])
                if not med:
                    continue
                if from_date < med:
                    start_index = med_index+1
                elif from_date > med:
                    last_index = med_index-1
                else:
                    break
            result_index = med_index
        else:
            result_index = -1

        for content in content_list[:result_index][::-1]:
            try:
                base_link = content.find_element_by_css_selector('a').get_attribute('href')

                if not base_link.startswith(self.base_url):
                    continue
                self.page_driver.get(base_link)

                header_base = self.page_driver.find_element_by_css_selector('h1').text
                brief = self.page_driver.find_element_by_css_selector('.caas-content-wrapper .caas-body').text

                author = self.page_driver.find_element_by_css_selector('.caas-content-wrapper .caas-attr .caas-attr-meta')
                exclude_time = self.page_driver.find_element_by_css_selector('.caas-content-wrapper .caas-attr .caas-attr-time-style').text
                author  = author.text.replace(exclude_time, "")

                datetime_info = self.page_driver.find_element_by_css_selector('time').get_attribute('datetime')

                if not datetime_info:
                    continue

                try:
                    read_more_button = WebDriverWait(self.page_driver, self.SCROLL_PAUSE_TIME).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, '.caas-readmore a, .caas-readmore button')))
                
                    page_link = read_more_button.get_attribute('href')
                    if page_link:
                        self.page_driver.get(page_link)
                        time.sleep(self.SCROLL_PAUSE_TIME)
                    else:
                        read_more_button.click()
                except:
                    page_link = None
                    pass
                
                print("Link: ",page_link if page_link else base_link)
                try:
                    # response = requests.get(base_link).text
                    # parser = BeautifulSoup(response, "html.parser")
                    # text_list = parser.select('article p, [class*="article"] p, [id*="article"]  p')
                    
                    header = WebDriverWait(self.page_driver, self.SCROLL_PAUSE_TIME).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))).text
                    WebDriverWait(self.page_driver, self.SCROLL_PAUSE_TIME).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article  p, [class*="article"]  p')))
                    text_list = self.page_driver.find_elements_by_css_selector('article p, [class*="article"] p, [id*="article"]  p')

                except Exception as e:
                        print("ERROR can't find article(perhaps, captcha)")
                        text_list = []
                        header = header_base
                
                text = ""
                for text_p in text_list:
                    text += text_p.text + " "


                article_info = ArticleInfo(company, self.news_portal, header, datetime_info, page_link if page_link else base_link, brief, author)
                article = Article(text, article_info)

                articles.append(article)


                dict_article = article.get_dict()

                insert = ('INSERT INTO yahoo ({}) VALUES ({})').format(
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
