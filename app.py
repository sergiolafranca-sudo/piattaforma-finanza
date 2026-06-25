import streamlit as st
import json
from supabase import create_client
from pypdf import PdfReader

st.set_page_config(page_title="Copilota Finanza", layout="wide", initial_sidebar_state="collapsed")

# --- SISTEMA DI AUTENTICAZIONE (LOGIN) ---
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

def modulo_login():
    st.markdown("<br><br><h2 style='text-align: center; color: #1E3A8A;'>🏛️ Hub Cloud Finanza Agevolata</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6B7280;'>Inserisci le credenziali operative per accedere alla piattaforma</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username / Operatore")
            password = st.text_input("Password di Sicurezza", type="password")
            if st.form_submit_button("Sblocca Piattaforma 🔓", use_container_width=True):
                if username == st.secrets["AUTH_USERNAME"] and password == st.secrets["AUTH_PASSWORD"]:
                    st.session_state.autenticato = True
                    st.rerun()
                else:
                    st.error("❌ Credenziali errate. Riprova.")
    st.stop()

if not st.session_state.autenticato:
    modulo_login()

# --- INIZIALIZZAZIONE SERVIZI CLOUD ---
@st.cache_resource
def inizializza_servizi():
    supabase_client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    import google.generativeai as genai
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return supabase_client, genai

try:
    supabase, genai = inizializza_servizi()
except Exception:
    st.error("🔒 Configurazione di sicurezza incompleta o errata nei Secrets di Streamlit.")
    st.stop()

# --- FUNZIONI OPERATIVE ---
def estrai_testo_da_pdf(file_caricato):
    if file_caricato is not None:
        try:
            reader = PdfReader(file_caricato)
            return "".join([page.extract_text() or "" for page in reader.pages])
        except Exception as e:
            st.error(f"Errore lettura PDF: {e}")
    return ""

