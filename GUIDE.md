# Guide pas à pas — Application Cloud de calcul de l'IMC

**Pour quelqu'un qui n'a jamais écrit d'API ni utilisé Docker.**

Chaque ligne de code est donnée et expliquée. Vous tapez, vous exécutez, vous
observez, et seulement ensuite on ajoute la brique suivante. Ne sautez pas les
exécutions : c'est en voyant le résultat que ça rentre.

---

# Où j'en suis

> **➡️ ÉTAPE EN COURS : v5 — `docker-compose.yml`.**
> La v4 est terminée : les trois services tournent en conteneurs sur le réseau
> `imc-net`, plus rien ne dépend de votre Mac. Reste à remplacer les cinq
> commandes `docker run` par un seul fichier.

| Étape | État |
|---|---|
| 1.1 Environnement Python et Flask | ✅ |
| 1.2 Premier serveur (6 lignes) | ✅ |
| 1.3 Réponse en JSON | ✅ |
| 1.4 Calcul de l'IMC (`POST /api/imc`) | ✅ |
| 1.5 Classification OMS | ✅ |
| 1.6 Validation des entrées | ✅ 10 tests sur 10 |
| 2.1 Historique en mémoire (`GET /api/historique`) | ✅ |
| 2.2 Constat de la perte au redémarrage | ✅ |
| 2.3 MySQL dans un conteneur | ✅ `mysql-tp` tourne |
| 2.4 Connecteur `mysql-connector-python` | ✅ installé |
| 2.5 Créer la table `mesures` | ✅ 6 colonnes |
| 2.6 Brancher l'API sur la base | ✅ `INSERT` et `SELECT` fonctionnels |
| 3.1 Page HTML | ✅ |
| 3.2 JavaScript et `fetch` | ✅ |
| 3.3 Le mur CORS, constaté | ✅ |
| 3.4 nginx en proxy inverse | ✅ conteneur `nginx-tp`, port 8080 |
| 4.1 `requirements.txt` assaini, `.dockerignore` | ✅ |
| 4.2 Image de l'API | ✅ `imc-api:1.0`, 301 Mo |
| 4.3 Réseau `imc-net` et conteneur `api` | ✅ `DB_HOST=mysql-tp` |
| 4.4 Image du frontend | ✅ `imc-frontend:1.0`, 76 Mo |
| 4.5 Pile entièrement conteneurisée | ✅ Flask local arrêté |
| **5.1 à 5.5 `docker-compose`, volumes, healthchecks** | **➡️ à faire** |

## L'état de votre environnement

| Élément | Détail |
|---|---|
| Dossier du projet | `TP1/imc-app` |
| Environnement Python | `.venv` — activez-le avec `source .venv/bin/activate` |
| Serveur Flask | port **5001**, lancé détaché, journaux dans `serveur.log` |
| MySQL | conteneur `mysql-tp`, port **3306**, base `imcdb`, compte `imcuser` / `imcpass` |
| Corrigé de secours | dossier voisin `TP1/IMCApp`, à ne consulter qu'en dernier recours |

## Les commandes du quotidien

Relancer le serveur après une modification :

```bash
lsof -ti tcp:5001 | xargs kill -9 2>/dev/null; nohup python api/app.py > serveur.log 2>&1 < /dev/null & sleep 3
```

Voir ce que dit le serveur :

```bash
tail -20 serveur.log
```

Interroger la base :

```bash
docker exec mysql-tp mysql -uimcuser -pimcpass imcdb -e "SELECT * FROM mesures;"
```

---

## Ce qu'on va construire, et pourquoi

Le TP demande une application « cloud » qui calcule l'IMC. Concrètement, trois
morceaux qui tournent chacun dans son propre conteneur :

```
   Votre navigateur
         │  (1) demande la page
         ▼
   ┌───────────────┐
   │   FRONTEND    │   la page web : formulaire, affichage
   │    (nginx)    │
   └───────┬───────┘
           │  (2) envoie poids et taille
           ▼
   ┌───────────────┐
   │      API      │   le calcul, les règles, la validation
   │    (Flask)    │
   └───────┬───────┘
           │  (3) enregistre et relit
           ▼
   ┌───────────────┐
   │     MYSQL     │   la mémoire de l'application
   └───────────────┘
```

**Pourquoi séparer en trois ?** Parce qu'on peut alors remplacer, redémarrer
ou dupliquer chaque morceau sans toucher aux autres. C'est tout le sujet du
cours : une application d'infonuagique est faite de services indépendants.

On construit dans cet ordre, et **chaque version doit marcher avant la
suivante** :

| Version | Contenu | Pourquoi maintenant |
|---|---|---|
| v1 | l'API seule, le calcul en mémoire | comprendre ce qu'est une API |
| v2 | + MySQL | les données doivent survivre |
| v3 | + la page web | l'utilisateur ne tape pas de commandes |
| v4 | + les `Dockerfile` | rendre tout ça reproductible |
| v5 | + `docker-compose` | tout lancer d'une seule commande |

---

## Le vocabulaire minimal

Cinq notions suffisent pour démarrer.

**Client et serveur.** Un serveur est un programme qui attend des demandes. Un
client en envoie. Votre navigateur est un client ; le programme Python que vous
allez écrire sera un serveur.

**HTTP.** La langue dans laquelle ils se parlent. Une demande (*requête*)
contient un **verbe** et un **chemin** :

- `GET /health` — « donne-moi l'état du service ». `GET` sert à lire.
- `POST /api/imc` — « voici des données, traite-les ». `POST` sert à envoyer.

**Code de statut.** Chaque réponse porte un nombre qui dit comment ça s'est
passé : `200` c'est bon, `201` créé avec succès, `400` la demande est mal
formée (faute du client), `404` ce chemin n'existe pas, `500` le serveur a
planté, `503` un service dont il dépend est indisponible.

**JSON.** Le format d'échange. Du texte qui ressemble à un dictionnaire
Python : `{"poids": 70, "taille": 1.75}`.

**Port.** Une machine a une seule adresse mais des milliers de portes
numérotées. Votre API écoutera sur le port `5001`, MySQL sur le `3306`. Deux
programmes ne peuvent pas écouter le même port en même temps.

**Route.** L'association entre un chemin (`/api/imc`) et une fonction Python.
Écrire une API, c'est essentiellement écrire des routes.

---

# v1 — Une API qui calcule l'IMC

## 1.1 — Préparer l'environnement Python

Placez-vous dans le dossier du projet :

```bash
cd "$HOME/Desktop/Documents de cours/CI3/Semestre 1 - UQAC/8CLD876 - Conception et architecture des systèmes d'infonuagique/TP/TP1/imc-app"
```

