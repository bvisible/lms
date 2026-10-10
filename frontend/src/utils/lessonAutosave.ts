//// Neoffice — added file (no upstream equivalent)
// When may the lesson editor mark a lesson as « modified » and save it?
//
// A lesson that only has a Markdown `body` (made by a generator, with captures as HTML and films as macros) is converted to blocks when it is
// opened in the editor. EditorJS then normalises those blocks and fires `onChange` BY ITSELF, and the editor saves 800 ms later: the text became
// plain paragraphs, the captures were lost and the new `content` took precedence over `body` (three times on 10 October 2026, each time by merely
// opening the lesson). Such a lesson is saved only after a gesture of the user in the editor (a key, a paste, a drop, a click). A lesson that
// already has a saved `content`, and a change of the title, keep their behaviour.
export function shouldMarkDirty(opts: {
	fromTitle: boolean
	initialLoadComplete: boolean
	hasSavedContent: boolean
	userTouched: boolean
}): boolean {
	if (opts.fromTitle) return true
	if (!opts.initialLoadComplete) return false
	if (!opts.hasSavedContent && !opts.userTouched) return false
	return true
}
