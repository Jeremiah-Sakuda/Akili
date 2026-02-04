export enum AppState {
  UPLOAD = 'UPLOAD',
  VERIFIED = 'VERIFIED',
  REFUSED = 'REFUSED'
}

/** Document from API (GET /documents) or after ingest */
export interface DocumentFile {
  id: string;
  name: string;
  meta: string;
  icon: string;
  active?: boolean;
}

/** Query result from API: answer + proof or refuse */
export type QueryResult =
  | { status: 'answer'; answer: string; proof: Array<{ x: number; y: number; source_id?: string | null; source_type?: string | null }> }
  | { status: 'refuse'; reason: string };