Créez un **environnement virtuel** et installez Flask :

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install Flask==3.0.3
```

**Ce que fait cette commande :**

- `python3 -m venv .venv` crée un dossier `.venv` contenant une installation
  Python isolée. Les bibliothèques que vous installerez ensuite iront dedans,
  et pas dans votre système.
- `source .venv/bin/activate` l'active. Votre invite de commande commence
  alors par `(.venv)` : c'est le signe que vous travaillez dans cet
  environnement isolé.
- `pip install Flask==3.0.3` installe Flask, la bibliothèque qui permet
  d'écrire un serveur web en Python. Le `==` fige la version.

**Pourquoi s'embêter avec ça ?** Parce que sans isolation, deux projets qui
ont besoin de versions différentes d'une même bibliothèque se gênent. C'est
la version « pour Python » de l'idée que Docker appliquera au système entier.

---

## 1.2 — Votre premier serveur (6 lignes)

Créez le fichier `api/app.py` et tapez **exactement** ceci :

```python
from flask import Flask

app = Flask(__name__)

@app.route("/health")
def health():
    return "L'API est vivante"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
```

### Ligne par ligne

| Code | Rôle |
|---|---|
| `from flask import Flask` | importe la classe principale de Flask |
| `app = Flask(__name__)` | crée l'application. `__name__` permet à Flask de savoir où il se trouve pour retrouver ses fichiers |
| `@app.route("/health")` | **le décorateur** : il dit « quand une requête arrive sur `/health`, appelle la fonction juste en dessous » |
| `def health():` | la fonction appelée. Son nom n'a pas d'importance technique, seul le chemin compte |
| `return "..."` | ce que le serveur renvoie au client |
| `if __name__ == "__main__":` | ce bloc ne s'exécute que si on lance le fichier directement |
| `app.run(...)` | démarre le serveur et **bloque** : le programme ne se termine pas, il attend des requêtes |

**`host="0.0.0.0"` :** écoute sur toutes les interfaces réseau de la machine.
Avec `127.0.0.1`, seul le programme lui-même pourrait se joindre. Ça ne change
rien aujourd'hui, mais ce sera capital quand l'API tournera dans un conteneur.

**`debug=True` :** redémarre automatiquement le serveur à chaque modification
du fichier, et affiche les erreurs en détail. Pratique pour développer,
**à ne jamais utiliser en production** : le débogueur permet d'exécuter du code
à distance.

### Lancez-le

```bash
python api/app.py
```

Le terminal affiche `Running on http://0.0.0.0:5001` puis **reste bloqué** :
c'est normal, le serveur tourne. Ouvrez <http://localhost:5001/health> dans
votre navigateur : vous devez lire « L'API est vivante ».

Essayez aussi <http://localhost:5001/nimporte-quoi> : vous obtenez une page
`404 Not Found`. Flask ne connaît que les chemins que vous avez déclarés.

Arrêtez le serveur avec `Ctrl+C`.

**Vous venez d'écrire un serveur web.** Tout le reste n'est que de
l'enrichissement.

---

## 1.3 — Répondre en JSON

Du texte brut, un programme ne sait pas quoi en faire. Une API renvoie du
**JSON**. Modifiez `api/app.py` :

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"service": "imc-api", "statut": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
```

`jsonify` transforme un dictionnaire Python en JSON et pose la bonne
en-tête `Content-Type: application/json`, qui indique au client comment lire
la réponse.

Relancez (`python api/app.py`) et, dans un **second onglet de terminal** :

```bash
curl -s http://localhost:5001/health
```

`curl` est un client HTTP en ligne de commande : il fait ce que fait votre
navigateur, mais sans interface. Vous devez voir :

```json
{"service":"imc-api","statut":"ok"}
```

---

## 1.4 — Le calcul de l'IMC

Maintenant la vraie fonctionnalité. Ajoutez `request` à l'import et écrivez
une deuxième route :

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"service": "imc-api", "statut": "ok"})

@app.route("/api/imc", methods=["POST"])
def calculer_imc():
    donnees = request.get_json()
    poids = float(donnees["poids"])
    taille = float(donnees["taille"])

    imc = round(poids / (taille ** 2), 2)

    return jsonify({"poids": poids, "taille": taille, "imc": imc}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
```

### Ce qui est nouveau

- **`methods=["POST"]`** : cette route n'accepte que le verbe `POST`. Sans ce
  paramètre, Flask n'autorise que `GET`. C'est cohérent : le client **envoie**
  des données.
- **`request.get_json()`** : `request` est un objet global fourni par Flask qui
  représente la requête en cours. `get_json()` lit son corps et le convertit
  en dictionnaire Python.
- **`taille ** 2`** : l'élévation au carré en Python. `taille * 2` serait une
  multiplication par deux — l'erreur classique.
- **`, 201`** : le code de statut renvoyé avec la réponse. `201 Created` est la
  convention quand une ressource a été créée.

### Testez

Relancez le serveur, puis dans l'autre onglet :

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":1.75}'
```

- `-X POST` choisit le verbe.
- `-H "Content-Type: application/json"` annonce qu'on envoie du JSON. Sans
  cet en-tête, `get_json()` renvoie `None` et le code plante.
- `-d '{...}'` est le corps de la requête.

Résultat attendu : `{"imc":22.86,"poids":70.0,"taille":1.75}`.

**Vérifiez le calcul à la main** : 70 ÷ (1,75 × 1,75) = 22,857… → 22,86. Votre
API calcule juste.

---

## 1.5 — Classer le résultat

Un nombre seul ne dit rien à un utilisateur. L'Organisation mondiale de la
santé définit des seuils. Ajoutez cette fonction **au-dessus** de vos routes :

```python
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
```

Puis utilisez-la dans la route, juste après le calcul :

```python
    categorie = classifier_imc(imc)

    return jsonify({
        "poids": poids,
        "taille": taille,
        "imc": imc,
        "categorie": categorie,
    }), 201
```

**Pourquoi une fonction séparée plutôt que le code dans la route ?**

1. La route s'occupe du web (lire la requête, renvoyer une réponse), la
   fonction s'occupe de la règle métier. Chaque chose à sa place.
2. Vous la réutiliserez en v2, pour reclasser les mesures venant de la base.
3. Elle se teste seule, sans lancer de serveur : `classifier_imc(22.86)`.

Notez l'absence de `else` : chaque `return` quitte la fonction, donc si on
arrive à la ligne suivante, c'est que la condition précédente était fausse.

Testez de nouveau avec la commande `curl` : vous devez voir apparaître
`"categorie":"Corpulence normale"`.

---

## 1.6 — À vous : la validation

C'est le premier morceau que vous écrivez seul. Ne le sautez pas : un serveur
qui fait confiance à ce qu'il reçoit est un serveur qui plante.

Essayez d'abord de casser votre API. Dans l'autre onglet :

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":0}'
```

Vous obtenez une page d'erreur `500 Internal Server Error` — une division par
zéro. Et avec `-d '{"poids":70}'`, une erreur de clé manquante. Dans les deux
cas, **c'est le client qui a mal fait**, mais votre serveur répond « c'est moi
qui ai planté ». C'est faux et ça n'aide personne.

### Ce que vous devez écrire

Au début de `calculer_imc`, avant le calcul, renvoyez une erreur `400` quand
les données ne conviennent pas. Le patron de réponse est toujours le même :

```python
    return jsonify({"erreur": "message explicite"}), 400
```

