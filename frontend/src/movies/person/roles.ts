// The person page's role types and the words used for each role.
import type { PersonDetail } from '@/api/client'

export type Role = PersonDetail['roles'][number]
export type RoleName = Role['role']

export const ROLE_TEXT: Record<RoleName, { noun: string; verb?: string; cast: string }> = {
  acting: { noun: 'Actor', cast: 'Most often with' },
  directing: { noun: 'Director', verb: 'Directed', cast: 'Most often cast' },
  writing: { noun: 'Writer', verb: 'Wrote', cast: 'Most often with' },
  production: { noun: 'Producer', verb: 'Produced', cast: 'Most often with' },
  music: { noun: 'Composer', verb: 'Scored', cast: 'Most often with' },
  camera: { noun: 'Cinematographer', verb: 'Shot', cast: 'Most often with' },
  editing: { noun: 'Editor', verb: 'Edited', cast: 'Most often with' },
}
