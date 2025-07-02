from utils.file_utils import sanitize_filename


def test_sanitize_filename_normalizes_query():
    url = "https://parto-ticket.ir/Ticket-Tehran-Kish.html?t=1404-03-20"
    expected = "parto-ticket.ir_Ticket-Tehran-Kish.html_t_1404-03-20"
    assert sanitize_filename(url) == expected


def test_sanitize_filename_query_order_irrelevant():
    url1 = "https://example.com/search?a=1&b=2"
    url2 = "https://example.com/search?b=2&a=1"
    assert sanitize_filename(url1) == sanitize_filename(url2)
