import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import threading
from PIL import Image, UnidentifiedImageError
from fpdf import FPDF
from PyPDF2 import PdfMerger
import shutil
import re
import time

DIR = os.getcwd()

def page_links(url) -> list:
    retry_attempts = 5
    for attempt in range(retry_attempts):
        try:
            r = requests.get(url)
            soup = BeautifulSoup(r.content, 'html.parser')
            div = str(soup.find("div", {"class": "container-chapter-reader"}))
            imgs = BeautifulSoup(div, 'html.parser').find_all("img")
            page_urls = [i['src'] for i in imgs]
            return page_urls
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page links: {e}")
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise

def download_image(name, url):
    retry_attempts = 5
    for attempt in range(retry_attempts):
        try:
            domain = urllib.parse.urlparse(url).netloc
            HEADERS = {
                'Accept': 'image/png,image/svg+xml,image/*;q=0.8,video/*;q=0.8,*/*;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Safari/605.1.15',
                'Host': domain, 'Accept-Language': 'en-ca', 'Referer': 'https://manganelo.com/',
                'Connection': 'keep-alive'
            }
            r = requests.get(url, headers=HEADERS, stream=True)

            if r.status_code != 200:
                raise Exception(f"HTTP error: {r.status_code}")

            content_type = r.headers.get('Content-Type')
            if not content_type or 'image' not in content_type:
                raise Exception(f"Invalid content type: {content_type}")

            # Save the response content to a file
            with open(name, 'wb') as f:
                f.write(r.content)

            # Verify if the image is valid
            with Image.open(name) as img:
                img.verify()

            inputimage = Image.open(name).convert("RGBA")
            image = Image.new("RGB", inputimage.size, "WHITE")
            image.paste(inputimage, (0, 0), inputimage)
            os.remove(name)
            image.save(name)
            break  # Break the loop if download is successful
        except (requests.exceptions.RequestException, UnidentifiedImageError, Exception) as e:
            print(f"Error downloading image {name} from {url}: {e}")
            if os.path.exists(name):
                os.remove(name)
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                # Save error response for analysis
                error_filename = f"error_{name}.html"
                with open(error_filename, 'wb') as f:
                    f.write(r.content)
                print(f"Saved error response content to {error_filename}")

def download_all_images(urls):
    threads = []
    for i in range(len(urls)):
        t = threading.Thread(target=download_image, args=(str(i + 1) + ".jpg", urls[i]))
        threads.append(t)
        t.start()
    for thread in threads:
        thread.join()

def convert_to_pdf(name, imgs, pdfs, path):
    i = 0
    for img in imgs:
        if os.path.exists(img):
            try:
                cover = Image.open(img)
                width, height = cover.size
                width, height = float(width * 0.264583), float(height * 0.264583)
                pdf = FPDF('P', 'mm', (width, height))
                pdf.add_page()
                pdf.image(img, 0, 0, width, height)
                pdf.output(pdfs[i], "F")
                os.remove(img)
                i += 1
            except UnidentifiedImageError as e:
                print(f"Error processing image {img}: {e}")
                continue  # Skip the problematic image
        else:
            print(f"File not found: {img}, skipping.")

    merger = PdfMerger()
    for pdf in pdfs:
        if os.path.exists(pdf):
            merger.append(pdf)
        else:
            print(f"PDF file not found: {pdf}, skipping.")

    merger.write(name + ".pdf")
    merger.close()
    os.rename(os.path.join(path, name + ".pdf"), os.path.join(DIR, name + ".pdf"))
    shutil.rmtree(path)
    print("Downloaded " + name + " successfully")

def download_manga(name, url):
    print("Downloading " + name + " from " + url)
    pages = page_links(url)
    num = len(pages)
    print("Downloading " + str(num) + " pages")
    path = os.path.join(DIR, name)
    if not os.path.exists(path):
        os.mkdir(path)
    os.chdir(path)
    download_all_images(pages)
    imgs = [str(i + 1) + ".jpg" for i in range(num)]
    pdfs = [str(i + 1) + ".pdf" for i in range(num)]
    convert_to_pdf(name, imgs, pdfs, path)

def chapter_links(URL) -> dict:
    retry_attempts = 5
    for attempt in range(retry_attempts):
        try:
            r = requests.get(URL)
            soup = BeautifulSoup(r.content, 'html.parser')
            chapters = soup.find_all("a", {"class": "chapter-name text-nowrap"})
            links = {chapter.text.strip(): chapter['href'] for chapter in chapters}
            return links
        except requests.exceptions.RequestException as e:
            print(f"Error fetching chapter links: {e}")
            if attempt < retry_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                raise

def sort_chapters(chapters):
    def extract_chapter_number(chapter_name):
        # Extracting chapter number considering possible decimal points
        match = re.search(r'Chapter (\d+(?:\.\d+)?)', chapter_name)
        return float(match.group(1)) if match else float('inf')

    sorted_chapters = dict(sorted(chapters.items(), key=lambda x: extract_chapter_number(x[0])))
    return sorted_chapters

def main():
    URL = input("Enter the URL of the manga: ")
    print("URL: " + URL)
    chapters = chapter_links(URL)

    # Filter out volume chapters
    chapters = {k: v for k, v in chapters.items() if "Chapter" in k}

    chapters = sort_chapters(chapters)

    while True:
        print("Choose an option:")
        print("1. Download all chapters at once")
        print("2. Download chapters sequentially")
        print("3. Download a particular chapter")
        print("4. Quit (q)")

        choice = input("Enter your choice (1/2/3/4): ")

        if choice == '1':
            for chapter in chapters:
                download_manga(chapter, chapters[chapter])
        elif choice == '2':
            for chapter in chapters:
                print(chapter + ": " + chapters[chapter])
                y = input("Download? (Y/n/q): ")
                if y.lower() == 'y':
                    download_manga(chapter, chapters[chapter])
                elif y.lower() == 'q':
                    print("Exiting...")
                    return
        elif choice == '3':
            print("Available chapters:")
            for chapter in chapters:
                print(chapter + ": " + chapters[chapter])
            chap_name = input("Enter the name of the chapter to download: ")
            if chap_name in chapters:
                download_manga(chap_name, chapters[chap_name])
            else:
                print("Chapter not found.")
        elif choice.lower() == '4' or choice.lower() == 'q':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
