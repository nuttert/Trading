from datetime import datetime
from modules.market_watch import Fetcher as MarketWatch
from modules.investorplace import Fetcher as Investorplace
from modules.fool import Fetcher as Fool
from modules.barrons import Fetcher as Barrons
from modules.yahoo import Fetcher as Yahoo


if __name__ == "__main__":
    company = "NIO"
    stream_id = "NIO"

    portals = [
        MarketWatch,
        Investorplace,
        Fool,
        Barrons,
        Yahoo
    ]
    for Fetcher in portals:
        ft = Fetcher()
        ft.get_stream(company=company, stream_id=stream_id)

