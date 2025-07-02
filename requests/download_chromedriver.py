import os
import requests
import zipfile
import io
import sys
import re


def get_latest_chromedriver_version():
    # Get the latest version from the ChromeDriver download page
    response = requests.get("https://googlechromelabs.github.io/chrome-for-testing/")
    response.raise_for_status()

    # Find the latest version
    versions = re.findall(r'"version": "(\d+\.\d+\.\d+\.\d+)"', response.text)
    if not versions:
        raise Exception("Could not find ChromeDriver version")

    return versions[0]


def download_chromedriver():
    version = "137.0.7151.69"
    download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"
    print(f"Downloading ChromeDriver for Chrome version {version}...")
    try:
        response = requests.get(download_url)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            for file in zip_file.namelist():
                if file.endswith("chromedriver.exe"):
                    with (
                        zip_file.open(file) as source,
                        open("chromedriver.exe", "wb") as target,
                    ):
                        target.write(source.read())
                    break
        print("ChromeDriver downloaded and extracted successfully!")
    except Exception as e:
        print(f"Error downloading ChromeDriver: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    download_chromedriver()
