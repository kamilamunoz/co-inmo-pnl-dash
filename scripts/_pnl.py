"""Motor de agregación P&L Inmobiliaria Colombia por (mes de facturación, region).

Estructura basada en el dashboard interno "Corporate_Finance_Master_Dashboard"
sección Unit Inmobiliaria — hoja "P&L INMOBILIARIA COLOMBIA", validada 2026-07-30
contra jun-2026 (62 properties, GMV $13.32B COP, Revenue $568.8k COP, CM $267.2k).

Convenciones específicas Inmo CO (distintas al MM y al Inmo MX):
- Fecha canónica: `fecha_factura` (DATE).
- NO hay split de producto — solo una línea Inmo (no como MX con Inmo 100 / Tradicional).
- NO hay Fee HC100 — CO no tiene HC100.
- NO hay gastos transaccionales — el motor va directo:
    GMV → Revenue → (-) Brokers → (-) Comisiones Internas (Sellers + Buyers) → CM.
- Solo tiene columna `ciudad` (snake_case minúsculas). El motor mapea ciudad→region
  para paridad con MM CO (Bogotá / Valle De Aburrá / Cali / Barranquilla / Otros).

Vistas:
- ACC       → usa columnas *_accounting.
- Sintético → usa columnas sin sufijo (que son el "canónico" en Inmo CO, según
  cuadre 100% del PDF interno con `comision_recibida` sin sufijo).

Todos los valores en COP.
"""

from __future__ import annotations

import pandas as pd

# Umbral de filas totales para colapsar en 'Otros'
MIN_ROWS_PER_REGION = 50
LABEL_OTROS = "Otros"
WHITELIST_REGIONS: set[str] = set()

# ─────────────────────────────────────────────────────────────────────────────
# Mapping ciudad (snake_case) → region (paridad con MM CO)
# Construido 2026-07-30 desde `finance_apartment_tracker_inmobiliaria_co`:
# top ciudades por volumen + geografía manual para municipios de Sabana Bogotá,
# área metropolitana Valle de Aburrá, área metropolitana Cali y Costa Caribe.
# ─────────────────────────────────────────────────────────────────────────────

CITY_TO_REGION: dict[str, str] = {
    # Bogotá y Sabana
    "bogota": "Bogotá",
    "soacha": "Bogotá", "madrid": "Bogotá", "mosquera": "Bogotá",
    "zipaquira": "Bogotá", "chia": "Bogotá", "cajica": "Bogotá",
    "tocancipa": "Bogotá", "funza": "Bogotá", "cota": "Bogotá",
    "tabio": "Bogotá", "tenjo": "Bogotá", "la_calera": "Bogotá",
    "sopo": "Bogotá", "gachancipa": "Bogotá", "sibate": "Bogotá",
    # Valle De Aburrá (Antioquia)
    "medellin": "Valle De Aburrá", "bello": "Valle De Aburrá",
    "sabaneta": "Valle De Aburrá", "envigado": "Valle De Aburrá",
    "itagui": "Valle De Aburrá", "rio_negro": "Valle De Aburrá",
    "rionegro": "Valle De Aburrá", "la_estrella": "Valle De Aburrá",
    "girardota": "Valle De Aburrá", "copacabana": "Valle De Aburrá",
    "caldas": "Valle De Aburrá",
    # Cali y área
    "cali": "Cali", "jamundi": "Cali", "palmira": "Cali",
    "yumbo": "Cali", "candelaria": "Cali",
    # Barranquilla y área
    "barranquilla": "Barranquilla", "soledad": "Barranquilla",
    "malambo": "Barranquilla", "puerto_colombia": "Barranquilla",
    "galapa": "Barranquilla",
}


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _num(series: pd.Series) -> pd.Series:
    """Convierte a float y trata NaN como 0 para sumas."""
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _coalesce_ue_acc(df: pd.DataFrame, ue_col: str, acc_col: str) -> pd.Series:
    """Vista Sintético: usa columna sin sufijo si no es NaN, si no _accounting."""
    ue = pd.to_numeric(df[ue_col], errors="coerce")
    acc = pd.to_numeric(df[acc_col], errors="coerce")
    return ue.where(ue.notna(), acc).fillna(0.0)


