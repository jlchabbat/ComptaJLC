// Aperçu d'un document au survol de sa ligne : tout élément portant data-apercu (adresse) et data-nom (nom du fichier).
addEventListener("DOMContentLoaded", function () {
  var lignes = document.querySelectorAll("[data-apercu]");
  if (!lignes.length) return;
  var boite = document.createElement("div"), minuteur;
  boite.hidden = true;
  boite.style.cssText = "position:fixed;right:12px;top:70px;width:min(460px,45vw);height:calc(100vh - 90px);background:#fff;" +
    "border:2px solid #5b7fb8;box-shadow:0 4px 18px rgba(0,0,0,.35);z-index:60;pointer-events:none";
  document.body.appendChild(boite);
  lignes.forEach(function (l) {
    l.addEventListener("mouseenter", function () {
      clearTimeout(minuteur);
      minuteur = setTimeout(function () {
        var u = l.dataset.apercu, image = /\.(jpe?g|png|gif|webp)$/i.test(l.dataset.nom || "");
        boite.innerHTML = image ? '<img src="' + u + '" style="width:100%;height:100%;object-fit:contain">'
                                : '<iframe src="' + u + '#toolbar=0&view=FitH" style="width:100%;height:100%;border:0"></iframe>';
        boite.hidden = false;
      }, 250);
    });
    l.addEventListener("mouseleave", function () { clearTimeout(minuteur); boite.hidden = true; boite.innerHTML = ""; });
  });
});
