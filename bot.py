import os
import time
import asyncio
import requests
import zvec
import json
from twikit import Client
from sentence_transformers import SentenceTransformer

# --- 1. CONFIGURATION ---
# On récupère tout ce qu'on a mis dans le .env
USERNAME = os.getenv("TWITTER_USER")
PHONE = os.getenv("TWITTER_PHONE")
PASSWORD = os.getenv("TWITTER_PASS")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Initialisation des outils
client = Client('en-US')
model = SentenceTransformer('all-MiniLM-L6-v2')
DEJA_ENVOYES = set()

# --- 2. INITIALISATION ZVEC ---
print("🗄️ Accès à la base Zvec...", flush=True)
schema = zvec.CollectionSchema(
    name="dofus_finder",
    vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 384)
)

try:
    # On tente de créer la base (premier lancement)
    collection = zvec.create_and_open(path="./zvec_data", schema=schema)
    
    # On nourrit l'IA avec des exemples Dofus au premier démarrage
    print("🐉 Programmation du cerveau : Mode Dofus...", flush=True)
    exemples = [
        # --- LES VRAIS CONCOURS (Data issue de tes tweets) ---
        ("Faire gagner un Caskwitteur ! RT + Follow. TAS bientôt.", "valide_1"),
        ("GIVEAWAY CASKWITER ! RT FOLLOW para participar. Suerte aventureros.", "valide_2"),
        ("Concours : 1 CASQWITTER à gagner. Follow + RT + Tag un pote !", "valide_3"),
        ("Tenter de gagner la coiffe d'apparat Caskwitteur, RT + Follow.", "valide_4"),
        ("Giveaway Bouclier Hitche sur ma chaîne Twitch ce soir !", "valide_5"),
        
        # --- LE BRUIT À IGNORER (Pour affiner l'IA) ---
        ("Cherche groupe pour donjon RN ou farm xp", "hors_sujet_jeu"),
        ("Le patch note de Dofus 3.0 est en ligne sur le forum", "hors_sujet_news"),
        ("Bon réveillon et joyeux Nowel à toute la guilde", "hors_sujet_social"),
        ("Vos commandes Uber Eats a -70% Panier ubereats promo", "arnaque_uber"),
        ("Vends kamas serveur Draconiros prix cassé", "arnaque_kamas"),
        ("Airdrop crypto monnaie gratuit $SOL $ETH", "arnaque_crypto"),
        ("Je cherche un groupe pour donjon ou xp", "hors_sujet")
    ]
        
    docs = []
    for i, (txt, label) in enumerate(exemples):
        vec = model.encode(txt).tolist()
        docs.append(zvec.Doc(id=f"{label}_{i}", vectors={"embedding": vec}))
    collection.insert(docs)

except Exception:
    # Si elle existe déjà, on l'ouvre simplement
    collection = zvec.open(path="./zvec_data")

print("✅ Cerveau Zvec opérationnel.", flush=True)

# --- 3. FONCTIONS ---

import json

async def login():
    # 1. On essaie d'abord de lire la variable d'environnement (pour le VPS/Coolify)
    cookies_env = os.getenv("COOKIES")
    
    try:
        if cookies_env:
            print("🍪 Chargement des cookies via variable d'environnement...", flush=True)
            cookies_list = json.loads(cookies_env)
        elif os.path.exists('cookies.json'):
            # 2. Si pas de variable, on cherche le fichier (pour ton test local sur Mac)
            print("🍪 Chargement des cookies via cookies.json...", flush=True)
            with open('cookies.json', 'r') as f:
                cookies_list = json.load(f)
        else:
            print("❌ ERREUR : Aucun cookie trouvé (Variable ENV ou fichier) !", flush=True)
            return

        # Transformation en dictionnaire pour Twikit
        cookies_dict = {c['name']: c['value'] for c in cookies_list}
        client.set_cookies(cookies_dict)
        print("✅ Session chargée avec succès !", flush=True)
        
    except Exception as e:
        print(f"❌ Erreur lors du chargement des cookies : {e}", flush=True)
        
def envoyer_discord(tweet_text, tweet_link):
    """Envoie la notification sur ton serveur"""
    payload = {
        "content": f"🐲 **NOUVEAU CONCOURS DOFUS DÉTECTÉ !**\n\n{tweet_text}\n\n🔗 {tweet_link}"
    }
    requests.post(WEBHOOK_URL, json=payload)

async def analyser_et_notifier(tweet):
    """Passe le tweet dans l'IA et décide si on l'envoie"""
    if tweet.id in DEJA_ENVOYES:
        return

    # On transforme le tweet en vecteur
    vecteur = model.encode(tweet.text).tolist()
    
    # On demande à Zvec si ça ressemble à un de nos bons exemples
    results = collection.query(zvec.VectorQuery("embedding", vector=vecteur), topk=1)
    
    if results:
        match = results[0]
        # On ne garde que si le score est bon et que c'est un exemple "valide"
        if "valide" in match.id and match.score > 0.50:
            link = f"https://x.com/user/status/{tweet.id}"
            print(f"🎯 MATCH ({match.score:.2f}) : {tweet.text[:50]}...", flush=True)
            envoyer_discord(tweet.text, link)
            DEJA_ENVOYES.add(tweet.id)
        else :
            print(f"☁️ Ignoré (Score: {match.score:.2f} | Id: {match.id})", flush=True)

async def chercher_tweets():
    """Lance la recherche sur X"""
    print(f"\n--- 🛰️ SCAN TWITTER ({time.strftime('%H:%M:%S')}) ---", flush=True)
    try:
        # Le "-filter:replies" dit à Twitter : "Ne me montre pas les réponses"
        query = 'Dofus (concours OR giveaway OR gagner OR "à gagner") -filter:replies'
        tweets = await client.search_tweet(query, 'Latest')
        
        print(f"📥 {len(tweets)} tweets récupérés. Analyse IA en cours...", flush=True)
        for tweet in tweets:

            if tweet.in_reply_to:
                continue
                
            if tweet.id in DEJA_ENVOYES: 
                continue

            await analyser_et_notifier(tweet)
            
    except Exception as e:
        print(f"⚠️ Erreur Scraping : {e}", flush=True)

# --- 4. BOUCLE PRINCIPALE ---
async def main():
    await login()
    while True:
        await chercher_tweets()
        # On attend 10 minutes entre chaque scan pour rester discret
        print("😴 Pause 10 min...", flush=True)
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())