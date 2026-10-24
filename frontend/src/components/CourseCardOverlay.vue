<template>
	<div class="border-2 rounded-5 min-w-80 max-w-sm">
		<VideoPreview
			:video-link="course.data?.video_link"
			:fallback-image="course.data?.image"
		/>
		<div class="p-5">
			<div class="text-3xl-semibold text-ink-gray-9 mb-4">
				{{ priceLabel }}
			</div>
			<div v-if="!readOnlyMode">
				<div v-if="course.data?.membership" class="space-y-2 mb-8">
					<ProgressBar :progress="progress" :label="__('Course progress')" />
					<div v-if="lessonCounts.total" class="text-p-sm text-ink-gray-7">
						{{ lessonsCompletedLabel }}
					</div>
					<Button
						variant="solid"
						size="md"
						class="w-full"
						:route="{
							name: 'Lesson',
							params: {
								courseName: course.data?.name,
								chapterNumber: course?.data?.current_lesson
									? course?.data?.current_lesson.split('-')[0]
									: 1,
								lessonNumber: course?.data?.current_lesson
									? course?.data?.current_lesson.split('-')[1]
									: 1,
							},
						}"
					>
						<template #prefix>
							<span class="lucide-book-text size-4" />
						</template>
						<span>
							{{ progress ? __('Continue Learning') : __('Start Learning') }}
						</span>
					</Button>
					<CertificationLinks :courseName="course.data.name" class="w-full" />
				</div>
				<!-- //// Neoffice — d6d8abd2 « le bouton d'achat d'un cours part vers le panier ».
				//// Upstream sends a paid course to its own Billing route. When an Item sells the
				//// course we send the visitor to the shop product page instead, so the cart,
				//// TWINT, Stripe, the invoice and the accounting entries all come with it.
				//// At the merge: keep BOTH branches, and keep ours FIRST — upstream's Button
				//// below is the fallback, and the two are made exclusive by their order. -->
				<!-- Neoffice: when an Item sells this course, buying goes through the
				     shop cart — TWINT / Stripe / invoice / accounting all come with
				     it. The LMS's own checkout is only the fallback, and having both
				     live at once would mean two tunnels for one course. -->
				<a
					v-else-if="course.data?.paid_course && !isAdmin && shopRoute.data"
					:href="safeUrl(shopRoute.data)"
				>
					<Button variant="solid" size="md" class="w-full mb-8">
						<template #prefix>
							<span class="lucide-shopping-cart size-4" />
						</template>
						<span>
							{{ __('Buy this course') }}
						</span>
					</Button>
				</a>
				<Button
					v-else-if="course.data?.paid_course && !isAdmin"
					variant="solid"
					size="md"
					class="w-full mb-8 text-p-base-medium"
					:route="{
						name: 'Billing',
						params: {
							type: 'course',
							name: course.data.name,
						},
					}"
				>
					<template #prefix>
						<span class="lucide-credit-card size-4" />
					</template>
					<span>
						{{ __('Buy this course') }}
					</span>
				</Button>
				<Badge
					v-else-if="course.data?.disable_self_learning && !isAdmin"
					theme="blue"
					size="lg"
					class="mb-4"
				>
					{{ __('Contact the Administrator to enroll for this course') }}
				</Badge>
				<Button
					v-else-if="!isAdmin"
					@click="enrollStudent()"
					variant="solid"
					class="w-full mb-8"
					size="md"
				>
					<template #prefix>
						<span class="lucide-book-text size-4" />
					</template>
					<span>
						{{ __('Enroll Now') }}
					</span>
				</Button>
				<Button
					v-if="canGetCertificate"
					@click="fetchCertificate()"
					variant="subtle"
					class="w-full mt-2"
					size="md"
				>
					<template #prefix>
						<span class="lucide-graduation-cap size-4" />
					</template>
					{{ __('Get Certificate') }}
				</Button>
			</div>
			<section v-if="hasCourseStats" class="space-y-3">
				<div class="text-base text-ink-gray-9 mb-1">
					{{ __('This course includes:') }}
				</div>
				<div
					v-if="enrolledLabel"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-users size-4 shrink-0 text-ink-gray-7" />
					<span>{{ enrolledLabel }} {{ __('enrolled') }}</span>
				</div>
				<div
					v-if="course.data?.video_link"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-monitor-play size-4 shrink-0 text-ink-gray-7" />
					<span>{{ __('On demand course video') }}</span>
				</div>
				<div
					v-if="course.data?.lessons"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-book-open size-4 shrink-0 text-ink-gray-7" />
					<span>
						{{ course.data?.lessons }}
						{{ course.data?.lessons === 1 ? __('Lesson') : __('Lessons') }}
					</span>
				</div>
				<div
					v-if="(course.data?.quiz_count || 0) > 0"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-help-circle size-4 shrink-0 text-ink-gray-7" />
					<span>
						{{ course.data?.quiz_count }}
						{{
							course.data?.quiz_count === 1
								? __('Quiz topic')
								: __('Quiz topics')
						}}
					</span>
				</div>
				<div
					v-if="course.data?.enable_certification"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-award size-4 shrink-0 text-ink-gray-7" />
					<span>{{ __('Certificate of completion') }}</span>
				</div>
			</section>
		</div>
	</div>