Les cas à traiter :

| Cas | Comment le détecter |
|---|---|
| Pas de JSON du tout | `request.get_json(silent=True)` renvoie `None` (`silent=True` évite que Flask lève une exception) |
| Champ manquant | `"poids" not in donnees` |
| Valeur non numérique | entourer les `float(...)` d'un `try / except (TypeError, ValueError)` |
| Poids aberrant | hors de l'intervalle 2 à 500 |
| Taille aberrante | hors de l'intervalle 0,5 à 2,5 — ce qui attrape aussi la taille saisie en centimètres, l'erreur la plus fréquente |

**Indice de structure :** un enchaînement de `if` qui font chacun un `return`
au plus tôt. Pas besoin de `else`, exactement comme dans `classifier_imc`.

### Vérifiez votre travail

Ces quatre commandes doivent toutes renvoyer un message d'erreur clair, et
plus jamais de page `500` :

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":0}'
```

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70}'
```

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":"abc","taille":1.75}'
```

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":175}'
```

Et celle-ci doit continuer à fonctionner :

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":1.75}'
```

---

## 1.7 — L'état final de votre validation

Votre route contrôle, dans cet ordre :

1. le corps est bien du JSON (`get_json(silent=True)` puis test à `None`) ;
2. les deux champs sont présents (sinon `donnees["poids"]` lèverait une
   `KeyError`, donc une erreur `500`) ;
3. les valeurs sont convertibles en nombres (`try` / `except`) ;
4. la taille et le poids sont strictement positifs ;
5. la taille ne dépasse pas 3 mètres.

**Sur cette dernière règle :** nous avons délibérément renoncé aux bornes
supérieures, sauf pour la taille. Plafonner un poids est arbitraire, et une
valeur aberrante reste calculable. La taille est un cas différent : saisie en
centimètres — l'erreur la plus fréquente — elle produirait une réponse
**fausse mais crédible**, un IMC proche de 0 assorti d'une catégorie
officielle. Une API doit refuser plutôt que de mentir. Le seuil de 3 mètres
plutôt que 2,5 garantit qu'aucune taille humaine réelle n'est rejetée.

### La batterie de tests de la v1

| Envoi | Attendu |
|---|---|
| corps non JSON | 400 |
| `{"poids":70}` | 400 |
| `{"poids":"abc","taille":1.75}` | 400 |
| `{"poids":null,"taille":1.75}` | 400 |
| `{"poids":70,"taille":0}` | 400 |
| `{"poids":-5,"taille":1.75}` | 400 |
| `{"poids":70,"taille":175}` | 400 |
| `{"poids":70,"taille":1.75}` | 201 — IMC 22,86, Corpulence normale |
| `{"poids":92,"taille":1.80}` | 201 — IMC 28,40, Surpoids |
| `{"poids":48,"taille":1.72}` | 201 — IMC 16,22, Insuffisance pondérale |

**Rejouez-les tous après chaque modification**, pas seulement celui que vous
venez de corriger. C'est ainsi qu'on attrape les *régressions* — ces défauts
qu'une correction introduit ailleurs. Nous en avons rencontré une : en
appliquant `silent=True`, le contrôle des champs manquants a disparu, et les
`500` sont revenus sans prévenir.

## Ce que vous savez faire à la fin de la v1

- Écrire un serveur web en Python et le lancer.
- Déclarer des routes, choisir les verbes HTTP et les codes de statut.
- Lire un corps JSON, valider des entrées, renvoyer une réponse structurée.
- Distinguer une faute du client (`4xx`) d'une faute du serveur (`5xx`).
- Tester une API sans interface graphique, avec `curl`.
- Lancer un serveur détaché (`nohup … &`), le retrouver (`lsof`) et l'arrêter.

---

# v2 — Donner une mémoire à l'application

Votre API calcule, mais n'enregistre rien. On va lui donner une mémoire en
deux temps : d'abord la plus simple qui soit, pour en constater les limites,
puis une vraie base de données.

## 2.1 — Une liste en mémoire

**Déclarez la liste** juste après `app = Flask(__name__)`, à la marge gauche :

```python
mesures = []
```

**Enregistrez chaque calcul** : remplacez la ligne `return jsonify({...}), 201`
de `calculer_imc` par trois lignes :

```python
    resultat = {"poids": poids, "taille": taille, "imc": imc, "categorie": categorie}
    mesures.append(resultat)
    return jsonify(resultat), 201
```

On construit le dictionnaire une fois, on le range dans la liste, on le renvoie.

**Ajoutez la route de lecture**, entre `calculer_imc` et le bloc
`if __name__` :

```python
@app.route("/api/historique")
def historique():
    return jsonify({"total": len(mesures), "mesures": mesures})
```

Pas de `methods=` : `GET` est le comportement par défaut, et c'est bien une
lecture. Renvoyer un objet avec `total` plutôt que la liste brute permettra
d'ajouter d'autres informations plus tard sans casser les clients existants.

### Testez

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":1.75}'
```

Refaites-le avec d'autres valeurs, puis relisez :

```bash
curl -s http://localhost:5001/api/historique
```

Vos mesures sont là.

### Ce que cette liste a de trompeur

Elle vit **dans le processus du serveur**, en mémoire vive. Deux conséquences,
qui sont exactement les problèmes que le reste du cours traite :

1. **Elle disparaît à chaque arrêt du serveur** — y compris lors d'un simple
   rechargement automatique après modification du fichier.
2. **Elle n'est pas partageable.** Si vous lancez plusieurs exemplaires de
   l'API pour répartir la charge — ce que vous ferez à la fin —, chacun aura
   sa propre liste, et un même utilisateur verra un historique différent selon
   l'exemplaire qui le sert.

C'est ce qu'on appelle un **état local**. Une application d'infonuagique doit
être *sans état* : toute donnée qui doit survivre ou être partagée sort du
processus, vers une base de données.

## 2.2 — L'expérience de la perte

Faites trois calculs, vérifiez l'historique, puis arrêtez le serveur :

```bash
lsof -ti tcp:5001 | xargs kill -9
```

Relancez-le :

```bash
nohup python api/app.py > serveur.log 2>&1 < /dev/null &
```

Relisez l'historique : `{"total": 0, "mesures": []}`.

**Tout a disparu.** Ce n'est pas un défaut de votre code, c'est la nature d'un
processus : sa mémoire meurt avec lui. Retenez cette phrase, elle s'appliquera
mot pour mot aux conteneurs — d'où les *volumes*, que vous verrez en v5.

## 2.3 — Obtenir MySQL sans l'installer

Il faut donc une base de données. Deux façons de l'obtenir.

**La façon traditionnelle**, que nous n'allons pas suivre :

```
brew install mysql
brew services start mysql
mysql_secure_installation
mysql -u root -p     puis CREATE DATABASE, CREATE USER, GRANT...
```

Elle installe MySQL **dans votre Mac**, durablement, dans une version imposée
par Homebrew. Votre coéquipier en obtiendra une autre : c'est le fameux « ça
marche chez moi ».

