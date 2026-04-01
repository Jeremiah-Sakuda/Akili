/**
 * MSW server setup for Node.js / vitest environment.
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
