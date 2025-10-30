import { ref } from 'vue'

export function useScans() {
  const scan   = ref<any>(null)
  const counts = ref<any>(null)
  const reports = ref<any[]>([])
  const findings = ref<any[]>([])

  async function loadScan(_id?: string) {}
  async function startScan(_id?: string) {}
  async function cancelScan(_id?: string) {}
  async function loadReports(_scanId?: string) {}
  async function loadFindings(_scanId?: string) {}
  function subscribe(_scanId?: string) {}
  function unsubscribe() {}

  return { scan, counts, reports, findings,
           loadScan, startScan, cancelScan,
           loadReports, loadFindings, subscribe, unsubscribe }
}
export default useScans
