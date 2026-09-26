// Requête « Ecritures-20260925-1927 » — extraite de Fusion.xlsm le 26/09/2026 (état d'origine)
let
    Source = Csv.Document(File.Contents("D:\OneDrive\Applications\Compta\Exports\Ecritures-20260925-1927.csv"),[Delimiter="	", Columns=13, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    #"En-têtes promus" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Type modifié" = Table.TransformColumnTypes(#"En-têtes promus",{{"Date", type date}, {"Jnl", type text}, {"Mvt", Int64.Type}, {"Pièce", Int64.Type}, {"Compte", type text}, {"Intitulé", type text}, {"Libellé", type text}, {"Débit", type text}, {"Crédit", type text}, {"Solde", Int64.Type}, {"Anal1", type text}, {"Anal2", type text}, {"Let", type text}})
in
    #"Type modifié"
