from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        executable_path=r"C:\Users\dudha\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"
    )

    page = browser.new_page()
    page.goto("https://www.youtube.com")

    print("Brave opened successfully!")

    input("Press Enter to close Brave...")

    browser.close()