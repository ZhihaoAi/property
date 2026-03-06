# Resale Transaction Data - Scrape Summary

**Data Source:** propertyforsale.com.sg  
**Extracted:** March 2026  
**Filter:** Type of Sale = Resale only (excludes New Sale, Sub Sale)

---

## Summary by Project

| # | Project | CSV File | Resale Records | TOP | Tenure | Total Units |
|---|---------|----------|----------------|-----|--------|-------------|
| 1 | Stirling Residences | stirling_residences_transactions.csv | **293** | 2022 | 99 yrs lease | 1,259 |
| 2 | Queens Peak | queens_peak_transactions.csv | **181** | 2020 | 99 yrs lease | ~700 |
| 3 | Commonwealth Towers | commonwealth_towers_transactions.csv | **302** | 2017 | 99 yrs lease | 845 |
| 4 | The Trilinq | the_trilinq_transactions.csv | **279** | 2017 | 99 yrs lease | ~600 |
| 5 | Clavon | clavon_transactions.csv | **15** | 2023 | 99 yrs lease | 640 |
| 6 | Artra | artra_transactions.csv | **36** | 2022 | 99 yrs lease | ~500 |
| 7 | Kent Ridge Hill Residences | kent_ridge_hill_transactions.csv | **33** | 2025 | 99 yrs lease | ~400 |
| 8 | J Gateway | j_gateway_transactions.csv | **229** | 2017 | 99 yrs lease | 738 |

---

## Notes

- **Clavon** (TOP 2023): Only 15 Resale records – project is very new, most transactions are still New Sale.
- **Kent Ridge Hill Residences** (TOP 2025): 33 Resale records – project is under construction; these may be pre-completion sub-sales recorded as Resale.
- **Artra** (TOP 2022): 36 Resale records – relatively new project.
- All other projects have substantial Resale history (5+ years of data).

---

## CSV Format

```
date,sqft,psf,price
```

- **date:** MonthYear (e.g. Feb2026, Jan2025) – 3-letter month abbreviation
- **sqft:** Floor area in square feet (no commas)
- **psf:** Price per square foot in SGD (no commas)
- **price:** Sale price in SGD (no commas)

---

## Output Location

All files saved to: `/Users/zhihao.ai/projects/property/data/`
