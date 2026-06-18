import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import json
import os
import aiohttp
import math

# Configurazione Bot e Intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# CARICAMENTO DATABASE SALVATO
DB_FILE = "database.json"
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        database = json.load(f)
else:
    database = {}

# Dizionario globale per salvare i task di raccolta droga attivi
raccolte_attive = {}

# Configurazione Economia di Default globale
if "SETTINGS" not in database:
    database["SETTINGS"] = {
        "valuta": "€",
        "tassa_servizi": 50,
        "stipendio_base": 100
    }

# Store di Default globale
if "STORE" not in database:
    database["STORE"] = {
        "telefono": {"prezzo": 500, "descrizione": "Un telefono cellulare di ultima generazione"},
        "pane": {"prezzo": 10, "descrizione": "Ripristina un po' di fame"},
        "acqua": {"prezzo": 5, "descrizione": "Dissetante"},
        "grimaldello": {"prezzo": 250, "descrizione": "Utile per scassinare veicoli"},
        "maschera": {"prezzo": 150, "descrizione": "Nasconde parzialmente l'identità"},
        "benda": {"prezzo": 30, "descrizione": "Cura piccole ferite"},
        "kit_riparazione": {"prezzo": 400, "descrizione": "Ripara un veicolo danneggiato"},
        "sim": {"prezzo": 100, "descrizione": "Scheda SIM vergine"},
        "zaino": {"prezzo": 1000, "descrizione": "Aumenta la capacità di inventario"},
        "radio": {"prezzo": 750, "descrizione": "Per comunicare con la tua gang"},
        "torcia": {"prezzo": 50, "descrizione": "Illumina le zone buie"},
        "tanica": {"prezzo": 80, "descrizione": "Tanica piena di benzina"}
    }

# Inizializzazione Database del Mercato Pubblico
if "MERCATO" not in database:
    database["MERCATO"] = {}

# Lista lavori disponibili nel server
if "JOBS" not in database:
    database["JOBS"] = ["Disoccupato", "Meccanico", "Polizia", "Medico", "Concessionario"]

# Configurazione Negozio a Pagine
ITEMS_PER_PAGE = 5

def salva_database():
    """Salva i dati su file per non perderli mai"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(database, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"ERRORE CRITICO: Impossibile salvare il database: {e}")

def controlla_utente(user_id):
    """Inizializza i dati dell'utente se non esistono"""
    uid = str(user_id)
    if uid not in database:
        database[uid] = {
            "inventario": {},
            "documenti": None,
            "veicoli": [],
            "armi": [],
            "lavoro": "Disoccupato",
            "in_servizio": False,
            "inizio_turno": None,
            "contanti": 500,
            "banca": 2500,
            "fedina": [],
            "multe": 0,
            "ammanettato": False,
            "sms_ricevuti": []
        }
        salva_database()
    else:
        cambiato = False
        chiavi_default = {
            "contanti": 500, "banca": 2500, "fedina": [], 
            "multe": 0, "ammanettato": False, "lavoro": "Disoccupato",
            "sms_ricevuti": []
        }
        for k, v in chiavi_default.items():
            if k not in database[uid]:
                database[uid][k] = v
                cambiato = True
        if cambiato:
            salva_database()

async def invia_log(titolo, descrizione, colore=discord.Color.light_gray()):
    """Invia un log dettagliato tramite Webhook nel canale Discord amministrativo"""
    if not LOG_WEBHOOK_URL:
        return  
        
    embed = discord.Embed(title=titolo, description=descrizione, color=colore)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(LOG_WEBHOOK_URL, session=session)
            await webhook.send(embed=embed)
    except Exception as e:
        print(f"Impossibile inviare il log al webhook: {e}")

@bot.event
async def on_ready():
    print(f"Sincronizzazione dei comandi in corso...")
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizzati {len(synced)} comandi slash!")
    except Exception as e:
        print(f"Errore di sincronizzazione: {e}")
    print(f"Bot Online come {bot.user}")
    await invia_log("🤖 Bot Avviato", "Il bot è ora online e pronto a tracciare le azioni.", discord.Color.green())

# ==========================================
# 1. SISTEMA DROGHE
# ==========================================

