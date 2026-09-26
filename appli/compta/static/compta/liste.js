/* Listes déroulantes cherchables : on tape une partie du code OU du libellé.
   S'applique à tout <select data-cherchable> ; la liste d'origine reste dans le formulaire
   (masquée) : c'est elle qui est envoyée. Les options masquées (hidden) sont ignorées. */
(function () {
  "use strict";
  var sansAccent = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
  var MAX = 300;

  function ameliorer(sel) {
    var boite = document.createElement("div");
    var champ = document.createElement("input");
    var liste = document.createElement("ul");
    boite.className = "liste-cherchable";
    champ.type = "text";
    champ.autocomplete = "off";
    champ.placeholder = sel.dataset.cherchable || "Code ou libellé…";
    champ.setAttribute("role", "combobox");
    liste.hidden = true;
    liste.setAttribute("role", "listbox");
    if (sel.id) {
      champ.id = sel.id + "_recherche";
      var etiquette = document.querySelector('label[for="' + sel.id + '"]');
      if (etiquette) etiquette.htmlFor = champ.id;
    }
    sel.parentNode.insertBefore(boite, sel);
    boite.appendChild(champ);
    boite.appendChild(liste);
    boite.appendChild(sel);
    sel.hidden = true;
    var actif = -1;

    function texteChoisi() {
      var o = sel.options[sel.selectedIndex];
      return o && o.value ? o.text : "";
    }
    function afficher(filtre) {
      var mots = sansAccent(filtre).split(/\s+/).filter(Boolean);
      liste.innerHTML = "";
      actif = -1;
      var n = 0;
      for (var i = 0; i < sel.options.length && n < MAX; i++) {
        var o = sel.options[i];
        if (o.hidden || o.disabled) continue;
        var t = sansAccent(o.text + " " + o.value);
        if (!mots.every(function (m) { return t.indexOf(m) >= 0; })) continue;
        var li = document.createElement("li");
        li.textContent = o.value ? o.text : "(aucun)";
        li.dataset.valeur = o.value;
        li.setAttribute("role", "option");
        if (o.value === sel.value) li.className = "choisi";
        liste.appendChild(li);
        n++;
      }
      if (!n) {
        var vide = document.createElement("li");
        vide.className = "vide";
        vide.textContent = "Aucun résultat";
        liste.appendChild(vide);
      }
      liste.hidden = false;
    }
    function choisir(valeur) {
      if (sel.value !== valeur) {
        sel.value = valeur;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
      champ.value = texteChoisi();
      liste.hidden = true;
    }
    function surligner(i) {
      var items = liste.querySelectorAll("li[data-valeur]");
      if (!items.length) return;
      actif = (i + items.length) % items.length;
      items.forEach(function (li, k) { li.classList.toggle("actif", k === actif); });
      items[actif].scrollIntoView({ block: "nearest" });
    }

    champ.value = texteChoisi();
    function ouvrir() { champ.select(); afficher(""); }
    champ.addEventListener("focus", ouvrir);
    champ.addEventListener("click", function () { if (liste.hidden) ouvrir(); });
    champ.addEventListener("input", function () { afficher(champ.value); });
    champ.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (liste.hidden) afficher(champ.value); surligner(actif + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); surligner(actif - 1); }
      else if (e.key === "Enter" && !liste.hidden) {
        var items = liste.querySelectorAll("li[data-valeur]");
        var li = items[actif >= 0 ? actif : 0];
        if (li) { e.preventDefault(); choisir(li.dataset.valeur); }
      } else if (e.key === "Escape") { champ.value = texteChoisi(); liste.hidden = true; }
    });
    champ.addEventListener("blur", function () {
      setTimeout(function () {
        // texte effacé : on vide le choix si la liste le permet ; sinon on remet le choix en cours
        if (!champ.value.trim() && Array.prototype.some.call(sel.options, function (o) { return o.value === ""; })) choisir("");
        champ.value = texteChoisi();
        liste.hidden = true;
      }, 150);
    });
    liste.addEventListener("mousedown", function (e) {
      var li = e.target.closest("li[data-valeur]");
      if (li) { e.preventDefault(); choisir(li.dataset.valeur); }
    });
    sel.addEventListener("change", function () { champ.value = texteChoisi(); });
    sel.majListe = function () { champ.value = texteChoisi(); };
  }

  function tout() { document.querySelectorAll("select[data-cherchable]").forEach(ameliorer); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", tout); else tout();
})();
