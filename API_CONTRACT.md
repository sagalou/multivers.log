# API_CONTRACT.md — Multivers.log

Contrat entre le front et le back. Toutes les réponses décrites ici ont été
relevées sur le serveur réel, pas déduites du code.

Adresse en développement : `http://localhost:8000`

CORS : `allow_origins=["*"]`, le front peut appeler l'API depuis n'importe quelle
origine (à restreindre au palier 5).

---

## GET /health

Vérifie que le serveur répond. Aucun paramètre.

```json
{ "status": "ok" }
```

---

## POST /upload

Dépose un ou plusieurs documents. Corps en `multipart/form-data`, champ `files`,
répétable pour envoyer plusieurs fichiers.

Le serveur sauvegarde le fichier dans `UPLOAD_DIR`, l'enregistre en base, lance
l'extraction, puis renvoie le statut **final**, pas le statut initial.

```json
{
  "documents": [
    {
      "id": "doc_0978a616",
      "filename": "rapport.txt",
      "status": "processed",
      "error_message": null
    }
  ]
}
```

Sans fichier : `422`, avec le détail de validation de FastAPI.

```json
{ "detail": [{ "type": "missing", "loc": ["body", "files"], "msg": "Field required" }] }
```

---

## GET /documents

Liste tous les documents et leur statut. Sert à remplir la liste du front au
chargement de la page, sans attendre un dépôt.

```json
{
  "documents": [
    {
      "id": "doc_0978a616",
      "filename": "rapport.txt",
      "status": "processed",
      "error_message": null
    }
  ]
}
```

---

## GET /chunks/{chunk_id}

Renvoie un passage complet. Sert à l'étape 5 du happy path : clic sur une
citation, ouverture du passage source.

```json
{
  "id": "c_3063bd0d",
  "document_id": "doc_0978a616",
  "content": "Rapport de janvier. Montant total facture : 4 200 euros HT\nRegle par virement.",
  "page_number": null,
  "position": 0,
  "filename": "rapport.txt"
}
```

Passage inconnu : `404`.

```json
{ "detail": "Chunk c_inexistant introuvable." }
```

---

## POST /ask

Pose une question en langage naturel. Corps en JSON, champ `question`.

```json
{ "question": "Quel est le montant total facture ?" }
```

Cette route ne renvoie **jamais** de 500. Tout échec est converti en réponse
`no_answer`, ce qui laisse un seul format d'erreur à gérer côté front.

Réponse normale :

```json
{
  "answer": "Le montant total facture est de 4 200 euros HT.",
  "citations": []
}
```

Réponse en échec, quatre cas : question vide, clé API absente, appel au LLM en
erreur, aucune information trouvée dans le corpus.

```json
{
  "answer": null,
  "citations": [],
  "no_answer": true,
  "message": "Question vide."
}
```

---

## POST /report

Génère une synthèse du corpus. Corps en JSON, champ `query`.

```json
{
  "report": "Rapport factice en attendant l'implementation.",
  "sources": ["doc_0978a616"]
}
```

---

## Valeurs de `status`

| Valeur | Sens | Affichage front |
|---|---|---|
| `processing` | déposé, extraction en cours | en cours |
| `processed` | extraction réussie, interrogeable | traité |
| `error` | document illisible, voir `error_message` | erreur |

---

## Format des citations (palier 4, à valider ensemble)

`citations` est une liste vide jusqu'au branchement de `search_chunks` dans
`/ask`. Format proposé pour la suite, à confirmer entre Sagal et David avant
implémentation :

```json
{
  "chunk_id": "c_3063bd0d",
  "doc_id": "doc_0978a616",
  "filename": "rapport.txt",
  "page": 7,
  "quote": "4 200 euros HT",
  "char_start": 1580,
  "char_end": 1745,
  "bbox": null
}
```

Trois points à trancher :

1. `doc_id` porte l'identifiant (`doc_0978a616`), `filename` porte le nom lisible
   (`rapport.txt`). Le front affiche `filename`, et utilise `doc_id` pour les
   liens. Ne pas mettre le nom de fichier dans `doc_id`.
2. `page` vaut `null` pour les formats sans pagination (CSV, notes texte).
3. `bbox` vaut `null` pour du texte. Pour une capture d'écran, `bbox` vaut
   `[x, y, w, h]` et `char_start` / `char_end` valent `null`.

Chaque citation passe par `verify_citation` (voir `app/verification.py`) avant
d'être renvoyée : le `chunk_id` doit exister en base, et la `quote` doit se
retrouver dans le contenu du passage. Une citation rejetée n'est jamais affichée.
