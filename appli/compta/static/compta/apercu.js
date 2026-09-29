// Aperçu d'un document au survol de son nom : tout élément portant data-apercu (adresse) et data-nom (nom du fichier).
// Écoute placée sur la page entière : elle continue de marcher même si un tableau est redessiné (tri, filtre).
(function () {
  var boite = null, minuteur = null;
  function panneau() {
    if (boite) return boite;
    boite = document.createElement("div");
    boite.style.cssText = "position:fixed;right:12px;top:128px;width:min(460px,45vw);height:calc(100vh - 148px);background:#fff;" +
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
      var u = l.getAttribute("data-apercu"), b = panneau(), img = document.createElement("img");
      img.style.cssText = "width:100%;height:100%;object-fit:contain;background:#fff";
      // un PDF est affiché par sa première page (image) ; si le navigateur ne peut pas, repli sur l'affichage direct
      img.onerror = function () { b.innerHTML = '<iframe src="' + u + '#toolbar=0&view=FitH" style="width:100%;height:100%;border:0"></iframe>'; };
      img.src = u + (u.indexOf("?") < 0 ? "?" : "&") + "apercu=1";
      b.innerHTML = ""; b.appendChild(img);
      b.style.display = "block";
    }, 250);
  });
  document.addEventListener("mouseout", function (e) {
    var l = e.target.closest ? e.target.closest("[data-apercu]") : null;
    if (l && !(e.relatedTarget && l.contains(e.relatedTarget))) cacher();
  });
  document.addEventListener("scroll", cacher, true);
})();
