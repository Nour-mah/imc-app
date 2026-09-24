import os
import mysql.connector
from flask import Flask, jsonify, request
from mysql.connector import Error as MySQLError

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "imcuser"),
    "password": os.getenv("DB_PASSWORD", "imcpass"),
    "database": os.getenv("DB_NAME", "imcdb"),
}


def get_connection():
    """Ouvre une connexion a MySQL. Leve MySQLError si la base est injoignable."""
    return mysql.connector.connect(**DB_CONFIG)

app = Flask(__name__)

def classifier_imc(imc):
        """Renvoie la categorie OMS correspondant a un IMC."""
        if imc < 18.5:
            return "Insuffisance ponderale"
        if imc < 25:
            return "Corpulence normale"
        if imc < 30:
            return "Surpoids"
        if imc < 35:
            return "Obesite moderee (classe I)"
        if imc < 40:
            return "Obesite severe (classe II)"
        return "Obesite morbide (classe III)"

@app.route("/health")
def health():
    return jsonify({"service": "imc-api", "statut": "ok"})

@app.route("/api/imc", methods=["POST"])
def calculer_imc():

    # silent=True : get_json renvoie None au lieu de lever une exception quand
    # le corps n'est pas du JSON valide. On garde ainsi la main sur la reponse,
    # qui reste au format JSON comme toutes les autres.
    donnees = request.get_json(silent=True)
    if donnees is None:
        return jsonify({"error": "Requete invalide, JSON attendu"}), 400

    # Sans ce controle, donnees["poids"] leverait une KeyError -> erreur 500,
    # alors que la faute revient au client.
    if "poids" not in donnees or "taille" not in donnees:
        return jsonify({"error": "Requete invalide, poids et taille requis"}), 400

    try:
        poids = float(donnees["poids"])
        taille = float(donnees["taille"])
    except (TypeError, ValueError):
        return jsonify({"error": "Poids et taille doivent etre des nombres"}), 400

    # On verifie que les valeurs sont valides
    if taille <= 0:
        return jsonify({"error": "Taille doit etre superieure a 0"}), 400
    if poids <= 0:
        return jsonify({"error": "Poids doit etre superieur a 0"}), 400
    if taille > 3:
        return jsonify({"error": "La taille doit etre en metres, pas en centimetres"}), 400
    
    imc = round(poids / (taille ** 2), 2)

    categorie = classifier_imc(imc)

    resultat = {"poids": poids, "taille": taille, "imc": imc, "categorie": categorie}

    try:
        conn = get_connection()
        curseur = conn.cursor()
        curseur.execute(
            "INSERT INTO mesures (poids, taille, imc, categorie) VALUES (%s, %s, %s, %s)",
            (poids, taille, imc, categorie),
        )
        conn.commit()
        resultat["id"] = curseur.lastrowid
        curseur.close()
        conn.close()
    except MySQLError as err:
        return jsonify({"error": f"Base de donnees indisponible : {err}"}), 503

    return jsonify(resultat), 201

@app.route("/api/historique")
def historique():
    try:
        conn = get_connection()
        curseur = conn.cursor(dictionary=True)
        curseur.execute(
            "SELECT id, poids, taille, imc, categorie, date_creation "
            "FROM mesures ORDER BY id DESC LIMIT 20"
        )
        lignes = curseur.fetchall()
        curseur.close()
        conn.close()
    except MySQLError as err:
        return jsonify({"error": f"Base de donnees indisponible : {err}"}), 503

    mesures = [{
        "id": ligne["id"],
        "poids": float(ligne["poids"]),
        "taille": float(ligne["taille"]),
        "imc": float(ligne["imc"]),
        "categorie": ligne["categorie"],
        "date": ligne["date_creation"].strftime("%Y-%m-%d %H:%M:%S"),
    } for ligne in lignes]

    return jsonify({"total": len(mesures), "mesures": mesures})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
