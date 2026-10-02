#!/usr/bin/env bash
# ============================================================================
#  Tests de l'application IMC
#  Prerequis : la pile doit tourner (docker compose up -d)
#  Usage     : ./tests.sh
# ============================================================================

BASE="http://localhost:8080"
JSON="Content-Type: application/json"
REUSSIS=0
ECHOUES=0

verifie() {
  # verifie <description> <code attendu> <corps de la requete>
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/imc" -H "$JSON" -d "$3")
  corps=$(curl -s -X POST "$BASE/api/imc" -H "$JSON" -d "$3" | tr -d '\n' | tr -s ' ')
  if [ "$code" = "$2" ]; then
    printf "  [OK]     %-28s -> %s\n" "$1" "$code"
    REUSSIS=$((REUSSIS + 1))
  else
    printf "  [ECHEC]  %-28s -> %s (attendu %s)\n" "$1" "$code" "$2"
    ECHOUES=$((ECHOUES + 1))
  fi
  echo "           $corps"
}

echo "============================================================"
echo " Tests de l'application IMC — $(date '+%d/%m/%Y %H:%M')"
echo "============================================================"

echo
echo "--- 1. Etat des services ---"
docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'

echo
echo "--- 2. Disponibilite de l'API ---"
echo "  \$ curl -s $BASE/health"
curl -s "$BASE/health" | tr -d '\n' | tr -s ' '
echo

echo
echo "--- 3. Calculs valides (201 attendu) ---"
verifie "70 kg / 1,75 m"   "201" '{"poids":70,"taille":1.75}'
verifie "92 kg / 1,80 m"   "201" '{"poids":92,"taille":1.80}'
verifie "48 kg / 1,72 m"   "201" '{"poids":48,"taille":1.72}'
verifie "105 kg / 1,78 m"  "201" '{"poids":105,"taille":1.78}'

echo
echo "--- 4. Validation des entrees (400 attendu) ---"
verifie "taille nulle"       "400" '{"poids":70,"taille":0}'
verifie "champ manquant"     "400" '{"poids":70}'
verifie "valeur non numerique" "400" '{"poids":"abc","taille":1.75}'
verifie "poids negatif"      "400" '{"poids":-5,"taille":1.75}'
verifie "taille en cm"       "400" '{"poids":70,"taille":175}'

echo
echo "--- 5. Historique relu depuis la base ---"
echo "  \$ curl -s $BASE/api/historique"
curl -s "$BASE/api/historique" | head -c 300
echo

echo
echo "--- 6. Contenu de la base de donnees ---"
docker compose exec -T mysql mysql -uimcuser -pimcpass imcdb \
  -e "SELECT id, poids, taille, imc, categorie FROM mesures ORDER BY id DESC LIMIT 5;" 2>/dev/null

echo
echo "--- 7. Decouverte de services ---"
echo "  \$ docker compose exec frontend ping -c 2 api"
docker compose exec -T frontend ping -c 2 api 2>&1 | head -3

echo
echo "============================================================"
echo " Resultat : $REUSSIS reussis, $ECHOUES echoues"
echo "============================================================"
[ "$ECHOUES" -eq 0 ]
