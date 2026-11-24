import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { usersStore } from './user'
import { forgetContinuePanelClosed } from '@/utils/continuePanel'
import { computed, reactive, ref } from 'vue'

export const sessionStore = defineStore('lms-session', () => {
	let { userResource } = usersStore()
	const brand = reactive({})

	function sessionUser() {
		let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
		let _sessionUser = cookies.get('user_id')
		if (_sessionUser === 'Guest') {
			_sessionUser = null
		} else {
			userResource.reload()
		}
		return _sessionUser
	}

	let user = ref(sessionUser())
	const isLoggedIn = computed(() => !!user.value)

	const logout = createResource({
		url: 'logout',
		onSuccess() {
			userResource.reset()
			user.value = null
			// A closed continue-your-course panel comes back on the next sign-in.
			forgetContinuePanelClosed()
			window.location.reload()
		},
	})

	const branding = createResource({
		url: 'lms.lms.api.get_branding',
		cache: 'brand',
		auto: true,
		onSuccess(data) {
			brand.name = data.app_name
			brand.logo = data.app_logo
			//// Neoffice — upstream falls back on its own mark, which replaced the icon of the page (the site's, or ours:
			//// lms/www/_lms.py) on every screen without the cockpit, a phone's first. Without one, the page keeps its own.
			brand.favicon = data.favicon?.file_url
		},
	})

	return {
		user,
		isLoggedIn,
		logout,
		brand,
		branding,
	}
})
