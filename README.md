# co-inmo-pnl-dash

Dashboard estático de **P&L Inmobiliaria por ciudad · Colombia** (Habi).

- **Fuente**: `clients-domain-data-master.finance_wh_bi.finance_apartment_tracker_inmobiliaria_co`
- **Cohorte**: `fecha_factura` (facturación NetSuite Inmo CO)
- **Currency**: COP MM (millones)
- **Alcance**: hasta Contribution Margin
- **Dos vistas**: ACC (`_accounting`) · Sintético (columnas sin sufijo son el canónico según PDF interno)

## Estructura del P&L Inmo CO

Más simple que Inmo MX — sin split de producto, sin Fee HC100, sin gastos transaccionales:

```
Properties                (count)
GMV Inmobiliaria          (income)
Avg. Ticket               (COP MM/property)

Revenue                   (comisión cobrada al cliente)
Avg. Commission           (COP MM/property)
% fee charged             (Revenue / GMV)

(-) Brokers Commissions   (comisión pagada a broker externo)
% fee paid                (|Brokers| / GMV)

  Sellers                 (comisión interna lado sellers)
  Buyers                  (comisión interna lado buyers)
(-) Comisiones Internas   (rubro)

(=) Contribution Margin
% Revenue                 (CM / Revenue)
% GMV                     (CM / GMV)
```

## Comandos

```bash
make install     # una vez
make raw         # trae raw de BQ → data/raw_apartment_inmo_co.parquet
make refresh     # raw + agrega P&L → site/data/kpi_pnl.json
make serve       # http://localhost:8005/site/
```

## Prerequisitos

```bash
gcloud auth application-default login
```

## Mapeo ciudad → región

CO Inmo NO tiene columna `region`, solo `ciudad` en snake_case minúsculas
(`bogota`, `soacha`, `rio_negro`). El motor mapea a las 4 regiones canónicas
del MM CO (`scripts/_pnl.py::CITY_TO_REGION`):

- **Bogotá**: bogota, soacha, madrid, mosquera, zipaquira, chia, cajica, tocancipa, funza + otros municipios de Sabana
- **Valle De Aburrá**: medellin, bello, sabaneta, envigado, itagui, rio_negro, la_estrella, girardota, copacabana, caldas
- **Cali**: cali, jamundi, palmira, yumbo, candelaria
- **Barranquilla**: barranquilla, soledad, malambo, puerto_colombia, galapa
- **Otros**: cartagena y demás (por debajo del umbral `MIN_ROWS_PER_REGION=50`)

## Notas técnicas

- **Revenue** = `comision_recibida` (sin sufijo) — columna canónica según PDF interno.
- **Brokers** = `comision_pagada_brokers_accounting` (la columna sin sufijo overestima ~0.3-3%).
- **% fee charged** = `Revenue / GMV Total`. **% fee paid** = `|Brokers| / GMV Total`.
- **CM** = Revenue + Brokers + Comisiones Internas (fórmula matemática limpia).

Validado 2026-07-30 contra Corporate_Finance_Master_Dashboard jun-2026:
62 properties, GMV $13.32B COP, Revenue $568.8k COP, CM $267.2k COP.
