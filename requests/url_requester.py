import os
import argparse
import tkinter as tk
from tkinter import messagebox
import requests

SAVE_DIR = os.path.join(os.path.dirname(__file__), "pages")

os.makedirs(SAVE_DIR, exist_ok=True)


def sanitize_filename(url: str) -> str:
    """Return a filesystem-friendly representation of ``url``."""
    unsafe_chars = ["://", "/", "?", "&", "="]
    safe = url
    for ch in unsafe_chars:
        safe = safe.replace(ch, "_")
    return safe


def fetch_and_save(url: str) -> str:
    """Fetch ``url`` and store its HTML. Returns the path of the saved file."""
    response = requests.get(url)
    response.raise_for_status()
    filename = sanitize_filename(url) + ".html"
    filepath = os.path.join(SAVE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(response.text)
    return filepath


def fetch_url():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Please enter a URL")
        return
    try:
        path = fetch_and_save(url)
        messagebox.showinfo("Success", f"Saved HTML to {path}")
    except Exception as e:
        messagebox.showerror("Request Failed", str(e))


def open_gui():
    global url_entry

    root = tk.Tk()
    root.title("Website Requester")

    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)

    label = tk.Label(frame, text="Enter URL:")
    label.pack(side=tk.LEFT)

    url_entry = tk.Entry(frame, width=70)
    url_entry.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

    fetch_button = tk.Button(root, text="Fetch", command=fetch_url)
    fetch_button.pack(pady=(5, 10))

    url_entry.focus()
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a webpage and save the HTML response")
    parser.add_argument("--url", help="URL to fetch. If omitted, a GUI opens.")
    args = parser.parse_args()

    if args.url:
        try:
            path = fetch_and_save(args.url)
            print(f"Saved HTML to {path}")
        except Exception as exc:
            raise SystemExit(f"Request failed: {exc}")
    else:
        open_gui()


if __name__ == "__main__":
    main()
