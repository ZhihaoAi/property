# Resale Transaction Data - Whitehaven, Caspian, Lakefront Residences

Scraped from propertyforsale.com.sg on 5 March 2026.

## Summary

| Project | Records | File | TOP Year | Tenure | Total Units |
|---------|---------|------|----------|--------|-------------|
| **Whitehaven** | 34 | whitehaven_transactions.csv | 2017 | Freehold | 121 |
| **Caspian** | 226 | caspian_transactions.csv | 2008 | 99 yrs lease | 712 |
| **Lakefront Residences** | 211 | lakefront_transactions.csv | 2010 | 99 yrs lease | 629 |

## CSV Format

All files: `date,sqft,psf,price`
- **date**: MonthYear (e.g., Feb2026, Jan2025) - 3-letter month abbreviation
- **sqft**: Floor area, numbers only (no commas)
- **psf**: Price per sqft (S$), numbers only
- **price**: Sale price (S$), numbers only

Only **Resale** records included (New Sale and Sub Sale excluded).

## URLs Used

- Whitehaven: https://www.propertyforsale.com.sg/whitehaven/sales-transactions
- Caspian: https://www.propertyforsale.com.sg/caspian/sales-transactions
- Lakefront: https://www.propertyforsale.com.sg/the-lakefront-residences/sales-transactions
