# Request Archiver

This folder contains a simple Python utility to fetch website content and store it locally for future crawling.

Run `python url_requester.py` to open a small GUI. Paste your URL and click **Fetch**. The program saves the HTML response into the `pages` directory with a filename derived from the full URL.

If you prefer using the command line or your environment does not support the GUI, you can pass a URL directly:

```bash
python url_requester.py --url "https://example.com/page?query=1"
```

This will fetch the page and print the path of the saved file.
