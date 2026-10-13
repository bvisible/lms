//// Neoffice — added file (no upstream equivalent).
//// `{{ InstanceLink("/app/nora-demo/new", "Open the practice form in your Neoffice") }}`: a lesson macro that opens, in a new tab,
//// the Neoffice of the person who follows the course, on the screen the lesson talks about. The pure parts are here so that
//// they are unit-tested (src/tests/instanceLink.test.ts); the base address comes from the server (lms.lms.neoffice_instance),
//// never from the lesson, never from the address of the page.
//// Rules (the server applies the same ones and has the last word):
////  - the path is a desk path of a doctype, a new document or a list, nothing else (`/app/<doctype>`, `/app/<doctype>/new`,
////    `/app/<doctype>/view/list`), with no query string and no fragment: a lesson cannot carry data to the instance;
////  - the base is an https origin with no path, taken from the learner's registered instance (or empty when the course lives on
////    the instance itself: the link is then relative to the same site);
////  - for the staff of an accounting firm (one Neoffice per client) the link goes through the hub, which checks the mandate and
////    signs the person in: `/api/method/lms.lms.neoffice_instance.open_instance?instance=<id>&path=<path>`.
//// At the merge: kept whole.

export interface InstanceLinkMacro {
	path: string
	label: string
}

const MACRO_RE =
	/\{\{\s*InstanceLink\(\s*(["'])(.*?)\1\s*,\s*(["'])(.*?)\3\s*\)\s*\}\}/s

// /app/<doctype>[/new | /view/list | /view/report | /view/kanban] : lowercase words and hyphens, as the desk writes a doctype.
export const ALLOWED_PATH =
	/^\/app\/[a-z0-9][a-z0-9_-]{0,60}(?:\/(?:new|view\/(?:list|report|kanban)))?$/

// https://<host>[.<host>…] with no path, no port, no credentials.
export const ALLOWED_ORIGIN =
	/^https:\/\/[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62}){1,4}$/

export function parseInstanceLink(block: string): InstanceLinkMacro | null {
	const match = block.match(MACRO_RE)
	if (!match) return null
	const path = match[2].trim()
	const label = match[4].trim()
	if (!path || !label) return null
	return { path, label }
}

export function isAllowedPath(path: string): boolean {
	return ALLOWED_PATH.test(path)
}

export function isAllowedOrigin(origin: string): boolean {
	return ALLOWED_ORIGIN.test(origin)
}

/**
 * The address a link points to: the path alone when the base is empty (the course lives on the instance), the base plus the
 * path when the base is a registered instance. null when either part is not acceptable: the caller then shows no link.
 */
export function buildInstanceUrl(base: string, path: string): string | null {
	if (!isAllowedPath(path)) return null
	if (!base) return path
	if (!isAllowedOrigin(base)) return null
	return base + path
}

export interface FiduciaryOption {
	instance: string
	label: string
	host: string
}

// The id of a client instance as the hub names it (SRV-9001): letters, digits, dot, dash, underscore.
const INSTANCE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,139}$/

/**
 * The address of a link for the staff of an accounting firm: the hub opens the chosen client's Neoffice, signed in, on the page
 * of the lesson. null when the path or the client is not acceptable: the caller then shows no link.
 */
export function buildFiduciaryUrl(instance: string, path: string): string | null {
	if (!isAllowedPath(path) || !INSTANCE_ID.test(instance)) return null
	return (
		'/api/method/lms.lms.neoffice_instance.open_instance?instance=' +
		encodeURIComponent(instance) +
		'&path=' +
		encodeURIComponent(path)
	)
}

/** The client to preselect: the one remembered if it is still offered, the first (or only) one otherwise. */
export function pickFiduciaryOption(
	options: FiduciaryOption[],
	remembered: string | null
): FiduciaryOption | null {
	if (!options.length) return null
	return options.find((option) => option.instance === remembered) || options[0]
}
