import os
import re
import csv
import time
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.marvelherorush.com/en/cards"
IMAGE_DIR = "card_images"
OUTPUT_CSV = "marvel_cards.csv"

def sanitize_filename(name: str) -> str:
    """Removes or replaces characters not allowed in file names."""
    return re.sub(r'[\\/*?:"<>|「」]', "", name).strip().replace(" ", "_")

def download_image(url: str, save_path: str):
    """Downloads image from URL to local disk."""
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return False

def scrape_cards():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    all_cards = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Loading {BASE_URL}...")
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)

        # Optional: Switch per-page size to 100 if dropdown is present to speed up pagination
        try:
            page.locator("text='100'").first.click(timeout=3000)
            time.sleep(2)
        except Exception:
            pass

        page_num = 1
        while True:
            print(f"Scraping Page {page_num}...")
            page.wait_for_selector("img", timeout=10000)

            # Extract card elements from the list container
            cards_data = page.evaluate("""() => {
                const results = [];
                // Look for card containers in the list grid
                const cardElements = document.querySelectorAll('.card-item, .cards-list > div, [class*="card"]');
                
                // Fallback: grab all card images with associated titles and metadata
                const images = document.querySelectorAll('img');
                images.forEach((img) => {
                    const src = img.src || img.getAttribute('data-src') || '';
                    if (src && (src.includes('/cards/') || src.includes('/upload/') || src.includes('.png') || src.includes('.jpg'))) {
                        const container = img.closest('div') || img.parentElement;
                        const textContent = container ? container.innerText : '';
                        
                        // Extract level if specified in text/badge
                        const levelMatch = textContent.match(/Level\\s*[:：]?\\s*(\\d+)|Lv[.]?\\s*(\\d+)/i);
                        const level = levelMatch ? (levelMatch[1] || levelMatch[2]) : 'N/A';
                        
                        // Extract name from alt, title, or surrounding heading/text
                        const name = img.alt || img.getAttribute('title') || textContent.split('\\n')[0] || 'Unknown';
                        
                        results.push({
                            name: name.trim(),
                            level: level,
                            image_url: src
                        });
                    }
                });
                return results;
            }""")

            # Deduplicate items collected on the current page
            for card in cards_data:
                if card["image_url"] and not any(c["image_url"] == card["image_url"] for c in all_cards):
                    card_name = card["name"] or f"card_{len(all_cards)+1}"
                    card_level = card["level"]
                    img_url = card["image_url"]

                    # Save image file
                    file_ext = ".png" if ".png" in img_url else ".jpg"
                    clean_name = sanitize_filename(card_name)
                    img_filename = f"{len(all_cards)+1}_{clean_name}{file_ext}"
                    img_filepath = os.path.join(IMAGE_DIR, img_filename)

                    download_image(img_url, img_filepath)

                    all_cards.append({
                        "id": len(all_cards) + 1,
                        "name": card_name,
                        "level": card_level,
                        "image_url": img_url,
                        "local_path": img_filepath
                    })
                    print(f"Extracted: {card_name} (Level: {card_level})")

            # Handle pagination (click next page button)
            next_btn = page.locator(".btn-next, .pagination-next, button:has-text('Next'), .el-pagination__next")
            if next_btn.count() > 0 and next_btn.is_enabled():
                next_btn.first.click()
                time.sleep(2)
                page_num += 1
            else:
                break

        browser.close()

    # Save metadata to CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "level", "image_url", "local_path"])
        writer.writeheader()
        writer.writerows(all_cards)

    print(f"\nDone! Scraped {len(all_cards)} cards.")
    print(f"- Data saved to: {OUTPUT_CSV}")
    print(f"- Images downloaded to: {IMAGE_DIR}/")

if __name__ == "__main__":
    scrape_cards()