#!/usr/bin/env python3
# bot.py - Worker dedicato per un singolo account

import os
import time
import sys
import json
import re
import requests
import asyncio
from playwright.async_api import async_playwright
from urllib.parse import unquote
from datetime import datetime
import imagehash
from PIL import Image
import io

# ============================================================
# CONFIGURAZIONE (DA VARIABILI D'AMBIENTE)
# ============================================================
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")
PROXY = os.environ.get("PROXY")  # Formato: username:password@host:port
HEADLESS = os.environ.get("HEADLESS", "True").lower() == "true"

if not EMAIL or not PASSWORD:
    print("❌ EMAIL e PASSWORD devono essere impostate come variabili d'ambiente")
    sys.exit(1)

# ============================================================
# PARSE PROXY
# ============================================================
def parse_proxy(proxy_string):
    """Parsea il proxy in formato username:password@host:port"""
    try:
        if '@' in proxy_string:
            auth, host = proxy_string.split('@')
            username, password = auth.split(':')
            host_parts = host.split(':')
            if len(host_parts) == 2:
                hostname, port = host_parts
                return {
                    "server": f"http://{hostname}:{port}",
                    "username": username,
                    "password": password
                }
    except:
        pass
    return None

# ============================================================
# CARICA DATABASE PHASH
# ============================================================
def carica_database():
    try:
        with open("hash_phash_db.json", "r") as f:
            return json.load(f)
    except:
        return {}

phash_db = carica_database()

# ============================================================
# LOGGING
# ============================================================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ============================================================
# FUNZIONI DI PULIZIA
# ============================================================
def pulisci_url(url):
    url = re.sub(r'<[^>]+>', '', url)
    url = url.strip()
    url = unquote(url)
    url = re.sub(r'[<>\'"]', '', url)
    return url

def pulisci_ad_id(ad_id):
    ad_id = unquote(ad_id)
    ad_id = re.sub(r'<[^>]+>', '', ad_id)
    ad_id = re.sub(r'[<>\'"]', '', ad_id)
    match = re.search(r'(\d+)', ad_id)
    if match:
        return match.group(1)
    return ad_id

# ============================================================
# RISOLUZIONE CAPTCHA
# ============================================================
async def risolvi_captcha(page, phash_db, max_tentativi=5):
    for tentativo in range(max_tentativi):
        log(f"   🔄 Tentativo captcha {tentativo+1}/{max_tentativi}")
        html = await page.content()
        cap_match = re.search(r'capimg\.php\?id=(\d+)', html)
        if not cap_match:
            log("   ✅ Nessun captcha rilevato")
            return True
        cap_id = cap_match.group(1)
        cids = [int(x) for x in re.findall(r'cid=(\d+)', html)]
        cids_unici = list(set(cids))
        log(f"   🖼️ Captcha ID: {cap_id}")
        try:
            img_element = page.locator('img[src*="capimg.php"]')
            img_data = await img_element.screenshot()
            img_pil = Image.open(io.BytesIO(img_data))
            phash = imagehash.phash(img_pil)
            phash_str = str(phash)
            log(f"   🔑 PHASH: {phash_str}")
        except Exception as e:
            log(f"   ⚠️ Errore screenshot: {e}")
            await page.reload()
            await asyncio.sleep(2)
            continue
        for stored_phash, cid in phash_db.items():
            try:
                diff = imagehash.hex_to_hash(phash_str) - imagehash.hex_to_hash(stored_phash)
                if diff <= 10:
                    await page.goto(f"https://antautosurf.com/index.php?cid={cid}")
                    await asyncio.sleep(2)
                    log(f"   ✅ CAPTCHA RISOLTO! CID: {cid}")
                    return True
            except:
                pass
        for cid in cids_unici:
            log(f"   🔄 Provo CID {cid}...")
            await page.goto(f"https://antautosurf.com/index.php?cid={cid}")
            await asyncio.sleep(2)
            html_test = await page.content()
            if "Please Click Similar" not in html_test:
                phash_db[phash_str] = cid
                with open("hash_phash_db.json", "w") as f:
                    json.dump(phash_db, f, indent=2)
                log(f"   ✅ CAPTCHA RISOLTO! CID: {cid} (nuovo)")
                return True
        log(f"   ⚠️ Tentativo {tentativo+1} fallito, ricarico...")
        await page.goto("https://antautosurf.com/index.php", wait_until="domcontentloaded")
        await asyncio.sleep(3)
    log(f"   ❌ CAPTCHA NON RISOLTO DOPO {max_tentativi} TENTATIVI!")
    return False

