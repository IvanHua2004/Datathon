"""Console EDA for the AlphaForge starter CSV files (standard library only)."""

import csv
import sys
from datetime import date
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
MISSING = {"", "na", "n/a", "nan", "null", "none"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames or [], list(reader)


def is_date(value):
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def infer_type(column, values):
    values = [value.strip() for value in values if value.strip().lower() not in MISSING]
    if not values:
        return "empty"
    if column.endswith("_date") or column == "date" or column == "retrieved_on":
        if all(is_date(value) for value in values):
            return "date"
    try:
        for value in values:
            int(value)
        return "int64"
    except ValueError:
        pass
    try:
        for value in values:
            float(value)
        return "float64"
    except ValueError:
        return "object"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    datasets = {}

    print("EDA — données AlphaForge")
    print("=" * 72)
    for path in csv_files:
        columns, rows = read_csv(path)
        datasets[path.name] = (columns, rows)
        print(f"\n{path.name}: {len(rows):,} lignes")
        for column in columns:
            values = [row.get(column, "") or "" for row in rows]
            missing = sum(value.strip().lower() in MISSING for value in values)
            proportion = missing / len(rows) if rows else 0
            print(
                f"  {column}: {infer_type(column, values)}"
                f" | manquants {missing:,} ({proportion:.1%})"
            )

    if "prices_daily.csv" not in datasets or "assets_universe.csv" not in datasets:
        raise FileNotFoundError("prices_daily.csv et assets_universe.csv sont requis.")

    _, prices = datasets["prices_daily.csv"]
    _, assets = datasets["assets_universe.csv"]
    price_dates = [row["date"] for row in prices if row.get("date")]
    price_symbols = {row["ticker"].strip() for row in prices if row.get("ticker")}
    universe_symbols = {row["ticker"].strip() for row in assets if row.get("ticker")}
    price_currencies = sorted(
        {row.get("currency", "").strip() for row in prices if row.get("currency")}
    )

    print("\nCouverture temporelle")
    print("-" * 72)
    if price_dates:
        print(f"Prix : {min(price_dates)} → {max(price_dates)}")
    else:
        print("Aucune date exploitable dans prices_daily.csv.")

    asset_by_symbol = {row["ticker"].strip(): row for row in assets if row.get("ticker")}
    market_dates = {}
    symbol_dates = {}
    for row in prices:
        symbol = row.get("ticker", "").strip()
        observed_date = row.get("date", "").strip()
        if not symbol or not observed_date:
            continue
        symbol_dates.setdefault(symbol, set()).add(observed_date)
        asset = asset_by_symbol.get(symbol)
        if asset:
            market_dates.setdefault(asset.get("market", "Inconnu"), set()).add(observed_date)

    print("Écarts par rapport aux séances observées chez les pairs du même marché :")
    gap_total = 0
    for symbol in sorted(symbol_dates):
        asset = asset_by_symbol.get(symbol)
        market = asset.get("market", "Inconnu") if asset else "Inconnu"
        observed = symbol_dates[symbol]
        peer_sessions = market_dates.get(market, set())
        expected = {day for day in peer_sessions if min(observed) <= day <= max(observed)}
        gaps = sorted(expected - observed)
        if gaps:
            gap_total += len(gaps)
            sample = ", ".join(gaps[:5])
            suffix = "…" if len(gaps) > 5 else ""
            print(f"  {symbol} ({market}): {len(gaps)} séance(s) absente(s): {sample}{suffix}")
    if not gap_total:
        print("  Aucun écart détecté par comparaison aux pairs.")
    print("  (Les fermetures communes au marché sont exclues; les crypto-actifs sont évalués")
    print("   selon les jours observés pour les autres actifs Crypto.)")

    markets = sorted({row.get("market", "").strip() for row in assets if row.get("market")})
    currencies = sorted({row.get("currency", "").strip() for row in assets if row.get("currency")})
    print("\nActifs et marchés")
    print("-" * 72)
    print(f"Marchés dans assets_universe.csv : {', '.join(markets) or 'aucun'}")
    print(f"Devises dans assets_universe.csv : {', '.join(currencies) or 'aucune'}")
    print(f"Devises dans prices_daily.csv : {', '.join(price_currencies) or 'aucune'}")
    print(f"Prix sans actif correspondant : {', '.join(sorted(price_symbols - universe_symbols)) or 'aucun'}")
    print(f"Actifs sans série de prix : {', '.join(sorted(universe_symbols - price_symbols)) or 'aucun'}")

    duplicate_keys = set()
    seen_keys = set()
    non_positive_prices = 0
    invalid_price_values = 0
    invalid_volume_values = 0
    zero_volume_rows = 0
    currency_mismatches = set()
    for row in prices:
        key = (row.get("date", ""), row.get("ticker", ""))
        if key in seen_keys:
            duplicate_keys.add(key)
        seen_keys.add(key)
        row_has_non_positive_price = False
        for column in ("close", "adj_close"):
            value = row.get(column, "").strip()
            if value:
                try:
                    row_has_non_positive_price |= float(value) <= 0
                except ValueError:
                    invalid_price_values += 1
        non_positive_prices += row_has_non_positive_price
        volume = row.get("volume", "").strip()
        if volume:
            try:
                zero_volume_rows += int(volume) == 0
            except ValueError:
                invalid_volume_values += 1
        asset = asset_by_symbol.get(row.get("ticker", "").strip())
        if asset and row.get("currency") and row["currency"] != asset.get("currency"):
            currency_mismatches.add(row["ticker"])

    print("\nContrôles ciblés")
    print("-" * 72)
    print(f"Clés (date, ticker) dupliquées : {len(duplicate_keys)}")
    print(f"Lignes avec close/adj_close non positifs : {non_positive_prices}")
    print(f"Valeurs de prix non numériques : {invalid_price_values}")
    print(f"Lignes avec volume nul : {zero_volume_rows}")
    print(f"Valeurs de volume non numériques : {invalid_volume_values}")
    print(f"Tickers avec devise prix/univers incohérente : {', '.join(sorted(currency_mismatches)) or 'aucun'}")

    print("\nRecommandations de préparation")
    print("-" * 72)
    print("• Utiliser adj_close pour calculer les rendements (splits et dividendes ajustés);")
    print("  ne pas réappliquer les corporate actions aux prix déjà ajustés.")
    print("• Convertir les prix USD en CAD via usdcad (USD × usdcad); convertir CAD en USD")
    print("  via cadusd. Joindre par date, avec report du dernier taux uniquement selon une")
    print("  règle explicite pour les jours fériés canadiens.")
    print("• Ne pas aligner/forward-fill les prix sans politique documentée; les crypto-actifs")
    print("  ont des jours UTC continus, contrairement aux marchés boursiers.")
    print("• Vérifier les dates manquantes, doublons (date, ticker), prix nuls/non positifs et")
    print("  volumes nuls; éviter les fuites temporelles avec les séries macro mensuelles.")


if __name__ == "__main__":
    main()
