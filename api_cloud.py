from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import datetime
import random

# Initialisation de l'application
app = FastAPI(title="HandPay Cloud API", version="1.0.0")

# --- MODÈLES DE DONNÉES (Ce qu'on attend de l'appli mobile) ---
class InscriptionModel(BaseModel):
    nom: str
    email: str
    password: str
    adresse: str
    carte: str
    signature_geo: list  # La liste biométrique
    
class PaiementModel(BaseModel):
    client_nom: str
    marchand_nom: str
    montant: float

class LoginModel(BaseModel):
    identifiant: str
    password: str

# --- GESTION BASE DE DONNÉES ---
def get_db_connection():
    conn = sqlite3.connect('handpay_cloud.db')
    conn.row_factory = sqlite3.Row # Permet d'accéder aux colonnes par nom
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Table Clients (Avec Biométrie stockée sous forme de texte)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, 
                    nom TEXT UNIQUE, 
                    email TEXT, 
                    password TEXT, 
                    adresse TEXT, 
                    last_4_digits TEXT,
                    signature_bio TEXT
                )''')
    # Table Transactions
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY, 
                    de_qui TEXT, 
                    a_qui TEXT, 
                    montant REAL, 
                    date TEXT, 
                    status TEXT
                )''')
    conn.commit()
    conn.close()

# On lance la DB au démarrage
init_db()

# ==================== LES ROUTES (ENDPOINTS) ====================

@app.get("/")
def home():
    return {"message": "Serveur HandPay en ligne 🟢"}

@app.post("/inscription")
def inscription(data: InscriptionModel):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # On garde que les 4 derniers chiffres de la carte pour sécu
        last_4 = data.carte[-4:]
        # On stocke la signature biométrique en string
        sig_str = str(data.signature_geo)
        
        c.execute("INSERT INTO users (nom, email, password, adresse, last_4_digits, signature_bio) VALUES (?, ?, ?, ?, ?, ?)",
                  (data.nom, data.email, data.password, data.adresse, last_4, sig_str))
        conn.commit()
        return {"status": "succes", "message": f"Compte créé pour {data.nom}"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur existe déjà")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/login")
def login(data: LoginModel):
    conn = get_db_connection()
    c = conn.cursor()
    # Recherche par Nom ou Email
    c.execute("SELECT nom, last_4_digits FROM users WHERE (nom=? OR email=?) AND password=?", 
              (data.identifiant, data.identifiant, data.password))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {"status": "succes", "nom": user['nom'], "carte": user['last_4_digits']}
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

@app.get("/profil/{nom}")
def get_profil(nom: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT email, adresse, last_4_digits FROM users WHERE nom=?", (nom,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {
            "email": user['email'],
            "adresse": user['adresse'],
            "carte": user['last_4_digits']
        }
    else:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

@app.post("/paiement")
def effectuer_paiement(data: PaiementModel):
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Vérifier le client
    c.execute("SELECT last_4_digits FROM users WHERE nom=?", (data.client_nom,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Client inconnu pour le paiement")
    
    # 2. Exécuter la transaction (Simulation Stripe)
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "SUCCÈS"
    
    c.execute("INSERT INTO transactions (de_qui, a_qui, montant, date, status) VALUES (?, ?, ?, ?, ?)",
              (data.client_nom, data.marchand_nom, data.montant, date_now, status))
    conn.commit()
    conn.close()
    
    return {"status": "validé", "message": f"Paiement de {data.montant}€ accepté"}

@app.get("/historique/{nom}")
def historique(nom: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT date, a_qui, montant FROM transactions WHERE de_qui=? ORDER BY id DESC", (nom,))
    rows = c.fetchall()
    conn.close()
    
    return [{"date": r['date'], "marchand": r['a_qui'], "montant": r['montant']} for r in rows]