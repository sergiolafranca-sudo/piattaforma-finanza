import os
import requests
from bs4 import BeautifulSoup
import json
from supabase import create_client
import google.generativeai as genai
from urllib.parse import urljoin

# Connessione Cloud e Inizializzazione AI
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def leggi_e_pulisci_sito_con_link(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=25)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # OTTIMIZZAZIONE CRUCIALE: Rende espliciti i link delle pagine interne per l'AI
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_link = urljoin(url, href)
            testo_tag = a.get_text(strip=True)
            # Sostituisce il tag HTML con testo leggibile che ancora contiene l'URL interno
            a.replace_with(f" {testo_tag} [LINK: {full_link}] ")
            
        # Pulisce i tag di formattazione e script
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
            
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        print(f"Errore download del sito {url}: {e}")
        return ""

def esegui_monitoraggio_universale_ai():
    print("🤖 Avvio del Robot AI di Monitoraggio Universale...")
    # Prende solo le fonti configurate dall'applicazione come attive
    fonti = supabase.table("fonti").select("*").eq("attiva", True).execute().data
    
    if not fonti:
        print("Nessuna fonte abilitata nel database.")
        return

    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    for f in fonti:
        print(f"Scansione in corso: Ente '{f['ente']}' sull'indirizzo: {f['url']}")
        testo_pulito = leggi_e_pulisci_sito_con_link(f['url'])
        
        if not testo_pulito or len(testo_pulito) < 200:
            print(f"Testo insufficiente o errore di connessione per {f['ente']}.")
            continue
            
        prompt = f"""
        Sei un analista esperto in finanza agevolata. Analizza il seguente testo estratto dalla pagina bacheca dei bandi dell'ente '{f['ente']}'.
        Isola ed estrai tutti i bandi di finanziamento, le agevolazioni, i contributi o le delibere programmatorie recenti.
        Presta massima attenzione ai link racchiusi nei blocchi '[LINK: ...]': abbina a ciascun bando individuato il suo specifico link della pagina interna.
        
        TESTO DELLA PAGINA ESTRATTO:
        {testo_pulito[:35000]}
        
        Restituisci l'elenco dei bandi trovati ESCLUSIVAMENTE sotto forma di array JSON (senza introduzioni o blocchi markdown esterni), formattato esattamente così:
        [
          {{
            "titolo": "Nome formale e completo del bando identificato",
            "riassunto_breve": "Sintesi chiara delle finalità del bando, soggetti beneficiari e intensità del contributo",
            "link_ufficiale": "L'URL specifico della pagina interna del bando trovato o, in mancanza, usa '{f['url']}'"
          }}
        ]
        """
        try:
            risposta = model.generate_content(prompt)
            clean_text = risposta.text.replace("```json", "").replace("```", "").strip()
            nuovi_bandi = json.loads(clean_text)
            
            for bando in nuovi_bandi:
                # Controllo anti-duplicati basato sul link univoco della pagina interna
                check = supabase.table("bandi").select("id").eq("link_ufficiale", bando['link_ufficiale']).execute()
                if not check.data:
                    payload = {
                        "titolo": bando['titolo'],
                        "ente_erogatore": f['ente'],
                        "link_ufficiale": bando['link_ufficiale'],
                        "riassunto_breve": bando['riassunto_breve'],
                        "stato": "Aperto"
                    }
                    supabase.table("bandi").insert(payload).execute()
                    print(f"✅ Nuovo bando intercettato e registrato: {bando['titolo']}")
        except Exception as e:
            print(f"Errore di parsing AI sulla fonte {f['ente']}: {e}")

if __name__ == "__main__":
    esegui_monitoraggio_universale_ai()
