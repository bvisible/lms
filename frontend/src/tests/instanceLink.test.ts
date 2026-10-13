//// Neoffice — added file (no upstream equivalent): the macro `{{ InstanceLink("/app/…", "…") }}` and its address rules.
import { describe, expect, it } from 'vitest'
import {
	buildFiduciaryUrl,
	buildInstanceUrl,
	isAllowedOrigin,
	isAllowedPath,
	parseInstanceLink,
	pickFiduciaryOption,
} from '@/utils/instanceLink'

describe('parseInstanceLink', () => {
	it('reads the path and the label of the macro', () => {
		expect(
			parseInstanceLink(
				'{{ InstanceLink("/app/nora-demo/new", "Ouvrir le formulaire d\'essai") }}'
			)
		).toEqual({
			path: '/app/nora-demo/new',
			label: "Ouvrir le formulaire d'essai",
		})
	})

	it('accepts single quotes and spaces around the arguments', () => {
		expect(
			parseInstanceLink("{{InstanceLink( '/app/item' ,'Les articles' )}}")
		).toEqual({ path: '/app/item', label: 'Les articles' })
	})

	it('returns null for a macro with one argument, empty arguments or no macro', () => {
		expect(parseInstanceLink('{{ InstanceLink("/app/item") }}')).toBeNull()
		expect(parseInstanceLink('{{ InstanceLink("", "x") }}')).toBeNull()
		expect(parseInstanceLink('{{ InstanceLink("/app/item", "") }}')).toBeNull()
		expect(parseInstanceLink('plain text')).toBeNull()
		expect(parseInstanceLink('{{ InstanceLink( }}')).toBeNull()
	})
})

describe('isAllowedPath', () => {
	it('accepts a doctype, a new document and the list views', () => {
		for (const path of [
			'/app/item',
			'/app/item/new',
			'/app/nora-demo/new',
			'/app/sales-invoice/view/list',
			'/app/quotation/view/report',
			'/app/task/view/kanban',
		])
			expect(isAllowedPath(path)).toBe(true)
	})

	it('refuses anything that could carry data or leave the desk', () => {
		for (const path of [
			'/app/item?name=x',
			'/app/item#top',
			'/app/item/COURS-1',
			'/app/item/new?item_code=x',
			'/api/method/frappe.ping',
			'/login',
			'//evil.example/app/item',
			'https://evil.example/app/item',
			'/app/',
			'/app/Item',
			'/app/item/../user',
			'/app/item/view/../x',
			'javascript:alert(1)',
			'',
		])
			expect(isAllowedPath(path)).toBe(false)
	})
})

describe('isAllowedOrigin', () => {
	it('accepts an https host with no path', () => {
		expect(isAllowedOrigin('https://example.neoffice.me')).toBe(true)
		expect(isAllowedOrigin('https://erp.client-example.ch')).toBe(true)
	})

	it('refuses http, a path, a port and credentials (look-alike domains are the server list\'s job)', () => {
		for (const origin of [
			'http://example.neoffice.me',
			'https://example.neoffice.me/',
			'https://example.neoffice.me/app',
			'https://example.neoffice.me:8000',
			'https://user:pass@example.neoffice.me',
			'https://localhost',
			'//example.neoffice.me',
			'example.neoffice.me',
			'',
		])
			expect(isAllowedOrigin(origin)).toBe(false)
	})
})

describe('buildInstanceUrl', () => {
	it('is relative when the course lives on the instance (empty base)', () => {
		expect(buildInstanceUrl('', '/app/item/new')).toBe('/app/item/new')
	})

	it('joins a registered instance and the path', () => {
		expect(buildInstanceUrl('https://example.neoffice.me', '/app/item/new')).toBe(
			'https://example.neoffice.me/app/item/new'
		)
	})

	it('returns null when the path or the base is not acceptable', () => {
		expect(buildInstanceUrl('', '/login')).toBeNull()
		expect(buildInstanceUrl('https://example.neoffice.me', '/app/item?x=1')).toBeNull()
		expect(buildInstanceUrl('http://example.neoffice.me', '/app/item')).toBeNull()
		expect(buildInstanceUrl('https://example.neoffice.me/x', '/app/item')).toBeNull()
	})
})

describe('buildFiduciaryUrl', () => {
	it('goes through the hub with the client and the page, both encoded', () => {
		expect(buildFiduciaryUrl('SRV-9001', '/app/nora-demo/new')).toBe(
			'/api/method/lms.lms.neoffice_instance.open_instance?instance=SRV-9001&path=%2Fapp%2Fnora-demo%2Fnew'
		)
	})

	it('returns null when the page or the client is not acceptable', () => {
		expect(buildFiduciaryUrl('SRV-9001', '/login')).toBeNull()
		expect(buildFiduciaryUrl('SRV-9001', '/app/item?x=1')).toBeNull()
		for (const instance of ['', ' SRV-9001', 'SRV 0029', 'a/b', 'a&path=/login', '-x', 'x'.repeat(141)])
			expect(buildFiduciaryUrl(instance, '/app/item')).toBeNull()
	})
})

describe('pickFiduciaryOption', () => {
	const options = [
		{ instance: 'SRV-9001', label: 'Osiris SA', host: 'osiris.neoffice.me' },
		{ instance: 'SRV-9002', label: 'Example SA', host: 'example.ch' },
	]

	it('keeps the remembered client while it is still offered', () => {
		expect(pickFiduciaryOption(options, 'SRV-9002')?.label).toBe('Example SA')
	})

	it('falls back to the first client', () => {
		expect(pickFiduciaryOption(options, null)?.instance).toBe('SRV-9001')
		expect(pickFiduciaryOption(options, 'SRV-9003')?.instance).toBe('SRV-9001')
	})

	it('has nothing to pick without clients', () => {
		expect(pickFiduciaryOption([], 'SRV-9001')).toBeNull()
	})
})
