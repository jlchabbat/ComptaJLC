// Requête « Requête1 » — extraite de Fusion.xlsm le 26/09/2026 (état d'origine)
let
    // ===== 1. Paramètres =====
    Chemin   = "D:\OneDrive\Compta Bnei Brith\tnuot.pdf",
    TradBrut = Excel.CurrentWorkbook(){[Name="T_TradBanque"]}[Content],

    // ===== 2. Fonctions de nettoyage =====
    Invisibles = {Character.FromNumber(8206), Character.FromNumber(8207), Character.FromNumber(8234),
                  Character.FromNumber(8235), Character.FromNumber(8236), Character.FromNumber(8237),
                  Character.FromNumber(8238)},
    fxTexte  = (t) => if t = null then null else Text.Trim(Text.Remove(Text.From(t), Invisibles)),
    fxCle    = (t) => if t = null then null else Text.Remove(fxTexte(t), {"(", ")", " ", "<"}),
    fxNombre = (t) => let s = if t = null then "" else Text.Remove(fxTexte(t), {",", "₪", " "}) in
                      if s = "" then null else try Number.FromText(s, "en-US") otherwise null,
    fxDate   = (t) => if t = null then null
                      else try Date.FromText(fxTexte(t), [Format = "dd/MM/yy", Culture = "fr-FR"]) otherwise null,

    Trad = Table.AddColumn(TradBrut, "Cle", each fxCle([#"Opération (hébreu)"]), type text),

    // ===== 3. Lecture de toutes les pages du PDF =====
    Source = Pdf.Tables(File.Contents(Chemin), [Implementation = "1.3"]),
    Tables = Table.SelectRows(Source, each [Kind] = "Table"),

    // ===== 4. Normalisation de chaque tableau (en-tête détecté automatiquement) =====
    fxNormaliser = (t as table) as table =>
        let
            t0      = Table.DemoteHeaders(t),
            Rangs   = Table.ToRows(t0),
            PosEnt  = List.PositionOf(Rangs, List.First(List.Select(Rangs,
                          each List.AnyTrue(List.Transform(_, (c) => c <> null and Text.Contains(fxTexte(c) ?? "", "סוג"))))) ),
            t1      = if PosEnt < 0 then t0 else Table.Skip(t0, PosEnt),
            t2      = Table.PromoteHeaders(t1, [PromoteAllScalars = true]),
            Anciens = Table.ColumnNames(t2),
            Nouveaux = List.Transform(Anciens, each
                        let n = fxTexte(_) ?? "" in
                        if Text.Contains(n, "ערך") then "DateValeur"
                        else if Text.Contains(n, "תאריך") then "Date"
                        else if Text.Contains(n, "סוג") then "Type"
                        else if Text.Contains(n, "זכות") or Text.Contains(n, "חובה") then "Montant"
                        else if Text.Contains(n, "יתרה") then "Solde"
                        else if Text.Contains(n, "אסמכתה") then "Reference"
                        else _),
            t3 = Table.RenameColumns(t2, List.Zip({Anciens, Nouveaux}), MissingField.Ignore)
        in
            Table.SelectColumns(t3, {"Date", "Reference", "Type", "Montant", "Solde"}, MissingField.UseNull),

    Combine = Table.Combine(List.Transform(Tables[Data], fxNormaliser)),

    // ===== 5. Typage et conservation des seules lignes de mouvement =====
    Types  = Table.TransformColumns(Combine, {
                {"Date", fxDate}, {"Reference", fxTexte}, {"Type", fxTexte},
                {"Montant", fxNombre}, {"Solde", fxNombre}}),
    Lignes = Table.SelectRows(Types, each [Date] <> null and [Montant] <> null),

    // ===== 6. Ordre chronologique (ordre du relevé conservé dans la journée) =====
    Index       = Table.AddIndexColumn(Lignes, "Ordre", 1, 1),
    SensInverse = List.First(Index[Date]) > List.Last(Index[Date]),
    Tri         = Table.Sort(Index, {{"Date", Order.Ascending},
                                     {"Ordre", if SensInverse then Order.Descending else Order.Ascending}}),

    // ===== 7. Traduction via la table T_TradBanque =====
    AvecCle = Table.AddColumn(Tri, "Cle", each fxCle([Type]), type text),
    Fusion  = Table.NestedJoin(AvecCle, {"Cle"}, Trad, {"Cle"}, "T", JoinKind.LeftOuter),
    Traduit = Table.AddColumn(Fusion, "Opération (traduction)", each
                if Table.IsEmpty([T]) then "À traduire" else [T]{0}[Traduction], type text),

    // ===== 8. Colonnes finales (identiques à T_Banque1) =====
    Final   = Table.SelectColumns(Traduit, {"Date", "Reference", "Type", "Opération (traduction)", "Montant", "Solde"}),
    Renomme = Table.RenameColumns(Final, {{"Reference", "Référence"}, {"Type", "Opération (relevé)"},
                                          {"Solde", "Solde relevé"}}),
    Resultat = Table.TransformColumnTypes(Renomme, {{"Date", type date}, {"Référence", type text},
                {"Opération (relevé)", type text}, {"Opération (traduction)", type text},
                {"Montant", type number}, {"Solde relevé", type number}})
in
    Resultat