# ============================================================
# SURF ACCOUNT
# ============================================================
async def surf_account():
    log(f"🚀 Avvio worker per {EMAIL}")
    
    proxy_config = None
    if PROXY:
        proxy_config = parse_proxy(PROXY)
        if proxy_config:
            log(f"🌐 Proxy: {PROXY.split('@')[1]}")
        else:
            log("⚠️ Proxy non valido, procedo senza proxy")
    
    try:
        async with async_playwright() as p:
            # ============================================================
            # BROWSER CON PROXY (SE DISPONIBILE)
            # ============================================================
            browser = await p.chromium.launch(
                headless=HEADLESS,
                proxy=proxy_config,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            log("📝 Login/Registrazione...")
            await page.goto("https://antautosurf.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            await page.fill('input[name="bitcoinwallet"]', EMAIL)
            await page.click('input[type="submit"][value*="Enter"]')
            await asyncio.sleep(3)
            
            html = await page.content()
            
            if "Set Login Password" in html:
                log(f"📝 Nuovo account: {EMAIL}")
                await page.fill('input[name="password"]', PASSWORD)
                await page.fill('input[name="passwordb"]', PASSWORD)
                match = re.search(r'name="confirm2" value="(\d+)"', html)
                if match:
                    confirm2 = match.group(1)
                    await page.goto(f"https://antautosurf.com/index.php?password={PASSWORD}&passwordb={PASSWORD}&confirm2={confirm2}", wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    log("   ✅ Password impostata!")
            
            html = await page.content()
            if "Please enter Password" in html:
                log("🔑 Login con password...")
                await page.fill('input[name="password"]', PASSWORD)
                await page.click('input[value="Enter"]')
                await asyncio.sleep(3)
            
            log("✅ Account pronto!")
            
            # ============================================================
            # DASHBOARD
            # ============================================================
            log("📊 Dashboard...")
            await page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
            html = await page.content()
            
            if "Please Click Similar" in html:
                log("⚠️ CAPTCHA RILEVATO!")
                if not await risolvi_captcha(page, phash_db):
                    log("❌ Captcha non risolto!")
                    return
            
            # Balance
            balance_match = re.search(r'btoday["\']?\s*[=:]\s*([\d.]+)', html)
            if balance_match:
                log(f"💰 Balance: {balance_match.group(1)}")
            
            # CSRF
            csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
            if not csrf_match:
                log("❌ CSRF non trovato!")
                return
            
            csrf = csrf_match.group(1)
            log(f"🎫 CSRF: {csrf[:16]}...")
            
            # Cookies
            cookies = await context.cookies()
            cookie_dict = {}
            for cookie in cookies:
                cookie_dict[cookie['name']] = cookie['value']
            
            await browser.close()
            
            # ============================================================
            # SURF SENZA PROXY
            # ============================================================
            log("🚀 Avvio surf SENZA proxy...")
            
            browser_no_proxy = await p.chromium.launch(
                headless=HEADLESS,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context_no_proxy = await browser_no_proxy.new_context()
            
            for name, value in cookie_dict.items():
                await context_no_proxy.add_cookies([{
                    'name': name,
                    'value': value,
                    'domain': '.antautosurf.com',
                    'path': '/'
                }])
            
            page_no_proxy = await context_no_proxy.new_page()
            
            key = ""
            time_val = 12
            ad_id = ""
            cycle = 0
            csrf_invalidi = 0
            MAX_CSRF_INVALIDI = 5
            
            while True:
                cycle += 1
                log(f"🔄 CICLO {cycle}")
                
                if ad_id:
                    ad_id_pulito = pulisci_ad_id(ad_id)
                else:
                    ad_id_pulito = ""
                
                params = {
                    "wallet": EMAIL,
                    "key": key,
                    "time": time_val,
                    "ad_id": ad_id_pulito,
                    "isitbad": 0,
                    "csrf_token": csrf
                }
                
                url = "https://antautosurf.com/surf.php?" + "&".join([f"{k}={v}" for k, v in params.items()])
                
                await page_no_proxy.goto(url, wait_until="domcontentloaded", timeout=30000)
                page_text = await page_no_proxy.content()
                
                if "Invalid CSRF token" in page_text:
                    csrf_invalidi += 1
                    log(f"❌ CSRF invalido! ({csrf_invalidi}/{MAX_CSRF_INVALIDI})")
                    
                    if csrf_invalidi >= MAX_CSRF_INVALIDI:
                        log("🔄 Troppi CSRF invalidi! Riavvio...")
                        return
                    
                    await page_no_proxy.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)
                    html = await page_no_proxy.content()
                    csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
                    if csrf_match:
                        csrf = csrf_match.group(1)
                        csrf_invalidi = 0
                        log(f"🎫 Nuovo CSRF: {csrf[:16]}...")
                    continue
                else:
                    csrf_invalidi = 0
                
                if "--_--" not in page_text:
                    await asyncio.sleep(5)
                    continue
                
                parts = page_text.split("--_--")
                if len(parts) < 4:
                    continue
                
                ad_url = pulisci_url(parts[0])
                time_val = int(parts[1])
                key = parts[2]
                ad_id = parts[3]
                
                if "connection.php" in ad_url:
                    log("   📂 Test anti-bot...")
                    try:
                        new_page = await context_no_proxy.new_page()
                        await new_page.goto(ad_url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2)
                    except Exception as e:
                        log(f"   ⚠️ Errore apertura: {e}")
                    
                    for i in range(time_val, 0, -1):
                        print(f"   ⏳ {i}s", end="\r")
                        await asyncio.sleep(1)
                    print("   " * 20, end="\r")
                    
                    try:
                        await new_page.close()
                    except:
                        pass
                    continue
                
                log(f"   📢 Annuncio reale! Timer: {time_val}s")
                
                try:
                    new_page = await context_no_proxy.new_page()
                    await new_page.goto(ad_url, wait_until="domcontentloaded", timeout=10000)
                    await asyncio.sleep(1)
                except Exception as e:
                    log(f"   ⚠️ Errore apertura: {e}")
                
                for i in range(time_val, 0, -1):
                    print(f"   ⏳ {i}s", end="\r")
                    await asyncio.sleep(1)
                print("   " * 20, end="\r")
                log(f"   ✅ Timer completato!")
                
                try:
                    await new_page.close()
                except:
                    pass
                
                if cycle % 3 == 0:
                    await page_no_proxy.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)
                    html = await page_no_proxy.content()
                    csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
                    if csrf_match:
                        csrf = csrf_match.group(1)
                        log(f"   🎫 CSRF aggiornato: {csrf[:16]}...")
    
    except Exception as e:
        log(f"❌ Errore: {e}")

# ============================================================
# MAIN
# ============================================================
async def main():
    while True:
        try:
            await surf_account()
        except Exception as e:
            log(f"❌ Errore nel ciclo: {e}")
        
        log("⏳ Attesa 60 secondi prima di riavviare...")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())