const API = "";

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
