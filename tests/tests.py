import unittest
from datetime import datetime
# from market_watch import Fetcher
# from investorplace import Fetcher
from modules.fool import Fetcher
# from barrons import Fetcher
# from yahoo import Fetcher
import timestring

class TestFTAPI(unittest.TestCase):

    def  setUp(self):
        self.ft = Fetcher()

        #this tests with key file/environ, make tests for these individually

    def test_stream(self):
        # from_date = timestring.Date("2017-05-05 13:19:00+00")
        # from_date = None
        # content_json = self.ft.get_stream(company="sp-500-index", stream_id="%5Egspc", from_date=from_date, stock_type='snpindex')
        content_json = self.ft.get_stream(company="NIO", stream_id="")
        # self.assertTrue("bodyXML" in content_json)

    # def test_content_notifications(self):
        
    #     #test since yesterday 
    #     #yesterday = datetime.now()
    #     content_json = self.ft.get_content_notifications("2015-01-01")
    #     self.assertTrue("requestUrl" in content_json)
    #     self.assertTrue("notifications" in content_json)
        
if __name__ == "__main__":
    unittest.main()