def _normalize_region(region: pd.Series, counts: pd.Series) -> pd.Series:
    below = [r for r in counts[counts < MIN_ROWS_PER_REGION].index.tolist()
             if r not in WHITELIST_REGIONS]
    out = region.where(region.notna(), LABEL_OTROS)
    out = out.where(~out.isin(below), LABEL_OTROS)
    return out


def _resolve_region(ciudad) -> str:
    """Mapea ciudad snake_case → region MM canónica. Fallback a 'Otros'."""
    if pd.isna(ciudad):
        return LABEL_OTROS
    return CITY_TO_REGION.get(ciudad, LABEL_OTROS)


# ─────────────────────────────────────────────────────────────────────────────
# preparación
# ─────────────────────────────────────────────────────────────────────────────

def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Añade columna `mes` y `region_norm` (mapeo desde ciudad)."""
    out = df.copy()
    fecha = pd.to_datetime(out["fecha_factura"])
    out = out.loc[fecha.notna()].copy()
    out["mes"] = pd.to_datetime(out["fecha_factura"]).dt.to_period("M").astype(str)
    out["region_resolved"] = out["ciudad"].apply(_resolve_region)
    counts_by_region = out["region_resolved"].value_counts(dropna=False)
    out["region_norm"] = _normalize_region(out["region_resolved"], counts_by_region)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# estructura del P&L Inmo CO (más simple que Inmo MX)
# ─────────────────────────────────────────────────────────────────────────────

PNL_STRUCTURE = [
    {"key": "properties", "label": "Properties", "parent": None, "type": "kpi", "sign": "count"},
    {"key": "gmv_inmobiliaria", "label": "GMV Inmobiliaria", "parent": None, "type": "kpi", "sign": "income"},
    {"key": "avg_ticket", "label": "Avg. Ticket", "parent": None, "type": "kpi", "sign": "ticket"},

    {"key": "revenue", "label": "Revenue", "parent": None, "type": "total", "sign": "income"},
    {"key": "avg_commission", "label": "Avg. Commission", "parent": None, "type": "kpi", "sign": "ticket"},
    {"key": "pct_fee_charged", "label": "% fee charged", "parent": None, "type": "kpi", "sign": "pct"},

    {"key": "brokers", "label": "(-) Brokers Commissions", "parent": None, "type": "rubro", "sign": "cost"},
    {"key": "pct_fee_paid", "label": "% fee paid", "parent": None, "type": "kpi", "sign": "pct"},

    {"key": "com_int_sellers", "label": "Sellers", "parent": "com_int_total", "type": "subcuenta", "sign": "cost"},
    {"key": "com_int_buyers", "label": "Buyers", "parent": "com_int_total", "type": "subcuenta", "sign": "cost"},
    {"key": "com_int_total", "label": "(-) Comisiones Internas", "parent": None, "type": "rubro", "sign": "cost"},

    {"key": "contribution_margin", "label": "(=) Contribution Margin", "parent": None, "type": "total", "sign": "net"},
    {"key": "pct_cm_revenue", "label": "% Revenue", "parent": None, "type": "kpi", "sign": "pct"},
    {"key": "pct_cm_gmv", "label": "% GMV", "parent": None, "type": "kpi", "sign": "pct"},
]


# ─────────────────────────────────────────────────────────────────────────────
# cálculo por vista
# ─────────────────────────────────────────────────────────────────────────────

def _line_values(df: pd.DataFrame, vista: str) -> dict[str, pd.Series]:
    is_sint = vista == "sintetico"

    def pick(sinsuf_col: str, acc_col: str) -> pd.Series:
        """Sintético: coalesce(sin_sufijo, _accounting). ACC: solo _accounting.

        En Inmo CO la columna sin sufijo es el 'canónico' (cuadra 100% con el
        dashboard interno). _accounting es el snapshot contable puro.
        """
        if is_sint and sinsuf_col in df.columns:
            return _coalesce_ue_acc(df, sinsuf_col, acc_col)
        return _num(df[acc_col])

    lines: dict[str, pd.Series] = {}

    # properties = 1 por fila
    lines["properties"] = pd.Series(1, index=df.index, dtype=float)

    # GMV
    gmv = _num(df["precio_venta"])
    lines["gmv_inmobiliaria"] = gmv
    lines["avg_ticket"] = gmv  # promedio ponderado en aggregate() por properties

    # Revenue = comisión cobrada.
    # 2026-08-20: la tabla dejó de exponer `comision_recibida_accounting`; ambas
    # vistas usan `comision_recibida` (cuadra 100% con PDF interno).
    revenue = _num(df["comision_recibida"])
    lines["revenue"] = revenue
    lines["avg_commission"] = revenue
    # % fee charged / % fee paid / % CM ratios se calculan post-agregación.
    lines["pct_fee_charged"] = pd.Series(0.0, index=df.index)

    # Brokers. En Inmo CO SIEMPRE se usa `_accounting` — la columna sin sufijo
    # es un modelo con overestimación sistemática (validado 2026-07-30 contra PDF).
    brokers = -_num(df["comision_pagada_brokers_accounting"])
    lines["brokers"] = brokers
    lines["pct_fee_paid"] = pd.Series(0.0, index=df.index)

    # Comisiones internas
    lines["com_int_sellers"] = -_num(df["comision_sellers"])
    lines["com_int_buyers"] = -_num(df["comision_buyers"])
    lines["com_int_total"] = lines["com_int_sellers"] + lines["com_int_buyers"]

    # Contribution Margin
    lines["contribution_margin"] = revenue + brokers + lines["com_int_total"]
    lines["pct_cm_revenue"] = pd.Series(0.0, index=df.index)
    lines["pct_cm_gmv"] = pd.Series(0.0, index=df.index)

    return lines


def line_values_per_nid(df_prepared: pd.DataFrame, vista: str) -> pd.DataFrame:
    """DataFrame por-NID con [nid, region, mes, <key1>, <key2>, ...]."""
    lines = _line_values(df_prepared, vista)
    wide = pd.DataFrame(lines)
    wide.insert(0, "mes", df_prepared["mes"].values)
    wide.insert(0, "region", df_prepared["region_norm"].values)
    wide.insert(0, "nid", df_prepared["nid"].values)
    return wide


# Columnas ponderadas por properties (NIDs).
AVG_COLUMNS = {
    "avg_ticket": "properties",
    "avg_commission": "properties",
}

# Ratios derivados post-agregación.
DERIVED_COLUMNS = {
    "pct_fee_charged": ("revenue", "gmv_inmobiliaria", False),
    "pct_fee_paid": ("brokers", "gmv_inmobiliaria", True),  # brokers negativo → abs
    "pct_cm_revenue": ("contribution_margin", "revenue", False),
    "pct_cm_gmv": ("contribution_margin", "gmv_inmobiliaria", False),
}


def _post_avg(grouped: pd.DataFrame) -> pd.DataFrame:
    for col, count_col in AVG_COLUMNS.items():
        if col in grouped.columns and count_col in grouped.columns:
            denom = grouped[count_col].where(grouped[count_col] > 0, other=pd.NA)
            grouped[col] = (grouped[col] / denom).fillna(0.0)
    for col, (num_col, den_col, use_abs) in DERIVED_COLUMNS.items():
        if col in grouped.columns and num_col in grouped.columns and den_col in grouped.columns:
            num = grouped[num_col].abs() if use_abs else grouped[num_col]
            denom = grouped[den_col].where(grouped[den_col] > 0, other=pd.NA)
            grouped[col] = (num / denom).fillna(0.0)
    return grouped


def aggregate(df_prepared: pd.DataFrame, vista: str) -> pd.DataFrame:
    lines = _line_values(df_prepared, vista)
    wide = pd.DataFrame(lines)
    wide["region"] = df_prepared["region_norm"].values
    wide["mes"] = df_prepared["mes"].values
    grouped = wide.groupby(["region", "mes"], as_index=False).sum(numeric_only=True)
    grouped = _post_avg(grouped)
    long = grouped.melt(id_vars=["region", "mes"], var_name="key", value_name="valor")
    return long


def aggregate_all_regions(df_prepared: pd.DataFrame, vista: str) -> pd.DataFrame:
    by_region = aggregate(df_prepared, vista)
    lines = _line_values(df_prepared, vista)
    wide = pd.DataFrame(lines)
    wide["mes"] = df_prepared["mes"].values
    total = wide.groupby("mes", as_index=False).sum(numeric_only=True)
    total = _post_avg(total)
    total["region"] = "Total"
    total_long = total.melt(id_vars=["region", "mes"], var_name="key", value_name="valor")
    return pd.concat([by_region, total_long], ignore_index=True)
