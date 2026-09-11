# ExeCraft

**ExeCraft** est un petit logiciel avec interface graphique qui transforme :
- un script **Python (.py)** en exécutable Windows **.exe** (grâce à PyInstaller)
- une page **HTML (.html)** en application de bureau **.exe** (grâce à pywebview, qui affiche le HTML dans une vraie fenêtre native, pas dans un navigateur)

## ⚠️ Important

Un `.exe` Windows doit être compilé **sur Windows**. ExeCraft doit donc être
exécuté sur une machine Windows pour produire un `.exe` fonctionnel sous Windows.
(Sur Mac il produira un `.app`, sur Linux un binaire ELF — PyInstaller compile
toujours pour l'OS courant.)

## Installation (une seule fois)

1. Installe Python (3.9+) depuis https://python.org si ce n'est pas déjà fait.
   Pendant l'installation, cocher **"Add Python to PATH"**.

2. Ouvre une invite de commande (`cmd` ou PowerShell) dans le dossier contenant
   `ExeCraft.pyw`, puis installe les dépendances :

   ```
   pip install -r requirements.txt
   ```

   (ExeCraft essaiera aussi de les installer automatiquement au démarrage
   s'il détecte qu'elles manquent.)

## Utilisation

1. Lance ExeCraft, soit :
   - en double-cliquant sur `ExeCraft.pyw` (l'extension `.pyw` lance
     l'application sans faire apparaître de fenêtre de console) ;
   - soit depuis une invite de commande :

     ```
     pythonw ExeCraft.pyw
     ```

2. Clique sur **"Parcourir..."** et choisis ton fichier `.py` ou `.html`.

3. Donne un nom à ton application (ce sera le nom du `.exe`).

4. Clique sur **"Convertir en EXE"**.

5. Une fois terminé, ton `.exe` se trouve dans un **nouveau dossier portant
   le nom de ton application** :
   - Pour un fichier **HTML** : ce dossier est créé dans **Téléchargements**
     et s'appelle **"NomApplication EXE"**
     (`Téléchargements\MonOutil EXE\MonOutil.exe`).
   - Pour un fichier **Python (.py)** : ce dossier est créé juste à côté du
     fichier source (`C:\Projets\MonOutil\MonOutil.exe`).

   Aucun fichier temporaire de compilation (`build`, `.spec`, etc.) n'est
   laissé à côté — tout est nettoyé automatiquement.

## Notes utiles

- Pour une page HTML qui utilise des fichiers CSS/JS/images situés dans le
  même dossier, ExeCraft copie automatiquement ces ressources (extensions
  `.css`, `.js`, `.json`, images, polices, médias) pour que l'application
  fonctionne hors ligne. Les autres fichiers du dossier (vidéos, documents,
  autres pages, etc. sans rapport avec le HTML) ne sont **pas** copiés,
  notamment si ton HTML se trouve dans un dossier très rempli comme
  Téléchargements. Si un fichier pose problème pendant la copie (chemin
  trop long, verrouillé...), il est ignoré et signalé dans le journal
  plutôt que de faire échouer toute la conversion.
- Coche **"Afficher une console"** si tu veux voir les messages d'erreur de
  ton script au moment de l'exécution (utile pour déboguer).
- La première conversion peut prendre 1 à 2 minutes (PyInstaller doit
  analyser toutes les dépendances).
- L'antivirus Windows peut parfois signaler à tort les `.exe` créés par
  PyInstaller (faux positif très courant). Rien d'anormal, mais garde-le en tête.

## ⚠️ Ne convertis pas ExeCraft lui-même !

Si tu essaies de transformer `ExeCraft.pyw` (cet outil) en `.exe`, l'exécutable
va s'ouvrir en boucle à l'infini. Ce n'est pas un bug lié à
`multiprocessing` mais une conséquence directe de son fonctionnement :

- ExeCraft appelle `sys.executable` pour lancer `pip install` et
  `PyInstaller` en sous-processus.
- Une fois figé en `.exe`, `sys.executable` désigne l'exe lui-même (et
  non plus un vrai `python.exe`).
- Résultat : au démarrage, l'outil essaie de "relancer Python" mais
  relance en réalité une nouvelle copie de lui-même, qui fait pareil,
  etc.

**Utilise toujours ExeCraft avec `pythonw ExeCraft.pyw`** (ou en double-
cliquant dessus), jamais sous forme de `.exe` — c'est avec lui que tu
convertis *tes autres* fichiers `.py` ou `.html`. Une protection est
intégrée dans le script : s'il détecte qu'il tourne en tant qu'exe figé,
il affiche un message d'erreur clair au lieu de boucler.

## Problème fréquent : l'appli convertie s'ouvre en boucle à l'infini

C'est un bug connu de **PyInstaller en mode `--onefile` sur Windows** : sans
l'appel à `multiprocessing.freeze_support()`, l'exécutable relance une
nouvelle instance de lui-même dès qu'il démarre (souvent en lien avec
`multiprocessing`, des threads, ou certaines librairies GUI comme
`pywebview`).

**ExeCraft corrige ce problème automatiquement**, pour les deux types de
conversion :
- Pour un `.py` : le correctif est injecté tout en haut d'une copie
  temporaire de ton script avant compilation (ton fichier original n'est
  jamais modifié).
- Pour un `.html` : le correctif est déjà dans le modèle du wrapper
  pywebview généré.

Si tu avais généré un `.exe` avec une version précédente d'ExeCraft et que
le problème persiste :

1. Supprime l'ancien dossier de sortie (celui qui porte le nom de
   l'application) ainsi que tout `build`/`dist`/`.spec` restant d'une
   conversion précédente.
2. Remplace `ExeCraft.pyw` par cette version mise à jour et relance la
   conversion.

Si le problème persiste malgré tout, c'est probablement que ton script
Python relance lui-même une nouvelle fenêtre/processus dans son propre
code (par exemple `subprocess.Popen(sys.argv[0])`, un rechargement
automatique de type "auto-reload", ou une boucle d'événements imbriquée).
Dans ce cas, il faut regarder le code du script lui-même.
