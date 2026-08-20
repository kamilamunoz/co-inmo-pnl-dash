"""Trae el raw de finance_apartment_tracker_inmobiliaria_co y lo guarda como parquet.

Convenciones Inmo CO (distintas al MM y al Inmo MX):
- Fecha canónica facturación: `fecha_factura` (DATE) — no `c_fecha_factura`.
- NO hay split de producto (Inmo 100 vs Tradicional) — CO tiene una sola línea de Inmo.
- NO hay Fee HC100 — CO no tiene HC100.
- NO hay gastos transaccionales (avaluos, notariales, apertura, inscripción)
  registrados en el tracker — el motor Inmo CO va directo Revenue → Brokers →
  Comisiones Internas → CM.
- Solo tiene `ciudad` (snake_case minúsculas: `bogota`, `rio_negro`). El motor
  mapea ciudad → region para paridad con MM CO (Bogotá / Cali / Barranquilla /
  Valle De Aburrá).

Uso:
    make raw
"""

from __future__ import annotations

import logging
from pathlib import Path

from scripts._bq import BILLING_PROJECT, TABLE_APT_INMO_CO, run_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s · %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "raw_apartment_inmo_co.parquet"

QUERY = f"""
SELECT
    nid,
    ciudad,

    -- fechas
    fecha_factura,
    fecha_promesa,
    fecha_escritura,
    fecha_captacion,
    fecha_primer_publicacion,

    -- precio
    precio_venta,

    -- Revenue (comisión cobrada por Habi al cliente).
    -- Nota (2026-08-20): la tabla dejó de exponer `comision_recibida_accounting`.
    -- Ambas vistas ACC/Sintético colapsan a `comision_recibida` (cuadra 100% con PDF).
    comision_recibida,
    porcentaje_comision_recibida,

    -- Brokers externos
    comision_pagada_brokers,
    comision_pagada_brokers_accounting,
    porcentaje_comision_brokers,

    -- Comisiones internas
    comision_sellers,
    comision_buyers,
    porcentaje_comision_sellers,
    porcentaje_comision_buyers
FROM `{TABLE_APT_INMO_CO}`
WHERE fecha_factura IS NOT NULL
"""


def main() -> None:
    log.info("Trayendo raw de %s (billing=%s) ...", TABLE_APT_INMO_CO, BILLING_PROJECT)
    df = run_query(QUERY, label="apartment_inmo_co_raw")
    log.info("Total filas: %d", len(df))
    log.info(
        "Rango fecha_factura: %s → %s",
        df["fecha_factura"].min(), df["fecha_factura"].max(),
    )
    log.info("Ciudades únicas: %d", df["ciudad"].nunique(dropna=True))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    log.info("Escrito → %s (%.1f MB)", OUT_PATH, OUT_PATH.stat().st_size / 1024**2)


if __name__ == "__main__":
    main()
