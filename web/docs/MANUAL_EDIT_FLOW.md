# Draft assignment editing

Continue the existing Ink/Workshop treatment: canvas #f2f3f4, surface #fdfdfc, ink #26303b, muted #56606d, line #d7dce2 and action #2a4f9e. Bricolage headings and Plex form text remain consistent with the roster and optional appearance treatments.

    published week -> create editing draft
    draft -> choose assignment -> change fields -> preview against server
          -> inspect assignment changes, metrics and violations
          -> apply explicitly -> returned revision -> proposal review

Use an inline editor above the roster, with two-column labelled fields on desktop and a single column on phones. A readable assignment selector is the keyboard entry point. The preview leads with concrete before/after values, followed by cost/coverage changes and server constraint messages. Do not hide violations inside a decorative badge or substitute local estimates for server metrics. Keep a single primary action at each stage.

Existing-assignment operations: reassign/unassign, move/resize with outlet-local start/end dates, role change, lock/unlock and remove. No break-duration policy editor. New assignments and drag gestures remain separate work; a template catalog is needed before offering a template-based Add action. The form provides the keyboard editing path required before drag interactions.

Changing any input invalidates the preview. A save sends exactly the reviewed request and revision. Hard-invalid previews are visible but cannot be applied through this UI. Save responses alone replace the draft; preview results never replace the accepted roster. Editing hides proposal approval until the editor closes; an applied revision resets the previous proposal view. No automatic write retries.

Create-draft is idempotent. Apply-edits is revision-fenced and has no provider replay guarantee: after an ambiguous response, block another save and offer explicit reload. Reload replaces the edit view with current server data; stale errors keep inputs visible until that action. Server authorization remains authoritative.

Synthetic preview supports only the declared example reassignment (invalid) and opening-cook lock (valid). Other edits return an explicit missing-fixture response. Request examples are generated from provider fixture metadata. No client-side solver or invented validation is introduced.
