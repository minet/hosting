# Guide de contribution
---

## 1. Créer une issue

Avant tout changement, **créez une issue** décrivant votre ajout ou correction de bug. Cela permet d'assurer un suivi clair de chaque modification.

- Donnez un titre explicite à votre issue.
- Ajoutez les **labels appropriés** selon le type de changement (feature, bug, backend, frontend, etc.) et la partie du projet concernée.
- **Assignez l'issue** à vous-même.

---

## 2. Créer une branche

Une fois l'issue créée, créez une branche dédiée :

1. Depuis l'issue, cliquez sur la flèche à côté du bouton **"Create merge request"**.
2. Sélectionnez **"Create branch"**.
3. Assurez-vous que la branche est basée sur **`preprod`**.

---

## 3. Effectuer vos changements

Travaillez sur votre branche et effectuez vos modifications. Une fois terminé, **vérifiez que l'environnement `preprod` fonctionne correctement** via un merge request sur la preprod avec vos changements.

---

## 4. Ouvrir une Merge Request

Quand tout est en ordre, ouvrez une **Merge Request vers la branche `main`**.