// Requête « Préfixes-des-codes-analytiques-20260926-0752 » — extraite de Fusion.xlsm le 26/09/2026 (état d'origine)
let
    Source = Csv.Document(File.Contents("D:\OneDrive\Applications\Compta\Exports\Préfixes-des-codes-analytiques-20260926-0752.csv"),[Delimiter=";", Columns=4, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"En-têtes promus" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Type modifié" = Table.TransformColumnTypes(#"En-têtes promus",{{"Préfixe", type text}, {"Axe", Int64.Type}, {"Libellé", type text}, {"Code suivant", type text}})
in
    #"Type modifié"
