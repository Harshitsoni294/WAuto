import { addDays, setHours, setMinutes, setSeconds } from 'date-fns'

function tryParseClock(s) {
  // returns {hours, minutes} or null
  const m1 = s.match(/^(\d{1,2}):(\d{2})\s*(am|pm)?$/i)
  if (m1) {
    let h = parseInt(m1[1], 10)
    const min = parseInt(m1[2], 10)
    const ap = m1[3]?.toLowerCase()
    if (ap === 'pm' && h < 12) h += 12
    if (ap === 'am' && h === 12) h = 0
    return { hours: h, minutes: min }
  }
  const m2 = s.match(/^(\d{1,2})\s*(am|pm)$/i)
  if (m2) {
    let h = parseInt(m2[1], 10)
    const ap = m2[2].toLowerCase()
    if (ap === 'pm' && h < 12) h += 12
    if (ap === 'am' && h === 12) h = 0
    return { hours: h, minutes: 0 }
  }
  const m3 = s.match(/^(\d{1,2})$/)
  if (m3) {
    let h = parseInt(m3[1], 10)
    if (h >= 0 && h <= 23) return { hours: h, minutes: 0 }
  }
  return null
}

export function parseNaturalDateTime(input) {
  // supports: "today 5pm", "tomorrow 14:30", "5pm today", "tomorrow at 9"
  const lower = input.toLowerCase().trim()
  let base = new Date()
  let timePart = lower

  if (lower.includes('tomorrow')) {
    base = addDays(base, 1)
    timePart = lower.replace('tomorrow', '').replace('at', '').trim()
  } else if (lower.includes('today')) {
    timePart = lower.replace('today', '').replace('at', '').trim()
  } else if (/\d{4}-\d{2}-\d{2}/.test(lower)) {
    // yyyy-mm-dd hh:mm?
    const [dateStr, rest] = lower.split(/\s+/)
    const [y, m, d] = dateStr.split('-').map(n=>parseInt(n,10))
    base = new Date(y, m-1, d)
    timePart = rest || '09:00'
  } else if (/\d{1,2}\/\d{1,2}(\/\d{2,4})?/.test(lower)) {
    // mm/dd[/yyyy] hh:mm?
    const [dateStr, rest] = lower.split(/\s+/)
    const [mm, dd, yy] = dateStr.split('/')
    const y = yy ? parseInt(yy,10) : new Date().getFullYear()
    base = new Date(y, parseInt(mm,10)-1, parseInt(dd,10))
    timePart = rest || '09:00'
  } else {
    // default: today
    timePart = lower.replace('at', '').trim()
  }

  const t = tryParseClock(timePart)
  if (t) {
    let dt = setSeconds(setMinutes(setHours(new Date(base), t.hours), t.minutes), 0)
    // If time has already passed today, roll to next day
    if (dt < new Date()) dt = addDays(dt, 1)
    return dt
  }

  // fallback: 1 hour from now
  return new Date(Date.now() + 60*60*1000)
}