**La façon conteneur**, une seule commande, rien d'installé à demeure :

```bash
docker run -d --name mysql-tp -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=imcdb -e MYSQL_USER=imcuser -e MYSQL_PASSWORD=imcpass -p 3306:3306 mysql:8.0
```

### Décortiquez-la avant de l'exécuter

| Morceau | Signification |
|---|---|
| `docker run` | crée **et** démarre un conteneur à partir d'une image |
| `-d` | *detached* : rend la main au terminal. C'est le `&` que vous avez utilisé pour votre serveur |
| `--name mysql-tp` | un nom, pour le désigner ensuite sans manipuler d'identifiant |
| `-e CLE=valeur` | une variable d'environnement passée au conteneur |
| `-p 3306:3306` | publie un port, au format `hôte:conteneur` |
| `mysql:8.0` | l'image, au format `nom:version` |

Les quatre `-e` ne sont pas inventés : ils sont **documentés par l'image
MySQL**. Au premier démarrage, elle crée la base `imcdb` et le compte
`imcuser`. Une image, c'est un logiciel livré avec son mode d'emploi.

### Observez

```bash
docker ps
```

Une ligne, `STATUS` à `Up`. Puis suivez l'initialisation :

```bash
docker logs -f mysql-tp
```

Attendez `ready for connections` — 20 à 30 secondes. `Ctrl+C` quitte
l'affichage **sans** arrêter le conteneur : c'est exactement le rapport entre
votre `tail -f serveur.log` et votre serveur.

### Ce que vous venez d'apprendre

- **Image ≠ conteneur.** L'image est le modèle figé, téléchargé depuis Docker
  Hub ; le conteneur est une instance qui tourne. Même rapport qu'entre une
  classe et un objet.
- **`docker run -d` et `docker logs`** sont la version outillée du `nohup … &`
  et du fichier `serveur.log` que vous avez bricolés à la main.
- **« Démarré » ne veut pas dire « prêt ».** Le conteneur est `Up` dès la
  première seconde, mais la base n'accepte les connexions qu'une demi-minute
  plus tard. Ce constat justifiera les *healthchecks* en v5.

## 2.4 — Installer le connecteur

Python ne sait pas parler à MySQL tout seul : il lui faut une bibliothèque qui
traduise ses appels en protocole MySQL. C'est le **connecteur**, publié par
l'éditeur de MySQL lui-même.

```bash
pip install mysql-connector-python==8.4.0
```

Profitez-en pour figer vos dépendances dans un fichier, comme le fera tout
projet sérieux — et comme votre `Dockerfile` l'exigera en v4 :

```bash
pip freeze | grep -E "^(Flask|mysql-connector-python)" > api/requirements.txt
```

`pip freeze` liste ce qui est installé avec les versions exactes ; on ne garde
que les deux bibliothèques demandées explicitement, pas leurs dépendances
indirectes (Werkzeug, Jinja2…), que pip réinstallera automatiquement.

---

## 2.5 — Créer la table

Une base de données ne stocke pas n'importe quoi n'importe comment : il faut
décrire la **structure** des données. Créez le fichier `db/init.sql` :

```sql
CREATE TABLE IF NOT EXISTS mesures (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    poids         DECIMAL(5, 2) NOT NULL,
    taille        DECIMAL(4, 2) NOT NULL,
    imc           DECIMAL(5, 2) NOT NULL,
    categorie     VARCHAR(50)   NOT NULL,
    date_creation TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Ce que chaque ligne décide

| Élément | Rôle |
|---|---|
| `id INT AUTO_INCREMENT PRIMARY KEY` | un identifiant unique, attribué par MySQL. C'est lui qui permettra de supprimer une mesure précise |
| `DECIMAL(5, 2)` | un nombre à 5 chiffres dont 2 après la virgule : de 0,00 à 999,99. **Pas `FLOAT`** : les flottants introduisent des erreurs d'arrondi, inacceptables dès qu'on manipule des mesures ou de l'argent |
| `VARCHAR(50)` | une chaîne d'au plus 50 caractères |
| `NOT NULL` | le champ est obligatoire ; la base refusera une ligne incomplète |
| `DEFAULT CURRENT_TIMESTAMP` | la date se remplit toute seule à l'insertion |
| `IF NOT EXISTS` | rejouer le script ne provoque pas d'erreur |

**Notez le partage des rôles :** vous validez déjà les données dans l'API, et
la base impose *en plus* ses propres contraintes. Ce n'est pas redondant — la
base est la dernière ligne de défense, et elle protège les données même contre
un bug de votre code.

### Charger le script dans la base

```bash
docker exec -i mysql-tp mysql -uimcuser -pimcpass imcdb < db/init.sql
```

- `docker exec` exécute une commande **à l'intérieur** d'un conteneur qui
  tourne déjà — à ne pas confondre avec `docker run`, qui en crée un nouveau.
- `-i` garde l'entrée standard ouverte, ce qui permet au `<` de faire passer
  le contenu du fichier dans le client `mysql` du conteneur.

Vérifiez que la table existe :

```bash
docker exec mysql-tp mysql -uimcuser -pimcpass imcdb -e "DESCRIBE mesures;"
```

---

## 2.6 — Connecter l'API

### La configuration ne s'écrit pas dans le code

Ajoutez en haut de `api/app.py`, après les imports :

```python
import os
import mysql.connector
from mysql.connector import Error as MySQLError

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "imcuser"),
    "password": os.getenv("DB_PASSWORD", "imcpass"),
    "database": os.getenv("DB_NAME", "imcdb"),
}
```

`os.getenv("DB_HOST", "127.0.0.1")` lit la variable d'environnement `DB_HOST`
et, à défaut, retient `127.0.0.1`.

**Pourquoi ne pas écrire l'adresse en dur ?** Parce qu'elle changera. Ici la
base est jointe par `127.0.0.1` depuis votre Mac ; en v5, l'API tournera dans
un conteneur et devra écrire `mysql`, le nom du service. Avec une variable,
**la même application fonctionne dans les deux cas sans être modifiée**. C'est
le principe de la configuration externalisée, et c'est ce qui rend une image
Docker réutilisable d'un environnement à l'autre.

### Ouvrir une connexion

```python
def get_connection():
    """Ouvre une connexion a MySQL. Leve MySQLError si la base est injoignable."""
    return mysql.connector.connect(**DB_CONFIG)
