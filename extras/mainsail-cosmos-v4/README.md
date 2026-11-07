# COSMOS Mainsail Theme V4

Thème Mainsail intégré au firmware COSMOS pour Elegoo Centauri Carbon.

## Contenu
- `custom.css` : thème sombre « smoke glass », transparence, relief 3D, ombres et reflets bleus.
- `cosmos-starfield.svg` : fond étoilé vertical avec nébuleuse et horizon planétaire, sans texte ni logo.

## Installation dans COSMOS
Le recipe Yocto Mainsail installe automatiquement les deux fichiers dans :

`/etc/klipper/config/.theme/`

Le thème est donc livré avec l'image COSMOS. Aucun chemin Raspberry Pi `~/printer_data/config` n'est utilisé sur cette cible.

Après installation d'une nouvelle image, actualiser Mainsail avec un rechargement forcé du navigateur (Ctrl+F5). Les paramètres et macros Mainsail existants restent conservés.

## Développement manuel
Pour tester le thème sans reconstruire l'image, copier `custom.css` et `cosmos-starfield.svg` dans `/etc/klipper/config/.theme/`, puis recharger Mainsail.

Ce thème ne modifie ni Klipper, ni Moonraker, ni les GPIO, ni les paramètres de mouvement de l'imprimante.
