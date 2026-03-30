/** Rule-based repair assistant (mock AI). */
export function getRepairReply(userMessage, context) {
  const q = String(userMessage || '').toLowerCase()
  const device = context?.label || 'this device'

  if (/water|liquid|wet/i.test(q)) {
    return [
      '1. Power off immediately and do not charge.',
      '2. Remove battery if possible; dry exterior with a lint-free cloth.',
      '3. Place in a dry, ventilated area; silica gel helps — avoid heat guns.',
      '4. For phones/laptops, professional ultrasonic cleaning may be needed within 48h.',
      `5. If ${device} still fails after drying, assume board corrosion — plan for board swap or recycle.`,
    ].join('\n')
  }

  if (/screen|display|lcd|oled|glass/i.test(q)) {
    return [
      '1. Power down and remove any case or screen protector.',
      '2. Heat the adhesive edge gently (60–80°C max) if opening is required.',
      '3. Disconnect battery first, then flex cables for the panel.',
      '4. Install a compatible panel; re-seat connectors and test before sealing.',
      '5. Calibrate touch if the OS prompts; verify dead pixels under solid colors.',
    ].join('\n')
  }

  if (/battery|charge|power|swell/i.test(q)) {
    return [
      '1. Discharge to ~25% in a safe area if swelling is suspected.',
      '2. Use correct screwdrivers; track screw lengths for reassembly.',
      '3. Disconnect battery connector before other work.',
      '4. Replace with an OEM-grade or certified cell; reset battery health if applicable.',
      '5. Run charge cycles and monitor temperature for 24h.',
    ].join('\n')
  }

  if (/speaker|mic|audio|sound/i.test(q)) {
    return [
      '1. Clean grille with soft brush; avoid liquids near openings.',
      '2. Test in safe mode or alternate OS to rule out software.',
      '3. Re-seat flex cables for audio daughterboard if accessible.',
      '4. Replace module if crackling persists after cleaning.',
    ].join('\n')
  }

  if (/how|fix|repair|steps/i.test(q)) {
    return `For ${device}: start with diagnostics (battery health, storage, thermals). Share the symptom (e.g. “won’t boot”, “lines on screen”) for step-by-step guidance.`
  }

  return [
    `I can help with ${device}. Try asking:`,
    '• “How to fix screen?”',
    '• “Battery replacement steps”',
    '• “Water damage — what now?”',
  ].join('\n')
}
