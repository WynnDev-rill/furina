// Compatibility export for older server functions. It deliberately uses the request's
// bearer token with the public Supabase key so Row Level Security remains authoritative.
// A service-role client must never be used for user-scoped Furina memory operations.
import { createClient } from '@supabase/supabase-js';
import { getRequest } from '@tanstack/react-start/server';
import type { Database } from './types';

const RETIRED_LEGACY_PROJECT_REF = 'smltficntqkoncyrnajx';

function createRequestScopedClient() {
  const SUPABASE_URL = process.env.SUPABASE_URL?.trim();
  const SUPABASE_PUBLISHABLE_KEY = process.env.SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
    const missing = [
      ...(!SUPABASE_URL ? ['SUPABASE_URL'] : []),
      ...(!SUPABASE_PUBLISHABLE_KEY ? ['SUPABASE_PUBLISHABLE_KEY'] : []),
    ];
    throw new Error(`Missing Supabase environment variable(s): ${missing.join(', ')}`);
  }

  let host: string;
  try {
    host = new URL(SUPABASE_URL).hostname.toLowerCase();
  } catch {
    throw new Error('Invalid SUPABASE_URL');
  }

  // The old Lovable-managed backend is no longer under Wynn's connected Supabase control.
  // Fail closed rather than silently sending user-scoped memory traffic to an unmanaged project.
  if (host === `${RETIRED_LEGACY_PROJECT_REF}.supabase.co`) {
    throw new Error('Retired Furina legacy Supabase backend is blocked');
  }

  const request = getRequest();
  const authorization = request.headers.get('authorization') || '';
  return createClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    global: {
      headers: authorization ? { Authorization: authorization } : {},
    },
    auth: {
      storage: undefined,
      persistSession: false,
      autoRefreshToken: false,
    },
  });
}

// Kept under the old name so existing legacy server functions fail closed without a risky bulk rewrite.
// Every property access resolves a client for the current request; RLS and auth.uid() remain authoritative
// for any future explicitly managed backend.
export const supabaseAdmin = new Proxy({} as ReturnType<typeof createRequestScopedClient>, {
  get(_, prop) {
    const client = createRequestScopedClient();
    const value = Reflect.get(client, prop, client);
    return typeof value === 'function' ? value.bind(client) : value;
  },
});