@bot.tree.command(name="raccogli", description="Inizia a raccogliere 1kg di droga (Azione pubblica, richiede 15 min)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Cocaina", value="cocaina"),
    app_commands.Choice(name="Marijuana", value="marijuana"),
    app_commands.Choice(name="Metanfetamina", value="metanfetamina")
])
async def raccogli(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if user_id in raccolte_attive:
        await interaction.response.send_message("❌ Stai già raccogliendo della droga! Usa `/annulla_raccolta` se vuoi fermarti.", ephemeral=True)
        return
        
    if database[user_id].get("ammanettato", False):
        await interaction.response.send_message("❌ Non puoi raccogliere droga mentre sei ammanettato!", ephemeral=True)
        return

    droga_scelta = tipo.value
    
    embed_inizio = discord.Embed(
        title="🌿 Raccolta Iniziata",
        description=f"👀 {interaction.user.mention} ha iniziato a raccogliere **{tipo.name}** in questa zona. Ci vorranno **15 minuti**...\n*Usa `/annulla_raccolta` per fermarti.*",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed_inizio)
    
    await invia_log(
        "🚨 Inizio Attività Illecita", 
        f"L'utente {interaction.user.mention} (`{interaction.user.id}`) ha **iniziato** a raccogliere **{tipo.name}** in pubblico.", 
        discord.Color.orange()
    )

    raccolte_attive[user_id] = asyncio.current_task()

    try:
        await asyncio.sleep(900)
        controlla_utente(user_id)
        
        if database[user_id].get("ammanettato", False):
            embed_fallito = discord.Embed(
                title="❌ Raccolta Interrotta",
                description=f"La raccolta di {interaction.user.mention} è fallita perché è stato ammanettato!",
                color=discord.Color.red()
            )
            await interaction.channel.send(embed=embed_fallito)
            return

        database[user_id]["inventario"][droga_scelta] = database[user_id]["inventario"].get(droga_scelta, 0) + 1
        salva_database()
        
        embed_fine = discord.Embed(
            title="🌿 Raccolta Completata",
            description=f"✅ {interaction.user.mention} ha completato la raccolta! **1 Kg** di **{tipo.name}** è stato messo in inventario.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed_fine)

    except asyncio.CancelledError:
        embed_annullato = discord.Embed(
            title="🛑 Raccolta Annullata",
            description=f"🏃‍♂️ {interaction.user.mention} ha **interrotto manualmente** la raccolta di {tipo.name} ed è scappato!",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed_annullato)
    finally:
        raccolte_attive.pop(user_id, None)

@bot.tree.command(name="annulla_raccolta", description="Annulla il tuo processo di raccolta droga in corso")
async def annulla_raccolta(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    if user_id in raccolte_attive:
        raccolte_attive[user_id].cancel()
        await interaction.response.send_message("✅ Richiesta di annullamento inviata.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Non hai nessuna raccolta di droga attiva al momento.", ephemeral=True)

# ==========================================
# 2. SISTEMA LAVORI & TURNI
# ==========================================

@bot.tree.command(name="inizio_turno", description="Inizia il tuo turno di lavoro")
async def inizio_turno(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    lavoro_attuale = database[user_id].get("lavoro", "Disoccupato")
    if lavoro_attuale == "Disoccupato":
        await interaction.response.send_message("❌ Sei disoccupato! Trova un lavoro prima di andare in servizio.", ephemeral=True)
        return

    if database[user_id]["in_servizio"]:
        await interaction.response.send_message("❌ Sei già in servizio!", ephemeral=True)
        return
        
    database[user_id]["in_servizio"] = True
    database[user_id]["inizio_turno"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    salva_database()
    
    embed = discord.Embed(
        title="💼 Turno Avviato",
        description=f"L'utente {interaction.user.mention} ha iniziato il turno come **{lavoro_attuale}**.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)
    
    await invia_log(
        "💼 Log Servizio", 
        f"L'utente {interaction.user.mention} è entrato **In Servizio** come **{lavoro_attuale}**.", 
        discord.Color.blue()
    )

@bot.tree.command(name="fine_turno", description="Termina il tuo turno di lavoro")
async def fine_turno(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if not database[user_id]["in_servizio"]:
        await interaction.response.send_message("❌ Non sei in servizio al momento.", ephemeral=True)
        return
        
    lavoro = database[user_id]["lavoro"]
    database[user_id]["in_servizio"] = False
    salva_database()
    
    embed = discord.Embed(
        title="🚪 Turno Terminato",
        description=f"L'utente {interaction.user.mention} ha terminato il turno da **{lavoro}**.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)
    
    await invia_log(
        "🚪 Log Servizio", 
        f"L'utente {interaction.user.mention} ha terminato il suo turno di lavoro da **{lavoro}**.", 
        discord.Color.red()
    )

@bot.tree.command(name="imposta_lavoro", description="[ADMIN] Assegna un lavoro specifico a un utente")
@app_commands.checks.has_permissions(administrator=True)
async def imposta_lavoro(interaction: discord.Interaction, utente: discord.User, lavoro: str):
    user_id = str(utente.id)
    controlla_utente(user_id)
    
    if lavoro not in database["JOBS"]:
        database["JOBS"].append(lavoro)
        
    database[user_id]["lavoro"] = lavoro
    salva_database()
    await interaction.response.send_message(f"💼 Il lavoro di {utente.mention} è stato impostato su **{lavoro}**.")
    
    await invia_log(
        "🛠️ Log Admin - Lavoro", 
        f"L'amministratore {interaction.user.mention} ha impostato il lavoro di {utente.mention} su **{lavoro}**.", 
        discord.Color.purple()
    )

@bot.tree.command(name="aggiungi_lavoro", description="[ADMIN] Aggiungi un nuovo tipo di lavoro nel server")
@app_commands.checks.has_permissions(administrator=True)
async def aggiungi_lavoro(interaction: discord.Interaction, nome_lavoro: str):
    if nome_lavoro in database["JOBS"]:
        await interaction.response.send_message("❌ Questo lavoro esiste già nella lista del server.", ephemeral=True)
        return
        
    database["JOBS"].append(nome_lavoro)
    salva_database()
    await interaction.response.send_message(f"✅ Nuovo lavoro **{nome_lavoro}** aggiunto alle opzioni disponibili del server.")
    
    await invia_log(
        "🛠️ Log Admin - Config", 
        f"L'amministratore {interaction.user.mention} ha aggiunto un nuovo impiego globale: **{nome_lavoro}**.", 
        discord.Color.purple()
    )

# ==========================================
# 3. CHIAMATE DI EMERGENZA
# ==========================================

@bot.tree.command(name="112", description="Invia una chiamata d'emergenza alle forze dell'ordine o medici")
@app_commands.choices(servizio=[
    app_commands.Choice(name="Polizia (LSPD)", value="polizia"),
    app_commands.Choice(name="Medici (EMFS)", value="medici"),
    app_commands.Choice(name="Meccanici / Servizi", value="servizi")
])
async def emergenza(interaction: discord.Interaction, servizio: app_commands.Choice[str], motivo: str, posizione: str):
    mappa_colori = {"polizia": discord.Color.blue(), "medici": discord.Color.red(), "servizi": discord.Color.orange()}
    
    embed = discord.Embed(
        title=f"📞 CHIAMATA DI EMERGENZA: {servizio.name.upper()}",
        description=f"**Segnalazione da:** {interaction.user.mention}\n**Posizione:** {posizione}\n**Motivazione/Dettagli:** {motivo}",
        color=mappa_colori.get(servizio.value, discord.Color.light_gray())
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    await interaction.response.send_message("🚨 Chiamata d'emergenza inoltrata ai dipartimenti competenti.", ephemeral=True)
    await interaction.channel.send(embed=embed)
    
    await invia_log(
        "📞 Log Chiamata Emergenza", 
        f"L'utente {interaction.user.mention} ha chiamato il **{servizio.name}**.\n**Posizione:** {posizione}\n**Motivo:** {motivo}", 
        mappa_colori.get(servizio.value, discord.Color.light_gray())
    )

# ==========================================
# 4. SISTEMA RAPINE
# ==========================================

@bot.tree.command(name="rapina", description="Invia un alert di rapina in corso (Per i Criminali)")
@app_commands.describe(luogo="Dove stai rapinando?", dettagli="Note (es. 2 ostaggi, armati)")
async def rapina(interaction: discord.Interaction, luogo: str, dettagli: str):
    embed = discord.Embed(
        title="🚨 ALLERTA RAPINA IN CORSO 🚨",
        description=f"**Luogo:** {luogo}\n**Dettagli:** {dettagli}\n\n*Tutte le unità disponibili della Polizia devono recarsi sul posto immediatamente!*",
        color=discord.Color.brand_red()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    await interaction.response.send_message("Allarme inviato alla centrale!", ephemeral=True)
    await interaction.channel.send(embed=embed)
    
    await invia_log(
        "🚨 Log Rapina", 
        f"L'utente {interaction.user.mention} ha avviato una rapina.\n**Luogo:** {luogo}\n**Dettagli:** {dettagli}", 
        discord.Color.brand_red()
    )

# ==========================================
# 5. GESTIONE CIVILI E DOCUMENTI DETTAGLIATI
# ==========================================

@bot.tree.command(name="crea_documenti", description="Crea la tua carta d'identità RP completa")
@app_commands.choices(cittadinanza=[
    app_commands.Choice(name="Italiana", value="Italiana"),
    app_commands.Choice(name="Rumena", value="Rumena"),
    app_commands.Choice(name="Albanese", value="Albanese"),
    app_commands.Choice(name="Spagnola", value="Spagnola"),
    app_commands.Choice(name="Francese", value="Francese"),
    app_commands.Choice(name="Tedesca", value="Tedesca")
])
@app_commands.choices(genere=[
    app_commands.Choice(name="Uomo", value="Uomo"),
    app_commands.Choice(name="Donna", value="Donna"),
    app_commands.Choice(name="Altro", value="Altro")
])
async def crea_documenti(interaction: discord.Interaction, nome: str, cognome: str, eta: int, cittadinanza: app_commands.Choice[str], citta_provenienza: str, genere: app_commands.Choice[str], altezza: str, colore_capelli: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if eta < 16 or eta > 100:
        await interaction.response.send_message("❌ L'età deve essere compresa tra 16 e 100 anni.", ephemeral=True)
        return
    
    database[user_id]["documenti"] = {
        "nome": nome, 
        "cognome": cognome, 
        "eta": eta,
        "cittadinanza": cittadinanza.value,
        "citta_provenienza": citta_provenienza,
        "genere": genere.value,
        "altezza": altezza,
        "colore_capelli": colore_capelli
    }
    salva_database()
    await interaction.response.send_message(f"✅ Documenti creati per **{nome} {cognome}**!", ephemeral=True)
    
    await invia_log(
        "🪪 Log Documenti", 
        f"L'utente {interaction.user.mention} ha creato i suoi documenti RP:\n**Nome:** {nome} {cognome}\n**Età:** {eta}\n**Cittadinanza:** {cittadinanza.value}\n**Città:** {citta_provenienza}\n**Genere:** {genere.value}\n**Altezza:** {altezza}\n**Capelli:** {colore_capelli}", 
        discord.Color.teal()
    )

@bot.tree.command(name="modifica_documenti", description="Modifica le tue generalità / documenti")
@app_commands.choices(cittadinanza=[
    app_commands.Choice(name="Italiana", value="Italiana"),
    app_commands.Choice(name="Rumena", value="Rumena"),
    app_commands.Choice(name="Albanese", value="Albanese"),
    app_commands.Choice(name="Spagnola", value="Spagnola"),
    app_commands.Choice(name="Francese", value="Francese"),
    app_commands.Choice(name="Tedesca", value="Tedesca")
])
@app_commands.choices(genere=[
    app_commands.Choice(name="Uomo", value="Uomo"),
    app_commands.Choice(name="Donna", value="Donna"),
    app_commands.Choice(name="Altro", value="Altro")
])
async def modifica_documenti(interaction: discord.Interaction, nome: str, cognome: str, eta: int, cittadinanza: app_commands.Choice[str], citta_provenienza: str, genere: app_commands.Choice[str], altezza: str, colore_capelli: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if eta < 16 or eta > 100:
        await interaction.response.send_message("❌ L'età deve essere compresa tra 16 e 100 anni.", ephemeral=True)
        return
    
    database[user_id]["documenti"] = {
        "nome": nome, 
        "cognome": cognome, 
        "eta": eta,
        "cittadinanza": cittadinanza.value,
        "citta_provenienza": citta_provenienza,
        "genere": genere.value,
        "altezza": altezza,
        "colore_capelli": colore_capelli
    }
    salva_database()
    await interaction.response.send_message(f"✅ Generalità modificate con successo per: **{nome} {cognome}**.", ephemeral=True)

@bot.tree.command(name="info_civile", description="Visualizza il profilo pubblico o documenti di un civile")
async def info_civile(interaction: discord.Interaction, utente: discord.User):
    user_id = str(utente.id)
    controlla_utente(user_id)
    data = database[user_id]
    doc = data.get("documenti")
    
    embed = discord.Embed(title=f"👤 Scheda Civile: {utente.display_name}", color=discord.Color.teal())
    if doc:
        info_doc = (
            f"**Nome:** {doc['nome']}\n"
            f"**Cognome:** {doc['cognome']}\n"
            f"**Età:** {doc['eta']}\n"
            f"**Genere:** {doc.get('genere', 'N/D')}\n"
            f"**Cittadinanza:** {doc.get('cittadinanza', 'N/D')}\n"
            f"**Provenienza:** {doc.get('citta_provenienza', 'N/D')}\n"
            f"**Altezza:** {doc.get('altezza', 'N/D')}\n"
            f"**Capelli:** {doc.get('colore_capelli', 'N/D')}"
        )
        embed.add_field(name="Identità", value=info_doc, inline=False)
    else:
        embed.add_field(name="Identità", value="Nessun documento registrato.", inline=False)
        
    embed.add_field(name="Impiego", value=f"**Lavoro:** {data.get('lavoro', 'Disoccupato')}\n**In Servizio:** {'Sì' if data.get('in_servizio') else 'No'}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lista_civili", description="[ADMIN] Elenco completo di tutti i profili registrati")
@app_commands.checks.has_permissions(administrator=True)
async def lista_civili(interaction: discord.Interaction):
    embed = discord.Embed(title="📋 Lista Civili nel Database", color=discord.Color.dark_grey())
    
    for uid, info in database.items():
        if uid in ["SETTINGS", "STORE", "JOBS", "MERCATO"]:
            continue
        user = bot.get_user(int(uid))
        name_str = user.mention if user else f"ID: {uid}"
        doc = info.get("documenti")
        details = f"{doc['nome']} {doc['cognome']}" if doc else "Senza Documenti"
        embed.add_field(name=f"Utente: {user.display_name if user else uid}", value=f"{name_str} | RP: *{details}* | Lavoro: {info.get('lavoro')}", inline=False)
        
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="elimina_civile", description="[ADMIN] Resetta completamente i dati di un utente")
@app_commands.checks.has_permissions(administrator=True)
async def elimina_civile(interaction: discord.Interaction, utente: discord.User):
    user_id = str(utente.id)
    if user_id in database:
        del database[user_id]
        salva_database()
        await interaction.response.send_message(f"🗑️ Tutti i dati relativi a {utente.mention} sono stati cancellati permanentemente.")
        
        await invia_log(
            "🗑️ Log Admin - Reset", 
            f"L'amministratore {interaction.user.mention} ha **eliminato permanentemente** il profilo database di {utente.mention}.", 
            discord.Color.red()
        )
    else:
        await interaction.response.send_message("❌ Utente non presente nel database.", ephemeral=True)

# ==========================================
# 6. PORTAFOGLIO, VEICOLI, ARMI & INVENTARIO
# ==========================================

@bot.tree.command(name="registra_veicolo", description="Registra un veicolo a tuo nome")
async def registra_veicolo(interaction: discord.Interaction, modello: str, targa: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    database[user_id]["veicoli"].append({"modello": modello, "targa": targa.upper()})
    salva_database()
    await interaction.response.send_message(f"🚗 Veicolo **{modello}** [{targa.upper()}] registrato nel portafoglio!", ephemeral=True)

@bot.tree.command(name="registra_arma", description="Registra la matricola di un'arma")
async def registra_arma(interaction: discord.Interaction, modello: str, matricola: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    database[user_id]["armi"].append({"modello": modello, "matricola": matricola})
    salva_database()
    await interaction.response.send_message(f"🔫 Arma **{modello}** (S/N: {matricola}) registrata nel porto d'armi!", ephemeral=True)

@bot.tree.command(name="portafoglio", description="Mostra i tuoi soldi, documenti, veicoli e armi")
async def portafoglio(interaction: discord.Interaction, utente: discord.User = None):
    target = utente if utente else interaction.user
    user_id = str(target.id)
    controlla_utente(user_id)
    
    data = database[user_id]
    doc = data.get("documenti")
    val = database["SETTINGS"]["valuta"]
    
    embed = discord.Embed(title=f"💳 Portafoglio di {target.display_name}", color=discord.Color.gold())
    embed.add_field(name="💰 Bilancio", value=f"**Contanti:** {data.get('contanti',0)}{val}\n**Banca:** {data.get('banca',0)}{val}\nMulte pendenti: {data.get('multe',0)}{val}", inline=False)
    
    if doc:
        info_doc = (
            f"**Nome:** {doc['nome']} {doc['cognome']}\n"
            f"**Età:** {doc['eta']}\n"
            f"**Genere:** {doc.get('genere', 'N/D')}\n"
            f"**Nazionalità:** {doc.get('cittadinanza', 'N/D')} ({doc.get('citta_provenienza', 'N/D')})\n"
            f"**Fisionomia:** {doc.get('altezza', 'N/D')}, Capelli {doc.get('colore_capelli', 'N/D')}"
        )
        embed.add_field(name="🪪 Carta d'Identità", value=info_doc, inline=False)
    else:
        embed.add_field(name="🪪 Carta d'Identità", value="Nessun documento creato.", inline=False)
        
    veicoli_txt = "\n".join([f"- {v['modello']} ({v['targa']})" for v in data["veicoli"]]) if data["veicoli"] else "Nessun veicolo"
    embed.add_field(name="🚗 Veicoli", value=veicoli_txt, inline=True)
    
    armi_txt = "\n".join([f"- {a['modello']} [{a['matricola']}]" for a in data["armi"]]) if data["armi"] else "Nessuna arma"
    embed.add_field(name="🔫 Armi Registrate", value=armi_txt, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="inventario", description="Visualizza gli oggetti e le sostanze nelle tue tasche")
async def inventario(interaction: discord.Interaction, utente: discord.User = None):
    target = utente if utente else interaction.user
    
    if utente and utente.id != interaction.user.id:
        user_id = str(interaction.user.id)
        controlla_utente(user_id)
        if database[user_id].get("ammanettato", False):
            await interaction.response.send_message("❌ Non puoi guardare negli zaini altrui mentre sei ammanettato!", ephemeral=True)
            return
    
    target_id = str(target.id)
    controlla_utente(target_id)
    
    inv = database[target_id]["inventario"]
    embed = discord.Embed(title=f"🎒 Inventario di {target.display_name}", color=discord.Color.green())
    
    corpo = ""
    for item, qta in inv.items():
        if qta > 0:
            corpo += f"• **{item.capitalize()}**: {qta} unità\n"
            
    embed.description = corpo if corpo != "" else "*L'inventario è completamente vuoto.*"
    await interaction.response.send_message(embed=embed)

# ==========================================
# 7. SISTEMA ECONOMIA
# ==========================================

@bot.tree.command(name="deposita", description="Deposita denaro contante in banca")
async def deposita(interaction: discord.Interaction, cifra: int):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    val = database["SETTINGS"]["valuta"]
    
    if cifra <= 0:
        await interaction.response.send_message("❌ Inserisci una cifra valida.", ephemeral=True)
        return
        
    if database[user_id]["contanti"] < cifra:
        await interaction.response.send_message("❌ Non possiedi abbastanza contanti da depositare.", ephemeral=True)
        return
        
    database[user_id]["contanti"] -= cifra
    database[user_id]["banca"] += cifra
    salva_database()
    await interaction.response.send_message(f"🏦 Hai depositato **{cifra}{val}** sul tuo conto bancario.")
    
    await invia_log(
        "🏦 Log Banca - Deposito", 
        f"L'utente {interaction.user.mention} ha depositato **{cifra}{val}** sul conto bancario.", 
        discord.Color.light_gray()
    )

@bot.tree.command(name="preleva", description="Ritira denaro dalla banca e mettilo in contanti")
async def preleva(interaction: discord.Interaction, cifra: int):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    val = database["SETTINGS"]["valuta"]
    
    if cifra <= 0:
        await interaction.response.send_message("❌ Inserisci una cifra valida.", ephemeral=True)
        return
        
    if database[user_id]["banca"] < cifra:
        await interaction.response.send_message("❌ Non hai abbastanza fondi sul conto bancario.", ephemeral=True)
        return
        
    database[user_id]["banca"] -= cifra
    database[user_id]["contanti"] += cifra
    salva_database()
    await interaction.response.send_message(f"💵 Hai ritirato **{cifra}{val}** in contanti dalla banca.")
    
    await invia_log(
        "🏦 Log Banca - Prelievo", 
        f"L'utente {interaction.user.mention} ha prelevato **{cifra}{val}** in contanti.", 
        discord.Color.light_gray()
    )

@bot.tree.command(name="paga_cittadino", description="Paga un altro cittadino usando i tuoi contanti disponibili")
async def paga_cittadino(interaction: discord.Interaction, cittadino: discord.User, cifra: int):
    user_id = str(interaction.user.id)
    target_id = str(cittadino.id)
    controlla_utente(user_id)
    controlla_utente(target_id)
    val = database["SETTINGS"]["valuta"]
    
    if cifra <= 0 or interaction.user.id == cittadino.id:
        await interaction.response.send_message("❌ Transazione non valida.", ephemeral=True)
        return
        
    if database[user_id]["contanti"] < cifra:
        await interaction.response.send_message("❌ Non hai abbastanza contanti.", ephemeral=True)
        return
        
    database[user_id]["contanti"] -= cifra
    database[target_id]["contanti"] += cifra
    salva_database()
    await interaction.response.send_message(f"💸 Hai consegnato **{cifra}{val}** a {cittadino.mention}.")
    
    await invia_log(
        "💸 Log Transazioni Civili", 
        f"L'utente {interaction.user.mention} ha passato **{cifra}{val}** in contanti a {cittadino.mention}.", 
        discord.Color.gold()
    )

@bot.tree.command(name="paga_multa", description="Paga una multa usando il tuo saldo bancario")
async def paga_multa(interaction: discord.Interaction, importo: int):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    val = database["SETTINGS"]["valuta"]
    
    if database[user_id]["multe"] < importo:
        await interaction.response.send_message("❌ L'importo inserito supera le tue multe effettive.", ephemeral=True)
        return
        
    if database[user_id]["banca"] < importo:
        await interaction.response.send_message("❌ Fondi bancari insufficienti.", ephemeral=True)
        return
        
    database[user_id]["banca"] -= importo
    database[user_id]["multe"] -= importo
    salva_database()
    await interaction.response.send_message(f"✅ Pagamento di **{importo}{val}** per le tue sanzioni elaborato con successo.")
    
    await invia_log(
        "🏛️ Log Pagamento Multe", 
        f"L'utente {interaction.user.mention} ha saldato sanzioni per **{importo}{val}** tramite banca.", 
        discord.Color.blue()
    )

@bot.tree.command(name="paga_deposito", description="Paga il riscatto del veicolo al deposito della centrale")
async def paga_deposito(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    costo = database["SETTINGS"]["tassa_servizi"]
    val = database["SETTINGS"]["valuta"]
    
    if database[user_id]["banca"] < costo:
        await interaction.response.send_message(f"❌ Ti servono {costo}{val} in banca per riscattare il mezzo.", ephemeral=True)
        return
        
    database[user_id]["banca"] -= costo
    salva_database()
    await interaction.response.send_message(f"🛞 Deposito pagato! Hai speso **{costo}{val}**. Il tuo veicolo rimosso è di nuovo disponibile.")
    
    await invia_log(
        "🚗 Log Deposito Veicoli", 
        f"L'utente {interaction.user.mention} ha pagato il riscatto del veicolo sequestrato spendendo **{costo}{val}**.", 
        discord.Color.orange()
    )

# ==========================================
# 8. SISTEMA MERCATO GIOCATORI
# ==========================================

@bot.tree.command(name="mercato_vendi", description="Metti in vendita un oggetto dal tuo inventario al mercato pubblico")
@app_commands.describe(
    oggetto="Nome dell'oggetto da vendere",
    prezzo="Prezzo unitario in contanti",
    quantita="Quantità da mettere in vendita"
)
async def mercato_vendi(interaction: discord.Interaction, oggetto: str, prezzo: int, quantita: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    oggetto = oggetto.lower()
    
    if prezzo <= 0 or quantita <= 0:
        await interaction.response.send_message("❌ Prezzo e quantità devono essere positivi.", ephemeral=True)
        return
        
    if database[user_id]["inventario"].get(oggetto, 0) < quantita:
        await interaction.response.send_message(f"❌ Non hai abbastanza **{oggetto}** nel tuo inventario (hai {database[user_id]['inventario'].get(oggetto, 0)} unità).", ephemeral=True)
        return
    
    database[user_id]["inventario"][oggetto] -= quantita
    
    if oggetto not in database["MERCATO"]:
        database["MERCATO"][oggetto] = []
    
    database["MERCATO"][oggetto].append({
        "venditore_id": user_id,
        "venditore_nome": interaction.user.display_name,
        "prezzo": prezzo,
        "quantita": quantita
    })
    
    salva_database()
    val = database["SETTINGS"]["valuta"]
    await interaction.response.send_message(f"🏪 Hai messo in vendita **{quantita}x {oggetto}** a **{prezzo}{val}** ciascuno sul mercato pubblico!")
    
    await invia_log(
        "🏪 Log Mercato - Vendita", 
        f"L'utente {interaction.user.mention} ha messo in vendita **{quantita}x {oggetto}** a {prezzo}{val} l'uno.", 
        discord.Color.gold()
    )

@bot.tree.command(name="mercato_compra", description="Compra un oggetto dal mercato pubblico")
@app_commands.describe(
    oggetto="Nome dell'oggetto da comprare",
    venditore="Il venditore da cui comprare",
    quantita="Quantità da acquistare"
)
async def mercato_compra(interaction: discord.Interaction, oggetto: str, venditore: discord.User, quantita: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    oggetto = oggetto.lower()
    venditore_id = str(venditore.id)
    
    if quantita <= 0:
        await interaction.response.send_message("❌ La quantità deve essere positiva.", ephemeral=True)
        return
        
    if oggetto not in database["MERCATO"]:
        await interaction.response.send_message("❌ Nessuno vende questo oggetto al momento.", ephemeral=True)
        return
    
    annuncio = None
    for idx, ann in enumerate(database["MERCATO"][oggetto]):
        if ann["venditore_id"] == venditore_id and ann["quantita"] >= quantita:
            annuncio = idx
            break
    
    if annuncio is None:
        await interaction.response.send_message(f"❌ {venditore.mention} non vende abbastanza **{oggetto}** per soddisfare la tua richiesta.", ephemeral=True)
        return
    
    ann = database["MERCATO"][oggetto][annuncio]
    costo_totale = ann["prezzo"] * quantita
    val = database["SETTINGS"]["valuta"]
    
    if database[user_id]["contanti"] < costo_totale:
        await interaction.response.send_message(f"❌ Non hai abbastanza contanti. Ti servono **{costo_totale}{val}**.", ephemeral=True)
        return
    
    database[user_id]["contanti"] -= costo_totale
    database[venditore_id]["contanti"] += costo_totale
    database[user_id]["inventario"][oggetto] = database[user_id]["inventario"].get(oggetto, 0) + quantita
    
    if ann["quantita"] == quantita:
        database["MERCATO"][oggetto].pop(annuncio)
        if not database["MERCATO"][oggetto]:
            del database["MERCATO"][oggetto]
    else:
        database["MERCATO"][oggetto][annuncio]["quantita"] -= quantita
    
    salva_database()
    await interaction.response.send_message(f"🛍️ Hai comprato **{quantita}x {oggetto}** da {venditore.mention} per **{costo_totale}{val}**!")
    
    await invia_log(
        "🏪 Log Mercato - Acquisto", 
        f"L'utente {interaction.user.mention} ha comprato **{quantita}x {oggetto}** da {venditore.mention} per {costo_totale}{val}.", 
        discord.Color.gold()
    )

@bot.tree.command(name="mercato_rimuovi", description="Rimuovi una tua vendita dal mercato")
async def mercato_rimuovi(interaction: discord.Interaction, oggetto: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    oggetto = oggetto.lower()
    
    if oggetto not in database["MERCATO"]:
        await interaction.response.send_message("❌ Non hai annunci per questo oggetto.", ephemeral=True)
        return
    
    da_rimuovere = []
    for idx, ann in enumerate(database["MERCATO"][oggetto]):
        if ann["venditore_id"] == user_id:
            da_rimuovere.append(idx)
            database[user_id]["inventario"][oggetto] = database[user_id]["inventario"].get(oggetto, 0) + ann["quantita"]
    
    if not da_rimuovere:
        await interaction.response.send_message("❌ Non hai annunci per questo oggetto.", ephemeral=True)
        return
    
    for idx in reversed(da_rimuovere):
        database["MERCATO"][oggetto].pop(idx)
    
    if not database["MERCATO"][oggetto]:
        del database["MERCATO"][oggetto]
    
    salva_database()
    await interaction.response.send_message(f"✅ Hai rimosso i tuoi annunci per **{oggetto}** e gli oggetti sono tornati nel tuo inventario.")

@bot.tree.command(name="mercato_lista", description="Mostra tutti gli annunci del mercato pubblico")
async def mercato_lista(interaction: discord.Interaction, pagina: int = 1):
    if not database["MERCATO"]:
        await interaction.response.send_message("🏪 Il mercato pubblico è vuoto al momento.", ephemeral=True)
        return
    
    val = database["SETTINGS"]["valuta"]
    embed = discord.Embed(title="🏪 Mercato Pubblico di Los Santos", color=discord.Color.gold())
    
    items_list = list(database["MERCATO"].items())
    items_per_page = 10
    total_pages = math.ceil(len(items_list) / items_per_page)
    
    if pagina < 1 or pagina > total_pages:
        await interaction.response.send_message(f"❌ Pagina non valida. Pagine disponibili: 1-{total_pages}", ephemeral=True)
        return
    
    start_idx = (pagina - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(items_list))
    
    for oggetto, annunci in items_list[start_idx:end_idx]:
        testo = ""
        for ann in annunci:
            testo += f"• Venditore: **{ann['venditore_nome']}** | Prezzo: {ann['prezzo']}{val} | Qtà: {ann['quantita']}\n"
        embed.add_field(name=f"📦 {oggetto.capitalize()}", value=testo, inline=False)
    
    embed.set_footer(text=f"Pagina {pagina}/{total_pages} • Usa /mercato_lista pagina:<numero>")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="proponi_vendita", description="Proponi a un giocatore specifico di comprare un tuo oggetto")
@app_commands.describe(
    acquirente="Il giocatore a cui vuoi vendere",
    oggetto="L'oggetto che vuoi vendere",
    prezzo="Il prezzo richiesto",
    quantita="Quanti ne vuoi vendere"
)
async def proponi_vendita(interaction: discord.Interaction, acquirente: discord.User, oggetto: str, prezzo: int, quantita: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    oggetto = oggetto.lower()
    val = database["SETTINGS"]["valuta"]
    
    if acquirente.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi proporre vendite a te stesso!", ephemeral=True)
        return
        
    if prezzo <= 0 or quantita <= 0:
        await interaction.response.send_message("❌ Prezzo e quantità devono essere positivi.", ephemeral=True)
        return
        
    if database[user_id]["inventario"].get(oggetto, 0) < quantita:
        await interaction.response.send_message(f"❌ Non hai abbastanza **{oggetto}** (hai {database[user_id]['inventario'].get(oggetto, 0)} unità).", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💼 Proposta di Vendita",
        description=f"**{interaction.user.mention}** vuole venderti:\n\n"
                   f"📦 **{quantita}x {oggetto.capitalize()}**\n"
                   f"💰 Prezzo: **{prezzo}{val}** ciascuno\n"
                   f"💵 Totale: **{prezzo * quantita}{val}**\n\n"
                   f"Usa `/accetta_vendita @{interaction.user.display_name} {oggetto} {quantita}` per accettare!",
        color=discord.Color.green()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    try:
        await acquirente.send(embed=embed)
        await interaction.response.send_message(f"✅ Proposta di vendita inviata a {acquirente.mention} per **{quantita}x {oggetto}** a **{prezzo}{val}** l'uno.")
        
        await invia_log(
            "💼 Log Proposta Vendita", 
            f"L'utente {interaction.user.mention} ha proposto a {acquirente.mention} di comprare **{quantita}x {oggetto}** a {prezzo}{val} l'uno.", 
            discord.Color.blue()
        )
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Impossibile inviare un messaggio privato a {acquirente.mention}. Potrebbe avere i DM chiusi.", ephemeral=True)

@bot.tree.command(name="accetta_vendita", description="Accetta una proposta di vendita ricevuta")
@app_commands.describe(
    venditore="Il giocatore che ti ha proposto la vendita",
    oggetto="L'oggetto della proposta",
    quantita="Quanti ne vuoi comprare"
)
async def accetta_vendita(interaction: discord.Interaction, venditore: discord.User, oggetto: str, quantita: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    venditore_id = str(venditore.id)
    controlla_utente(venditore_id)
    oggetto = oggetto.lower()
    
    if venditore.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi accettare una vendita da te stesso!", ephemeral=True)
        return
    
    if database[venditore_id]["inventario"].get(oggetto, 0) < quantita:
        await interaction.response.send_message(f"❌ {venditore.mention} non ha più abbastanza **{oggetto}** da venderti.", ephemeral=True)
        return
    
    await interaction.response.send_message(
        f"⚠️ Per completare l'acquisto, usa `/paga_cittadino @{venditore.display_name} <importo>` per pagare {venditore.mention}.\n"
        f"Poi il venditore dovrà usare `/consegna_oggetto @{interaction.user.display_name} {oggetto} {quantita}` per consegnarti l'oggetto.\n"
        f"*Sistema manuale per garantire sicurezza nella transazione.*",
        ephemeral=True
    )

@bot.tree.command(name="consegna_oggetto", description="Consegna un oggetto del tuo inventario a un altro giocatore")
@app_commands.describe(
    ricevente="Chi riceverà l'oggetto",
    oggetto="L'oggetto da consegnare",
    quantita="Quanti ne vuoi consegnare"
)
async def consegna_oggetto(interaction: discord.Interaction, ricevente: discord.User, oggetto: str, quantita: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    ricevente_id = str(ricevente.id)
    controlla_utente(ricevente_id)
    oggetto = oggetto.lower()
    
    if ricevente.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi consegnare oggetti a te stesso!", ephemeral=True)
        return
        
    if quantita <= 0:
        await interaction.response.send_message("❌ La quantità deve essere positiva.", ephemeral=True)
        return
        
    if database[user_id]["inventario"].get(oggetto, 0) < quantita:
        await interaction.response.send_message(f"❌ Non hai abbastanza **{oggetto}** (hai {database[user_id]['inventario'].get(oggetto, 0)} unità).", ephemeral=True)
        return
    
    database[user_id]["inventario"][oggetto] -= quantita
    if database[user_id]["inventario"][oggetto] == 0:
        del database[user_id]["inventario"][oggetto]
    
    database[ricevente_id]["inventario"][oggetto] = database[ricevente_id]["inventario"].get(oggetto, 0) + quantita
    salva_database()
    
    await interaction.response.send_message(f"✅ Hai consegnato **{quantita}x {oggetto}** a {ricevente.mention}!")
    
    try:
        embed = discord.Embed(
            title="📦 Oggetto Ricevuto!",
            description=f"**{interaction.user.mention}** ti ha consegnato **{quantita}x {oggetto}**.\nControlla il tuo `/inventario`!",
            color=discord.Color.green()
        )
        await ricevente.send(embed=embed)
    except discord.Forbidden:
        pass
    
    await invia_log(
        "📦 Log Consegna Oggetti", 
        f"L'utente {interaction.user.mention} ha consegnato **{quantita}x {oggetto}** a {ricevente.mention}.", 
        discord.Color.teal()
    )

# ==========================================
# 9. COMANDI INTERAZIONE POLIZIA
# ==========================================

@bot.tree.command(name="p_multa", description="[POLIZIA] Fai una multa a un cittadino")
async def p_multa(interaction: discord.Interaction, cittadino: discord.User, importo: int, motivo: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if database[user_id].get("lavoro") != "Polizia" or not database[user_id].get("in_servizio"):
        await interaction.response.send_message("❌ Comando riservato alla Polizia in servizio.", ephemeral=True)
        return

    controlla_utente(str(cittadino.id))
    val = database["SETTINGS"]["valuta"]
    
    database[str(cittadino.id)]["multe"] += importo
    salva_database()
    
    embed = discord.Embed(
        title="🚔 CENTRALE LSPD - VERBALE DI MULTA",
        description=f"**Agente:** {interaction.user.mention}\n**Cittadino:** {cittadino.mention}\n**Importo:** {importo}{val}\n**Motivazione:** {motivo}\n\n*La sanzione è stata caricata sul profilo del cittadino.*",
        color=discord.Color.dark_blue()
    )
    await interaction.response.send_message("Multa notificata.", ephemeral=True)
    await interaction.channel.send(embed=embed)
    
    await invia_log(
        "🚔 Log Polizia - Multa", 
        f"L'Agente {interaction.user.mention} ha multato {cittadino.mention} di **{importo}{val}**.\n**Motivo:** {motivo}", 
        discord.Color.dark_blue()
    )

@bot.tree.command(name="p_arresto", description="[POLIZIA] Registra un arresto e aggiorna la fedina penale")
async def p_arresto(interaction: discord.Interaction, cittadino: discord.User, mesi: int, motivo: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if database[user_id].get("lavoro") != "Polizia" or not database[user_id].get("in_servizio"):
        await interaction.response.send_message("❌ Comando riservato alla Polizia in servizio.", ephemeral=True)
        return

    t_id = str(cittadino.id)
    controlla_utente(t_id)
    
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y")
    database[t_id]["fedina"].append(f"[{timestamp}] {mesi} Mesi per: {motivo}")
    salva_database()
    
    embed = discord.Embed(
        title="🚨 LSPD - MANDATO DI ARRESTO ESEGUITO",
        description=f"**Sospetto:** {cittadino.mention}\n**Tempo:** {mesi} mesi/minuti\n**Capo d'accusa:** {motivo}\n\n*Il reato è stata trascritto sulla fedina penale criminale.*",
        color=discord.Color.dark_red()
    )
    await interaction.response.send_message("Arresto registrato.", ephemeral=True)
    await interaction.channel.send(embed=embed)
    
    await invia_log(
        "🚨 Log Polizia - Arresto", 
        f"L'Agente {interaction.user.mention} ha arrestato {cittadino.mention} per **{mesi} mesi**.\n**Accusa:** {motivo}", 
        discord.Color.dark_red()
    )

@bot.tree.command(name="fedina", description="Visualizza la fedina penale crimini di un cittadino")
async def fedina(interaction: discord.Interaction, utente: discord.User = None):
    target = utente if utente else interaction.user
    controlla_utente(str(target.id))
    
    lista_reati = database[str(target.id)].get("fedina", [])
    
    embed = discord.Embed(title=f"📂 Archivio Penale di {target.display_name}", color=discord.Color.dark_purple())
    
    if lista_reati:
        embed.description = "\n".join(lista_reati)
    else:
        embed.description = "✅ Fedina Penale completamente pulita. Nessun precedente registrato."
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="p_pulisci_fedina", description="[POLIZIA/ADMIN] Ripulisci la fedina penale di un cittadino")
async def p_pulisci_fedina(interaction: discord.Interaction, utente: discord.User):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    is_admin = interaction.user.guild_permissions.administrator
    is_cop = database[user_id].get("lavoro") == "Polizia" and database[user_id].get("in_servizio")
    
    if not (is_admin or is_cop):
        await interaction.response.send_message("❌ Non hai l'autorizzazione o non sei in servizio nella Polizia.", ephemeral=True)
        return
        
    target_id = str(utente.id)
    controlla_utente(target_id)
    database[target_id]["fedina"] = []
    database[target_id]["multe"] = 0
    salva_database()
    await interaction.response.send_message(f"🧼 La fedina penale e le sanzioni storiche di {utente.mention} sono state ripulite integralmente.")
    
    await invia_log(
        "🧼 Log Polizia - Fedina Ripulita", 
        f"L'utente {interaction.user.mention} ha **ripulito completamente** la fedina penale di {utente.mention}.", 
        discord.Color.blue()
    )

@bot.tree.command(name="ammanetta", description="[POLIZIA] Blocca o sblocca un cittadino sul posto")
async def ammanetta(interaction: discord.Interaction, utente: discord.User):
    u_id = str(interaction.user.id)
    controlla_utente(u_id)
    if database[u_id].get("lavoro") != "Polizia" or not database[u_id].get("in_servizio"):
        await interaction.response.send_message("❌ Comando riservato alla Polizia in servizio.", ephemeral=True)
        return
        
    t_id = str(utente.id)
    controlla_utente(t_id)
    stato = not database[t_id].get("ammanettato", False)
    database[t_id]["ammanettato"] = stato
    salva_database()
    
    msg = f"🔗 {utente.mention} è stato **ammanettato**!" if stato else f"🔓 {utente.mention} è stato **smanettato** e liberato."
    await interaction.response.send_message(msg)
    
    await invia_log(
        "🔗 Log Polizia - Manette", 
        f"L'Agente {interaction.user.mention} ha {'**ammanettato**' if stato else '**liberato dalle manette**'} {utente.mention}.", 
        discord.Color.dark_blue()
    )

@bot.tree.command(name="confisca", description="[POLIZIA] Sequestra e svuota gli oggetti illegali/tasche di un sospetto")
async def confisca(interaction: discord.Interaction, utente: discord.User):
    u_id = str(interaction.user.id)
    controlla_utente(u_id)
    if database[u_id].get("lavoro") != "Polizia" or not database[u_id].get("in_servizio"):
        await interaction.response.send_message("❌ Comando riservato alla Polizia in servizio.", ephemeral=True)
        return
        
    t_id = str(utente.id)
    controlla_utente(t_id)
    
    database[t_id]["inventario"] = {}
    salva_database()
    await interaction.response.send_message(f"🛡️ Ispezione eseguita. Tutti gli articoli illeciti/oggetti nelle tasche di {utente.mention} sono stati confiscati e distrutti.")
    
    await invia_log(
        "🛡️ Log Polizia - Confisca", 
        f"L'Agente {interaction.user.mention} ha perquisito e **confiscato l'intero inventario illecito** di {utente.mention}.", 
        discord.Color.dark_blue()
    )

# ==========================================
# 10. SISTEMA NEGOZIO (CON PAGINAZIONE)
# ==========================================

@bot.tree.command(name="negozio", description="Mostra il catalogo degli articoli acquistabili in città")
async def negozio(interaction: discord.Interaction, pagina: int = 1):
    val = database["SETTINGS"]["valuta"]
    items = list(database["STORE"].items())
    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
    
    if pagina < 1 or pagina > total_pages:
        await interaction.response.send_message(f"❌ Pagina non valida. Pagine disponibili: 1-{total_pages}", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🛒 Negozio di Los Santos (Pagina {pagina}/{total_pages})", 
        color=discord.Color.gold()
    )
    
    start_idx = (pagina - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(items))
    
    for item, dettagli in items[start_idx:end_idx]:
        embed.add_field(
            name=f"📦 {item.upper()}", 
            value=f"Prezzo: **{dettagli['prezzo']}{val}**\nInfo: *{dettagli['descrizione']}*", 
            inline=False
        )
    
    embed.set_footer(text=f"Usa /negozio pagina:<numero> per navigare • /compra_oggetto per acquistare")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="compra_oggetto", description="Acquista un articolo dallo store cittadino")
async def compra_oggetto(interaction: discord.Interaction, nome_oggetto: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    nome_oggetto = nome_oggetto.lower()
    
    if nome_oggetto not in database["STORE"]:
        await interaction.response.send_message("❌ Questo articolo non è venduto nel negozio.", ephemeral=True)
        return
        
    prezzo = database["STORE"][nome_oggetto]["prezzo"]
    val = database["SETTINGS"]["valuta"]
    
    if database[user_id]["contanti"] < prezzo:
        await interaction.response.send_message(f"❌ Non hai abbastanza contanti ({prezzo}{val} richiesti).", ephemeral=True)
        return
        
    database[user_id]["contanti"] -= prezzo
    database[user_id]["inventario"][nome_oggetto] = database[user_id]["inventario"].get(nome_oggetto, 0) + 1
    salva_database()
    await interaction.response.send_message(f"🛍️ Hai comprato 1x **{nome_oggetto}** per **{prezzo}{val}**.")
    
    await invia_log(
        "🛒 Log Store - Acquisto", 
        f"L'utente {interaction.user.mention} ha acquistato **1x {nome_oggetto}** spendendo **{prezzo}{val}** in contanti.", 
        discord.Color.gold()
    )

@bot.tree.command(name="aggiungi_oggetto_negozio", description="[ADMIN] Aggiungi o modifica un articolo in vendita al negozio")
@app_commands.checks.has_permissions(administrator=True)
async def aggiungi_oggetto_negozio(interaction: discord.Interaction, nome: str, prezzo: int, descrizione: str):
    database["STORE"][nome.lower()] = {"prezzo": prezzo, "descrizione": descrizione}
    salva_database()
    await interaction.response.send_message(f"✅ Articolo **{nome}** configurato nello store a {prezzo}.")
    
    await invia_log(
        "🛠️ Log Admin - Negozio", 
        f"L'amministratore {interaction.user.mention} ha aggiunto/modificato l'articolo **{nome}** nello Store (Prezzo: {prezzo}).", 
        discord.Color.purple()
    )

@bot.tree.command(name="rimuovi_oggetto_negozio", description="[ADMIN] Rimuovi permanentemente un articolo dal negozio")
@app_commands.checks.has_permissions(administrator=True)
async def rimuovi_oggetto_negozio(interaction: discord.Interaction, nome: str):
    nome_l = nome.lower()
    if nome_l in database["STORE"]:
        del database["STORE"][nome_l]
        salva_database()
        await interaction.response.send_message(f"🗑️ Articolo **{nome}** rimosso dal negozio.")
        
        await invia_log(
            "🛠️ Log Admin - Negozio", 
            f"L'amministratore {interaction.user.mention} ha rimosso l'articolo **{nome}** dal catalogo del negozio.", 
            discord.Color.purple()
        )
    else:
        await interaction.response.send_message("❌ Articolo non presente nello store.", ephemeral=True)

# ==========================================
# 11. COMANDI ADMIN GESTIONE INVENTARIO
# ==========================================

@bot.tree.command(name="dai_oggetto", description="[ADMIN] Aggiunge un oggetto all'inventario di un giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore che riceverà l'oggetto",
    oggetto="Nome dell'oggetto da aggiungere",
    quantita="Quantità da aggiungere (default: 1)"
)
async def dai_oggetto(interaction: discord.Interaction, utente: discord.User, oggetto: str, quantita: int = 1):
    target_id = str(utente.id)
    controlla_utente(target_id)
    oggetto = oggetto.lower()
    
    if quantita <= 0:
        await interaction.response.send_message("❌ La quantità deve essere positiva.", ephemeral=True)
        return
    
    if quantita > 1000:
        await interaction.response.send_message("❌ Massimo 1000 unità per volta.", ephemeral=True)
        return
    
    database[target_id]["inventario"][oggetto] = database[target_id]["inventario"].get(oggetto, 0) + quantita
    salva_database()
    
    await interaction.response.send_message(f"✅ Aggiunto **{quantita}x {oggetto}** all'inventario di {utente.mention}.")
    
    await invia_log(
        "🎁 Log Admin - Oggetto Aggiunto", 
        f"L'amministratore {interaction.user.mention} ha aggiunto **{quantita}x {oggetto}** all'inventario di {utente.mention}.", 
        discord.Color.green()
    )

@bot.tree.command(name="rimuovi_oggetto", description="[ADMIN] Rimuove un oggetto dall'inventario di un giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore a cui rimuovere l'oggetto",
    oggetto="Nome dell'oggetto da rimuovere",
    quantita="Quantità da rimuovere (default: 1)"
)
async def rimuovi_oggetto(interaction: discord.Interaction, utente: discord.User, oggetto: str, quantita: int = 1):
    target_id = str(utente.id)
    controlla_utente(target_id)
    oggetto = oggetto.lower()
    
    if quantita <= 0:
        await interaction.response.send_message("❌ La quantità deve essere positiva.", ephemeral=True)
        return
    
    current_qty = database[target_id]["inventario"].get(oggetto, 0)
    
    if current_qty < quantita:
        await interaction.response.send_message(f"❌ {utente.mention} ha solo **{current_qty}x {oggetto}**. Impossibile rimuoverne {quantita}.", ephemeral=True)
        return
    
    database[target_id]["inventario"][oggetto] -= quantita
    
    if database[target_id]["inventario"][oggetto] == 0:
        del database[target_id]["inventario"][oggetto]
    
    salva_database()
    
    await interaction.response.send_message(f"✅ Rimosso **{quantita}x {oggetto}** dall'inventario di {utente.mention}.")
    
    await invia_log(
        "🗑️ Log Admin - Oggetto Rimosso", 
        f"L'amministratore {interaction.user.mention} ha rimosso **{quantita}x {oggetto}** dall'inventario di {utente.mention}.", 
        discord.Color.red()
    )

@bot.tree.command(name="svuota_inventario", description="[ADMIN] Svuota completamente l'inventario di un giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore a cui svuotare l'inventario"
)
async def svuota_inventario(interaction: discord.Interaction, utente: discord.User):
    target_id = str(utente.id)
    controlla_utente(target_id)
    
    total_items = sum(database[target_id]["inventario"].values())
    
    database[target_id]["inventario"] = {}
    salva_database()
    
    await interaction.response.send_message(f"🗑️ Inventario di {utente.mention} completamente svuotato! ({total_items} oggetti rimossi)")
    
    await invia_log(
        "🗑️ Log Admin - Inventario Svuotato", 
        f"L'amministratore {interaction.user.mention} ha **svuotato completamente** l'inventario di {utente.mention} ({total_items} oggetti).", 
        discord.Color.red()
    )

@bot.tree.command(name="imposta_oggetto", description="[ADMIN] Imposta una quantità esatta di un oggetto nell'inventario")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore target",
    oggetto="Nome dell'oggetto",
    quantita="Nuova quantità esatta (0 per rimuovere)"
)
async def imposta_oggetto(interaction: discord.Interaction, utente: discord.User, oggetto: str, quantita: int):
    target_id = str(utente.id)
    controlla_utente(target_id)
    oggetto = oggetto.lower()
    
    if quantita < 0:
        await interaction.response.send_message("❌ La quantità non può essere negativa.", ephemeral=True)
        return
    
    if quantita > 1000:
        await interaction.response.send_message("❌ Massimo 1000 unità.", ephemeral=True)
        return
    
    old_qty = database[target_id]["inventario"].get(oggetto, 0)
    
    if quantita == 0:
        if oggetto in database[target_id]["inventario"]:
            del database[target_id]["inventario"][oggetto]
        await interaction.response.send_message(f"✅ Rimosso completamente **{oggetto}** dall'inventario di {utente.mention} (aveva {old_qty}x).")
    else:
        database[target_id]["inventario"][oggetto] = quantita
        await interaction.response.send_message(f"✅ Impostato **{oggetto}** a **{quantita}x** nell'inventario di {utente.mention} (prima: {old_qty}x).")
    
    salva_database()
    
    await invia_log(
        "⚙️ Log Admin - Oggetto Impostato", 
        f"L'amministratore {interaction.user.mention} ha impostato **{oggetto}** a **{quantita}x** per {utente.mention} (prima: {old_qty}x).", 
        discord.Color.blue()
    )

@bot.tree.command(name="vedi_inventario", description="[ADMIN] Vedi l'inventario dettagliato di qualsiasi giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore di cui vedere l'inventario"
)
async def vedi_inventario(interaction: discord.Interaction, utente: discord.User):
    target_id = str(utente.id)
    controlla_utente(target_id)
    
    inv = database[target_id]["inventario"]
    
    embed = discord.Embed(
        title=f"🎒 Inventario di {utente.display_name}",
        description=f"**ID:** {utente.id}\n**Lavoro:** {database[target_id].get('lavoro', 'N/D')}",
        color=discord.Color.blue()
    )
    
    if inv:
        corpo = ""
        for item, qta in sorted(inv.items()):
            corpo += f"• **{item.capitalize()}**: {qta} unità\n"
        embed.add_field(name="📦 Oggetti", value=corpo, inline=False)
        embed.set_footer(text=f"Totale oggetti: {sum(inv.values())} | Tipi diversi: {len(inv)}")
    else:
        embed.add_field(name="📦 Oggetti", value="*Inventario completamente vuoto*", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="dai_soldi", description="[ADMIN] Aggiunge denaro al contante di un giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore che riceverà i soldi",
    importo="Quantità di denaro da aggiungere"
)
async def dai_soldi(interaction: discord.Interaction, utente: discord.User, importo: int):
    target_id = str(utente.id)
    controlla_utente(target_id)
    val = database["SETTINGS"]["valuta"]
    
    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
        return
    
    database[target_id]["contanti"] += importo
    salva_database()
    
    await interaction.response.send_message(f"💸 Aggiunto **{importo}{val}** ai contanti di {utente.mention}.")
    
    await invia_log(
        "💰 Log Admin - Soldi Aggiunti", 
        f"L'amministratore {interaction.user.mention} ha aggiunto **{importo}{val}** ai contanti di {utente.mention}.", 
        discord.Color.green()
    )

@bot.tree.command(name="dai_soldi_banca", description="[ADMIN] Aggiunge denaro al conto bancario di un giocatore")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    utente="Il giocatore che riceverà i soldi",
    importo="Quantità di denaro da aggiungere in banca"
)
async def dai_soldi_banca(interaction: discord.Interaction, utente: discord.User, importo: int):
    target_id = str(utente.id)
    controlla_utente(target_id)
    val = database["SETTINGS"]["valuta"]
    
    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
        return
    
    database[target_id]["banca"] += importo
    salva_database()
    
    await interaction.response.send_message(f"🏦 Aggiunto **{importo}{val}** al conto bancario di {utente.mention}.")
    
    await invia_log(
        "💰 Log Admin - Soldi Banca Aggiunti", 
        f"L'amministratore {interaction.user.mention} ha aggiunto **{importo}{val}** alla banca di {utente.mention}.", 
        discord.Color.green()
    )

# ==========================================
# 12. TELEFONO & SOCIAL
# ==========================================

@bot.tree.command(name="anonimo", description="Invia un messaggio anonimo nella chat oscura")
async def anonimo(interaction: discord.Interaction, messaggio: str):
    embed = discord.Embed(
        title="🥷 Messaggio Anonimo",
        description=f"« {messaggio} »",
        color=discord.Color.default()
    )
    await interaction.response.send_message("Inviato anonimamente.", ephemeral=True)
    await interaction.channel.send(embed=embed)
    
    await invia_log(
        "🥷 Log Chat Oscura (Anonimo)", 
        f"L'utente {interaction.user.mention} (`{interaction.user.id}`) ha inviato in chat l'anonimo:\n« *{messaggio}* »", 
        discord.Color.dark_gray()
    )

@bot.tree.command(name="twitter", description="Posta un tweet sul canale social")
async def twitter(interaction: discord.Interaction, messaggio: str):
    embed = discord.Embed(
        title="🐦 Twitter RP",
        description=f"**@{interaction.user.display_name}**\n\n{messaggio}",
        color=discord.Color.from_rgb(29, 161, 242)
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await interaction.response.send_message("Tweet pubblicato!", ephemeral=True)
    await interaction.channel.send(embed=embed)

@bot.tree.command(name="chiama", description="Invia un alert di chiamata sul telefono di un utente")
async def chiama(interaction: discord.Interaction, utente: discord.User):
    embed = discord.Embed(
        title="📱 Chiamata in Entrata",
        description=f"📞 {interaction.user.mention} ti sta chiamando sul telefono di Los Santos!\nEntra in un canale vocale per rispondergli.",
        color=discord.Color.green()
    )
    try:
        await utente.send(embed=embed)
        await interaction.response.send_message(f"✅ Inviata richiesta di chiamata a {utente.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Impossibile inviare la chiamata a {utente.mention} (DM chiusi).", ephemeral=True)

# ==========================================
# 13. SISTEMA SMS
# ==========================================

@bot.tree.command(name="sms", description="Invia un SMS a un giocatore")
@app_commands.describe(
    destinatario="Chi riceverà l'SMS",
    messaggio="Il testo del messaggio"
)
async def sms(interaction: discord.Interaction, destinatario: discord.User, messaggio: str):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    target_id = str(destinatario.id)
    controlla_utente(target_id)
    
    if destinatario.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi inviare SMS a te stesso!", ephemeral=True)
        return
    
    if len(messaggio) > 500:
        await interaction.response.send_message("❌ Il messaggio è troppo lungo (max 500 caratteri).", ephemeral=True)
        return
    
    if "telefono" not in database[user_id]["inventario"] or database[user_id]["inventario"]["telefono"] <= 0:
        await interaction.response.send_message("❌ Non hai un telefono per inviare SMS! Compra un telefono al negozio.", ephemeral=True)
        return
    
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    sms_data = {
        "mittente_id": user_id,
        "mittente_nome": interaction.user.display_name,
        "messaggio": messaggio,
        "timestamp": timestamp
    }
    
    database[target_id]["sms_ricevuti"].append(sms_data)
    salva_database()
    
    embed = discord.Embed(
        title="📱 SMS Inviato",
        description=f"✉️ {interaction.user.mention} ha inviato un SMS a {destinatario.mention}.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)
    
    try:
        notifica_embed = discord.Embed(
            title="📲 Nuovo SMS Ricevuto",
            description=f"**Da:** {interaction.user.mention}\n"
                       f"**Ora:** {timestamp}\n"
                       f"**Messaggio:** {messaggio}\n\n"
                       f"Usa `/leggi_sms` per vedere tutti i tuoi messaggi.",
            color=discord.Color.green()
        )
        await destinatario.send(embed=notifica_embed)
    except discord.Forbidden:
        pass
    
    await invia_log(
        "📱 Log SMS", 
        f"L'utente {interaction.user.mention} ha inviato un SMS a {destinatario.mention}:\n« {messaggio} »", 
        discord.Color.blue()
    )

@bot.tree.command(name="leggi_sms", description="Leggi tutti gli SMS ricevuti")
async def leggi_sms(interaction: discord.Interaction, pagina: int = 1):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    sms_list = database[user_id]["sms_ricevuti"]
    
    if not sms_list:
        await interaction.response.send_message("📭 La tua casella SMS è vuota.", ephemeral=True)
        return
    
    sms_list_ordinati = list(reversed(sms_list))
    sms_per_pagina = 5
    total_pages = math.ceil(len(sms_list_ordinati) / sms_per_pagina)
    
    if pagina < 1 or pagina > total_pages:
        await interaction.response.send_message(f"❌ Pagina non valida. Pagine disponibili: 1-{total_pages}", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"📱 I tuoi SMS Ricevuti (Pagina {pagina}/{total_pages})",
        color=discord.Color.blue()
    )
    
    start_idx = (pagina - 1) * sms_per_pagina
    end_idx = min(start_idx + sms_per_pagina, len(sms_list_ordinati))
    
    for sms in sms_list_ordinati[start_idx:end_idx]:
        embed.add_field(
            name=f"📩 Da: {sms['mittente_nome']} • {sms['timestamp']}",
            value=f"« {sms['messaggio']} »",
            inline=False
        )
    
    embed.set_footer(text=f"Usa /leggi_sms pagina:<numero> • /cancella_sms per svuotare la casella")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="cancella_sms", description="Svuota la tua casella SMS")
async def cancella_sms(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    num_sms = len(database[user_id]["sms_ricevuti"])
    database[user_id]["sms_ricevuti"] = []
    salva_database()
    
    await interaction.response.send_message(f"🗑️ Hai cancellato **{num_sms}** SMS dalla tua casella.", ephemeral=True)

# ==========================================
# 14. SISTEMA AZIONI RP
# ==========================================

@bot.tree.command(name="azione", description="Esegui un'azione RP visibile a tutti nel canale")
@app_commands.describe(
    azione="Descrivi l'azione che stai compiendo",
    target="Giocatore coinvolto nell'azione (opzionale)"
)
async def azione(interaction: discord.Interaction, azione: str, target: discord.User = None):
    user_id = str(interaction.user.id)
    controlla_utente(user_id)
    
    if len(azione) > 1000:
        await interaction.response.send_message("❌ L'azione è troppo lunga (max 1000 caratteri).", ephemeral=True)
        return
    
    if len(azione) < 3:
        await interaction.response.send_message("❌ L'azione è troppo corta (min 3 caratteri).", ephemeral=True)
        return
    
    if target and target.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi fare un'azione su te stesso! Usa /azione senza target.", ephemeral=True)
        return
    
    if target:
        descrizione = f"🎭 **{interaction.user.mention}** *{azione}* **{target.mention}**"
    else:
        descrizione = f"🎭 **{interaction.user.mention}** *{azione}*"
    
    embed = discord.Embed(
        title="🎬 Azione Roleplay",
        description=descrizione,
        color=discord.Color.purple()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text=f"ID Azione: {interaction.user.id} • Usa /azione per fare un'azione")
    
    await interaction.response.send_message(embed=embed)
    
    await invia_log(
        "🎭 Log Azione RP", 
        f"L'utente {interaction.user.mention} ha eseguito un'azione{' su ' + target.mention if target else ''}:\n*{azione}*", 
        discord.Color.purple()
    )

@bot.tree.command(name="azione_master", description="[ADMIN] Esegui un'azione RP come Game Master (Narratore)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    azione="Descrivi l'azione/scena che accade nel mondo",
    target="Giocatore coinvolto (opzionale)"
)
async def azione_master(interaction: discord.Interaction, azione: str, target: discord.User = None):
    if len(azione) > 1500:
        await interaction.response.send_message("❌ L'azione è troppo lunga (max 1500 caratteri).", ephemeral=True)
        return
    
    if len(azione) < 5:
        await interaction.response.send_message("❌ L'azione è troppo corta (min 5 caratteri).", ephemeral=True)
        return
    
    if target:
        descrizione = f"📖 **{azione}** *({target.mention})*"
    else:
        descrizione = f"📖 **{azione}**"
    
    embed = discord.Embed(
        title="📜 Azione del Game Master",
        description=descrizione,
        color=discord.Color.dark_gold()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text="Azione Narratore • Game Master")
    
    await interaction.response.send_message(embed=embed)
    
    await invia_log(
        "📜 Log Azione GM", 
        f"Il Game Master {interaction.user.mention} ha narrato un'azione{' su ' + target.mention if target else ''}:\n*{azione}*", 
        discord.Color.dark_gold()
    )

# ==========================================
# 15. GESTIONE STATO SESSIONE & UTILITY RP
# ==========================================

@bot.tree.command(name="rpon", description="🟢 Attiva la sessione RP - Apre la città al Roleplay")
async def rpon(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌆 MIDNIGHT STREET RP 3.0",
        description="**La sessione di Roleplay è ora APERTA!**\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "🏙️ **STATO SERVER**\n"
                   "```diff\n"
                   "+ SERVER ONLINE\n"
                   "+ RP ATTIVO\n"
                   "+ ACCESSO CONSENTITO\n"
                   "```\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "📜 **REGOLAMENTO ATTIVO**\n"
                   "• Rispettare il regolamento IC/OOC\n"
                   "• Mantenere un comportamento consono al RP\n"
                   "• Evitare metagaming e powergaming\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "🚗 **BUON DIVERTIMENTO A TUTTI!**\n"
                   "*Che il Roleplay abbia inizio!*",
        color=discord.Color.green()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text="Midnight Street RP • Sessione Attiva")
    
    await interaction.response.send_message(content="# 🌟 RP ON @everyone @here", embed=embed)

@bot.tree.command(name="rpoff", description="🔴 Disattiva la sessione RP - Chiude la città")
async def rpoff(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌃 MIDNIGHT STREET RP 3.0",
        description="**La sessione di Roleplay è stata CHIUSA!**\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "🏙️ **STATO SERVER**\n"
                   "```diff\n"
                   "- SERVER IN PAUSA\n"
                   "- RP DISATTIVATO\n"
                   "- ACCESSO NEGATO\n"
                   "```\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "📜 **AVVISI IMPORTANTI**\n"
                   "• Disconnettersi dalla città\n"
                   "• Salvare il proprio equipaggiamento\n"
                   "• Attendere la prossima sessione\n\n"
                   "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                   "🌙 **GRAZIE A TUTTI I CITTADINI!**\n"
                   "*Ci rivediamo alla prossima sessione!*",
        color=discord.Color.red()
    )
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    embed.set_footer(text="Midnight Street RP • Sessione Terminata")
    
    await interaction.response.send_message(content="# 🌙 RP OFF @everyone @here", embed=embed)

# ==========================================
# GESTIONE ERRORI GLOBALE
# ==========================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando!", ephemeral=True)
    elif isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Comando in cooldown! Riprova tra {error.retry_after:.1f} secondi.", ephemeral=True)
    else:
        print(f"Errore comando '{interaction.command.name}': {error}")
        try:
            await interaction.response.send_message("❌ Si è verificato un errore imprevisto. Contatta un amministratore.", ephemeral=True)
        except:
            pass

# ==========================================
# AVVIO BOT & CONFIGURAZIONE FINALE
# ==========================================
import os

LOG_WEBHOOK_URL = os.getenv('WEBHOOK_URL')

bot.run(os.getenv('TOKEN'))