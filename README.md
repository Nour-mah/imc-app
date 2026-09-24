# Application Cloud de calcul de l'IMC

**Cours :** 8CLD876 — Conception et architecture des systèmes d'infonuagique
**Travail pratique 1, Question I** — UQAC, automne 2026

Application web conteneurisée qui calcule l'indice de masse corporelle d'une
personne, le classe selon les seuils de l'Organisation mondiale de la santé et
conserve l'historique des mesures dans une base de données.

L'ensemble se lance d'une seule commande et s'ouvre sur <http://localhost:8080>.

---

## 1. Description du système

L'utilisateur saisit un poids et une taille dans une page web. L'application
calcule l'IMC selon la formule de Quetelet, détermine la catégorie
correspondante, enregistre la mesure et affiche l'historique des vingt
dernières.

```
IMC = poids (kg) / taille (m)²
```

| IMC | Catégorie |
|---|---|
| moins de 18,5 | Insuffisance pondérale |
| 18,5 – 24,9 | Corpulence normale |
| 25,0 – 29,9 | Surpoids |
| 30,0 – 34,9 | Obésité modérée (classe I) |
| 35,0 – 39,9 | Obésité sévère (classe II) |
| 40,0 et plus | Obésité morbide (classe III) |

---

## 2. Architecture

Architecture **trois tiers**, chaque tiers dans son propre conteneur, reliés
par un réseau Docker privé.

```
                    ┌──────────────────────────────────────────────┐
                    │          Réseau Docker « imc-net »           │
   Navigateur       │                                              │
        │           │  ┌────────────┐  ┌──────────┐  ┌──────────┐  │
        └────8080───┼─►│  frontend  │─►│   api    │─►│  mysql   │  │
                    │  │   nginx    │  │  Flask   │  │   8.0    │  │
                    │  │    :80     │  │  :5000   │  │  :3306   │  │
                    │  └────────────┘  └──────────┘  └────┬─────┘  │
                    │   présentation      métier          │        │
                    └─────────────────────────────────────┼────────┘
                                                          │
                                                   ┌──────┴───────┐
                                                   │  mysql-data  │ volume
                                                   └──────────────┘
```

| Tiers | Service | Technologie | Rôle |
|---|---|---|---|
| Présentation | `frontend` | nginx 1.27 alpine | sert la page et relaie `/api` vers l'API |
| Métier | `api` | Python 3.12, Flask, Gunicorn | calcule, classe, valide, dialogue avec la base |
| Données | `mysql` | MySQL 8.0 | persiste les mesures dans la table `mesures` |

### Décisions d'architecture

**Un seul port publié.** Seul `frontend` expose `8080` vers la machine hôte.
L'API et la base ne sont joignables que depuis le réseau interne, ce qui réduit
la surface d'attaque à une seule porte d'entrée.

**Proxy inverse.** nginx sert les fichiers statiques *et* relaie `/api` vers
l'API. Le navigateur ne voit qu'une seule origine : aucun problème de CORS, et
l'adresse de l'API n'apparaît nulle part dans le code du frontend, qui utilise
des URL relatives.

**Découverte de services.** L'API joint la base par le nom `mysql`, résolu par
le DNS interne de Docker. Aucune adresse IP n'est écrite en dur.

**Configuration externalisée.** Les paramètres de connexion proviennent de
variables d'environnement (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`,
`DB_NAME`). La même image fonctionne en local et dans le réseau Docker sans
être reconstruite.

**Démarrage ordonné.** MySQL met une trentaine de secondes à accepter des
connexions alors que son conteneur est marqué « démarré » immédiatement. Un
`healthcheck` combiné à `depends_on: condition: service_healthy` fait attendre
l'API jusqu'à ce que la base réponde réellement.

**Persistance.** Les données vivent dans le volume nommé `mysql-data`, et non
dans le conteneur. Elles survivent donc à sa suppression et à sa recréation.

---

## 3. Prérequis

- Docker Desktop (Docker Engine 20.10 ou plus récent, Compose v2)
- Le port **8080** libre

```bash
docker --version && docker compose version
```

---

## 4. Installation et lancement

```bash
docker compose up -d --build
```

Le premier lancement construit les images et initialise la base ; comptez une
minute. Vérifiez ensuite l'état des services :

```bash
docker compose ps
```

`imc-mysql` doit afficher `(healthy)`. L'application est alors accessible :

**<http://localhost:8080>**

Pour arrêter :

```bash
docker compose down
```

`docker compose down -v` supprime en plus le volume, donc **toutes les
mesures enregistrées**.

---

## 5. Guide de l'utilisateur

1. Ouvrez <http://localhost:8080>.
2. Saisissez un **poids en kilogrammes** et une **taille en mètres**, par
   exemple 70 et 1.75.
3. Cliquez sur **Calculer**.
4. Le résultat s'affiche sous le formulaire : la valeur de l'IMC et la
   catégorie de l'OMS.