```

Le `**` déplie le dictionnaire en arguments nommés : `host=…, port=…, user=…`.

### Enregistrer au lieu d'empiler

Dans `calculer_imc`, remplacez les trois lignes `resultat = …` /
`mesures.append(…)` / `return …` par :

```python
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
```

**Quatre points à comprendre :**

1. **Les `%s` ne sont pas du formatage Python.** Ce sont des *paramètres* : le
   connecteur envoie la requête et les valeurs séparément, et la base ne
   confond jamais une donnée avec une instruction. Écrire
   `f"… VALUES ({poids})"` ouvrirait une faille d'**injection SQL** — la
   vulnérabilité la plus classique du web.
2. **`conn.commit()`** valide la transaction. Sans lui, l'insertion est
   annulée à la fermeture de la connexion.
3. **`curseur.lastrowid`** récupère l'`id` attribué par MySQL, qu'on renvoie
   au client.
4. **Le code `503`**, et non `500` : le serveur va bien, c'est un service dont
   il dépend qui est indisponible. Cette nuance permettra plus tard à Docker
   et Kubernetes de distinguer « l'application est cassée » de « sa base n'est
   pas encore prête ».

### Relire depuis la base

Remplacez le corps de `historique` par :

```python
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
```

- `cursor(dictionary=True)` renvoie des dictionnaires plutôt que des tuples :
  `ligne["imc"]` au lieu de `ligne[3]`, bien plus lisible et robuste.
- `ORDER BY id DESC LIMIT 20` : les plus récentes d'abord, et jamais plus de
  vingt. **Une requête sans limite est une bombe à retardement** : elle est
  rapide sur trois lignes et paralyse tout sur un million.
- La conversion en `float` et l'appel à `strftime` sont indispensables :
  MySQL renvoie des objets `Decimal` et `datetime`, que `jsonify` ne sait pas
  sérialiser.

Vous pouvez enfin supprimer la ligne `mesures = []` du haut du fichier : elle
n'a plus de raison d'être.

### Tester

```bash
curl -s -X POST http://localhost:5001/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":1.75}'
```

Puis, le test qui compte — redémarrer le serveur et vérifier que les données
sont toujours là :

```bash
lsof -ti tcp:5001 | xargs kill -9 2>/dev/null; nohup python api/app.py > serveur.log 2>&1 < /dev/null & sleep 4; curl -s http://localhost:5001/api/historique
```

Cette fois, **vos mesures survivent**. Elles ne sont plus dans votre
application : elles sont dans la base, qui tourne dans son propre conteneur,
indépendamment du sort de votre serveur Python.

### Ce que vous avez gagné, et ce qu'il reste à régler

Vous venez de séparer le **calcul** du **stockage** : deux services au cycle
de vie distinct. C'est la définition même d'une architecture d'infonuagique.

Mais essayez ceci, plus tard, quand vous aurez le cœur bien accroché :
`docker rm -f mysql-tp`, puis recréez le conteneur. La base sera vide. Les
données vivaient **dans le conteneur**, pas à côté. C'est le problème que les
*volumes* résoudront en v5.

---

# v3 — Une page web pour les humains

Jusqu'ici, votre application ne s'utilise qu'avec `curl`. Il lui faut une
interface. Et cette interface va vous faire découvrir, de la pire façon qui
soit — un message d'erreur incompréhensible dans la console du navigateur —
pourquoi toute architecture web sérieuse place un **proxy inverse** devant ses
services.

## 3.1 — La page HTML

Créez `frontend/index.html` :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Calculateur d'IMC</title>
</head>
<body>
  <h1>Calculateur d'indice de masse corporelle</h1>

  <form id="formulaire">
    <label>Poids (kg) <input type="number" id="poids" step="0.1" required></label>
    <label>Taille (m) <input type="number" id="taille" step="0.01" required></label>
    <button type="submit">Calculer</button>
  </form>

  <p id="resultat"></p>
  <p id="erreur" style="color: red"></p>

  <h2>Historique</h2>
  <table id="historique" border="1"></table>

  <script src="app.js"></script>
</body>
</html>
```

Volontairement sans style : on ajoutera le CSS quand le mécanisme
fonctionnera. Deux points à noter :

- **`type="number"` et `step`** : le navigateur valide déjà un peu, mais cela
  ne remplace jamais la validation de l'API. Un client peut toujours appeler
  l'API directement, comme vous le faites avec `curl`.
- **`<script src="app.js">` en fin de `<body>`** : le script s'exécute une
  fois le HTML chargé, donc les éléments qu'il manipule existent déjà.

## 3.2 — Le JavaScript qui appelle l'API

Créez `frontend/app.js` :

```javascript
const API = "http://localhost:5001";

const formulaire = document.getElementById("formulaire");
const resultat   = document.getElementById("resultat");
const erreur     = document.getElementById("erreur");
const historique = document.getElementById("historique");

formulaire.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  erreur.textContent = "";

  const corps = {
    poids:  parseFloat(document.getElementById("poids").value),
    taille: parseFloat(document.getElementById("taille").value),
  };

  try {
    const reponse = await fetch(API + "/api/imc", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(corps),
    });
    const donnees = await reponse.json();

    if (!reponse.ok) {
      erreur.textContent = donnees.error;
      return;
    }

    resultat.textContent = `IMC : ${donnees.imc} — ${donnees.categorie}`;
    chargerHistorique();
  } catch (err) {
    erreur.textContent = "Impossible de joindre l'API : " + err.message;
  }
});

async function chargerHistorique() {
  const reponse = await fetch(API + "/api/historique");
  const donnees = await reponse.json();

  historique.innerHTML = "<tr><th>Date</th><th>Poids</th><th>Taille</th><th>IMC</th><th>Categorie</th></tr>"
    + donnees.mesures.map((m) =>
        `<tr><td>${m.date}</td><td>${m.poids}</td><td>${m.taille}</td><td>${m.imc}</td><td>${m.categorie}</td></tr>`
      ).join("");
}

chargerHistorique();
```

### Les mécanismes à comprendre

- **`evenement.preventDefault()`** empêche le navigateur de recharger la page,
  son comportement par défaut à la soumission d'un formulaire. Sans cette
  ligne, votre page clignote et rien ne se passe.
- **`fetch`** envoie une requête HTTP depuis le navigateur. C'est l'équivalent
  exact de vos `curl` : même verbe, mêmes en-têtes, même corps JSON.
- **`await`** attend la réponse sans bloquer le navigateur. La fonction est
  déclarée `async` pour cela.
- **`reponse.ok`** est vrai pour les codes 200 à 299. C'est là que votre
  travail de la v1 porte ses fruits : les `400` deviennent des messages
  lisibles pour l'utilisateur, et non des plantages.
- **`donnees.error`** : la clé exacte que votre API renvoie. Si vous l'aviez
  nommée `erreur` côté Python, il faudrait écrire `donnees.erreur` ici. C'est
  pourquoi la cohérence de nommage compte.

## 3.3 — Servir la page, et rencontrer le mur

Un fichier HTML ouvert directement depuis le Finder s'exécute avec l'adresse
`file://`, que les navigateurs traitent avec une méfiance particulière. Il
faut donc un serveur, même minimal. Python en fournit un :

```bash
cd frontend && python3 -m http.server 8080
```

Ouvrez <http://localhost:8080>, saisissez 70 et 1.75, cliquez sur Calculer.

**Rien ne se passe.** Ouvrez la console du navigateur — `Cmd+Option+J` dans
Chrome, `Cmd+Option+C` dans Safari après avoir activé le menu Développement.
Vous y lirez :

```
Access to fetch at 'http://localhost:5001/api/imc' from origin
'http://localhost:8080' has been blocked by CORS policy
```

