/* Tableaux « comme dans Excel », sur tous les tableaux de données :
   - clic sur un en-tête = tri croissant, second clic = décroissant (sauf tableaux déjà triés par le serveur) ;
   - bord droit d'un en-tête à glisser = largeur de la colonne (mémorisée sur cet ordinateur) ;
   - bouton ▾ d'un en-tête = choisir les valeurs à garder dans cette colonne (cases à cocher, recherche) ;
   - case « Filtrer ce tableau… » au-dessus des tableaux de plus de 8 lignes.
   Les lignes de total (tr.total) restent en bas. Exclure un tableau : class="sans-outils" ; ne pas trier : data-tri="non". */
(function () {
  "use strict";
  var sansAccent = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
  var lire = function (k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
  var ecrire = function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* rien */ } };

  function valeur(cellule) {
    var t = (cellule && (cellule.dataset.tri || cellule.textContent) || "").trim();
    var d = t.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    if (d) return { n: +(d[3] + d[2] + d[1]) };
    var m = t.replace(/[\s  ₪%]/g, "").replace("−", "-").replace(",", ".");
    if (/^-?\d+(\.\d+)?$/.test(m)) return { n: parseFloat(m) };
    return { t: t };
  }

  function comparer(a, b) {
    if (a.n !== undefined && b.n !== undefined) return a.n - b.n;
    if (a.t === "" && b.t !== "") return 1;           // vides en bas
    if (b.t === "" && a.t !== "") return -1;
    return String(a.t !== undefined ? a.t : a.n).localeCompare(String(b.t !== undefined ? b.t : b.n), "fr",
                                                             { numeric: true, sensitivity: "base" });
  }

  var texte = function (c) { return (c ? c.textContent : "").trim().replace(/\s+/g, " "); };

  function preparer(table, rang) {
    if (table.dataset.outils) return;
    var entete = Array.prototype.find.call(table.rows, function (r) { return r.querySelector("th"); });
    if (!entete || table.closest(".sans-outils") || table.classList.contains("sans-outils")) return;
    table.dataset.outils = "1";
    var donnees = function () {
      return Array.prototype.filter.call(table.rows, function (r) {
        return r !== entete && !r.classList.contains("total") && !r.querySelector("th") && r.cells.length >= entete.cells.length;
      });
    };
    var groupes = table.querySelector("tr.sit-compte, tr.sit-sous-total");      // tableau à sous-totaux : ni tri ni filtre
    var cle = "comptabb-colonnes:" + location.pathname + ":" + rang;
    var largeurs = lire(cle) || {};
    var choix = {};                                                              // colonne -> valeurs gardées
    var champGlobal = null, compte = null;

    function appliquer() {
      var mots = champGlobal ? sansAccent(champGlobal.value).split(/\s+/).filter(Boolean) : [], vues = 0, rs = donnees();
      rs.forEach(function (r) {
        var ok = mots.every(function (m) { return sansAccent(r.textContent).indexOf(m) >= 0; });
        Object.keys(choix).forEach(function (i) { if (ok && !choix[i].has(texte(r.cells[i]))) ok = false; });
        r.style.display = ok ? "" : "none";
        if (ok) vues++;
      });
      var actif = mots.length || Object.keys(choix).length;
      if (compte) compte.textContent = actif ? vues + " / " + rs.length + " lignes" : "";
      Array.prototype.forEach.call(entete.cells, function (th, i) { th.classList.toggle("filtre-actif", !!choix[i]); });
    }

    Array.prototype.forEach.call(entete.cells, function (th, i) {
      if (!th.textContent.trim()) return;
      th.classList.add("outils");
      if (largeurs[i]) { th.style.width = largeurs[i] + "px"; th.style.minWidth = largeurs[i] + "px"; }
      // tri (sauf tri déjà fait par le serveur : lien dans l'en-tête)
      var serveur = th.querySelector("a");
      if (!serveur && !groupes && table.dataset.tri !== "non" && !th.classList.contains("sans-tri")) {
        th.classList.add("tri");
        th.title = "Trier";
        th.addEventListener("click", function (e) {
          if (e.target.closest(".poignee, .choix-colonne, .menu-colonne")) return;
          var sens = th.dataset.sens === "asc" ? "desc" : "asc";
          Array.prototype.forEach.call(entete.cells, function (x) { delete x.dataset.sens; });
          th.dataset.sens = sens;
          var rs = donnees();
          rs.sort(function (a, b) { var r = comparer(valeur(a.cells[i]), valeur(b.cells[i])); return sens === "asc" ? r : -r; });
          var totaux = Array.prototype.filter.call(table.rows, function (r) { return r.classList.contains("total"); });
          var parent = rs.length ? rs[0].parentNode : entete.parentNode;
          rs.forEach(function (r) { parent.appendChild(r); });
          totaux.forEach(function (r) { r.parentNode.appendChild(r); });
        });
      }
      // choix des valeurs de la colonne (comme le filtre d'Excel)
      if (!groupes && donnees().length > 1) {
        var bouton = document.createElement("span");
        bouton.className = "choix-colonne";
        bouton.textContent = "▾";
        bouton.title = "Choisir les valeurs à afficher";
        th.appendChild(bouton);
        bouton.addEventListener("click", function (e) {
          e.stopPropagation();
          document.querySelectorAll(".menu-colonne").forEach(function (m) { m.remove(); });
          var valeurs = Array.from(new Set(donnees().map(function (r) { return texte(r.cells[i]); })))
            .sort(function (a, b) { return comparer(valeur({ textContent: a, dataset: {} }), valeur({ textContent: b, dataset: {} })); });
          var menu = document.createElement("div");
          menu.className = "menu-colonne";
          var recherche = document.createElement("input");
          recherche.type = "search";
          recherche.placeholder = "Rechercher…";
          menu.appendChild(recherche);
          var tous = document.createElement("label");
          tous.innerHTML = '<input type="checkbox"> <b>(Tout sélectionner)</b>';
          menu.appendChild(tous);
          var liste = document.createElement("div");
          liste.className = "valeurs";
          valeurs.slice(0, 500).forEach(function (v) {
            var l = document.createElement("label");
            var c = document.createElement("input");
            c.type = "checkbox";
            c.value = v;
            c.checked = !choix[i] || choix[i].has(v);
            l.appendChild(c);
            l.appendChild(document.createTextNode(" " + (v || "(vide)")));
            liste.appendChild(l);
          });
          menu.appendChild(liste);
          var boutons = document.createElement("div");
          boutons.className = "boutons-colonne";
          boutons.innerHTML = '<button type="button" class="principal">OK</button> <button type="button">Effacer le filtre</button>';
          menu.appendChild(boutons);
          var cases = function () { return Array.from(liste.querySelectorAll("input")).filter(function (c) { return c.parentNode.style.display !== "none"; }); };
          var majTous = function () { tous.firstChild.checked = cases().every(function (c) { return c.checked; }); };
          majTous();
          tous.firstChild.addEventListener("change", function () { cases().forEach(function (c) { c.checked = tous.firstChild.checked; }); });
          liste.addEventListener("change", majTous);
          recherche.addEventListener("input", function () {
            var m = sansAccent(recherche.value);
            liste.querySelectorAll("label").forEach(function (l) { l.style.display = sansAccent(l.textContent).indexOf(m) >= 0 ? "" : "none"; });
            majTous();
          });
          boutons.children[0].addEventListener("click", function () {
            var gardees = Array.from(liste.querySelectorAll("input:checked")).map(function (c) { return c.value; });
            if (gardees.length === valeurs.length) delete choix[i]; else choix[i] = new Set(gardees);
            menu.remove();
            appliquer();
          });
          boutons.children[1].addEventListener("click", function () { delete choix[i]; menu.remove(); appliquer(); });
          menu.addEventListener("click", function (e) { e.stopPropagation(); });
          document.body.appendChild(menu);
          var r = bouton.getBoundingClientRect();
          menu.style.left = Math.max(8, Math.min(r.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - menu.offsetWidth - 8)) + "px";
          menu.style.top = (r.bottom + window.scrollY + 4) + "px";
          recherche.focus();
        });
      }
      // largeur réglable : poignée sur le bord droit de l'en-tête
      var poignee = document.createElement("span");
      poignee.className = "poignee";
      poignee.title = "Glisser pour régler la largeur (double clic : largeur automatique)";
      th.appendChild(poignee);
      poignee.addEventListener("click", function (e) { e.stopPropagation(); });
      poignee.addEventListener("dblclick", function (e) {
        e.stopPropagation();
        th.style.width = th.style.minWidth = "";
        delete largeurs[i];
        ecrire(cle, largeurs);
      });
      poignee.addEventListener("mousedown", function (e) {
        e.preventDefault();
        var x0 = e.clientX, l0 = th.offsetWidth;
        var bouger = function (ev) { var l = Math.max(40, l0 + ev.clientX - x0); th.style.width = th.style.minWidth = l + "px"; };
        var lacher = function () {
          document.removeEventListener("mousemove", bouger);
          document.removeEventListener("mouseup", lacher);
          largeurs[i] = th.offsetWidth;
          ecrire(cle, largeurs);
        };
        document.addEventListener("mousemove", bouger);
        document.addEventListener("mouseup", lacher);
      });
    });

    if (!groupes && donnees().length >= 8 && table.dataset.filtre !== "non") {
      champGlobal = document.createElement("input");
      champGlobal.type = "search";
      champGlobal.placeholder = "Filtrer ce tableau…";
      champGlobal.className = "filtre-tableau";
      compte = document.createElement("span");
      compte.className = "aide";
      var boite = document.createElement("div");
      boite.className = "barre-filtre";
      boite.appendChild(champGlobal);
      boite.appendChild(compte);
      table.parentNode.insertBefore(boite, table);
      champGlobal.addEventListener("input", appliquer);
    }
  }

  function tout() {
    document.querySelectorAll("main table").forEach(preparer);
    document.addEventListener("click", function () { document.querySelectorAll(".menu-colonne").forEach(function (m) { m.remove(); }); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", tout); else tout();
})();
