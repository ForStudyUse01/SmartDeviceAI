/**
 * Valuation + decision engine — static metal prices, water-damage rules.
 */
import { metalPrices } from './metalPrices'

const CONDITION_FACTORS = { Good: 1, Average: 0.7, Poor: 0.4 }

function ageFactor(ageYears) {
  const a = Math.min(15, Math.max(0, Number(ageYears) || 0))
  return Math.max(0.35, 1 - a * 0.055)
}

/** Screen −20%, body −10%; water −15% additional derating on value. */
export function damageFactor(screenDamage, bodyDamage, waterDamage) {
  const screen = String(screenDamage).toLowerCase() === 'yes' ? 0.8 : 1
  const body = String(bodyDamage).toLowerCase() === 'yes' ? 0.9 : 1
  const water = String(waterDamage).toLowerCase() === 'yes' ? 0.85 : 1
  return screen * body * water
}

/** Repair cost 10–25% of base price by condition. */
export function repairCostFromBase(basePrice, conditionLabel) {
  const c = String(conditionLabel || 'Good').trim()
  const pct = c === 'Poor' ? 0.25 : c === 'Average' ? 0.175 : 0.1
  return Math.round(Number(basePrice) * pct)
}

function riskForCondition(condition, waterDamage) {
  if (String(waterDamage).toLowerCase() === 'yes') return 'High'
  if (condition === 'Poor') return 'High'
  if (condition === 'Average') return 'Medium'
  return 'Low'
}

/**
 * Metal recovery INR from static `metalPrices` (₹/10g gold & palladium, ₹/g silver, ₹/kg copper).
 */
export function estimateMetalRecoveryInr(deviceType) {
  const g = metalPrices.gold
  const s = metalPrices.silver
  const c = metalPrices.copper
  const p = metalPrices.palladium
  const t = String(deviceType || '').toLowerCase()
  let goldMg = 35
  let silverMg = 40
  let copperG = 80
  let palladiumMg = 0
  if (t.includes('laptop')) {
    goldMg = 15
    silverMg = 0
    copperG = 200
  }
  if (t.includes('gpu') || t.includes('graphic')) {
    goldMg = 80
    copperG = 300
    palladiumMg = 2
  }
  if (t.includes('mobile') || t.includes('phone') || t.includes('tablet')) {
    goldMg = 40
    silverMg = 50
    copperG = 90
  }
  const goldInr = (g / 10) * (goldMg / 1000)
  const silverInr = s * (silverMg / 1000)
  const copperInr = (c / 1000) * copperG
  const palInr = (p / 10) * (palladiumMg / 1000)
  return Math.round(goldInr + silverInr + copperInr + palInr)
}

export function computeSmartDecision({
  conditionLabel,
  waterDamage,
  resaleValue,
  basePrice,
  metalRecoveryValue,
}) {
  if (String(waterDamage).toLowerCase() === 'yes') {
    return {
      decision: 'Scrap parts',
      bestOptionLabel: 'Disassemble & recover boards after liquid ingress',
      alternatives: ['Recycle remainder', 'Professional data recovery only if needed'],
    }
  }

  const cond = String(conditionLabel || 'Good').trim()
  const valueHigh = resaleValue >= basePrice * 0.35

  if (cond === 'Good' && valueHigh) {
    return {
      decision: 'Resell',
      bestOptionLabel: 'Resell at market value',
      alternatives: ['Refurbish', 'Repair'],
    }
  }
  if (cond === 'Average') {
    return {
      decision: 'Refurbish',
      bestOptionLabel: 'Refurbish & Resell',
      alternatives: ['Repair', 'Resell as-is'],
    }
  }
  if (cond === 'Poor') {
    return {
      decision: 'Recycle',
      bestOptionLabel: 'Certified e-waste recycling',
      alternatives: ['Scrap parts'],
    }
  }
  if (metalRecoveryValue >= 8000) {
    return {
      decision: 'Scrap parts',
      bestOptionLabel: 'Harvest boards & precious metals',
      alternatives: ['Recycle'],
    }
  }
  if (cond === 'Good') {
    return {
      decision: 'Resell',
      bestOptionLabel: 'Resell',
      alternatives: ['Refurbish'],
    }
  }
  return {
    decision: 'Refurbish',
    bestOptionLabel: 'Refurbish & Resell',
    alternatives: ['Resell', 'Recycle'],
  }
}