### Ce qui se passe, et pourquoi c'est une bonne chose

Votre page vient de `localhost:8080`, votre API répond sur `localhost:5001`.
Pour un navigateur, **ce sont deux origines différentes** — une origine, c'est
le triplet protocole + domaine + port. Et par défaut, une page ne peut pas
lire la réponse d'une autre origine.

Cette règle s'appelle la *same-origin policy*, et elle vous protège : sans
elle, n'importe quel site visité pourrait, depuis votre navigateur, appeler
l'API de votre banque en réutilisant vos cookies de session.

Il existe deux façons de s'en sortir :

| Solution | Principe | Inconvénient |
|---|---|---|
| **CORS** | l'API ajoute un en-tête `Access-Control-Allow-Origin` autorisant explicitement l'autre origine | il faut modifier l'API, maintenir une liste d'origines autorisées, et gérer les requêtes préalables (*preflight*) |
| **Proxy inverse** | un seul serveur en façade sert la page **et** relaie `/api` vers l'API : tout vient de la même origine | une pièce de plus dans l'architecture |

**Nous prendrons la seconde**, parce que c'est celle qu'emploient les
architectures réelles. Elle a d'autres vertus : l'adresse de l'API n'est plus
écrite dans le code du frontend, l'API n'a plus besoin d'être exposée
publiquement, et le point d'entrée unique devient l'endroit naturel où placer
le TLS, la limitation de débit et les journaux d'accès.

Arrêtez le serveur Python avec `Ctrl+C` : nginx va le remplacer.

## 3.4 — nginx en proxy inverse

Le principe : **un seul point d'entrée**. nginx écoute sur le port 8080, sert
votre page, et transmet tout ce qui commence par `/api` à votre API Flask.

```
                    ┌──────────────────────────┐
  navigateur ──8080─►  nginx                   │
                    │   /        → fichiers    │
                    │   /api/... → relais ─────┼──5001──► API Flask
                    └──────────────────────────┘
```

Pour le navigateur, **tout vient de `localhost:8080`** : une seule origine,
donc plus aucun contrôle CORS à satisfaire.

### La configuration

Créez `nginx/default.conf` — dans un dossier **distinct** de `frontend`, pour
que ce fichier de configuration ne se retrouve pas servi publiquement avec
vos pages :

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://host.docker.internal:5001;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    }

    location /health {
        proxy_pass http://host.docker.internal:5001/health;
    }
}
```

### Ce que chaque directive décide

| Directive | Rôle |
|---|---|
| `listen 80` | le port **à l'intérieur** du conteneur ; on le publiera sur 8080 |
| `root` | le dossier où nginx cherche les fichiers |
| `location /` | tout le reste : on sert le fichier demandé, sinon `index.html` |
| `location /api/` | **le proxy** : ces requêtes ne sont pas servies, elles sont relayées |
| `proxy_set_header` | transmet l'identité du client d'origine, sinon l'API ne verrait que l'adresse de nginx |

### `host.docker.internal`, et pourquoi pas `localhost`

Votre API tourne **sur votre Mac**, pas dans un conteneur. Or à l'intérieur
d'un conteneur, `localhost` désigne le conteneur lui-même : nginx s'appellerait
lui-même et échouerait. Docker Desktop fournit donc le nom spécial
`host.docker.internal`, qui pointe vers la machine hôte.

**Retenez que c'est provisoire.** En v5, quand l'API tournera elle aussi dans
un conteneur, cette ligne deviendra `proxy_pass http://api:5000;` — le nom du
service, résolu par le DNS interne de Docker. C'est la *découverte de
services*, et c'est le même mécanisme que Kubernetes généralise.

### Lancer nginx

D'abord, libérez le port 8080 occupé par le serveur Python :

```bash
lsof -ti tcp:8080 | xargs kill -9
```

Puis, depuis le dossier `imc-app` :

```bash
docker run -d --name nginx-tp -p 8080:80 -v "$(pwd)/frontend:/usr/share/nginx/html:ro" -v "$(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:1.27-alpine
```

Deux montages, tous deux en lecture seule (`:ro`) :

- votre dossier `frontend` devient le dossier servi ;
- votre `default.conf` **remplace** la configuration par défaut de l'image,
  celle qui affiche la page « Welcome to nginx ».

Un montage n'est pas une copie : modifiez `index.html` sur votre Mac, et le
changement est immédiatement visible dans le conteneur. Très pratique en
développement — et à ne pas confondre avec l'image que vous construirez en v4,
qui, elle, **contiendra** les fichiers.

### Le frontend n'a plus à connaître l'API

Dans `frontend/app.js`, remplacez la première ligne :

```javascript
const API = "";
```

Les appels deviennent `fetch("/api/imc")` : une adresse **relative**, résolue
par le navigateur sur l'origine courante, donc `localhost:8080`, donc nginx.

**C'est un gain d'architecture, pas une astuce.** Le frontend ne sait plus où
vit l'API : elle peut déménager, changer de port, être répartie sur dix
instances, rien ne changera dans cette page.

### Tester

Rechargez <http://localhost:8080>, saisissez 70 et 1.75. Le résultat s'affiche
et l'historique se remplit. Dans la console du navigateur : plus aucune erreur
CORS, puisqu'il n'y a plus qu'une seule origine.

Vérifiez aussi que le relais fonctionne en ligne de commande :

```bash
curl -s http://localhost:8080/api/historique
```

Vous interrogez nginx sur le port 8080, et c'est Flask qui répond.

### Ce que vous avez gagné

| Avant | Après |
|---|---|
| deux origines, CORS bloquant | une seule origine |
| l'adresse de l'API écrite dans le frontend | une adresse relative |
| l'API exposée directement au navigateur | l'API derrière un intermédiaire |

Ce point d'entrée unique est aussi l'endroit naturel où l'on placera plus tard
le certificat TLS, la limitation de débit, la compression et les journaux
d'accès. Une seule porte à surveiller au lieu de trois.

---

# v4 — Mettre l'application en images

Votre application fonctionne, mais elle ne fonctionne que **chez vous**. Elle
dépend de votre `.venv`, de votre version de Python, de votre `pip install`,
et d'une suite de commandes qu'il faut connaître. Donnez le dossier à votre
coéquipier, et il passera une heure à reproduire votre environnement.

Une **image** est la réponse à ce problème : un système de fichiers figé qui
contient l'application *et* tout ce dont elle a besoin pour s'exécuter.

## 4.1 — Régler d'abord une dette

Regardez votre `api/requirements.txt` :

```
Flask @ file:///private/var/folders/nz/.../croot/flask_1716545886197/work
mysql-connector-python==8.4.0
```

La première ligne vient d'un `pip freeze` qui a capturé le **chemin local**
d'un Flask installé par Anaconda, au lieu de son numéro de version. Ce chemin
n'existe que sur votre Mac : la construction de l'image échouerait
immédiatement.

Remplacez le contenu du fichier par :

```
Flask==3.0.3
mysql-connector-python==8.4.0
gunicorn==22.0.0
```

