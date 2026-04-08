import logging
import re
from math import ceil
from pathlib import Path

from bs4 import BeautifulSoup
from icrawler.builtin import BingImageCrawler, GoogleImageCrawler
from icrawler.builtin.google import GoogleParser


logging.getLogger("icrawler").setLevel(logging.ERROR)

BASE_DIR = Path(r"C:\State-Secrets\Projects\INFT\SB Project - clone 2\Dataset")
IMAGES_PER_CLASS = 100

CLASS_QUERIES = {
    "mobile": [
        "real world mobile phone",
        "damaged mobile phone",
        "working smartphone in hand",
        "used mobile phone on table",
    ],
    "laptop": [
        "real world laptop",
        "damaged laptop screen",
        "working laptop on desk",
        "used laptop computer",
    ],
    "tablet": [
        "real world tablet device",
        "damaged tablet screen",
        "working tablet in hand",
        "used tablet on table",
    ],
    "powerbank": [
        "real world power bank",
        "damaged power bank",
        "working power bank charger",
        "used power bank device",
    ],
    "other": [
        "real world electronic waste",
        "damaged electronic device",
        "used gadget scrap",
        "broken consumer electronics",
    ],
}


class SafeGoogleParser(GoogleParser):
    def parse(self, response):
        html = response.content.decode("utf-8", "ignore")
        soup = BeautifulSoup(html, "lxml")
        urls = []

        for script in soup.find_all("script"):
            text = script.get_text(" ", strip=False)
            if not text:
                continue

            matches = re.findall(
                r"https?://[^\"'\\s<>]+\\.(?:jpg|jpeg|png|bmp|webp)",
                text,
                flags=re.IGNORECASE,
            )
            urls.extend(matches)

        cleaned_urls = []
        seen = set()
        for url in urls:
            clean_url = bytes(url, "utf-8").decode("unicode-escape")
            if clean_url not in seen:
                seen.add(clean_url)
                cleaned_urls.append({"file_url": clean_url})

        return cleaned_urls


def count_images(folder: Path) -> int:
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sum(1 for file in folder.iterdir() if file.is_file() and file.suffix.lower() in image_extensions)


def crawl_google(query: str, class_dir: Path, max_num: int) -> None:
    crawler = GoogleImageCrawler(
        downloader_threads=4,
        parser_cls=SafeGoogleParser,
        storage={"root_dir": str(class_dir)},
    )
    crawler.crawl(keyword=query, max_num=max_num)


def crawl_bing(query: str, class_dir: Path, max_num: int) -> None:
    crawler = BingImageCrawler(
        downloader_threads=4,
        storage={"root_dir": str(class_dir)},
    )
    crawler.crawl(keyword=query, max_num=max_num)


def download_class_images(class_name: str, queries: list[str], total_images: int) -> None:
    class_dir = BASE_DIR / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    per_query = ceil(total_images / len(queries))

    for query in queries:
        current_count = count_images(class_dir)
        remaining_total = total_images - current_count
        if remaining_total <= 0:
            break

        target_for_query = min(per_query, remaining_total)

        print(f"[{class_name}] Running query: {query}")
        before_google = count_images(class_dir)
        crawl_google(query, class_dir, target_for_query)
        after_google = count_images(class_dir)

        downloaded_by_google = after_google - before_google
        still_needed = target_for_query - downloaded_by_google

        if still_needed > 0:
            print(f"[{class_name}] Google returned fewer images, using fallback for: {query}")
            crawl_bing(query, class_dir, still_needed)

    final_count = count_images(class_dir)
    if final_count < total_images:
        extra_needed = total_images - final_count
        extra_query = f"{class_name} real world product"
        print(f"[{class_name}] Filling remaining {extra_needed} images with: {extra_query}")
        crawl_bing(extra_query, class_dir, extra_needed)


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for class_name, queries in CLASS_QUERIES.items():
        download_class_images(class_name, queries, IMAGES_PER_CLASS)

    print("Image download complete.")


if __name__ == "__main__":
    main()
