# Singapore Resale Condo Transaction Data Sources (with Unit-Type Granularity)

## Objective

Find data sources for **Singapore resale condo transactions** with sufficiently fine granularity to distinguish unit types such as:

- 2b1b
- 2b2b
- 3b2b

---

## Executive Summary

For **official resale condo transaction records**, the most reliable source is **URA**.

However, for **unit-type granularity** like `2b1b / 2b2b / 3b2b`, **official transaction data alone is usually not enough**. Based on currently verifiable public information, I **cannot confirm** that official URA transaction search pages directly expose **bathroom count**.

### Practical approach

Use:

1. **Official transaction data** for actual resale records
2. **Project/unit floor plan databases** to infer and label bedroom/bathroom configuration

In practice:

**Transaction records (official) + project floor plans / unit mix database (third party or developer documents) = usable 2b1b / 2b2b / 3b2b mapping**

---

## Main Data Sources

### 1) URA Private Residential Property Transactions (Free official search)

**Use case:**  
Best free official source for checking recent resale condo transactions at the transaction level.

**What it provides:**
- Project / development name
- Transaction date
- Price
- Floor area
- Floor range / level-related info
- Private residential transaction records

**Official note:**  
URA states this e-service covers **the last 60 months** of private residential transactions where a **caveat has been lodged** or a **developer OTP has been issued**.

**Strengths:**
- Official
- Transaction-level
- Good for validating actual resale activity

**Limitation:**
- I have **not verified** that it directly includes:
  - bedroom count
  - bathroom count
  - explicit labels like `2b1b`, `2b2b`, `3b2b`

**Assessment:**  
Useful for the **transaction side**, but probably insufficient by itself for **unit-layout classification**.

**Source:**  
URA Residential Transaction Search  
https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch

---

### 2) URA REALIS (Paid official platform)

**Use case:**  
Best official option if the goal is to build a more complete and structured transaction database.

**What it provides:**
- More comprehensive and granular property market data
- Historical sales and rental transaction data
- Better suited for bulk analysis / research workflows

**Strengths:**
- Official
- More detailed than the free search
- Better for systematic extraction and analysis

**Limitation:**
- I have **not found a public field list** confirming that REALIS directly includes **bathroom count**
- Therefore I **cannot confirm** that REALIS alone will natively label units as:
  - 2b1b
  - 2b2b
  - 3b2b

**Assessment:**  
Likely the strongest **official raw-data source**, but may still require **external floor-plan mapping** for bath-count granularity.

**Source:**  
URA REALIS  
https://eservice.ura.gov.sg/reis/index

---

### 3) data.gov.sg open datasets

**Use case:**  
Macro validation only.

**What it provides:**
- Public open datasets related to private residential transactions
- Example dataset found: **quarterly** private residential transaction summary

**Limitation:**
- Available public dataset is too coarse
- Example dataset contains only aggregated fields such as:
  - Quarter
  - Type of Sale
  - Sale Status
  - Units

**Assessment:**  
Not suitable for project-level or unit-type-level resale condo analysis.

**Source:**  
data.gov.sg – Private Residential Property Transactions in the Whole of Singapore, Quarterly  
https://data.gov.sg/datasets/d_7c69c943d5f0d89d6a9a773d2b51f337/view

---

### 4) Third-party project databases (EdgeProp / 99.co / PropertyGuru)

**Use case:**  
Best source for **project-level floor plans**, **bed/bath configurations**, and unit mix data.

**Typical value-add:**
- Condo directory / project profiles
- Floor plans
- Unit type breakdown
- Bedrooms / bathrooms
- Sometimes transaction history in the same interface

**Why these matter:**
These platforms can be used to map transaction records to likely layouts by matching:
- Project name
- Floor area
- Stack / unit line
- Known floor plan types

#### EdgeProp
- Project directory
- Condo/project details
- Transaction-related information

Source:  
https://www.edgeprop.sg/condo-apartment

#### 99.co
- Condo directory
- Floor plans
- Transaction history

Source:  
https://www.99.co/singapore/condos-apartments

#### PropertyGuru
- Condo directory
- Project details and unit information

Source:  
https://www.propertyguru.com.sg/condo-directory

**Important caveat:**  
These are **not the primary legal source of transaction registration**.  
They are best used to **supplement official transaction records**, especially for **unit-type labeling**.

