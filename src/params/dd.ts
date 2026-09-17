import type { ParamMatcher } from '@sveltejs/kit';

/** Zero-padded day, 01-31. Calendar validity is checked in the load function. */
export const match: ParamMatcher = (param) => /^(0[1-9]|[12]\d|3[01])$/.test(param);
