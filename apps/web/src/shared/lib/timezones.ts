// A short, curated fallback for environments where
// `Intl.supportedValuesOf` doesn't exist (older browsers, some jsdom/test
// setups) — covers the regions this app's users are most likely in.
const FALLBACK_TIMEZONES = [
  "UTC",
  "Europe/Warsaw",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Kyiv",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
];

// `Intl.supportedValuesOf` (ES2022) isn't in this project's `tsconfig` lib
// target — narrowly typed here rather than widening the whole app's lib
// setting for one API.
type IntlWithSupportedValuesOf = typeof Intl & {
  supportedValuesOf?: (key: "timeZone") => string[];
};

export function listTimezones(): string[] {
  const supported = (Intl as IntlWithSupportedValuesOf).supportedValuesOf?.("timeZone");
  return supported && supported.length > 0 ? supported : FALLBACK_TIMEZONES;
}
