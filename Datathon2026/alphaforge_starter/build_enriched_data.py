"""Build enriched CAD-denominated prices and per-asset risk/performance metrics."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).resolve().parent
ANNUAL_DAYS = {"trading": 252, "calendar": 365}
FX_MAX_AGE = pd.Timedelta(days=7)


def require_columns(frame, columns, filename):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{filename}: colonnes requises absentes : {', '.join(missing)}")


def period_return(frame, start_date=None, end_date=None):
    """Return and CAGR between the last available price at/before each boundary."""
    frame = frame.sort_values("date")
    dates = frame["date"].to_numpy()
    if not len(frame):
        return np.nan, np.nan

    end_limit = pd.Timestamp(end_date) if end_date is not None else frame["date"].max()
    end_pos = np.searchsorted(dates, np.datetime64(end_limit), side="right") - 1
    if end_pos < 0:
        return np.nan, np.nan

    if start_date is None:
        start_pos = 0
    else:
        start_limit = pd.Timestamp(start_date)
        start_pos = np.searchsorted(dates, np.datetime64(start_limit), side="right") - 1
    if start_pos < 0 or start_pos >= end_pos:
        return np.nan, np.nan

    start = frame.iloc[start_pos]
    end = frame.iloc[end_pos]
    total = end["adj_close_cad"] / start["adj_close_cad"] - 1
    elapsed_days = (end["date"] - start["date"]).days
    cagr = (1 + total) ** (365.25 / elapsed_days) - 1 if elapsed_days > 0 else np.nan
    return total, cagr


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    prices_path = DATA_DIR / "prices_daily.csv"
    assets_path = DATA_DIR / "assets_universe.csv"
    fx_path = DATA_DIR / "fx_usdcad_daily.csv"
    macro_path = DATA_DIR / "macro_rates.csv"

    prices = pd.read_csv(prices_path, parse_dates=["date"])
    assets = pd.read_csv(assets_path)
    fx = pd.read_csv(fx_path, parse_dates=["date"])
    macro = pd.read_csv(macro_path, parse_dates=["date"])
    require_columns(
        prices,
        ["date", "ticker", "adj_close", "currency"],
        prices_path.name,
    )
    require_columns(
        assets,
        ["ticker", "name", "asset_class", "market", "currency", "sector"],
        assets_path.name,
    )
    require_columns(fx, ["date", "usdcad"], fx_path.name)
    require_columns(macro, ["date", "series_id", "value", "unit"], macro_path.name)

    prices["ticker"] = prices["ticker"].astype(str).str.strip()
    assets["ticker"] = assets["ticker"].astype(str).str.strip()
    if assets["ticker"].duplicated().any():
        raise ValueError("assets_universe.csv contient des tickers dupliqués.")
    if prices.duplicated(["date", "ticker"]).any():
        raise ValueError("prices_daily.csv contient des doublons (date, ticker).")

    prices["adj_close"] = pd.to_numeric(prices["adj_close"], errors="coerce")
    fx["usdcad"] = pd.to_numeric(fx["usdcad"], errors="coerce")
    if prices["date"].isna().any() or prices["adj_close"].isna().any():
        raise ValueError("prices_daily.csv contient des dates ou adj_close invalides.")
    if (prices["adj_close"] <= 0).any():
        raise ValueError("adj_close doit être strictement positif.")
    if fx["date"].isna().any() or fx["usdcad"].isna().any() or (fx["usdcad"] <= 0).any():
        raise ValueError("fx_usdcad_daily.csv contient des dates ou taux invalides.")

    unknown = sorted(set(prices["ticker"]) - set(assets["ticker"]))
    no_prices = sorted(set(assets["ticker"]) - set(prices["ticker"]))
    if unknown or no_prices:
        raise ValueError(f"Univers/prix désalignés — inconnus: {unknown}; sans prix: {no_prices}")

    prices = prices.merge(
        assets[["ticker", "name", "asset_class", "market", "currency", "sector"]]
        .rename(columns={"currency": "currency_origin"}),
        on="ticker",
        how="left",
        validate="many_to_one",
    )
    currency_mismatch = prices["currency"].ne(prices["currency_origin"])
    if currency_mismatch.any():
        symbols = sorted(prices.loc[currency_mismatch, "ticker"].unique())
        raise ValueError(f"Devises prix/univers incohérentes : {symbols}")
    if not prices["currency_origin"].isin(["CAD", "USD"]).all():
        raise ValueError("Seules les devises CAD et USD sont prises en charge.")

    # Backward as-of with a finite tolerance carries the last published FX rate
    # to weekends/holidays without silently spanning a prolonged data outage.
    fx = fx.rename(columns={"date": "fx_observation_date"})
    fx = fx.sort_values("fx_observation_date").drop_duplicates(
        "fx_observation_date", keep="last"
    )
    enriched = pd.merge_asof(
        prices.sort_values(["date", "ticker"]),
        fx[["fx_observation_date", "usdcad"]].sort_values("fx_observation_date"),
        left_on="date",
        right_on="fx_observation_date",
        direction="backward",
        tolerance=FX_MAX_AGE,
    )
    if enriched["usdcad"].isna().any():
        raise ValueError("Taux USD/CAD indisponible ou trop ancien pour certaines dates.")
    enriched["fx_rate_to_cad"] = np.where(
        enriched["currency_origin"].eq("USD"), enriched["usdcad"], 1.0
    )
    enriched["adj_close_cad"] = enriched["adj_close"] * enriched["fx_rate_to_cad"]

    # V39079 is the Canadian overnight target rate, recorded on announcement
    # dates. Apply it only from the following calendar day as a conservative
    # availability lag. Monthly macro rows have reference dates, not release
    # dates, so they are intentionally excluded from daily features/Sharpe.
    risk_free = macro.loc[
        macro["series_id"].eq("V39079") & macro["unit"].eq("percent"),
        ["date", "value"],
    ].copy()
    risk_free["value"] = pd.to_numeric(risk_free["value"], errors="coerce")
    risk_free = risk_free.dropna().sort_values("date")
    if risk_free.empty:
        raise ValueError("macro_rates.csv ne contient pas la série journalière V39079.")
    risk_free = risk_free.drop_duplicates("date", keep="last")
    risk_free["risk_free_rate_available_from"] = risk_free["date"] + pd.Timedelta(days=1)
    risk_free = risk_free.rename(columns={"value": "risk_free_rate_annual_pct"})
    enriched = pd.merge_asof(
        enriched.sort_values(["date", "ticker"]),
        risk_free[["risk_free_rate_available_from", "risk_free_rate_annual_pct"]]
        .sort_values("risk_free_rate_available_from"),
        left_on="date",
        right_on="risk_free_rate_available_from",
        direction="backward",
    )

    enriched = enriched.sort_values(["ticker", "date"]).reset_index(drop=True)
    is_crypto = enriched["asset_class"].str.lower().eq("crypto") | enriched[
        "market"
    ].str.lower().str.startswith("crypto")
    enriched["annualization_days"] = np.where(
        is_crypto, ANNUAL_DAYS["calendar"], ANNUAL_DAYS["trading"]
    )
    by_ticker = enriched.groupby("ticker", sort=False)
    enriched["daily_return"] = by_ticker["adj_close_cad"].pct_change(fill_method=None)
    enriched["sma_50"] = by_ticker["adj_close_cad"].transform(
        lambda values: values.rolling(50, min_periods=50).mean()
    )
    enriched["sma_200"] = by_ticker["adj_close_cad"].transform(
        lambda values: values.rolling(200, min_periods=200).mean()
    )
    enriched["rolling_vol_30d"] = by_ticker["daily_return"].transform(
        lambda values: values.rolling(30, min_periods=30).std(ddof=1)
    ) * np.sqrt(enriched["annualization_days"])
    enriched["drawdown"] = (
        enriched["adj_close_cad"]
        / enriched.groupby("ticker", sort=False)["adj_close_cad"].cummax()
        - 1
    )

    enriched_output = enriched[
        [
            "date",
            "ticker",
            "name",
            "asset_class",
            "market",
            "sector",
            "currency_origin",
            "adj_close",
            "fx_rate_to_cad",
            "adj_close_cad",
            "risk_free_rate_available_from",
            "risk_free_rate_annual_pct",
            "daily_return",
            "sma_50",
            "sma_200",
            "rolling_vol_30d",
            "drawdown",
        ]
    ]
    enriched_path = DATA_DIR / "prices_enriched.csv"
    enriched_output.to_csv(enriched_path, index=False)

    dataset_end = enriched["date"].max()
    last_year_start = dataset_end - pd.DateOffset(years=1)
    year_2022_start = pd.Timestamp("2022-01-01")
    year_2022_end = pd.Timestamp("2022-12-31")
    summaries = []
    for ticker, frame in enriched.groupby("ticker", sort=True):
        frame = frame.sort_values("date")
        daily_returns = frame["daily_return"].dropna()
        annualization = int(frame["annualization_days"].iloc[0])
        total_return, cagr = period_return(frame)
        last_year_return, last_year_cagr = period_return(
            frame, start_date=last_year_start, end_date=dataset_end
        )
        return_2022, _ = period_return(
            frame, start_date=year_2022_start, end_date=year_2022_end
        )
        annual_vol = daily_returns.std(ddof=1) * np.sqrt(annualization)
        rf_daily = frame["risk_free_rate_annual_pct"] / 100 / annualization
        excess_returns = frame["daily_return"] - rf_daily
        valid_excess = excess_returns.dropna()
        return_std = daily_returns.std(ddof=1)
        sharpe = (
            valid_excess.mean() / return_std * np.sqrt(annualization)
            if pd.notna(return_std) and return_std > 0 and not valid_excess.empty
            else np.nan
        )
        asset = frame.iloc[0]
        summaries.append(
            {
                "ticker": ticker,
                "name": asset["name"],
                "asset_class": asset["asset_class"],
                "market": asset["market"],
                "sector": asset["sector"],
                "currency_origin": asset["currency_origin"],
                "start_date": frame["date"].min().date(),
                "end_date": frame["date"].max().date(),
                "observations": len(frame),
                "total_return_pct": total_return * 100,
                "cagr_pct": cagr * 100,
                "last_year_return_pct": last_year_return * 100,
                "last_year_cagr_pct": last_year_cagr * 100,
                "annualized_volatility_pct": annual_vol * 100,
                "sharpe_ratio": sharpe,
                "mean_risk_free_rate_pct": frame["risk_free_rate_annual_pct"].mean(),
                "max_drawdown_pct": frame["drawdown"].min() * 100,
                "return_2022_pct": return_2022 * 100,
            }
        )

    summary_output = pd.DataFrame(summaries)
    summary_path = DATA_DIR / "assets_summary_metrics.csv"
    summary_output.to_csv(summary_path, index=False)

    fx_age = (enriched["date"] - enriched["fx_observation_date"]).dt.days
    print("Enrichissement terminé")
    print(f"• Série : {len(enriched_output):,} lignes → {enriched_path.name}")
    print(f"• Tableau de bord : {len(summary_output):,} actifs → {summary_path.name}")
    print(f"• Report FX maximal observé : {fx_age.max()} jour(s), limite {FX_MAX_AGE.days} jours")
    print("• Macro : V39079 décalée d’un jour; séries mensuelles exclues (date de publication absente).")
    print("• NaN attendus : début des rendements et des fenêtres SMA/volatilité.")
    print("\nAperçu — prices_enriched.csv")
    print(enriched_output.head(5).to_string(index=False))
    print("\nAperçu — assets_summary_metrics.csv")
    print(summary_output.head(5).to_string(index=False))
    print("\nLes colonnes suffixées _pct sont exprimées en points de pourcentage.")
    print("daily_return, rolling_vol_30d et drawdown sont des ratios décimaux.")


if __name__ == "__main__":
    main()
