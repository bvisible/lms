//// Neoffice — added file (no upstream equivalent)
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VideoPreview from '@/components/VideoPreview.vue'

describe('VideoPreview poster', () => {
	it('shows the course image as the poster of a hosted film', () => {
		const wrapper = mount(VideoPreview, {
			props: { videoLink: '/files/film.mp4', fallbackImage: '/files/cover.jpg' },
			global: { mocks: { __: (s: string) => s } },
		})
		const video = wrapper.find('video')
		expect(video.exists()).toBe(true)
		expect(video.attributes('poster')).toBe('/files/cover.jpg')
	})
	it('has no poster when the course has no image', () => {
		const wrapper = mount(VideoPreview, {
			props: { videoLink: '/files/film.mp4', fallbackImage: null },
			global: { mocks: { __: (s: string) => s } },
		})
		expect(wrapper.find('video').attributes('poster')).toBeUndefined()
	})
})