`gunicorn` est nouveau : c'est le serveur qui remplacera, dans l'image, le
serveur de développement de Flask. Celui-ci traite une requête à la fois et
affiche un débogueur exécutant du code à distance — acceptable sur votre
machine, inacceptable ailleurs.

**La leçon :** un fichier de dépendances est un contrat. `pip freeze` est
commode mais capture l'état d'une machine, pas l'intention. Relisez toujours
ce qu'il produit.

## 4.2 — Ce qui ne doit pas entrer dans l'image

Créez `.dockerignore` à la racine du projet :

```
.venv/
__pycache__/
*.pyc
*.log
.DS_Store
.git/
```

Au moment du build, Docker envoie le contenu du dossier au moteur : c'est le
*contexte de construction*. Sans ce fichier, votre `.venv` de plusieurs
centaines de mégaoctets serait transféré à chaque build — pour finir ignoré,
puisque l'image réinstalle ses dépendances elle-même.

Le principe dépasse la performance : un `.venv` construit pour macOS n'a rien
à faire dans une image Linux, et un fichier de journal n'a rien à faire dans
une image du tout.

## 4.3 — Le `Dockerfile` de l'API

Créez `api/Dockerfile` :

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN useradd --create-home imc
USER imc

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
```

### Ligne par ligne

**`FROM python:3.12-slim`** — l'image de départ. La variante *slim* pèse
environ 150 Mo contre près d'un gigaoctet pour l'image complète : moins de
paquets, donc moins de surface d'attaque et des transferts plus rapides.

**`ENV PYTHONDONTWRITEBYTECODE=1`** — pas de fichiers `.pyc` inutiles dans
l'image.

**`ENV PYTHONUNBUFFERED=1`** — les journaux sortent immédiatement, sans
tampon. Sans cette ligne, `docker logs` peut sembler vide alors que
l'application tourne : la sortie reste bloquée en mémoire.

**`WORKDIR /app`** — fixe le dossier de travail. C'est la réponse définitive
aux `cd` oubliés qui vous ont fait perdre du temps : dans l'image, les chemins
relatifs désignent toujours la même chose.

**`COPY requirements.txt .` puis `RUN pip install`** — et **seulement ensuite**
`COPY app.py .`. L'ordre est le point pédagogique de ce fichier. Chaque
instruction crée une **couche** mise en cache. Tant que `requirements.txt` ne
change pas, Docker réutilise la couche d'installation. Si vous copiiez tout
d'un coup, la moindre correction dans `app.py` réinstallerait Flask et le
connecteur MySQL à chaque build.

**`RUN useradd --create-home imc` puis `USER imc`** — par défaut un conteneur
s'exécute en `root`. Si une faille permet d'exécuter du code, autant que ce ne
soit pas en administrateur. Placez ces lignes **après** le `pip install`,
sinon l'installation manquerait de droits.

**`EXPOSE 5000`** — documente le port écouté. C'est une déclaration, pas une
ouverture : c'est `-p` au lancement qui publie réellement un port.

Remarquez d'ailleurs le retour au port **5000**, alors que vous utilisez 5001
depuis le début à cause du Récepteur AirPlay de macOS. Dans un conteneur, le
conflit n'existe pas : chaque conteneur a sa propre pile réseau. C'est l'un des
bénéfices concrets de l'isolation.

**`CMD [...]`** — la commande de démarrage, en forme JSON. Deux détails
comptent :

- `0.0.0.0` et non `127.0.0.1` : sinon l'application n'écouterait que
  l'intérieur du conteneur et resterait injoignable.
- la forme JSON, dite *exec*, lance Gunicorn **directement**. La forme shell
  (`CMD gunicorn …`) interpose un `/bin/sh` qui reçoit les signaux à la place
  de votre application : `docker stop` ne serait jamais transmis, et le
  conteneur serait tué de force au bout de dix secondes.

### Construire et regarder

```bash
docker build -t imc-api:1.0 ./api
```

```bash
docker images | grep imc-api
docker history imc-api:1.0
```

`docker history` montre les couches, une par instruction, avec leur taille.
Modifiez une ligne d'`app.py`, reconstruisez, et observez : seules les
dernières couches sont refaites, le reste vient du cache.

## 4.4 — Un réseau pour que les conteneurs se parlent

Vos conteneurs sont aujourd'hui sur le réseau par défaut de Docker, où **la
résolution par nom n'existe pas**. Il faut un réseau créé explicitement :

```bash
docker network create imc-net
```

```bash
docker network connect imc-net mysql-tp
```

Puis lancez l'API dans ce réseau :

```bash
docker run -d --name api --network imc-net -e DB_HOST=mysql-tp imc-api:1.0
```

**Le `-e DB_HOST=mysql-tp` est le moment de vérité de tout le projet.** Votre
code n'a pas changé d'une ligne depuis la v2 : il lit toujours
`os.getenv("DB_HOST", "127.0.0.1")`. Sur votre Mac, la valeur par défaut
convenait ; dans le réseau Docker, la variable désigne le conteneur MySQL par
son nom. **La même image fonctionne dans les deux mondes.** C'est exactement
ce que promettait la configuration externalisée de la v2.

Vérifiez :

```bash
docker logs api
```

```bash
docker exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/health').read())"
```

## 4.5 — Le `Dockerfile` du frontend

Le frontend est aujourd'hui un conteneur nginx avec vos fichiers **montés**
depuis votre disque. Pratique en développement, inacceptable pour une
livraison : l'image ne contient rien, elle dépend de votre Mac.

Créez `frontend/Dockerfile` :

```dockerfile
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY default.conf /etc/nginx/conf.d/default.conf

COPY index.html app.js /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

Copiez d'abord la configuration à côté des fichiers du site, puisqu'un `COPY`
ne peut pas sortir du contexte de construction :

```bash
cp nginx/default.conf frontend/default.conf
```

Et adaptez la ligne du proxy dans `frontend/default.conf` : l'API n'est plus
sur l'hôte, elle est dans le réseau Docker.

```nginx
        proxy_pass http://api:5000;
```

`api` est le nom du conteneur, `5000` le port qu'il écoute à l'intérieur du
réseau. `host.docker.internal` disparaît : c'était un pont provisoire vers
votre Mac.

**`daemon off;`** mérite une explication : un conteneur vit tant que son
processus principal tourne. nginx passe en arrière-plan par défaut, ce qui
ferait croire à Docker que le travail est terminé — le conteneur s'arrêterait
aussitôt.

Construisez et lancez :

```bash
docker build -t imc-frontend:1.0 ./frontend
```

```bash
docker rm -f nginx-tp
```

```bash
docker run -d --name frontend --network imc-net -p 8080:80 imc-frontend:1.0
```

Rechargez <http://localhost:8080> : tout fonctionne, et **plus rien ne vient
de votre disque**. Vous pouvez arrêter votre serveur Flask local, il ne sert
plus à rien.

### Le bilan de la v4

