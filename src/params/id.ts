import type { ParamMatcher } from '@sveltejs/kit';

/**
 * A bare positive integer id, with no leading zeros.
 *
 * Bounded to sixteen digits so `/i/<id>` cannot be handed a thousand-digit
 * number that reaches `Number()` and the database as something neither can
 * represent. The route re-checks with `Number.isSafeInteger`; this keeps the
 * obviously malformed shapes from ever becoming a request.
 */
export const match: ParamMatcher = (param) => /^[1-9]\d{0,15}$/.test(param);
