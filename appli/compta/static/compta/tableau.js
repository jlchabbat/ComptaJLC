/* Tableaux « comme dans Excel » (suite de tri.js), sur les tableaux de données :
   - bouton « Colonnes ▾ » : afficher ou masquer des colonnes (choix mémorisé sur cet ordinateur) ;
   - sélection de cellules : clic, glisser, Maj+clic (plage), Ctrl+clic (cellule isolée) ; Échap efface ;
   - barre en bas de l'écran : nombre de cellules, somme, moyenne, minimum et maximum des montants sélectionnés ;
   - Ctrl+C copie la sélection (colonnes séparées par des tabulations, collables dans Excel).
   Exclure un tableau : class="sans-outils". Les tableaux à en-tête fusionné n'ont pas le choix des colonnes. */
(function () {
  "use strict";
  var lire = function (k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
  var ecrire = function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* rien */ } };
  var format = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var interactif = "a, button, input, select, textarea, label, .choix-colonne, .poignee, .menu-colonne, .menu-colonnes";

  // montant d'une cellule, ou null (même lecture que le tri : espaces, ₪, virgule décimale, signe moins typographique)
  function nombre(cellule) {
    var t = (cellule.dataset.tri || cellule.textContent || "").trim();
    if (/^\d{2}\/\d{2}\/\d{4}/.test(t)) return null;
    var negatif = /^\(.*\)$/.test(t);
    var m = t.replace(/[()\s  ₪€$£%]/g, "").replace("−", "-").replace(",", ".");
    if (!/^-?\d+(\.\d+)?$/.test(m)) return null;
    var v = parseFloat(m);
    return negatif ? -Math.abs(v) : v;
  }

  var selection = [], ancre = null, glisse = false, tableActive = null, barre = null;

  function creerBarre() {
    barre = document.createElement("div");
    barre.id = "barre-selection";
    barre.hidden = true;
    document.body.appendChild(barre);
  }

  function majBarre() {
    selection.forEach(function (c) { c.classList.add("sel"); });
    if (!selection.length) { barre.hidden = true; return; }
    var nb = selection.map(nombre).filter(function (v) { return v !== null; });
    var somme = nb.reduce(function (a, b) { return a + b; }, 0), html = selection.length + " cellule" + (selection.length > 1 ? "s" : "");
    if (nb.length) {
      html += " · <b>Somme " + format.format(somme) + "</b> · Moyenne " + format.format(somme / nb.length) +
              " · Min " + format.format(Math.min.apply(null, nb)) + " · Max " + format.format(Math.max.apply(null, nb)) +
              " · " + nb.length + " montant" + (nb.length > 1 ? "s" : "");
    }
    barre.innerHTML = html + ' <span class="aide">(Ctrl+C : copier · Échap : effacer)</span>';
    barre.hidden = false;
  }

  function effacer() {
    selection.forEach(function (c) { c.classList.remove("sel"); });
    selection = [];
    ancre = null;
    majBarre();
  }

  function visibles(table) {
    return Array.prototype.filter.call(table.rows, function (r) {
      return !r.querySelector("th") && !r.classList.contains("total") && r.style.display !== "none";
    });
  }

  function plage(table, a, b) {
    var rs = visibles(table), ia = rs.indexOf(a.parentNode), ib = rs.indexOf(b.parentNode);
    if (ia < 0 || ib < 0) return [b];
    var r0 = Math.min(ia, ib), r1 = Math.max(ia, ib), c0 = Math.min(a.cellIndex, b.cellIndex), c1 = Math.max(a.cellIndex, b.cellIndex), res = [];
    for (var i = r0; i <= r1; i++) {
      for (var j = c0; j <= c1; j++) {
        var c = rs[i].cells[j];
        if (c && c.style.display !== "none") res.push(c);
      }
    }
    return res;
  }

  function cellule(e) {
    if (e.target.closest(interactif)) return null;
    var c = e.target.closest("td");
    if (!c || !c.closest("main") || c.closest(".sans-outils")) return null;
    var table = c.closest("table");
    if (!table || table.classList.contains("sans-outils") || !table.dataset.outils || c.colSpan > 1) return null;
    return c;
  }

  document.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    var c = cellule(e);
    if (!c) { if (!e.target.closest("#barre-selection")) effacer(); return; }
    var table = c.closest("table");
    if (tableActive && tableActive !== table) effacer();
    tableActive = table;
    if (e.shiftKey && ancre) {
      e.preventDefault();
      selection.forEach(function (x) { x.classList.remove("sel"); });
      selection = plage(table, ancre, c);
    } else if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      var i = selection.indexOf(c);
      if (i >= 0) { selection[i].classList.remove("sel"); selection.splice(i, 1); } else selection.push(c);
      ancre = c;
    } else {
      selection.forEach(function (x) { x.classList.remove("sel"); });
      selection = [c];
      ancre = c;
      glisse = true;
    }
    majBarre();
  });

  document.addEventListener("mouseover", function (e) {
    if (!glisse || !ancre) return;
    var c = e.target.closest && e.target.closest("td");
    if (!c || c.closest("table") !== tableActive) return;
    selection.forEach(function (x) { x.classList.remove("sel"); });
    selection = plage(tableActive, ancre, c);
    majBarre();
    if (selection.length > 1) window.getSelection().removeAllRanges();
  });

  document.addEventListener("mouseup", function () { glisse = false; });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") effacer();
    if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C") && selection.length &&
        !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) && !String(window.getSelection()).trim()) {
      var lignes = [], rs = visibles(tableActive);
      rs.forEach(function (r) {
        var cs = selection.filter(function (c) { return c.parentNode === r; }).sort(function (a, b) { return a.cellIndex - b.cellIndex; });
        if (cs.length) lignes.push(cs.map(function (c) { return c.textContent.trim().replace(/\s+/g, " "); }).join("\t"));
      });
      var texte = lignes.join("\n");
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texte);
      e.preventDefault();
    }
  });

  // ---- choix des colonnes
  function colonnes(table, rang) {
    var entete = Array.prototype.find.call(table.rows, function (r) { return r.querySelector("th"); });
    if (!entete || !table.dataset.outils) return;
    var n = entete.cells.length;
    // en-tête simple (ni colonnes ni lignes fusionnées) ; les lignes de total ou de remarque peuvent fusionner des colonnes
    var simple = !entete.querySelector("th[colspan], td[colspan], th[rowspan], td[rowspan]") && !table.querySelector("td[rowspan]");
    if (!simple || n < 2 || table.querySelector("tr.sit-compte, tr.sit-sous-total")) return;
    var cle = "comptajlc-masquees:" + location.pathname + ":" + rang, masquees = lire(cle) || [];
    var titre = function (i) { return (entete.cells[i].textContent || "").replace(/[▾▴▲▼]/g, "").trim() || "(colonne " + (i + 1) + ")"; };

    function appliquer() {
      Array.prototype.forEach.call(table.rows, function (r) {
        var i = 0;
        Array.prototype.forEach.call(r.cells, function (c) {
          var s = c.dataset.span ? +c.dataset.span : c.colSpan, vues = 0;
          if (s > 1) c.dataset.span = s;
          for (var k = i; k < i + s && k < n; k++) if (masquees.indexOf(k) < 0) vues++;
          c.style.display = vues ? "" : "none";
          if (s > 1 && vues) c.colSpan = vues;                 // la cellule fusionnée se réduit aux colonnes visibles
          i += s;
        });
      });
      bouton.classList.toggle("filtre-actif", masquees.length > 0);
      bouton.textContent = masquees.length ? "Colonnes (" + masquees.length + " masquée" + (masquees.length > 1 ? "s" : "") + ") ▾" : "Colonnes ▾";
    }

    var bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "choix-colonnes";
    bouton.title = "Afficher ou masquer des colonnes";
    bouton.addEventListener("click", function (e) {
      e.stopPropagation();
      document.querySelectorAll(".menu-colonnes, .menu-colonne").forEach(function (m) { m.remove(); });
      var menu = document.createElement("div");
      menu.className = "menu-colonnes";
      for (var i = 0; i < n; i++) {
        var l = document.createElement("label"), c = document.createElement("input");
        c.type = "checkbox";
        c.checked = masquees.indexOf(i) < 0;
        c.dataset.col = i;
        l.appendChild(c);
        l.appendChild(document.createTextNode(" " + titre(i)));
        menu.appendChild(l);
      }
      var bas = document.createElement("div");
      bas.className = "boutons-colonne";
      bas.innerHTML = '<button type="button">Tout afficher</button>';
      menu.appendChild(bas);
      menu.addEventListener("change", function (ev) {
        var cases = Array.from(menu.querySelectorAll("input"));
        if (cases.every(function (x) { return !x.checked; })) ev.target.checked = true;          // au moins une colonne reste affichée
        masquees = cases.filter(function (x) { return !x.checked; }).map(function (x) { return +x.dataset.col; });
        ecrire(cle, masquees);
        appliquer();
        effacer();
      });
      bas.firstChild.addEventListener("click", function () {
        masquees = [];
        ecrire(cle, masquees);
        menu.querySelectorAll("input").forEach(function (x) { x.checked = true; });
        appliquer();
        effacer();
      });
      menu.addEventListener("click", function (ev) { ev.stopPropagation(); });
      document.body.appendChild(menu);
      var r = bouton.getBoundingClientRect();
      menu.style.left = Math.max(8, Math.min(r.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - menu.offsetWidth - 8)) + "px";
      menu.style.top = (r.bottom + window.scrollY + 4) + "px";
    });

    var boite = table.previousElementSibling;
    if (!boite || !boite.classList.contains("barre-filtre")) {
      boite = document.createElement("div");
      boite.className = "barre-filtre";
      table.parentNode.insertBefore(boite, table);
    }
    boite.appendChild(bouton);
    appliquer();
  }

  function tout() {
    creerBarre();
    document.querySelectorAll("main table").forEach(colonnes);
    document.addEventListener("click", function () { document.querySelectorAll(".menu-colonnes").forEach(function (m) { m.remove(); }); });
  }
  // tri.js s'exécute avant (même ordre dans base.html) : ses tableaux portent data-outils
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", tout); else tout();
})();
