import os
import tkinter as tk
from tkinter import messagebox
import requests

SAVE_DIR = os.path.join(os.path.dirname(__file__), "pages")

os.makedirs(SAVE_DIR, exist_ok=True)


def sanitize_filename(url: str) -> str:
    """Sanitize URL to create a safe filename."""
    safe = url.replace('://', '_').replace('/', '_').replace('?', '_')
    return safe


def fetch_url():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Please enter a URL")
        return
    try:
        response = requests.get(url)
        response.raise_for_status()
        filename = sanitize_filename(url) + ".html"
        filepath = os.path.join(SAVE_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.text)
        messagebox.showinfo("Success", f"Saved HTML to {filepath}")
    except Exception as e:
        messagebox.showerror("Request Failed", str(e))


root = tk.Tk()
root.title("Website Requester")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

label = tk.Label(frame, text="Enter URL:")
label.pack(side=tk.LEFT)

url_entry = tk.Entry(frame, width=50)
url_entry.pack(side=tk.LEFT, padx=(5, 0))

fetch_button = tk.Button(root, text="Fetch", command=fetch_url)
fetch_button.pack(pady=(5, 10))

root.mainloop()
