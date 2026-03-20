#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT_DIR = path.resolve(__dirname, '..');
const DATA_DIR = path.join(ROOT_DIR, 'data');
const REGISTRY_PATH = path.join(DATA_DIR, 'srx_project_registry.json');

const PROJECTS = [
  {
    slug: 'sol_acres',
    name: 'Sol Acres',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/sol-acres-70092',
  },
  {
    slug: 'eco_sanctuary',
    name: 'Eco Sanctuary',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/eco-sanctuary-28152',
  },
  {
    slug: 'foresque_residences',
    name: 'Foresque Residences',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/foresque-residences-13642',
  },
  {
    slug: 'gem_residences',
    name: 'Gem Residences',
    region_group: 'Queenstown / RCR + Other',
    base_url: 'https://www.srx.com.sg/condo/gem-residences-74162',
  },
  {
    slug: 'the_skywoods',
    name: 'The Skywoods',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-skywoods-33122',
  },
  {
    slug: 'the_hillier',
    name: 'The Hillier',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-hillier-20552',
  },
  {
    slug: 'the_tre_ver',
    name: 'The Tre Ver',
    region_group: 'Queenstown / RCR + Other',
    base_url: 'https://www.srx.com.sg/condo/the-tre-ver-83062',
  },
  {
    slug: 'hillview_peak',
    name: 'Kingsford Hillview Peak',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/kingsford-hillview-peak-30242',
  },
  {
    slug: 'tree_house',
    name: 'Tree House',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/tree-house-9822',
  },
  {
    slug: 'hillsta',
    name: 'Hillsta',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/hillsta-23901',
  },
  {
    slug: 'hillion_residences',
    name: 'Hillion Residences',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/hillion-residences-31222',
  },
  {
    slug: 'midwood',
    name: 'Midwood',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/midwood-87102',
  },
  {
    slug: 'eight_riversuites',
    name: 'Eight Riversuites',
    region_group: 'Queenstown / RCR + Other',
    base_url: 'https://www.srx.com.sg/condo/eight-riversuites-23851',
  },
  {
    slug: 'the_tennery',
    name: 'The Tennery',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-tennery-11032',
  },
  {
    slug: 'dairy_farm_residences',
    name: 'Dairy Farm Residences',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/dairy-farm-residences-87591',
  },
  {
    slug: 'le_quest',
    name: 'Le Quest',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/le-quest-79662',
  },
  {
    slug: 'daintree_residence',
    name: 'Daintree Residence',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/daintree-residence-83182',
  },
  {
    slug: 'the_myst',
    name: 'The Myst',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-myst-107441',
  },
  {
    slug: 'the_botany_at_dairy_farm',
    name: 'The Botany At Dairy Farm',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-botany-at-dairy-farm-107021',
  },
  {
    slug: 'the_sen',
    name: 'The Sen',
    region_group: 'Hillview / Dairy Farm / Bukit Panjang',
    base_url: 'https://www.srx.com.sg/condo/the-sen-287681',
  },
];

const CANDIDATE_SUFFIXES = [
  '/last-transacted-prices',
  '/floor-plans',
  '/condo-map',
  '',
];

function selectedProjects() {
  const filters = new Set(process.argv.slice(2));
  if (!filters.size) return PROJECTS;
  return PROJECTS.filter(project => filters.has(project.slug));
}

function parseMonthYear(value) {
  const match = value.trim().match(/^([A-Za-z]{3})\s+(\d{2}|\d{4})$/);
  if (!match) {
    throw new Error(`Unsupported transaction date: ${value}`);
  }
  const month = match[1];
  const yearText = match[2];
  const year = yearText.length === 2 ? 2000 + Number(yearText) : Number(yearText);
  return `${month}${year}`;
}

function parseMoney(value) {
  const cleaned = value.replace(/\$/g, '').replace(/,/g, '').trim();
  if (cleaned.endsWith('K')) {
    return Math.round(Number(cleaned.slice(0, -1)) * 1000);
  }
  if (cleaned.endsWith('M')) {
    return Math.round(Number(cleaned.slice(0, -1)) * 1_000_000);
  }
  return Math.round(Number(cleaned));
}

function parseInteger(value) {
  const digits = value.replace(/[^\d]/g, '');
  return digits ? Number(digits) : null;
}

function normalizeTenure(rawTenure, propertyType) {
  if (!rawTenure) return null;
  if (/freehold/i.test(rawTenure)) return 'Freehold';
  if (/999/i.test(rawTenure)) return '999yr';
  if (/99/i.test(rawTenure)) {
    return /executive condominium/i.test(propertyType || '') ? '99yr (EC)' : '99yr';
  }
  return rawTenure.trim();
}

function parseInfoTable(rows) {
  const text = rows.join('\n');
  return parseInfoText(text);
}

