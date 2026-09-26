/* Tableaux « comme dans Excel » : clic sur un en-tête = tri croissant, second clic = décroissant ;
   une case « Filtrer » au-dessus ne garde que les lignes qui contiennent le texte tapé.
   S'applique à <table class="triable"> ; les lignes de total (tr.total) restent en bas. */
(function () {
  "use strict";
  var sansAccent = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };

  function valeur(cellule) {
    var t = (cellule && (cellule.dataset.tri || cellule.textContent) || "").trim();
    var d = t.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    if (d) return { n: +(d[3] + d[2] + d[1]) };
    var m = t.replace(/[\s  ₪%]/g, "").replace("−", "-").replace(",", ".");
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

  function preparer(table) {
    var lignes = Array.prototype.slice.call(table.rows);
    var entete = lignes.find(function (r) { return r.querySelector("th"); });
    if (!entete) return;
    var corps = entete.parentNode;
    var donnees = function () {
      return Array.prototype.slice.call(table.rows).filter(function (r) { return r !== entete && !r.classList.contains("total") && !r.querySelector("th"); });
    };
    Array.prototype.forEach.call(entete.cells, function (th, i) {
      if (th.classList.contains("sans-tri") || !th.textContent.trim()) return;
      th.classList.add("tri");
      th.title = "Trier";
      th.addEventListener("click", function () {
        var sens = th.dataset.sens === "asc" ? "desc" : "asc";
        Array.prototype.forEach.call(entete.cells, function (x) { delete x.dataset.sens; });
        th.dataset.sens = sens;
        var rs = donnees();
        var idx = i;
        rs.sort(function (a, b) {
          var r = comparer(valeur(a.cells[idx]), valeur(b.cells[idx]));
          return sens === "asc" ? r : -r;
        });
        var totaux = Array.prototype.filter.call(table.rows, function (r) { return r.classList.contains("total"); });
        var parent = rs.length ? rs[0].parentNode : corps;
        rs.forEach(function (r) { parent.appendChild(r); });
        totaux.forEach(function (r) { r.parentNode.appendChild(r); });
      });
    });
    if (donnees().length < 8 || table.dataset.filtre === "non") return;
    var champ = document.createElement("input");
    champ.type = "search";
    champ.placeholder = "Filtrer ce tableau…";
    champ.className = "filtre-tableau";
    var compte = document.createElement("span");
    compte.className = "aide";
    var boite = document.createElement("div");
    boite.className = "barre-filtre";
    boite.appendChild(champ);
    boite.appendChild(compte);
    table.parentNode.insertBefore(boite, table);
    champ.addEventListener("input", function () {
      var mots = sansAccent(champ.value).split(/\s+/).filter(Boolean), vues = 0, rs = donnees();
      rs.forEach(function (r) {
        var ok = mots.every(function (m) { return sansAccent(r.textContent).indexOf(m) >= 0; });
        r.style.display = ok ? "" : "none";
        if (ok) vues++;
      });
      compte.textContent = mots.length ? vues + " / " + rs.length + " lignes" : "";
    });
  }

  function tout() { document.querySelectorAll("table.triable").forEach(preparer); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", tout); else tout();
})();
