// Requête « Plan-comptable-20260926-0753 » — extraite de Fusion.xlsm le 26/09/2026 (état d'origine)
let
    Source = Csv.Document(File.Contents("D:\OneDrive\Applications\Compta\Exports\Plan-comptable-20260926-0753.csv"),[Delimiter=";", Columns=7, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Type modifié" = Table.TransformColumnTypes(Source,{{"Column1", type text}, {"Column2", type text}, {"Column3", type text}, {"Column4", type text}, {"Column5", type text}, {"Column6", type text}, {"Column7", type text}})
in
    #"Type modifié"