---

## Key Finding

### Can a single public official source directly provide `2b1b / 2b2b / 3b2b`?

**As of 2026-03-11: I cannot confirm that a public official source directly does this.**

What is confirmed:
- URA provides official transaction-level search for private residential transactions
- URA REALIS provides more granular official data via subscription
- Public open datasets on data.gov.sg are too aggregated
- Third-party condo directories often provide floor plans and bed/bath details

### Most realistic workflow

Use:

- **URA / REALIS** for true transaction records
- **99.co / EdgeProp / PropertyGuru / developer brochures** for floor plans and bath-count details

---

## Recommended Data Architecture

### Option A — Manual research workflow
Good for a small number of projects.

1. Pull transaction records from **URA free transaction search**
2. Open project pages on **99.co / EdgeProp / PropertyGuru**
3. Collect:
   - floor plans
   - bedroom count
   - bathroom count
   - area by unit type
4. Match transactions to likely layouts using:
   - project name
   - area
   - floor / stack clues
5. Label each transaction as:
   - 2b1b
   - 2b2b
   - 3b2b
   - etc.

---

### Option B — Scalable database workflow
Better for systematic research or automation.

#### Step 1: Transaction table
Source from:
- URA free search (small scale)
- URA REALIS (preferred for scale)

Fields to capture if available:
- project_name
- transaction_date
- transaction_price
- floor_area_sqft / sqm
- floor_range
- tenure
- district
- unit / stack-related info (if available)

#### Step 2: Unit-type reference table
Source from:
- 99.co
- EdgeProp
- PropertyGuru
- developer brochures / archived project documents

Fields to build:
- project_name
- unit_type_id
- bedrooms
- bathrooms
- floor_area_sqft / sqm
- stack
- floor_plan_url / source

#### Step 3: Mapping logic
Match transaction rows to unit types using:
- exact project match
- exact or near-exact area match
- stack match where available
- floor plan / brochure validation
- listing archives if needed

#### Step 4: Output
Produce a normalized dataset with labels such as:
- 2b1b
- 2b2b
- 3b2b
- 3b3b

---

## Reliability Hierarchy

### Best for transaction truth
1. **URA / REALIS**
2. Third-party platforms only as supporting references

### Best for bed/bath layout information
1. **Developer brochure / official floor plans**
2. Third-party project directories
3. Listing archives / cached historical pages

---

## Limitations / Uncertainties

These points remain **unconfirmed** based on currently checked public sources:

1. Whether the free URA transaction search directly includes **bathroom count**
2. Whether REALIS directly includes a **bathroom-count field**
3. Whether there is any public official dataset that directly labels transactions as:
   - 2b1b
   - 2b2b
   - 3b2b

Because of that, the safest working assumption is:

> Official data gives the transaction record; layout classification must be added through external unit/floor-plan mapping.

---

## Recommended Next Step for an AI Agent

Please evaluate and propose a practical workflow for building a dataset of **Singapore resale condo transactions classified by unit layout**.

### Desired output
A dataset where each transaction can be labeled with:
- number of bedrooms
- number of bathrooms
- normalized type label (e.g. `2b1b`, `2b2b`, `3b2b`)

### Questions to solve
1. What is the most efficient source combination?
2. How should transaction rows be matched to floor plans?
3. What matching logic should be used when area is close but not exact?
4. How should ambiguous cases be handled?
5. What is the best scalable pipeline:
   - manual
   - scraping-based
   - semi-automated
   - subscription-data-driven

### Likely best direction
A hybrid pipeline:
- **official transaction data** from URA / REALIS
- **unit mix + floor plan data** from project directories / brochures
- a mapping layer based on **project + area + stack/floor-plan clues**

---

## Sources

- URA Residential Transaction Search  
  https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch

- URA REALIS  
  https://eservice.ura.gov.sg/reis/index

- data.gov.sg quarterly private residential transaction dataset  
  https://data.gov.sg/datasets/d_7c69c943d5f0d89d6a9a773d2b51f337/view

- EdgeProp condo directory  
  https://www.edgeprop.sg/condo-apartment

- 99.co condo directory  
  https://www.99.co/singapore/condos-apartments

- PropertyGuru condo directory  
  https://www.propertyguru.com.sg/condo-directory