| Avant | Après |
|---|---|
| l'API dépendait de votre `.venv` | elle vit dans une image, avec ses dépendances |
| le serveur de développement de Flask | Gunicorn, 2 *workers* et 4 fils d'exécution |
| des fichiers montés depuis votre Mac | des fichiers contenus dans l'image |
| `host.docker.internal` | `api:5000`, par le DNS du réseau Docker |

Ce qui reste pénible : **cinq commandes à lancer dans le bon ordre**, avec les
bons noms, les bonnes variables et le bon réseau. C'est ce que la v5 supprime.

---

# v5 — Tout orchestrer avec docker compose

Un fichier déclaratif remplace la série de `docker run`. On y décrit **l'état
souhaité** — trois services, un réseau, un volume — et Docker se charge d'y
arriver.

## 5.1 — Le fichier

Créez `docker-compose.yml` à la racine du projet :

```yaml
services:

  mysql:
    image: mysql:8.0
    container_name: imc-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: imcdb
      MYSQL_USER: imcuser
      MYSQL_PASSWORD: imcpass
    volumes:
      - mysql-data:/var/lib/mysql
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-prootpass"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      - imc-net

  api:
    build: ./api
    image: imc-api:1.0
    container_name: imc-api
    restart: unless-stopped
    environment:
      DB_HOST: mysql
      DB_PORT: 3306
      DB_USER: imcuser
      DB_PASSWORD: imcpass
      DB_NAME: imcdb
    depends_on:
      mysql:
        condition: service_healthy
    networks:
      - imc-net

  frontend:
    build: ./frontend
    image: imc-frontend:1.0
    container_name: imc-frontend
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - api
    networks:
      - imc-net

networks:
  imc-net:
    driver: bridge

volumes:
  mysql-data:
```

Adaptez une dernière fois le proxy dans `frontend/default.conf` : le nom du
service devient `api` — c'est déjà le cas si vous avez suivi la v4.

## 5.2 — Les décisions que ce fichier contient

**Un seul port publié.** Seul `frontend` expose `8080`. L'API et la base ne
sont joignables que depuis le réseau interne : deux portes de moins à
surveiller. Pour inspecter la base pendant vos tests, passez par
`docker compose exec mysql …` plutôt que d'ouvrir 3306 au monde.

**`restart: unless-stopped`** relance les services au démarrage de Docker,
mais **respecte un arrêt manuel** — contrairement à `always`, qui les
ressuscite même après un `docker stop`. Souvenez-vous des conteneurs MLflow
qui revenaient sans cesse : c'était `always`.

**`healthcheck` et `condition: service_healthy`.** Vous savez depuis la v2
que MySQL met une trentaine de secondes à accepter des connexions alors que
son conteneur est `Up` dès la première seconde. La forme courte
`depends_on: [mysql]` n'attend que le lancement ; la forme longue avec
`condition` attend que le test de santé réussisse. C'est l'ancêtre direct des
*readiness probes* de Kubernetes, que vous étudierez à la Question IV.

**Deux montages différents sur `mysql`.** `mysql-data:/var/lib/mysql` est un
**volume nommé**, géré par Docker : c'est lui qui fait survivre les données à
la suppression du conteneur. `./db/init.sql:/…initdb.d/…:ro` est un **bind
mount** d'un fichier de votre disque, en lecture seule, que l'image exécute
automatiquement — mais uniquement quand la base est vide.

**Un volume nommé plutôt qu'anonyme.** Vous avez déjà rencontré un volume
orphelin nommé `ff505fabd6…`, dont plus rien n'indiquait l'origine. Avec
`mysql-data`, il apparaît clairement dans `docker volume ls`, se sauvegarde et
se restaure sans devinette.

## 5.3 — Lancer

Faites d'abord le ménage des conteneurs lancés à la main en v4 :

```bash
docker rm -f api frontend mysql-tp
```

Attention : cela efface les mesures enregistrées jusqu'ici, puisqu'elles
vivaient **dans** le conteneur `mysql-tp`, faute de volume. C'est la dernière
fois que cela vous arrive — et c'est une bonne démonstration à refaire pour
votre rapport.

```bash
docker compose config
```

Cette commande valide le fichier et affiche sa version complète, sans rien
lancer. Prenez le réflexe.

```bash
docker compose up --build
```

Puis, en arrière-plan une fois que tout va bien :

```bash
docker compose up -d
```

## 5.4 — Le quotidien avec compose

| Besoin | Commande |
|---|---|
| État des services | `docker compose ps` |
| Journaux d'un service | `docker compose logs -f api` |
| Ouvrir un shell dans un conteneur | `docker compose exec api /bin/bash` |
| Interroger la base | `docker compose exec mysql mysql -uimcuser -pimcpass imcdb -e "SELECT * FROM mesures;"` |
| Arrêter, garder les données | `docker compose down` |
| Arrêter, **effacer** les données | `docker compose down -v` |
| Reconstruire après modification du code | `docker compose up -d --build` |

## 5.5 — Les démonstrations à faire pour le rapport

**La persistance.** Enregistrez une mesure, puis :

```bash
docker compose down
```

```bash
docker compose up -d
```

Les données sont toujours là. Refaites-le avec `down -v` : elles disparaissent,
et la base est recréée à partir de `init.sql`. Vous tenez là, en deux
commandes, la démonstration de ce qu'est un volume.

**La découverte de services.**

```bash
docker compose exec frontend ping -c 2 api
```

Le nom `api` se résout vers l'adresse du conteneur, sans qu'aucune adresse IP
n'ait jamais été écrite nulle part.

**L'ordre de démarrage.** Regardez `docker compose ps` pendant le lancement :
`imc-mysql` passe par `health: starting` avant d'être `healthy`, et l'API
n'est lancée qu'ensuite.

**La montée en échelle.** Retirez `container_name` du service `api` — un nom
fixe interdit plusieurs exemplaires — puis :

```bash
docker compose up -d --scale api=3
```

```bash
docker compose ps
```

Trois instances de l'API répondent derrière nginx. Pour le voir depuis
l'extérieur, ajoutez le nom d'hôte du conteneur à votre réponse `/health` :

```python
import socket
...
    return jsonify({"service": "imc-api", "statut": "ok", "instance": socket.gethostname()})
```

Rechargez plusieurs fois <http://localhost:8080/health> : le champ `instance`
change. **Vous venez de faire de l'équilibrage de charge** — et de démontrer
au passage pourquoi la liste en mémoire de la v2.1 était une impasse : chaque
instance aurait eu son propre historique.

## Ce que vous saurez faire à la fin de la v5

- Écrire une API REST validée, connectée à une base de données.
- Décrire un environnement complet dans un fichier versionnable.
- Lancer l'ensemble d'une seule commande, sur n'importe quelle machine
  disposant de Docker.
- Expliquer la différence entre image, conteneur et volume — et pourquoi elle
  compte.
- Justifier chaque ligne de votre `docker-compose.yml` devant un correcteur.

Le dernier point est le plus important pour la note : la Question I demande un
code documenté et une architecture expliquée. Vous n'aurez rien à inventer,
tout ce guide retrace vos décisions et leurs raisons.
