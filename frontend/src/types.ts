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
