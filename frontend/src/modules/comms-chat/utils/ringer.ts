// spielt /ding.mp3 in Endlosschleife pro Chat-ID
const loops = new Map<number, HTMLAudioElement>()

export function startRing(id: number) {
  if (loops.has(id)) return
  const a = new Audio('/ding.mp3')
  a.loop = true
  // Lautstärke optional:
  a.volume = 1.0
  a.play().catch(() => { /* Autoplay wartet bis erste User-Interaktion */ })
  loops.set(id, a)
}

export function stopRing(id: number) {
  const a = loops.get(id)
  if (!a) return
  try { a.pause(); a.currentTime = 0 } catch {}
  loops.delete(id)
}

export function stopAllRings() {
  for (const id of Array.from(loops.keys())) stopRing(id)
}
