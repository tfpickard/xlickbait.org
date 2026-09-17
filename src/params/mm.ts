import type { ParamMatcher } from '@sveltejs/kit';

/** Zero-padded month, 01-12. Padding is required so each day has one URL. */
export const match: ParamMatcher = (param) => /^(0[1-9]|1[0-2])$/.test(param);