function parseInfoText(text) {
  const propertyType = (text.match(/Property Type:\s*([^\n]+)/i) || [])[1] || '';
  const topYearMatch =
    (text.match(/Expected TOP:\s*(\d{4})/i) || [])[1] ||
    (text.match(/Built:\s*(\d{4})/i) || [])[1] ||
    (text.match(/(?:Condominium|Executive Condominium)[^\n]*•[^\n]*•\s*(\d{4})/i) || [])[1];
  const tenureMatch =
    (text.match(/Tenure:\s*([^\n]+)/i) || [])[1] ||
    (text.match(/(?:Condominium|Executive Condominium)[^\n]*•\s*([0-9A-Za-z /]+Yrs?)/i) || [])[1] ||
    '';
  const unitsMatch =
    (text.match(/No\.\s*of Units:\s*([\d,]+)/i) || [])[1] ||
    (text.match(/Total units:\s*([\d,]+)/i) || [])[1] ||
    '';
  return {
    top_year: parseInteger(topYearMatch || ''),
    tenure: normalizeTenure(tenureMatch, propertyType),
    units: parseInteger(unitsMatch),
    property_type: propertyType || null,
  };
}

function parseTransactionRows(rows) {
  const transactions = [];
  for (const rowText of rows.slice(1)) {
    const cols = rowText.split('\t').map(part => part.trim()).filter(Boolean);
    if (cols.length < 6) continue;
    const [unit, priceRaw, psfRaw, sizeRaw, dateRaw, ...addressParts] = cols;
    const price = parseMoney(priceRaw);
    const psf = parseInteger(psfRaw);
    const sqft = parseInteger(sizeRaw);
    const date = parseMonthYear(dateRaw);
    const address = addressParts.join(' ').replace(/\s+/g, ' ').trim();
    if (!price || !psf || !sqft || !date) continue;
    transactions.push({ unit, price, psf, sqft, date, address });
  }
  return transactions;
}

async function waitForTables(page, timeoutMs = 20000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const title = await page.title().catch(() => '');
    const tableCount = await page.locator('table').count().catch(() => 0);
    if (title !== 'Just a moment...' && tableCount > 0) {
      return true;
    }
    await page.waitForTimeout(1000);
  }
  return false;
}

async function extractTables(page) {
  const tables = page.locator('table');
  const tableCount = await tables.count();
  const payload = [];
  for (let i = 0; i < tableCount; i += 1) {
    payload.push(await tables.nth(i).locator('tr').allInnerTexts());
  }
  return payload;
}

function findSalesTable(tables) {
  return tables.find(rows => {
    const header = rows[0] || '';
    return (
      header.includes('Unit') &&
      header.includes('Price') &&
      header.includes('Price (psf)') &&
      header.includes('Size (sqft)') &&
      header.includes('Date') &&
      header.includes('Address')
    );
  }) || null;
}

async function extractProject(page, project) {
  let lastError = null;
  for (const suffix of CANDIDATE_SUFFIXES) {
    const url = suffix ? `${project.base_url}${suffix}` : project.base_url;
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      const ready = await waitForTables(page);
      if (!ready) {
        throw new Error(`timed out waiting for tables on ${url}`);
      }
      const tables = await extractTables(page);
      const infoTable = tables[0] || [];
      const salesTable = findSalesTable(tables);
      if (!salesTable || salesTable.length <= 1) {
        throw new Error(`sales table not found on ${url}`);
      }
      const transactions = parseTransactionRows(salesTable);
      if (!transactions.length) {
        throw new Error(`sales table empty on ${url}`);
      }
      const bodyText = await page.locator('body').innerText();
      const info = parseInfoTable(infoTable);
      const bodyInfo = parseInfoText(bodyText);
      return {
        url,
        info: {
          top_year: info.top_year || bodyInfo.top_year,
          tenure: info.tenure || bodyInfo.tenure,
          units: info.units || bodyInfo.units,
          property_type: info.property_type || bodyInfo.property_type,
        },
        transactions,
      };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error(`no usable SRX page for ${project.slug}`);
}

function writeCsv(project, transactions) {
  const csvPath = path.join(DATA_DIR, `${project.slug}_transactions.csv`);
  const lines = ['date,sqft,psf,price'];
  for (const row of transactions) {
    lines.push(`${row.date},${row.sqft},${row.psf},${row.price}`);
  }
  fs.writeFileSync(csvPath, lines.join('\n') + '\n', 'utf8');
  return path.basename(csvPath);
}

async function main() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const registry = {};
  const targets = selectedProjects();
  if (!targets.length) {
    throw new Error('No matching projects selected');
  }

  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = await browser.newPage();

  try {
    for (const project of targets) {
      const result = await extractProject(page, project);
      const csvFile = writeCsv(project, result.transactions);
      registry[project.slug] = {
        slug: project.slug,
        name: project.name,
        region_group: project.region_group,
        top_year: result.info.top_year,
        tenure: result.info.tenure,
        units: result.info.units,
        property_type: result.info.property_type,
        source_kind: 'srx_csv',
        source_label: 'SRX last-transacted-prices',
        source_url: result.url,
        source_csv: csvFile,
        record_count: result.transactions.length,
      };
      console.log(
        `${project.slug}: ${result.transactions.length} rows -> ${csvFile} (${result.url})`
      );
    }
  } finally {
    await browser.close();
  }

  const existing = fs.existsSync(REGISTRY_PATH)
    ? JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'))
    : { projects: {} };

  const merged = { ...(existing.projects || {}) };
  for (const [slug, value] of Object.entries(registry)) {
    merged[slug] = value;
  }

  fs.writeFileSync(
    REGISTRY_PATH,
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        projects: merged,
      },
      null,
      2,
    ) + '\n',
    'utf8',
  );

  console.log(`registry updated -> ${REGISTRY_PATH}`);
}

main().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
