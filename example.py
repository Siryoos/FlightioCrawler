from requests.url_requester import AdvancedCrawler


def main():
    url = (
        "https://flightio.com/flight/THR-IST?depart=2025-06-18"
        "&adult=1&child=0&infant=0&flightType=1&cabinType=1"
    )
    crawler = AdvancedCrawler()
    success, data, message = crawler.crawl(url)
    if success:
        print("Crawl successful")
        print(message)
        print("Page title:", data.get("metadata", {}).get("title"))
    else:
        print("Crawl failed:", message)


if __name__ == "__main__":
    main()
