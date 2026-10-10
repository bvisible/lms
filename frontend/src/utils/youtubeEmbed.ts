//// Neoffice — added file (no upstream equivalent)
// The address of an embedded lesson video (YouTube, no cookie before play).
//
// Upstream embeds `youtube.com/embed/<id>` as it is. With no parameter the player (1) offers, on pause and at the end, « more videos » taken
// from ANY channel, i.e. advertising next to a course; (2) shows the automatic captions whenever the viewer's YouTube account says « always show
// captions », on top of the captions our films already carry; (3) shows annotations and cards. Our films are subtitled by themselves and are
// meant to be watched alone, so:
//   rel=0             « more videos » only come from the channel of the video, never from another one
//   cc_load_policy=0  no captions unless the viewer asks for them (an account setting « always show captions » can still override it: YouTube
//                     offers no way to force it off)
//   iv_load_policy=3  no annotations
//   playsinline=1     plays in the page on a phone, not in a full-screen player
export const YOUTUBE_EMBED_PARAMS = 'rel=0&cc_load_policy=0&iv_load_policy=3&playsinline=1'

export function youtubeEmbedUrl(id: string): string {
	return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?${YOUTUBE_EMBED_PARAMS}`
}
