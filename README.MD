# 📚 Gallica Image Downloader

Outil Streamlit pour télécharger et renommer en lot des images Gallica (BnF) depuis un fichier Excel.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Utilisation

1. **Importez** votre fichier `.xlsx` — les URLs Gallica doivent être en colonne A
2. **Définissez** votre modèle de nomenclature :
   - `{n}` → numéro séquentiel (1, 2, 3…)
   - `{N}` → numéro zéro-padé (001, 002…)
   - Exemple : `DEL-45_{N}` → `DEL-45_001.jpg`
3. **Ajoutez** optionnellement des variantes individuelles par fichier (ex : `[DEL-45][345-6]`)
4. **Lancez** le téléchargement — un ZIP est généré avec tous les fichiers renommés

## Formats d'URL Gallica supportés

- `https://gallica.bnf.fr/ark:/12148/btv1b...` (notice)
- `https://gallica.bnf.fr/ark:/12148/btv1b.../f1.item` (visionneuse)
- `https://gallica.bnf.fr/ark:/12148/btv1b.../f1.highres` (direct)

L'outil convertit automatiquement les URLs de notice vers les URLs haute résolution (`.highres`).