</template>
<script setup lang="ts">
//// Neoffice — d6d8abd2: `watch` added to upstream's import; the shop route is fetched
//// when the course resource resolves (see below).
import { computed, inject, watch } from 'vue'
import { Badge, Button, call, createResource, toast } from 'frappe-ui'
import type { FrappeResourceError } from 'frappe-ui'
import { resourceErrorMessage } from '@/utils/resource'
import { useRouter } from 'vue-router'
import CertificationLinks from '@/components/CertificationLinks.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import VideoPreview from '@/components/VideoPreview.vue'
import { openExternal } from '@/utils/openExternal'
//// Neoffice — for the shop link below: upstream's urlAttributeSafety test covers every bound :href.
import { safeUrl } from '@/utils/safeUrl'
import type { CourseDetails, Resource, SessionUser } from '@/types'
import { isInstructorOf } from '@/utils/instructors'

const router = useRouter()
const user = inject<SessionUser>('$user')!
const readOnlyMode = (window as Window & { read_only_mode?: boolean })
	.read_only_mode

const props = withDefaults(
	defineProps<{
		course: Resource<CourseDetails | null>
	}>(),
	{}
)

//// Neoffice — d6d8abd2: upstream has no shop route at all.
// Resolved once per course; null when no Item sells it, in which case the LMS
// checkout stays in place.
const shopRoute = createResource({
	url: 'lms.lms.neoffice_commerce.get_shop_route',
	makeParams: () => ({ course: props.course.data?.name }),
})

function enrollStudent() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	const courseName = props.course.data?.name
	if (!courseName) return
	call('frappe.client.insert', {
		doc: {
			doctype: 'LMS Enrollment',
			course: courseName,
			member: user.data.name,
		},
	})
		.then(() => {
			toast.success(__('You have been enrolled in this course'))
			setTimeout(() => {
				router.push({
					name: 'Lesson',
					params: {
						courseName,
						chapterNumber: 1,
						lessonNumber: 1,
					},
				})
			}, 1000)
		})
		.catch((err: FrappeResourceError) => {
			const msg = resourceErrorMessage(err, 'Error')
			toast.warning(__(msg))
			console.error(err)
		})
}

const is_instructor = (): boolean =>
	isInstructorOf(props.course.data?.instructors, user.data?.username)

//// Neoffice — d6d8abd2: fetch the shop route as soon as the course name lands.
//// `immediate` covers the mount where it is already there.
watch(
	() => props.course.data?.name,
	(name) => {
		if (name) shopRoute.fetch()
	},
	{ immediate: true }
)

const priceLabel = computed<string>(() => {
	if (props.course.data?.paid_course) return props.course.data?.price || ''
	//// Neoffice — 7aeaa695 « un cours gratuit affichait « Libre » au lieu de « Gratuit » ».
	//// Upstream's source string is __('Free'); the note below says why we cannot use it.
	// Neoffice: NOT __('Free') — Frappe merges every app's translations into one
	// flat namespace, and `suite` legitimately renders "Free" as "Libre" for the
	// calendar's Free/Busy status. Loaded after lms, it won, so a gratis course
	// was labelled "Libre". A price-specific source string sidesteps the clash.
	return __('Free of charge')
})

const enrolledLabel = computed<string>(() => {
	const n = props.course.data?.enrollments ?? 0
	if (!n) return ''
	if (n < 50) return String(n)
	const tier = n < 1000 ? 50 : 100
	return `${Math.floor(n / tier) * tier}+`
})

const hasCourseStats = computed<boolean>(() =>
	Boolean(
		enrolledLabel.value ||
			props.course.data?.video_link ||
			props.course.data?.lessons ||
			(props.course.data?.quiz_count ?? 0) > 0 ||
			props.course.data?.enable_certification
	)
)

const progress = computed<number>(
	() => props.course.data?.membership?.progress ?? 0
)

// The stored progress lags lesson edits, so count the outline's completed flags.
const outline = createResource({
	url: 'lms.lms.utils.get_course_outline',
	cache: ['course_outline_student', props.course.data?.name, 'progress'],
	makeParams() {
		return { course: props.course.data?.name, progress: true }
	},
}) as Resource<{ lessons?: { is_complete?: boolean }[] }[] | null>

watch(
	() => props.course.data?.membership && props.course.data.name,
	(name) => {
		if (name) outline.reload()
	},
	{ immediate: true }
)

const lessonCounts = computed(() => {
	const lessons = (outline.data || []).flatMap((c) => c.lessons || [])
	return {
		total: lessons.length,
		completed: lessons.filter((l) => l.is_complete).length,
	}
})

const lessonsCompletedLabel = computed<string>(() =>
	__('{0} of {1} lessons completed').format(
		lessonCounts.value.completed,
		lessonCounts.value.total
	)
)

const canGetCertificate = computed<boolean>(() => {
	return Boolean(
		props.course.data?.enable_certification &&
			(props.course.data?.membership?.progress ?? 0) >= 100
	)
})

const certificate = createResource({
	url: 'lms.lms.doctype.lms_certificate.lms_certificate.create_certificate',
	makeParams(values: { course?: string }) {
		return {
			course: values.course,
		}
	},
	onSuccess(data: { name: string; template: string }) {
		openExternal(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
				data.name
			}&format=${encodeURIComponent(data.template)}&no_letterhead=1`
		)
	},
}) as Resource<{ name: string; template: string } | null>

const fetchCertificate = () => {
	certificate.submit({
		course: props.course.data?.name,
		member: user.data?.name,
	})
}

const isAdmin = computed<boolean>(() => {
	return Boolean(user.data?.is_moderator) || is_instructor()
})
</script>