export function computeManualValuation(row, form) {
  const basePrice = Number(row.Original_Price) || Number(row.base_price_inr) || 0
  const condition = String(form.conditionLabel || row.Condition_Label || 'Good').trim()
  const cf = CONDITION_FACTORS[condition] ?? 0.65
  const af = ageFactor(form.ageYears)
  const df = damageFactor(form.screenDamage, form.bodyDamage, form.waterDamage)
  const resaleValue = Math.max(500, Math.round(basePrice * cf * af * df))

  const repairCost = repairCostFromBase(basePrice, condition)
  const net = resaleValue - repairCost
  const profit = net >= 0 ? net : 0
  const loss = net < 0 ? -net : 0

  const metalRecoveryValue = estimateMetalRecoveryInr(row.Device_Type || row.category)

  const { decision, bestOptionLabel, alternatives } = computeSmartDecision({
    conditionLabel: condition,
    waterDamage: form.waterDamage,
    resaleValue,
    basePrice,
    metalRecoveryValue,
  })

  const risk = riskForCondition(condition, form.waterDamage)

  const deviceHealth = Math.max(22, Math.min(96, Math.round(cf * 100 - Number(form.ageYears) * 5)))
  const lifecycleCompletion = Math.max(18, Math.min(92, Math.round(78 - Number(form.ageYears) * 4 + cf * 12)))

  return {
    id: `manual-${row.Model}-${condition}-${form.ageYears}-${Date.now()}`,
    basePrice,
    condition,
    deviceName: row.device_name || `${row.Brand} ${row.Model}`,
    model: row.Model,
    brand: row.Brand,
    deviceType: row.Device_Type,
    component: `${row.Device_Type || 'Device'} · ${row.Brand || ''} ${row.Model || ''}`.trim(),
    metals: {},
    metalParts: [],
    value: metalRecoveryValue,
    metalRecoveryValue,
    resaleValue,
    repairCost,
    profit,
    loss,
    netMargin: net,
    risk,
    decision,
    bestOptionLabel,
    decisionAlternatives: alternatives,
    deviceHealth,
    co2Saved: Number((resaleValue / 2400).toFixed(1)),
    lifecycleCompletion,
    status: {
      repairable: condition !== 'Poor',
      hazardous: condition === 'Poor' || String(form.waterDamage).toLowerCase() === 'yes',
      recyclable: true,
    },
    createdAt: new Date().toISOString(),
    deviceInfo: {
      deviceType: row.Device_Type,
      brand: row.Brand,
      model: row.Model,
      ageYears: form.ageYears,
      conditionLabel: condition,
      screenDamage: form.screenDamage,
      bodyDamage: form.bodyDamage,
      waterDamage: form.waterDamage,
    },
    metalCompositionNote:
      'Estimated content uses category weights vs static spot: gold ₹7200/10g, silver ₹88/g, copper ₹765/kg, palladium ₹2400/10g.',
  }
}

export function enrichScan(scan) {
  if (!scan) return null
  const resaleValue = scan.resaleValue ?? scan.value ?? 0
  const repairCost =
    scan.repairCost ?? repairCostFromBase(scan.basePrice ?? resaleValue * 2, scan.condition || 'Good')
  const net = resaleValue - repairCost
  const condition = scan.condition ?? (scan.risk === 'High' ? 'Poor' : scan.risk === 'Medium' ? 'Average' : 'Good')
  const basePrice = scan.basePrice ?? resaleValue * 2.5
  const metalRecoveryValue = scan.metalRecoveryValue ?? scan.value ?? 0
  const water = scan.deviceInfo?.waterDamage ?? 'No'
  const { decision, bestOptionLabel, alternatives } = computeSmartDecision({
    conditionLabel: condition,
    waterDamage: water,
    resaleValue,
    basePrice,
    metalRecoveryValue,
  })
  return {
    ...scan,
    resaleValue,
    repairCost,
    profit: net >= 0 ? net : 0,
    loss: net < 0 ? -net : 0,
    netMargin: net,
    decision: scan.decision ?? decision,
    bestOptionLabel: scan.bestOptionLabel ?? bestOptionLabel,
    decisionAlternatives: scan.decisionAlternatives ?? alternatives,
    condition,
    deviceInfo: scan.deviceInfo,
    metalCompositionNote: scan.metalCompositionNote,
  }
}
