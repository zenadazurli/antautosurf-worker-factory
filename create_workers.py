#!/usr/bin/env python3
# create_workers.py - Crea worker su Render per ogni account

import os
import time
import json
import requests
from datetime import datetime

# ============================================================
# CONFIGURAZIONE
# ============================================================
RENDER_API_KEY = "rnd_FzD2vDchZer7UoXDuYopkTyWNtDz"
REPO_URL = "https://github.com/tuo-username/antautosurf-worker-factory"
REGION = "oregon"
PLAN = "starter"

# ============================================================
# LEGGI ACCOUNT E PROXY
# ============================================================
def leggi_account(file_path="accounts.txt"):
    accounts = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) == 2:
                    accounts.append({
                        "email": parts[0].strip(),
                        "password": parts[1].strip()
                    })
    return accounts

def leggi_proxy(file_path="proxies.txt"):
    with open(file_path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    return proxies

# ============================================================
# CREA WORKER VIA API RENDER
# ============================================================
def crea_worker(account, proxy, index):
    email = account["email"]
    password = account["password"]
    worker_name = f"antautosurf-{index:03d}"
    
    print(f"\n🚀 Creazione worker: {worker_name}")
    print(f"   📧 {email}")
    print(f"   🌐 Proxy: {proxy[:30]}...")
    
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "name": worker_name,
        "type": "worker",
        "runtime": "docker",
        "repo": REPO_URL,
        "region": REGION,
        "plan": PLAN,
        "envVars": [
            {"key": "EMAIL", "value": email},
            {"key": "PASSWORD", "value": password},
            {"key": "PROXY", "value": proxy},
            {"key": "HEADLESS", "value": "true"}
        ]
    }
    
    try:
        response = requests.post(
            "https://api.render.com/v1/services",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"   ✅ Worker creato! ID: {result.get('id')}")
            return True
        else:
            print(f"   ❌ Errore: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

# ============================================================
# MAIN
# ============================================================
def main():
    print("="*60)
    print("🚀 CREAZIONE WORKER AUTOMATICA")
    print("="*60)
    
    # 1. Leggi account e proxy
    accounts = leggi_account()
    proxies = leggi_proxy()
    
    if not accounts:
        print("❌ Nessun account trovato in accounts.txt")
        return
    
    if not proxies:
        print("❌ Nessun proxy trovato in proxies.txt")
        return
    
    print(f"📋 Account trovati: {len(accounts)}")
    print(f"📋 Proxy trovati: {len(proxies)}")
    
    # 2. Conferma
    print("\n⚠️ Verranno creati i seguenti worker:")
    for i, acc in enumerate(accounts[:5], 1):
        print(f"   {i}. {acc['email']}")
    if len(accounts) > 5:
        print(f"   ... e altri {len(accounts)-5}")
    
    conferma = input("\n✅ Continuare? (s/n): ")
    if conferma.lower() != 's':
        print("❌ Annullato")
        return
    
    # 3. Crea worker
    print("\n" + "="*60)
    print("🚀 CREAZIONE IN CORSO...")
    print("="*60)
    
    creati = 0
    falliti = 0
    
    for i, account in enumerate(accounts, 1):
        proxy = proxies[(i-1) % len(proxies)]
        success = crea_worker(account, proxy, i)
        
        if success:
            creati += 1
        else:
            falliti += 1
        
        time.sleep(3)
    
    # 4. Riepilogo
    print("\n" + "="*60)
    print("📊 RIEPILOGO")
    print("="*60)
    print(f"   ✅ Worker creati: {creati}")
    print(f"   ❌ Falliti: {falliti}")
    print(f"   📋 Account: {len(accounts)}")
    print("="*60)

if __name__ == "__main__":
    main()