5. La mesure est enregistrée et apparaît en tête du tableau **Historique**,
   avec sa date.

En cas de saisie invalide, un message rouge indique précisément ce qui ne va
pas.

---

## 6. API REST

| Méthode | Route | Corps | Réponse |
|---|---|---|---|
| `GET` | `/health` | — | `200` — état du service |
| `POST` | `/api/imc` | `{"poids": 70, "taille": 1.75}` | `201` — IMC, catégorie, identifiant |
| `GET` | `/api/historique` | — | `200` — les 20 dernières mesures |

Exemple :

```bash
curl -s -X POST http://localhost:8080/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":1.75}'
```

```json
{"id": 11, "poids": 70.0, "taille": 1.75, "imc": 22.86, "categorie": "Corpulence normale"}
```

### Validation des entrées

Tous ces cas sont refusés avec un code `400` et un message explicite :

| Envoi | Motif |
|---|---|
| corps non JSON | format attendu |
| `{"poids":70}` | champ obligatoire manquant |
| `{"poids":"abc","taille":1.75}` | valeur non numérique |
| `{"poids":null,"taille":1.75}` | valeur nulle |
| `{"poids":70,"taille":0}` | division par zéro évitée |
| `{"poids":-5,"taille":1.75}` | valeur négative |
| `{"poids":70,"taille":175}` | taille saisie en centimètres |

Le dernier cas mérite une justification : sans ce contrôle, l'API répondrait
`201` avec un IMC de 0,0 et la catégorie « Insuffisance pondérale ». Une
réponse fausse mais crédible est plus dangereuse qu'une erreur franche.

Si la base est injoignable, l'API répond `503` et non `500` : le serveur
fonctionne, c'est le service dont il dépend qui est indisponible.

---

## 7. Tests

Avec l'application démarrée.

**Calcul et classification :**

```bash
curl -s -X POST http://localhost:8080/api/imc -H "Content-Type: application/json" -d '{"poids":92,"taille":1.80}'
```

Attendu : IMC 28,4, catégorie « Surpoids ».

**Rejet d'une entrée invalide :**

```bash
curl -s -X POST http://localhost:8080/api/imc -H "Content-Type: application/json" -d '{"poids":70,"taille":175}'
```

Attendu : `400`, message sur la taille en mètres.

**Persistance des données :**

```bash
docker compose down && docker compose up -d && sleep 30 && curl -s http://localhost:8080/api/historique
```

Les conteneurs sont détruits puis recréés ; les mesures sont toujours là,
puisqu'elles vivent dans le volume.

**Contenu de la base :**

```bash
docker compose exec mysql mysql -uimcuser -pimcpass imcdb -e "SELECT * FROM mesures;"
```

**Découverte de services :**

```bash
docker compose exec frontend ping -c 2 api
```

Le nom `api` se résout vers l'adresse du conteneur.

**Journaux :**

```bash
docker compose logs -f api
```

---

## 8. Structure du projet

```
imc-app/
├── api/
│   ├── app.py            API Flask : routes, validation, accès MySQL
│   ├── requirements.txt  dépendances, versions figées
│   └── Dockerfile        image Python 3.12-slim, exécutée par Gunicorn
├── db/
│   └── init.sql          schéma de la table `mesures`
├── frontend/
│   ├── index.html        formulaire, résultat, historique
│   ├── app.js            appels à l'API en JSON
│   ├── default.conf      configuration nginx : statique + proxy inverse
│   └── Dockerfile        image nginx alpine
├── docker-compose.yml    orchestration des trois services
└── .dockerignore
```

---

## 9. Choix techniques

**`DECIMAL` plutôt que `FLOAT`** dans le schéma : les flottants introduisent
des erreurs d'arrondi, inacceptables sur des mesures.

**Requêtes paramétrées** (`%s`) pour toutes les insertions : protection contre
l'injection SQL.

**Gunicorn plutôt que le serveur de développement de Flask** dans l'image : ce
dernier est mono-processus et embarque un débogueur permettant l'exécution de
code à distance.

**Utilisateur non privilégié** dans l'image de l'API : un conteneur ne doit pas
s'exécuter en `root`.

**Copie des dépendances avant le code** dans le `Dockerfile` : une
modification du code n'invalide pas la couche d'installation, et la
reconstruction reste rapide.

**`restart: unless-stopped`** plutôt que `always` : les services redémarrent
automatiquement, mais un arrêt manuel est respecté.

---

## 10. Limites connues

| Limite | Piste |
|---|---|
| Les identifiants de la base figurent dans `docker-compose.yml` | un fichier `.env`, ou les *secrets* Docker |
| Une connexion est ouverte à chaque requête et non fermée en cas d'exception | un bloc `with`, ou un pool de connexions |
| Pas de HTTPS | un certificat TLS sur nginx |
| Pas de suite de tests automatisés | `pytest` pour la logique, un script pour les routes |
| Interface volontairement minimale | feuille de style à ajouter |
