/* Tableaux « façon Excel » : tri, filtres par colonne, recherche, largeur des colonnes,
   sélection de lignes, copie vers Excel, totaux. S'applique à table.grille (thead + tbody). */
(function () {
  'use strict';
  var NOMBRE = /^-?\d[\d\s  ]*([.,]\d+)?$/;

  function norm(t) { return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function nombre(v) {
    v = String(v == null ? '' : v).trim();
    if (!NOMBRE.test(v)) return NaN;
    return parseFloat(v.replace(/[\s  ]/g, '').replace(',', '.'));
  }
  function fmt(c) {                       // centimes -> « 1 234,56 »
    var neg = c < 0, v = Math.abs(Math.round(c)), e = Math.floor(v / 100), d = String(v % 100);
    return (neg ? '-' : '') + String(e).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ',' + (d.length < 2 ? '0' + d : d);
  }
  function texte(td) {
    var c = td.querySelector('select, input:not([type=checkbox]):not([type=hidden])');
    if (c) return c.tagName === 'SELECT' ? (c.selectedIndex >= 0 ? c.options[c.selectedIndex].text : '') : c.value;
    var cb = td.querySelector('input[type=checkbox]:not(.gsel)');
    if (cb) return cb.checked ? 'oui' : 'non';
    return td.textContent.replace(/\s+/g, ' ').trim();
  }
  function valeur(td) { return td.dataset.v !== undefined ? td.dataset.v : texte(td); }
  function cible(e) { return e.target.closest('a, input, select, button, label, summary, textarea'); }

  function init(table, num) {
    if (!table.tHead || !table.tBodies.length) return;
    var tbody = table.tBodies[0], entete = table.tHead.rows[0], ths = Array.prototype.slice.call(entete.cells);
    var n = ths.length, cle = 'grille:' + location.pathname + ':' + (table.id || num);
    var lignes = function () { return Array.prototype.slice.call(tbody.rows); };
    lignes().forEach(function (r, i) { r.dataset.i = i; });
    var serveur = table.querySelector('tfoot.serveur'); if (serveur) serveur.remove();

    /* ---- enveloppe, barre d'outils, défilement ---- */
    var wrap = document.createElement('div'); wrap.className = 'gwrap';
    var barre = document.createElement('div'); barre.className = 'gbarre';
    barre.innerHTML = '<input type="search" class="gsearch" placeholder="Rechercher dans le tableau…" aria-label="Rechercher">' +
      '<button type="button" class="gclear">Effacer filtres et tri</button>' +
      '<button type="button" class="gcopy" title="Copie les lignes sélectionnées (ou toutes les lignes affichées) pour les coller dans Excel">Copier</button>' +
      '<span class="gcount"></span>';
    var scroll = document.createElement('div'); scroll.className = 'gscroll';
    table.parentNode.insertBefore(wrap, table); wrap.appendChild(barre); wrap.appendChild(scroll); scroll.appendChild(table);
    var search = barre.querySelector('.gsearch'), count = barre.querySelector('.gcount');

    /* ---- ligne de filtres ---- */
    var frow = document.createElement('tr'); frow.className = 'gfiltre';
    ths.forEach(function (th) {
      var td = document.createElement('td');
      if (!th.classList.contains('nf')) {
        var i = document.createElement('input'); i.type = 'text'; i.placeholder = 'filtrer'; i.setAttribute('aria-label', 'Filtre ' + th.textContent.trim());
        i.addEventListener('input', appliquer); td.appendChild(i);
      } else if (th.querySelector('.gselall')) { td.textContent = ''; }
      frow.appendChild(td);
    });
    table.tHead.appendChild(frow);

    /* ---- totaux ---- */
    var colsTot = ths.map(function (th, i) { return th.dataset.total ? i : -1; }).filter(function (i) { return i >= 0; });
    var tfoot = null, rAff = null, rSel = null;
    if (colsTot.length) {
      tfoot = table.createTFoot(); tfoot.className = 'gtot';
      rAff = tfoot.insertRow(); rSel = tfoot.insertRow(); rSel.hidden = true;
      [rAff, rSel].forEach(function (r) {            // 1 cellule d'intitulé étalée jusqu'aux colonnes totalisées, puis 1 cellule par colonne
        r.insertCell().colSpan = colsTot[0];
        for (var i = colsTot[0]; i < n; i++) r.insertCell();
      });
    }

    function totaux() {
      var vis = lignes().filter(function (r) { return !r.hidden; }), sel = vis.filter(function (r) { return r.classList.contains('sel'); });
      count.textContent = vis.length + ' ligne(s) affichée(s) sur ' + lignes().length +
        (sel.length ? ' · ' + sel.length + ' sélectionnée(s)' : '');
      if (!tfoot) return;
      function remplir(row, rs, titre) {
        Array.prototype.forEach.call(row.cells, function (c) { c.textContent = ''; c.className = ''; });
        row.cells[0].textContent = titre + ' (' + rs.length + ')';
        colsTot.forEach(function (i) {
          var s = 0; rs.forEach(function (r) { var v = nombre(valeur(r.cells[i])); if (!isNaN(v)) s += v; });
          var c = row.cells[i - colsTot[0] + 1];
          c.textContent = ths[i].dataset.total === 'cents' ? fmt(s) : String(s);
          c.className = 'n';
        });
      }
      remplir(rAff, vis, 'Total affiché');
      rSel.hidden = sel.length === 0;
      if (sel.length) remplir(rSel, sel, 'Total sélection');
      Array.prototype.forEach.call(rAff.cells, function (c) { c.style.bottom = (rSel.hidden ? 0 : rSel.offsetHeight) + 'px'; });
      document.dispatchEvent(new CustomEvent('grille:selection', { detail: { table: table } }));
    }

    /* ---- filtre ---- */
    function testeFiltre(f, td) {
      f = f.trim(); if (!f) return true;
      var m = /^(>=|<=|>|<|=|!)\s*(.*)$/.exec(f), v = valeur(td), t = norm(texte(td));
      if (m) {
        var op = m[1], ref = m[2], a = nombre(v), b = nombre(ref);
        if (op === '!') return t.indexOf(norm(ref)) < 0;
        if (!isNaN(a) && !isNaN(b)) return op === '>' ? a > b : op === '<' ? a < b : op === '>=' ? a >= b : op === '<=' ? a <= b : a === b;
        return op === '=' ? t === norm(ref) : false;
      }
      return f.split('|').some(function (alt) { return t.indexOf(norm(alt.trim())) >= 0; });
    }
    function appliquer() {
      var g = norm(search.value), fs = Array.prototype.map.call(frow.cells, function (td) { var i = td.querySelector('input'); return i ? i.value : ''; });
      lignes().forEach(function (r) {
        var ok = !g || norm(Array.prototype.map.call(r.cells, texte).join(' ')).indexOf(g) >= 0;
        for (var i = 0; ok && i < n; i++) if (fs[i] && !testeFiltre(fs[i], r.cells[i])) ok = false;
        r.hidden = !ok;
        if (!ok && r.classList.contains('sel')) pose(r, false, true);
      });
      totaux();
    }
    search.addEventListener('input', appliquer);

    /* ---- tri ---- */
    var tri = { i: -1, sens: 0 };
    function trier() {
      var rs = lignes();
      if (tri.sens === 0) rs.sort(function (a, b) { return a.dataset.i - b.dataset.i; });
      else rs.sort(function (a, b) {
        var x = valeur(a.cells[tri.i]), y = valeur(b.cells[tri.i]);
        if (x === '' || y === '') return x === y ? 0 : (x === '' ? 1 : -1);          // vides toujours en bas
        var nx = nombre(x), ny = nombre(y);
        var c = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : String(x).localeCompare(String(y), 'fr', { numeric: true, sensitivity: 'base' });
        return c * tri.sens || a.dataset.i - b.dataset.i;
      });
      rs.forEach(function (r) { tbody.appendChild(r); });
      ths.forEach(function (th, i) { th.classList.toggle('asc', i === tri.i && tri.sens === 1); th.classList.toggle('desc', i === tri.i && tri.sens === -1); });
    }
    ths.forEach(function (th, i) {
      if (th.classList.contains('nf')) return;
      th.classList.add('tri'); th.title = 'Cliquer pour trier';
      th.addEventListener('click', function (e) {
        if (e.target.classList.contains('gres')) return;
        tri.sens = tri.i === i ? (tri.sens === 1 ? -1 : tri.sens === -1 ? 0 : 1) : 1; tri.i = i; trier();
      });
    });

    /* ---- largeur des colonnes (mémorisée) ---- */
    var larg = [];
    try { larg = JSON.parse(localStorage.getItem(cle) || '[]'); } catch (e) { larg = []; }
    function fixeLargeurs() {
      var total = 0;
      ths.forEach(function (th, i) { var w = larg[i] || th.offsetWidth; th.style.width = w + 'px'; total += w; });
      table.style.width = total + 'px'; table.style.tableLayout = 'fixed';
    }
    fixeLargeurs();
    ths.forEach(function (th, i) {
      var h = document.createElement('span'); h.className = 'gres'; h.title = 'Glisser pour changer la largeur'; th.appendChild(h);
      h.addEventListener('mousedown', function (e) {
        e.preventDefault(); e.stopPropagation();
        var x0 = e.clientX, w0 = th.offsetWidth, t0 = table.offsetWidth;
        function move(ev) { var w = Math.max(28, w0 + ev.clientX - x0); th.style.width = w + 'px'; table.style.width = (t0 - w0 + w) + 'px'; larg[i] = w; }
        function up() { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
          try { localStorage.setItem(cle, JSON.stringify(ths.map(function (t) { return t.offsetWidth; }))); } catch (e) { } }
        document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
      });
      h.addEventListener('dblclick', function () { th.style.width = ''; table.style.tableLayout = 'auto'; larg[i] = 0; fixeLargeurs(); });
    });

    /* ---- sélection (clic, Ctrl/Maj + clic, cases à cocher ; une écriture = toutes ses lignes via data-group) ---- */
    var ancre = null;
    function pose(r, etat, sansTotaux) {
      var g = r.dataset.group, cibles = g ? lignes().filter(function (x) { return x.dataset.group === g; }) : [r];
      cibles.forEach(function (x) { x.classList.toggle('sel', etat); var c = x.querySelector('.gsel'); if (c) c.checked = etat; });
      if (!sansTotaux) totaux();
    }
    function toutDesel() { lignes().forEach(function (r) { r.classList.remove('sel'); var c = r.querySelector('.gsel'); if (c) c.checked = false; }); }
    tbody.addEventListener('click', function (e) {
      var r = e.target.closest('tr'); if (!r || cible(e)) return;
      var vis = lignes().filter(function (x) { return !x.hidden; });
      if (e.shiftKey && ancre && !ancre.hidden) {
        var a = vis.indexOf(ancre), b = vis.indexOf(r); if (!e.ctrlKey && !e.metaKey) toutDesel();
        vis.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function (x) { pose(x, true, true); }); totaux();
      } else if (e.ctrlKey || e.metaKey) { pose(r, !r.classList.contains('sel')); ancre = r; }
      else { var deja = r.classList.contains('sel') && lignes().filter(function (x) { return x.classList.contains('sel'); }).length === (r.dataset.group ? lignes().filter(function (x) { return x.dataset.group === r.dataset.group; }).length : 1);
        toutDesel(); pose(r, !deja); ancre = r; }
    });
    tbody.addEventListener('change', function (e) {
      if (e.target.classList.contains('gsel')) pose(e.target.closest('tr'), e.target.checked);
    });
    var tout = entete.querySelector('.gselall');
    if (tout) tout.addEventListener('change', function () {
      lignes().forEach(function (r) { if (!r.hidden) pose(r, tout.checked, true); }); totaux();
    });

    /* ---- copie (vers Excel : colonnes séparées par des tabulations) ---- */
    function copier() {
      var vis = lignes().filter(function (r) { return !r.hidden; }), sel = vis.filter(function (r) { return r.classList.contains('sel'); });
      var rs = sel.length ? sel : vis, cols = ths.map(function (th, i) { return th.classList.contains('nf') ? -1 : i; }).filter(function (i) { return i >= 0; });
      var out = [cols.map(function (i) { return ths[i].textContent.trim(); }).join('\t')];
      rs.forEach(function (r) { out.push(cols.map(function (i) { return texte(r.cells[i]).replace(/[\t\r\n]+/g, ' '); }).join('\t')); });
      var t = out.join('\n');
      function repli() { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); } catch (e) { } a.remove(); }
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).catch(repli); else repli();
      var b = barre.querySelector('.gcopy'), old = b.textContent; b.textContent = rs.length + ' ligne(s) copiée(s)'; setTimeout(function () { b.textContent = old; }, 1600);
    }
    barre.querySelector('.gcopy').addEventListener('click', copier);
    wrap.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && !String(window.getSelection())) { e.preventDefault(); copier(); }
      if (e.key === 'Escape') { toutDesel(); totaux(); }
    });
    wrap.tabIndex = 0;
    barre.querySelector('.gclear').addEventListener('click', function () {
      search.value = ''; Array.prototype.forEach.call(frow.querySelectorAll('input'), function (i) { i.value = ''; });
      tri.i = -1; tri.sens = 0; trier(); appliquer();
    });

    /* ---- en-têtes collants : la ligne de filtres se place sous l'en-tête ---- */
    function collant() {
      var h = entete.offsetHeight;
      Array.prototype.forEach.call(frow.cells, function (c) { c.style.top = h + 'px'; });
    }
    collant(); window.addEventListener('resize', collant);

    /* ---- formulaires liés à la sélection (suppression) ---- */
    table.dataset.grille = '1';
    totaux();
  }

  /* Formulaire data-grille-table="#id" data-grille-champ="mvt" : à l'envoi, ajoute un champ par écriture sélectionnée. */
  function lierFormulaires() {
    Array.prototype.forEach.call(document.querySelectorAll('form[data-grille-table]'), function (f) {
      var table = document.querySelector(f.dataset.grilleTable); if (!table) return;
      function groupes() {
        var s = {}; Array.prototype.forEach.call(table.tBodies[0].rows, function (r) { if (r.classList.contains('sel')) s[r.dataset.group || r.dataset.i] = 1; });
        return Object.keys(s);
      }
      var etiquette = f.querySelector('.gnbsel');
      function maj() { if (etiquette) etiquette.textContent = groupes().length + ' écriture(s) sélectionnée(s)'; }
      document.addEventListener('grille:selection', maj); maj();
      f.addEventListener('submit', function (e) {
        var g = groupes(); Array.prototype.forEach.call(f.querySelectorAll('input.gchamp'), function (i) { i.remove(); });
        if (!g.length) { e.preventDefault(); alert('Sélectionnez d’abord des lignes (clic, Ctrl+clic, Maj+clic ou cases à cocher).'); return; }
        g.forEach(function (v) { var i = document.createElement('input'); i.type = 'hidden'; i.className = 'gchamp'; i.name = f.dataset.grilleChamp || 'id'; i.value = v; f.appendChild(i); });
      });
    });
  }

  window.retour = function () { if (history.length > 1 && document.referrer) history.back(); else location.href = document.body.dataset.accueil || '/'; };

  document.addEventListener('DOMContentLoaded', function () {
    Array.prototype.forEach.call(document.querySelectorAll('table.grille'), init);
    lierFormulaires();
    /* menus déroulants : un seul ouvert, fermeture au clic ailleurs ou Échap */
    var menus = document.querySelectorAll('nav.menu details');
    Array.prototype.forEach.call(menus, function (d) { d.addEventListener('toggle', function () { if (d.open) Array.prototype.forEach.call(menus, function (o) { if (o !== d) o.open = false; }); }); });
    document.addEventListener('click', function (e) { if (!e.target.closest('nav.menu details')) Array.prototype.forEach.call(menus, function (o) { o.open = false; }); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') Array.prototype.forEach.call(menus, function (o) { o.open = false; }); });
  });
})();
