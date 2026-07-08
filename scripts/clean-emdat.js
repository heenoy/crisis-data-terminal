/**
 * EM-DAT → disaster_events 清洗脚本
 *
 * 用法: node scripts/clean-emdat.js
 * 输入: data/emdat_raw.csv
 * 输出: data/disaster_events_clean.csv (UTF-8)
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { parse } from 'csv-parse/sync'
import { stringify } from 'csv-stringify/sync'
import XLSX from 'xlsx'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const INPUT_CSV = path.join(ROOT, 'data', 'emdat_raw.csv')
const INPUT_XLSX = path.join(ROOT, 'data', 'emdat_raw.xlsx')
const OUTPUT = path.join(ROOT, 'data', 'disaster_events_clean.csv')

const OUTPUT_COLUMNS = [
  'source_id',
  'title',
  'disaster_type',
  'country',
  'region',
  'event_date',
  'severity',
  'casualties',
  'affected_population',
  'economic_loss',
  'description',
  'source_name',
  'source_url',
  'status',
  'latitude',
  'longitude',
  'magnitude',
  'magnitude_scale',
  'start_year',
  'start_month',
  'end_year',
  'end_month',
]

function normalizeText(value) {
  return String(value ?? '').trim()
}

function toInt(value, fallback = 0) {
  const raw = normalizeText(value).replace(/,/g, '')
  if (!raw) return fallback
  const n = parseInt(raw, 10)
  return Number.isNaN(n) ? fallback : n
}

function toOptionalNumberField(value) {
  const raw = normalizeText(value).replace(/,/g, '')
  if (!raw) return ''
  const n = Number(raw)
  return Number.isNaN(n) ? '' : String(n)
}

function toOptionalString(value) {
  const raw = normalizeText(value)
  return raw || ''
}

function pad2(n) {
  const num = toInt(n, 0)
  if (!num) return '01'
  return String(num).padStart(2, '0')
}

function buildEventDate(startYear, startMonth, startDay) {
  const year = toInt(startYear, 0)
  if (!year) return ''
  const month = pad2(startMonth)
  const day = pad2(startDay)
  return `${year}-${month}-${day}`
}

function mapDisasterType(disasterType, disasterSubtype) {
  const type = normalizeText(disasterType).toLowerCase()
  const subtype = normalizeText(disasterSubtype).toLowerCase()
  const hay = `${type} ${subtype}`

  if (/earthquake|ground movement/.test(hay)) return 'earthquake'
  if (/tropical cyclone|typhoon|hurricane/.test(hay)) return 'typhoon'
  if (/flood|flash flood|coastal flood|lateral flood/.test(hay)) return 'flood'
  if (/wildfire|forest fire|bush fire|land fire/.test(hay)) return 'wildfire'
  if (/landslide|rockfall|avalanche|mass movement|subsidence|mudslide/.test(hay)) return 'landslide'
  if (/drought/.test(hay)) return 'drought'
  if (/epidemic|pandemic|infestation|biological|viral|bacterial/.test(hay)) return 'epidemic'
  if (/heat wave|cold wave|extreme temperature|extreme winter|wave of extreme/.test(hay)) {
    return 'extreme_temperature'
  }
  if (/storm|tornado|hail|convective|extra-tropical|local storm|thunderstorm|blizzard|sand/.test(hay)) {
    return 'storm'
  }

  return 'other'
}

function computeSeverity(casualties, affectedPopulation) {
  if (casualties >= 1000 || affectedPopulation >= 1000000) return 'critical'
  if (casualties >= 100 || affectedPopulation >= 100000) return 'high'
  if (casualties >= 10 || affectedPopulation >= 10000) return 'medium'
  return 'low'
}

function buildTitle(row) {
  const eventName = normalizeText(row['Event Name'])
  if (eventName) return eventName

  const country = normalizeText(row.Country)
  const disasterType = normalizeText(row['Disaster Type'])
  const startYear = normalizeText(row['Start Year'])

  return [country, disasterType, startYear].filter(Boolean).join(' ')
}

function buildDescription(row) {
  const parts = [
    normalizeText(row.Location),
    normalizeText(row.Origin),
    normalizeText(row['Associated Types']),
  ].filter(Boolean)

  return parts.join(' | ')
}

function buildRegion(row) {
  return normalizeText(row.Subregion) || normalizeText(row.Region) || ''
}

function transformRow(row) {
  const country = normalizeText(row.Country)
  const startYear = normalizeText(row['Start Year'])
  if (!country || !startYear) return null

  const casualties = toInt(row['Total Deaths'], 0)
  const affectedPopulation = toInt(row['Total Affected'], 0)
  const economicLoss = toInt(row["Total Damage ('000 US$)"], 0)

  return {
    source_id: normalizeText(row['DisNo.']),
    title: buildTitle(row),
    disaster_type: mapDisasterType(row['Disaster Type'], row['Disaster Subtype']),
    country,
    region: buildRegion(row),
    event_date: buildEventDate(row['Start Year'], row['Start Month'], row['Start Day']),
    severity: computeSeverity(casualties, affectedPopulation),
    casualties,
    affected_population: affectedPopulation,
    economic_loss: economicLoss,
    description: buildDescription(row),
    source_name: 'EM-DAT',
    source_url: 'https://www.emdat.be/',
    status: 'archived',
    latitude: toOptionalNumberField(row.Latitude),
    longitude: toOptionalNumberField(row.Longitude),
    magnitude: toOptionalNumberField(row.Magnitude),
    magnitude_scale: toOptionalString(row['Magnitude Scale']),
    start_year: toOptionalString(row['Start Year']),
    start_month: toOptionalString(row['Start Month']),
    end_year: toOptionalString(row['End Year']),
    end_month: toOptionalString(row['End Month']),
  }
}

function loadRecords() {
  if (fs.existsSync(INPUT_CSV)) {
    const raw = fs.readFileSync(INPUT_CSV, 'utf8')
    return {
      source: INPUT_CSV,
      records: parse(raw, {
        columns: true,
        skip_empty_lines: true,
        bom: true,
        relax_column_count: true,
        trim: true,
      }),
    }
  }

  if (fs.existsSync(INPUT_XLSX)) {
    const workbook = XLSX.readFile(INPUT_XLSX, { cellDates: false })
    const sheetName = workbook.SheetNames[0]
    const sheet = workbook.Sheets[sheetName]
    const records = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: false })
    return { source: INPUT_XLSX, records }
  }

  return null
}

function main() {
  const loaded = loadRecords()
  if (!loaded) {
    console.error(`[ERROR] 找不到输入文件:`)
    console.error(`  - ${INPUT_CSV}`)
    console.error(`  - ${INPUT_XLSX}`)
    console.error('请将 EM-DAT 数据保存为 data/emdat_raw.csv 或 data/emdat_raw.xlsx')
    process.exit(1)
  }

  const { source, records } = loaded

  const cleaned = []
  let skipped = 0

  for (const row of records) {
    const out = transformRow(row)
    if (!out || !out.title || !out.event_date) {
      skipped += 1
      continue
    }
    cleaned.push(out)
  }

  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true })

  const csv = stringify(cleaned, {
    header: true,
    columns: OUTPUT_COLUMNS,
    quoted_string: true,
  })

  fs.writeFileSync(OUTPUT, csv, 'utf8')

  console.log(`[OK] 清洗完成`)
  console.log(`  输入: ${source}`)
  console.log(`  输出: ${OUTPUT}`)
  console.log(`  原始行数: ${records.length}`)
  console.log(`  有效行数: ${cleaned.length}`)
  console.log(`  跳过行数: ${skipped}`)
}

main()
