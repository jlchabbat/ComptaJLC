// Aperçu d'un document au survol de son nom : tout élément portant data-apercu (adresse) et data-nom (nom du fichier).
// Écoute placée sur la page entière : elle continue de marcher même si un tableau est redessiné (tri, filtre).
(function () {
  var boite = null, minuteur = null;
  function panneau() {
    if (boite) return boite;
    boite = document.createElement("div");
    boite.style.cssText = "position:fixed;right:12px;top:70px;width:min(460px,45vw);height:calc(100vh - 90px);background:#fff;" +
      "border:2px solid #5b7fb8;box-shadow:0 4px 18px rgba(0,0,0,.35);z-index:9999;pointer-events:none;display:none";
    document.body.appendChild(boite);
    return boite;
  }
  function cacher() { clearTimeout(minuteur); if (boite) { boite.style.display = "none"; boite.innerHTML = ""; } }
  document.addEventListener("mouseover", function (e) {
    var l = e.target.closest ? e.target.closest("[data-apercu]") : null;
    if (!l) return;
    clearTimeout(minuteur);
    minuteur = setTimeout(function () {
      var u = l.getAttribute("data-apercu"), image = /\.(jpe?g|png|gif|webp)$/i.test(l.getAttribute("data-nom") || ""), b = panneau();
      b.innerHTML = image ? '<img src="' + u + '" style="width:100%;height:100%;object-fit:contain">'
                          : '<iframe src="' + u + '#toolbar=0&view=FitH" style="width:100%;height:100%;border:0"></iframe>';
      b.style.display = "block";
    }, 250);
  });
  document.addEventListener("mouseout", function (e) {
    var l = e.target.closest ? e.target.closest("[data-apercu]") : null;
    if (l && !(e.relatedTarget && l.contains(e.relatedTarget))) cacher();
  });
  document.addEventListener("scroll", cacher, true);
})();
