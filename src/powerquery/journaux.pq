// Requête « Journaux-20260926-0752 » — extraite de Fusion.xlsm le 26/09/2026 (état d'origine)
let
    Source = Csv.Document(File.Contents("D:\OneDrive\Applications\Compta\Exports\Journaux-20260926-0752.csv"),[Delimiter=";", Columns=7, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"En-têtes promus" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Type modifié" = Table.TransformColumnTypes(#"En-têtes promus",{{"Code", type text}, {"Intitulé", type text}, {"Type", type text}, {"Contrepartie", type text}, {"N° de compte", Int64.Type}, {"Compte bancaire", type text}, {"Actif", Int64.Type}})
in
    #"Type modifié"
