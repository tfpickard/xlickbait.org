import type { ParamMatcher } from '@sveltejs/kit';

/** Four digits, 1900-2999. Keeps `/[yyyy]/[mm]/[dd]` from swallowing junk. */
export const match: ParamMatcher = (param) => /^(19|20|21)\d{2}$/.test(param);
