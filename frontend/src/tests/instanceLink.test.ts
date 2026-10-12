//// Neoffice — added file (no upstream equivalent): the macro `{{ InstanceLink("/app/…", "…") }}` and its address rules.
import { describe, expect, it } from 'vitest'
import {
	buildInstanceUrl,
	isAllowedOrigin,
	isAllowedPath,
	parseInstanceLink,
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
		expect(isAllowedOrigin('https://dmis.neoffice.me')).toBe(true)
		expect(isAllowedOrigin('https://erp.client-example.ch')).toBe(true)
	})

	it('refuses http, a path, a port and credentials (look-alike domains are the server list\'s job)', () => {
		for (const origin of [
			'http://dmis.neoffice.me',
			'https://dmis.neoffice.me/',
			'https://dmis.neoffice.me/app',
			'https://dmis.neoffice.me:8000',
			'https://user:pass@dmis.neoffice.me',
			'https://localhost',
			'//dmis.neoffice.me',
			'dmis.neoffice.me',
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
		expect(buildInstanceUrl('https://dmis.neoffice.me', '/app/item/new')).toBe(
			'https://dmis.neoffice.me/app/item/new'
		)
	})

	it('returns null when the path or the base is not acceptable', () => {
		expect(buildInstanceUrl('', '/login')).toBeNull()
		expect(buildInstanceUrl('https://dmis.neoffice.me', '/app/item?x=1')).toBeNull()
		expect(buildInstanceUrl('http://dmis.neoffice.me', '/app/item')).toBeNull()
		expect(buildInstanceUrl('https://dmis.neoffice.me/x', '/app/item')).toBeNull()
	})
})
