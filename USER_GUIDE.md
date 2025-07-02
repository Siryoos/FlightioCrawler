# User Guide | راهنمای کاربر

This guide explains how to run the crawler and search for flights. It is intended for both technical and non‑technical users.

## Quick Start (English)

1. Install **Docker** and **Docker Compose** on your machine.
2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/FlightioCrawler.git
   cd FlightioCrawler
   ```
3. Start all services using Docker Compose:
   ```bash
   docker-compose up --build -d
   ```
4. Open your browser and navigate to `http://localhost:8000/ui`.
5. Enter the origin, destination and dates to search for flights.
6. View the results and book directly with the airline or agency.

## راهنمای سریع (فارسی)

1. نرم‌افزار **Docker** و **Docker Compose** را نصب کنید.
2. مخزن را کلون کنید:
   ```bash
   git clone https://github.com/yourusername/FlightioCrawler.git
   cd FlightioCrawler
   ```
3. همه سرویس‌ها را با Docker Compose اجرا کنید:
   ```bash
   docker-compose up --build -d
   ```
4. مرورگر خود را باز کرده و به آدرس `http://localhost:8000/ui` بروید.
5. مبدأ، مقصد و تاریخ‌ها را وارد کنید و پروازها را جستجو کنید.
6. نتایج را ببینید و مستقیماً از شرکت هواپیمایی یا آژانس بلیط تهیه کنید.

## Advanced Tips | نکات پیشرفته

- Logs are stored in the `logs/` directory. Use `docker-compose logs -f` to monitor.
- Environment variables can be adjusted in `docker-compose.yml` for custom setups.
- Developers can run unit tests with `pytest -q`.

