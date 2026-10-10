//// Neoffice — added file (no upstream equivalent)
import { describe, expect, it } from 'vitest'
import { youtubeEmbedUrl, YOUTUBE_EMBED_PARAMS } from '@/utils/youtubeEmbed'

describe('youtubeEmbedUrl', () => {
	it('uses the no-cookie host and keeps the related videos to the same channel', () => {
		const url = new URL(youtubeEmbedUrl('0k1tWv1Mj5M'))
		expect(url.origin).toBe('https://www.youtube-nocookie.com')
		expect(url.pathname).toBe('/embed/0k1tWv1Mj5M')
		expect(url.searchParams.get('rel')).toBe('0')
	})
	it('does not ask for captions, annotations or a full-screen player on a phone', () => {
		const params = new URL(youtubeEmbedUrl('abc')).searchParams
		expect(params.get('cc_load_policy')).toBe('0')
		expect(params.get('iv_load_policy')).toBe('3')
		expect(params.get('playsinline')).toBe('1')
		expect(YOUTUBE_EMBED_PARAMS).toContain('rel=0')
	})
	it('keeps an identifier that starts with a dash or holds an underscore', () => {
		expect(youtubeEmbedUrl('-1PiY6eq1-A')).toContain('/embed/-1PiY6eq1-A?')
		expect(youtubeEmbedUrl('e8iVnNft_sc')).toContain('/embed/e8iVnNft_sc?')
	})
	it('cannot be turned into another path by a crafted identifier', () => {
		expect(youtubeEmbedUrl('x/../../evil')).not.toContain('/../')
	})
})
