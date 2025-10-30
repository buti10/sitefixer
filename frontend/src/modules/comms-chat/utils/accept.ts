import { useChatUi } from '../stores/UiStore'
import { stopRing } from '../utils/ringer'

export function acceptChat(id:number){
  const ui = useChatUi()
  ui.acknowledge(id)
  stopRing(id)
}