def analizza_documenti_con_ai(testo_visura, testo_bilancio, testo_progetto):
    prompt = f"""
    Analizza i seguenti testi estratti dai documenti aziendali (Visura, Bilancio e/o Bozza di Progetto).
    Estrai i dati necessari a popolare il database di finanza agevolata.
    
    VISURA CAMERALE: {testo_visura[:15000]}
    BILANCIO: {testo_bilancio[:15000]}
    BOZZA PROGETTO: {testo_progetto[:15000]}
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON valido con queste chiavi (se non trovi un dato, lascia "" o 0):
    {{
        "ragione_sociale": "Nome Azienda",
        "partita_iva": "11 cifre",
        "codice_ateco": "Solo il codice numerico principale",
        "dimensione": "Scegli tra: Micro, Piccola, Media, Grande Impresa",
        "fatturato": 100000,
        "regione": "Regione della sede operativa",
        "estratto_idea_progetto": "Sintesi chiara delle intenzioni di investimento e obiettivi descritti nella bozza"
    }}
    Non aggiungere introduzioni o formattazione markdown all'infuori del JSON puro.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        risposta = model.generate_content(prompt)
        clean_text = risposta.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception:
        st.error("L'AI non è riuscita a generare un formato dati pulito. Compila manualmente.")
        return {}

def esegui_due_diligence_profonda(id_cliente, id_bando):
    cliente = supabase.table("clienti").select("*").eq("id", id_cliente).single().execute().data
    bando = supabase.table("bandi").select("*").eq("id", id_bando).single().execute().data
    documenti = supabase.table("documenti_bando").select("*").eq("bando_id", id_bando).execute().data
    
    if not documenti:
        return "⚠️ Errore: Non sono presenti testi di decreti integrali o FAQ associati a questo bando nel database. L'analisi profonda richiede la presenza di un documento ufficiale."

    corpus = "".join([f"\n--- {d['titolo_documento']} ---\n{d['testo_integrale']}\n" for d in documenti])
    prompt = f"""
    Agisci come Esperto Senior in Finanza Agevolata e Revisore Legale.
    Esegui un'analisi di fattibilità incrociando i DATI AZIENDA con il CORPUS NORMATIVO INTEGRALE del bando.
    
    DATI AZIENDA:
    {json.dumps(cliente, indent=2)}
    
    TESTI DECRETI INTEGRALI E FAQ:
    {corpus}
    
    Genera un Report strutturato in Markdown con:
    # 📑 REPORT DI DUE DILIGENCE PER {cliente.get('ragione_sociale')}
    ## 🚦 STATO DI FATTIBILITÀ: [VERDE / GIALLO / ROSSO]
    ## 1. Verifiche del Soggetto Beneficiario (Soglie Formali, ATECO, Dimensione, Territorio)
    ## 2. Ammissibilità dell'Idea di Progetto e delle Spese (Cita gli articoli, allegati o FAQ specifici nel testo)
    ## 3. Vincoli, Insidie e Azioni Correttive Consigliate dallo Studio
    """
    model = genai.GenerativeModel('gemini-1.5-pro')
    return model.generate_content(prompt).text

def esegui_pre_screening_globale(id_cliente):
    cliente = supabase.table("clienti").select("*").eq("id", id_cliente).single().execute().data
    bandi_attivi = supabase.table("bandi").select("titolo, ente_erogatore, riassunto_breve").execute().data
    
    if not bandi_attivi:
        return "⚠️ Nessun bando memorizzato nel database. Impossibile eseguire il pre-screening."

    prompt = f"""
    Agisci come un selettore automatico di Finanza Agevolata. 
    Confronta il profilo del CLIENTE con la lista di tutti i BANDI disponibili a sistema.
    Determina per ciascun bando il livello di affinità ed eventuali criticità formali immediate.
    
    PROFILO CLIENTE: {json.dumps(cliente, indent=2)}
    LISTA BANDI DISPONIBILI: {json.dumps(bandi_attivi, indent=2)}
    
    Genera il report esclusivamente sotto forma di Tabella Markdown con le seguenti colonne:
    | Ente | Titolo Bando | Compatibilità (Alta / Media / Bassa) | Sospetti di Incompatibilità o Note Veloci |
    """
    model = genai.GenerativeModel('gemini-1.5-pro')
    return model.generate_content(prompt).text


# --- INTERFACCIA UTENTE ---
st.title("Hub Cloud: Finanza Agevolata")
st.markdown("---")

if st.sidebar.button("Log-out Sicuro 🔒"):
    st.session_state.autenticato = False
    st.rerun()

tab_clienti, tab_bandi, tab_due_diligence, tab_fonti = st.tabs([
    "👤 Gestione Clienti", 
    "📋 Catalogo Bandi", 
    "🔍 Analisi & Pre-Screening AI", 
    "⚙️ Gestione Fonti Robot"
])

# --- TAB 1: GESTIONE CLIENTI ---
with tab_clienti:
    st.subheader("Caricamento Automatico con AI Documentale")
    st.markdown("Carica contemporaneamente i documenti del cliente per valorizzare istantaneamente l'anagrafica.")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    v_file = col_f1.file_uploader("1. Visura Camerale (PDF)", type=["pdf"])
    b_file = col_f2.file_uploader("2. Ultimo Bilancio (PDF)", type=["pdf"])
    p_file = col_f3.file_uploader("3. Bozza Progetto / Idee (PDF)", type=["pdf"])
    
    if "draft" not in st.session_state:
        st.session_state.draft = {"ragione_sociale": "", "partita_iva": "", "codice_ateco": "", "dimensione": "Micro", "fatturato": 0, "regione": "", "estratto_idea_progetto": ""}
        
    if st.button("✨ Elabora Documenti ed Estrai Dati con AI", use_container_width=True):
        with st.spinner("Lettura dei PDF ed estrazione delle metriche aziendali in corso..."):
            t_visura = estrai_testo_da_pdf(v_file)
            t_bilancio = estrai_testo_da_pdf(b_file)
            t_progetto = estrai_testo_da_pdf(p_file)
            
            if t_visura or t_bilancio or t_progetto:
                dati_ai = analizza_documenti_con_ai(t_visura, t_bilancio, t_progetto)
                if dati_ai:
                    st.session_state.draft.update(dati_ai)
                    st.success("Dati estratti con successo! Verifica la scheda sottostante prima del salvataggio.")
            else:
                st.warning("Carica almeno un file PDF valido per l'estrazione automatica.")

    st.markdown("### Scheda Anagrafica Cliente (Verifica e Modifica)")
    with st.form("form_cliente"):
        col1, col2 = st.columns(2)
        r_sociale = col1.text_input("Ragione Sociale Azienda", value=st.session_state.draft["ragione_sociale"])
        p_iva = col2.text_input("Partita IVA", value=st.session_state.draft["partita_iva"])
        ateco = col1.text_input("Codice ATECO", value=st.session_state.draft["codice_ateco"])
        
        lista_dimensioni = ["Micro", "Piccola", "Media", "Grande Impresa"]
        idx_dim = lista_dimensioni.index(st.session_state.draft["dimensione"]) if st.session_state.draft["dimensione"] in lista_dimensioni else 0
        dimensione = col2.selectbox("Dimensione Azienda", lista_dimensioni, index=idx_dim)
        
        fatturato = col1.number_input("Fatturato Annuo (€)", min_value=0, value=int(st.session_state.draft["fatturato"]), step=5000)
        regione = col2.text_input("Regione Sede Operativa", value=st.session_state.draft["regione"])
        idea_progetto = st.text_area("Descrizione Investimento programmato / Obiettivi", value=st.session_state.draft["estratto_idea_progetto"])
        
        if st.form_submit_button("Salva Definitivamente nel Database Cloud 💾", use_container_width=True):
            payload = {
                "ragione_sociale": r_sociale, "partita_iva": p_iva, "codice_ateco": ateco,
                "dimensione": dimensione, "fatturato": fatturato, "regione": regione, "estratto_idea_progetto": idea_progetto
            }
            supabase.table("clienti").insert(payload).execute()
            st.success(f"Azienda '{r_sociale}' registrata in archivio con successo!")
            st.session_state.draft = {"ragione_sociale": "", "partita_iva": "", "codice_ateco": "", "dimensione": "Micro", "fatturato": 0, "regione": "", "estratto_idea_progetto": ""}

# --- TAB 2: CATALOGO BANDI ---
with tab_bandi:
    st.subheader("Archivio Misure Monitorate dai Robot")
    bandi = supabase.table("bandi").select("*").order("created_at", desc=True).execute().data
    if bandi:
        for b in bandi:
            with st.expander(f"📌 {b['titolo']} ({b['ente_erogatore']}) — *{b['stato']}*"):
                st.write(b['riassunto_breve'])
                st.markdown(f"**Fonte Ufficiale Rilevata:** [Link di Origine]({b['link_ufficiale']})")
                docs = supabase.table("documenti_bando").select("titolo_documento, tipologia").eq("bando_id", b['id']).execute().data
                if docs:
                    st.markdown("**Testi integrali pronti per la due diligence:**")
                    for d in docs:
                        st.write(f"- 📄 {d['titolo_documento']} (`{d['tipologia']}`)")
    else:
        st.info("Nessun bando nel database. Attiva lo scraper per popolare i dati.")

# --- TAB 3: DUE DILIGENCE & PRE-SCREENING ---
with tab_due_diligence:
    st.subheader("Motore Strategico di Controllo Incrociato")
    clienti_db = supabase.table("clienti").select("id, ragione_sociale").execute().data
    
    if clienti_db:
        mappa_c = {c['ragione_sociale']: c['id'] for c in clienti_db}
        c_sel = st.selectbox("Seleziona il Cliente da analizzare", list(mappa_c.keys()))
        
        tipo_analisi = st.radio("Seleziona la modalità operativa dell'AI:", [
            "Pre-screening Globale (Incrocia il cliente con TUTTI i bandi a sistema)", 
            "Due Diligence Mirata (Analisi profonda dei decreti di un singolo bando)"
        ])
        
        if tipo_analisi == "Pre-screening Globale (Incrocia il cliente con TUTTI i bandi a sistema)":
            if st.button("🔍 Esegui Scansione Totale del Mercato", use_container_width=True):
                with st.spinner("Analisi di affinità in corso su tutto l'archivio bandi..."):
                    risultato_screening = esegui_pre_screening_globale(mappa_c[c_sel])
                    st.markdown("### 📊 Matrice di Orientamento Strategico")
                    st.markdown(risultato_screening)
                    
        else:
            bandi_db = supabase.table("bandi").select("id, titolo").execute().data
            if bandi_db:
                mappa_b = {b['titolo']: b['id'] for b in bandi_db}
                b_sel = st.selectbox("Seleziona il Bando specifico da ispezionare", list(mappa_b.keys()))
                
                if st.button("🚀 Avvia Ispezione Legale del Decreto", use_container_width=True):
                    with st.spinner("Lettura dei testi di legge integrali e stesura del report in corso..."):
                        report = esegui_due_diligence_profonda(mappa_c[c_sel], mappa_b[b_sel])
                        st.markdown("---")
                        st.markdown(report)
            else:
                st.info("Nessun bando presente per l'ispezione mirata.")
    else:
        st.info("Registra o carica un cliente nel Tab 1 per sbloccare i motori di analisi.")

# --- TAB 4: GESTIONE FONTI ROBOT ---
with tab_fonti:
    st.subheader("Pannello di Controllo dei Robot di Monitoraggio")
    st.markdown("Aggiungi, modifica o disattiva le pagine bacheca/catalogo degli enti erogatori su cui puntano i robot.")
    
    with st.form("nuova_fonte_form"):
        col_u, col_e, col_t = st.columns([2, 1, 1])
        nuovo_url = col_u.text_input("URL della pagina bacheca (es: https://www.ente.it/catalogo-bandi)")
        nuovo_ente = col_e.text_input("Nome Ente Erogatore (es: Invitalia, Regione Veneto)")
        nuovo_tipo = col_t.selectbox("Tipologia Ambito", ["Nazionale", "Regionale", "Europeo"])
        
        if st.form_submit_button("Aggiungi Nuova Fonte ai Robot 📡", use_container_width=True):
            if nuovo_url and编制 = nuovo_ente:
                try:
                    supabase.table("fonti").insert({"url": nuovo_url, "ente": nuovo_ente, "tipologia": nuovo_tipo}).execute()
                    st.success(f"Fonte '{nuovo_ente}' aggiunta con successo. Verrà inclusa nella scansione notturna.")
                    st.rerun()
                except Exception:
                    st.error("Questo URL è già registrato a sistema.")
            else:
                st.warning("Tutti i campi del modulo sono obbligatori.")

    st.markdown("### Elenco delle Fonti Configurate")
    elenco_fonti = supabase.table("fonti").select("*").order("created_at", desc=False).execute().data
    if elenco_fonti:
        for f in elenco_fonti:
            col_info, col_azione = st.columns([4, 1])
            stato_icona = "🟢 Attiva" if f['attiva'] else "🔴 Sospesa"
            col_info.write(f"**{f['ente']}** ({f['tipologia']}) — `{f['url']}` | Stato: *{stato_icona}*")
            if col_azione.button("Inverti Stato 🔄", key=f['id'], use_container_width=True):
                supabase.table("fonti").update({"attiva": not f['attiva']}).eq("id", f['id']).execute()
                st.rerun()
    else:
        st.info("Nessuna fonte configurata nel sistema.")
