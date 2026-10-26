export interface paths {
    "/v2/session/demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Demo Session
         * @description Public synthetic demo only: issues a short-lived token for an isolated demo org (B6.2).
         *     403 permission_denied when the deployment is private.
         */
        post: operations["createDemoSession"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Me */
        get: operations["getMe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/shifts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Week
         * @description Staff only: the caller's own published shifts.
         */
        get: operations["getMyWeek"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Outlets
         * @description Owners see every outlet; managers and staff see their own.
         */
        get: operations["listOutlets"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Skills */
        get: operations["listSkills"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/employees": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Employees */
        get: operations["listEmployees"];
        put?: never;
        /** Create Employee */
        post: operations["createEmployee"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/employees/{employee_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Employee */
        get: operations["getEmployee"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Employee
         * @description 409 stale_version when base_revision is not current; details.current_revision is set.
         */
        patch: operations["updateEmployee"];
        trace?: never;
    };
    "/v2/employees/{employee_id}/availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Availability */
        get: operations["getAvailability"];
        /** Put Availability */
        put: operations["putAvailability"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/imports/employees/template": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Employee Import Template
         * @description The fixed CSV columns, one valid example row and the rules (architecture v3 section 19).
         */
        get: operations["getEmployeeImportTemplate"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/imports/employees": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Stage Employee Import
         * @description Parse and validate every row; writes no employees. status staged (all valid) or invalid (fix
         *     the row errors and upload again).
         */
        post: operations["stageEmployeeImport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/imports/{import_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Import */
        get: operations["getImport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/imports/{import_id}/commit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Commit Import
         * @description Create every employee in one transaction. 409 conflict when the import is invalid, expired or
         *     already committed, or when a row no longer fits (details.rows).
         */
        post: operations["commitImport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/shift-templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Shift Templates
         * @description The outlet's active shift shapes, for add_from_template edits. Read-only here.
         */
        get: operations["listShiftTemplates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/staffing-templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Staffing Templates
         * @description The outlet's weekly staffing template: weekday x block x role -> minimum and preferred staff.
         */
        get: operations["listStaffingTemplates"];
        /**
         * Put Staffing Templates
         * @description Replace the whole template set. 409 stale_version when base_revision is not current; 422 when
         *     blocks of one weekday and role overlap. Weeks change only when expanded.
         */
        put: operations["putStaffingTemplates"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/staffing-requirements/expand": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Expand Staffing Requirements
         * @description Regenerate the week's template (and, if asked, band) rows from the template. Manual overrides
         *     survive; the outlet-week demand_revision is bumped. 409 stale_version on a stale base.
         */
        post: operations["expandStaffingRequirements"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/staffing-requirements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Staffing Requirements */
        get: operations["getStaffingRequirements"];
        /** Put Staffing Requirements */
        put: operations["putStaffingRequirements"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Schedule Week
         * @description 200 with schedule_id null when the week has no schedule yet; 404 only for unknown outlets.
         */
        get: operations["getScheduleWeek"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Schedule Version */
        get: operations["getScheduleVersion"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Schedule
         * @description Queues a run and returns it (job_state queued). Poll getOptimizationRun. 409 stale_version
         *     when base_version_id is no longer the published version.
         */
        post: operations["generateSchedule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/optimization-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Optimization Run */
        get: operations["getOptimizationRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/optimization-candidates/{candidate_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Optimization Candidate
         * @description The candidate's diff against its base version. Candidates are not versions until selected.
         */
        get: operations["getOptimizationCandidate"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/optimization-candidates/{candidate_id}/select": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Select Optimization Candidate
         * @description Materializes the candidate into a draft (its base_version_id is the run's base, so publishing it
         *     after someone else published returns stale_version). Selecting again returns the same draft while it
         *     is still a draft.
         */
        post: operations["selectOptimizationCandidate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}/drafts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Draft
         * @description A new draft copied from the published version (or another version of the same week). 409
         *     stale_version when base_version_id is no longer the published version.
         */
        post: operations["createDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/edits/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Edits
         * @description Validate edits against the draft without writing anything (drag/resize/keyboard previews).
         */
        post: operations["previewEdits"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/edits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Apply Edits
         * @description Apply edits to a draft. 409 stale_version when expected_revision is not current
         *     (details.current_revision); 409 conflict when the version is not a draft. Edits that break rules
         *     are applied and reported in validation; publishing is what refuses hard violations.
         */
        post: operations["applyEdits"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Publish Version
         * @description Atomically publish a draft and supersede the current version. 409 stale_version when the published
         *     version or the draft revision moved; 422 validation_failed with details.violations when the draft has
         *     hard violations against current facts.
         */
        post: operations["publishVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Proposals
         * @description Find a week's proposals, e.g. the pending one after a reload. Newest first.
         */
        get: operations["listProposals"];
        put?: never;
        /**
         * Create Proposal
         * @description Propose a draft for publication, recording its revision and its metrics against current facts
         *     (what the manager agrees to). 409 stale_version when the draft revision moved; 422 validation_failed
         *     when it has hard violations.
         */
        post: operations["createProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Proposal */
        get: operations["getProposal"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/proposals/{proposal_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve Proposal
         * @description The publication transaction (architecture v3 section 31). Always 200 with an `outcome`: published,
         *     stale, invalid or changed. 409 conflict only when the proposal is no longer pending or expired.
         */
        post: operations["approveProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/proposals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Proposal */
        post: operations["rejectProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard Draft */
        post: operations["discardDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedules/{schedule_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Versions */
        get: operations["listVersions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/compare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Compare Versions
         * @description Changes from `with` to this version, keyed on logical_shift_id.
         */
        get: operations["compareVersions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/schedule-versions/{version_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore Version
         * @description A new draft with this version's shifts, validated against current facts (an absent employee's
         *     restored shift shows as a hard violation; it is never revived silently). History is never rewritten.
         */
        post: operations["restoreVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/absences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Absences */
        get: operations["listAbsences"];
        put?: never;
        /**
         * Report Absence
         * @description Records the absence as a fact first (it stands whether or not a repair succeeds). A confirmed
         *     absence then enqueues a repair run per affected schedule (repair_run_ids); locked affected shifts are
         *     listed in lock_conflicts and need explicit authorization through repairSchedule.
         */
        post: operations["reportAbsence"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/commands/parse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Parse Command
         * @description A request in words ("Give Ravi Saturday off") as a preview of an existing API call. Writes
         *     nothing; asks "Which Ravi?" rather than guessing (architecture v3 section 33).
         */
        post: operations["parseCommand"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/rules/parse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Parse Rule
         * @description A rule in words, compiled and run through previewRule. Unsupported rules are refused.
         */
        post: operations["parseRule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/rules/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Rule
         * @description Who the rule affects, conflicts with active rules (in business terms, with a suggested exception)
         *     and upcoming published shifts it would break. Writes nothing (architecture v3 section 21).
         */
        post: operations["previewRule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Rules */
        get: operations["listRules"];
        put?: never;
        /**
         * Create Rule
         * @description Activates the rule. 409 conflict with details.conflicts when it disagrees with an active rule
         *     for someone both cover and is not an explicit exception (overrides_rule_id).
         */
        post: operations["createRule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/rules/{rule_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Archive Rule */
        post: operations["archiveRule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Notifications
         * @description The caller's in-app inbox, filled by the outbox relay: schedule published, repair or options
         *     ready, absence confirmed, proposal ready or stale.
         */
        get: operations["getMyNotifications"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/notifications/{notification_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark Notification Read
         * @description Idempotent: reading twice keeps the first read_at.
         */
        post: operations["markNotificationRead"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/absences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Absences
         * @description The employee's own absences and requests, any status. Withdraw a pending request with
         *     updateAbsence status=cancelled.
         */
        get: operations["getMyAbsences"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/absences/{absence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Absence
         * @description Managers confirm, reject or cancel. Confirming enqueues repairs exactly as reportAbsence does.
         */
        patch: operations["updateAbsence"];
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}/repair": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Repair Schedule
         * @description Repair runs are claimed before batch work and never blocked by it. An active repair for the same
         *     absence is returned (idempotent). 409 conflict lists locked affected shifts without authorization.
         */
        post: operations["repairSchedule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/recommendations/replacements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Recommend Replacements
         * @description Who can cover this shift, ranked by disruption then the chosen profile (architecture v4 section 46).
         *     Read-only and synchronous; choose someone by applying the returned edit to a draft.
         */
        post: operations["recommendReplacements"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Scenario
         * @description A what-if on this week, starting from its current published version. Nothing real changes.
         */
        post: operations["createScenario"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Scenarios */
        get: operations["listScenarios"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/scenarios/{scenario_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario */
        get: operations["getScenario"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/scenarios/{scenario_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Scenario Event
         * @description 409 once the scenario is converted, discarded or expired.
         */
        post: operations["addScenarioEvent"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/scenarios/{scenario_id}/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Scenario
         * @description Queue a solve with the events applied. 409 stale_version when the real week moved since the
         *     scenario was created; 409 run_in_progress while this scenario already has an active run.
         */
        post: operations["runScenario"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/scenarios/{scenario_id}/convert": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Convert Scenario
         * @description Turn this into a plan: the candidate is re-checked against current facts and becomes a normal
         *     draft. 409 stale_version if the real week moved; 409 conflict if current facts break the plan.
         */
        post: operations["convertScenario"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/scenarios/{scenario_id}/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard Scenario */
        post: operations["discardScenario"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/forecast-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Request Forecast
         * @description Forecast a week's orders from past weeks, backtest it, and (if it passes) propose staffing.
         *     Advisory only: nothing changes until a manager accepts the proposal.
         */
        post: operations["requestForecast"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/forecast-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Forecast Run */
        get: operations["getForecastRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/staffing-requirement-proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Staffing Proposal */
        get: operations["getStaffingProposal"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/staffing-requirement-proposals/{proposal_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Staffing Proposal
         * @description Set the week's staffing from the proposal. Manual overrides survive. 409 stale_version when
         *     staffing changed after the forecast; 409 conflict when the proposal was already decided.
         */
        post: operations["acceptStaffingProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/staffing-requirement-proposals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Staffing Proposal */
        post: operations["rejectStaffingProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/open-shifts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Open Shifts
         * @description Open shifts in the published week that you are eligible for, with the checks that passed.
         */
        get: operations["getMyOpenShifts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/shift-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** My Shift Requests */
        get: operations["getMyShiftRequests"];
        put?: never;
        /**
         * Create Shift Request
         * @description Claim an open shift, offer one of yours, or propose a swap. 422 (with details.violations) when
         *     the change would break a rule; nothing is published until a manager approves.
         */
        post: operations["createShiftRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/shift-requests/{request_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Shift Request
         * @description Employees: take a giveaway or consent to a swap. Returns status stale when the published week
         *     moved under these shifts.
         */
        post: operations["acceptShiftRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/shift-requests/{request_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Shift Request */
        post: operations["cancelShiftRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/shift-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Shift Requests */
        get: operations["listShiftRequests"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/shift-requests/{request_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve Shift Request
         * @description Managers: re-validate against current facts and publish. The returned status is the outcome:
         *     approved (published_version_id), stale, invalid (violations) or expired.
         */
        post: operations["approveShiftRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/shift-requests/{request_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Shift Request */
        post: operations["rejectShiftRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/me/availability-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** My Availability Requests */
        get: operations["getMyAvailabilityRequests"];
        put?: never;
        /**
         * Create Availability Request
         * @description Propose a new weekly availability. The response lists the published shifts it would break;
         *     nothing changes until a manager accepts.
         */
        post: operations["createAvailabilityRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/availability-requests/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Availability Request */
        get: operations["getAvailabilityRequest"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/availability-requests/{request_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Availability Request */
        post: operations["cancelAvailabilityRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/availability-requests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Availability Requests */
        get: operations["listAvailabilityRequests"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/availability-requests/{request_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Availability Request
         * @description Replace the person's availability. 409 stale_version if it changed after the request. `affected`
         *     lists the shifts that now need cover.
         */
        post: operations["acceptAvailabilityRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/availability-requests/{request_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Availability Request */
        post: operations["rejectAvailabilityRequest"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/optimization-runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Stream Optimization Run
         * @description Run progress as server-sent events: one `run` event per change, then `end`. GET
         *     /v2/optimization-runs/{run_id} remains the fallback.
         */
        get: operations["streamOptimizationRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/forecast-runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream Forecast Run */
        get: operations["streamForecastRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v2/outlets/{outlet_id}/schedules/{week_start}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Stream Schedule Versions
         * @description Schedule-version invalidation: a `version` event whenever the week's published version changes.
         *     Reconnect after `end` (reason reconnect).
         */
        get: operations["streamScheduleVersions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AbsenceList */
        AbsenceList: {
            /** Items */
            items: components["schemas"]["AbsenceMark"][];
        };
        /** AbsenceMark */
        AbsenceMark: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "leave" | "sick" | "other";
            /**
             * Status
             * @description Only confirmed absences make an overlapping shift invalid. Rosters list only requested and confirmed absences; rejected and cancelled appear in absence management (2.4).
             * @enum {string}
             */
            status: "requested" | "confirmed" | "rejected" | "cancelled";
        };
        /** AbsenceReport */
        AbsenceReport: {
            absence: components["schemas"]["AbsenceMark"];
            /**
             * Affected
             * @description Live published shifts the absence overlaps, all outlets.
             */
            affected: components["schemas"]["AffectedShift"][];
            /**
             * Lock Conflicts
             * @description Logical ids of affected shifts that are locked; repairing them needs explicit unlock authorization.
             */
            lock_conflicts: string[];
            /** Repair Suggested */
            repair_suggested: boolean;
            /**
             * Repair Run Ids
             * @description Repair runs enqueued automatically for this confirmed absence (one per affected schedule without unauthorized lock conflicts). Poll them like any run.
             */
            repair_run_ids?: string[];
        };
        /**
         * AddFromTemplate
         * @description Add a shift shaped by one of the outlet's shift templates (listShiftTemplates). Start, end and
         *     break come from the template, so no client chooses a break policy.
         */
        AddFromTemplate: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "add_from_template";
            /**
             * Template Id
             * Format: uuid
             */
            template_id: string;
            /**
             * Day
             * Format: date
             * @description Outlet-local date the shift starts on; must be in the draft's week.
             */
            day: string;
            /**
             * Employee Id
             * @description null adds an open (unfilled) shift.
             */
            employee_id?: string | null;
            /**
             * Skill Id
             * @description Required when the template allows any skill; must match it otherwise.
             */
            skill_id?: string | null;
            /**
             * Locked
             * @default false
             */
            locked: boolean;
        };
        /** AddShift */
        AddShift: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "add";
            /**
             * Employee Id
             * @description null adds an open (unfilled) shift.
             */
            employee_id: string | null;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Break Start At */
            break_start_at?: string | null;
            /**
             * Break Minutes
             * @default 0
             */
            break_minutes: number;
            /**
             * Locked
             * @default false
             */
            locked: boolean;
        };
        /** AffectedShift */
        AffectedShift: {
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /**
             * Version Id
             * Format: uuid
             */
            version_id: string;
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Locked */
            locked: boolean;
        };
        /** AlternativeFact */
        AlternativeFact: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
            /**
             * Status
             * @description rejected: a concrete rule blocks this person (see reasons). eligible_not_selected: allowed, but this plan chose someone else; never presented as a rejection.
             * @enum {string}
             */
            status: "rejected" | "eligible_not_selected";
            /** Reasons */
            reasons: components["schemas"]["ExplanationFact"][];
        };
        /** ApproveProposalRequest */
        ApproveProposalRequest: {
            /**
             * Acknowledge Changes
             * @description Set after a `changed` outcome to accept the moved metrics and publish.
             * @default false
             */
            acknowledge_changes: boolean;
        };
        /** Availability */
        Availability: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Windows */
            windows: components["schemas"]["AvailabilityWindow"][];
            /** Revision */
            revision: number;
        };
        /** AvailabilityRequestList */
        AvailabilityRequestList: {
            /** Items */
            items: components["schemas"]["AvailabilityRequestView"][];
        };
        /**
         * AvailabilityRequestView
         * @description A proposed recurring availability (architecture v4 section 29). `affected` lists the published
         *     shifts (next 8 weeks) the person could no longer work: recomputed live while pending, frozen at the
         *     decision. Accepting replaces the real availability; the affected shifts then need cover (use
         *     recommendReplacements per shift).
         */
        AvailabilityRequestView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "accepted" | "rejected" | "cancelled";
            /** Base Revision */
            base_revision: number;
            /** Windows */
            windows: components["schemas"]["AvailabilityWindow"][];
            /**
             * Current
             * @description The availability in force now.
             */
            current: components["schemas"]["AvailabilityWindow"][];
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided By User Id */
            decided_by_user_id: string | null;
            /** Decided At */
            decided_at: string | null;
            /** Affected */
            affected: components["schemas"]["AffectedShift"][];
        };
        /** AvailabilityUpdate */
        AvailabilityUpdate: {
            /** Base Revision */
            base_revision: number;
            /** Windows */
            windows: components["schemas"]["AvailabilityWindow"][];
        };
        /** AvailabilityWindow */
        AvailabilityWindow: {
            /**
             * Weekday
             * @description 0 = Monday ... 6 = Sunday
             */
            weekday: number;
            /**
             * Start Minute
             * @description Minutes from outlet-local midnight; values above 1440 continue past midnight
             */
            start_minute: number;
            /**
             * End Minute
             * @description Minutes from outlet-local midnight; values above 1440 continue past midnight
             */
            end_minute: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "available" | "preferred" | "unavailable";
        };
        /** Candidate */
        Candidate: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Rank */
            rank: number;
            /** Strategy */
            strategy: ("balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness") | ("least_disruption" | "lowest_cost" | "best_coverage");
            /**
             * Solver Status
             * @enum {string}
             */
            solver_status: "OPTIMAL" | "FEASIBLE";
            /**
             * Proven Optimal
             * @description False when the time limit ended the search with a valid but unproven schedule.
             */
            proven_optimal: boolean;
            /**
             * Materialized Version Id
             * @description null until a manager selects this candidate (POST /v2/optimization-candidates/{id}/select); then the draft it became.
             */
            materialized_version_id?: string | null;
            metrics: components["schemas"]["Metrics"];
            /**
             * Changed Shifts
             * @description Logical shifts differing from the base version.
             */
            changed_shifts: number;
            /** @description Independent validator result. A candidate with hard violations is never returned. */
            validation: components["schemas"]["ValidationResult"];
            /** @description Repair runs only. */
            disruption?: components["schemas"]["Disruption"] | null;
            /**
             * Explanations
             * @description One per reassigned, created or unfilled shift against a base version (repairs, regeneration). Empty on an empty week, where every shift is new.
             */
            explanations?: components["schemas"]["ShiftExplanation"][];
            /** @description null for candidates stored before 3.18. */
            trace?: components["schemas"]["DecisionTrace"] | null;
        };
        /** CandidateDetail */
        CandidateDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Rank */
            rank: number;
            /** Strategy */
            strategy: ("balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness") | ("least_disruption" | "lowest_cost" | "best_coverage");
            /**
             * Solver Status
             * @enum {string}
             */
            solver_status: "OPTIMAL" | "FEASIBLE";
            /**
             * Proven Optimal
             * @description False when the time limit ended the search with a valid but unproven schedule.
             */
            proven_optimal: boolean;
            /**
             * Materialized Version Id
             * @description null until a manager selects this candidate (POST /v2/optimization-candidates/{id}/select); then the draft it became.
             */
            materialized_version_id?: string | null;
            metrics: components["schemas"]["Metrics"];
            /**
             * Changed Shifts
             * @description Logical shifts differing from the base version.
             */
            changed_shifts: number;
            /** @description Independent validator result. A candidate with hard violations is never returned. */
            validation: components["schemas"]["ValidationResult"];
            /** @description Repair runs only. */
            disruption?: components["schemas"]["Disruption"] | null;
            /**
             * Explanations
             * @description One per reassigned, created or unfilled shift against a base version (repairs, regeneration). Empty on an empty week, where every shift is new.
             */
            explanations?: components["schemas"]["ShiftExplanation"][];
            /** @description null for candidates stored before 3.18. */
            trace?: components["schemas"]["DecisionTrace"] | null;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            /**
             * Base Version Id
             * @description The version this diff applies to; null = empty week.
             */
            base_version_id: string | null;
            diff: components["schemas"]["CandidateDiff"];
            /**
             * Trace Changes
             * @description The change class of every non-kept shift, in time order.
             */
            trace_changes?: components["schemas"]["TraceChange"][];
        };
        /**
         * CandidateDiff
         * @description The candidate against its base version. For generation without a base, every shift is added.
         */
        CandidateDiff: {
            /** Added */
            added: components["schemas"]["CandidateShift"][];
            /**
             * Changed
             * @description The new state of shifts that exist in the base.
             */
            changed: components["schemas"]["CandidateShift"][];
            /**
             * Removed
             * @description Logical shift ids of base shifts the candidate drops.
             */
            removed: string[];
        };
        /**
         * CandidateShift
         * @description A shift as a candidate proposes it. It has no row id until the candidate is selected.
         */
        CandidateShift: {
            /**
             * Logical Shift Id
             * Format: uuid
             * @description Existing ids keep their identity; new shifts get new ids.
             */
            logical_shift_id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Employee Id
             * @description null = open (unfilled) shift.
             */
            employee_id: string | null;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Break Start At */
            break_start_at: string | null;
            /** Break Minutes */
            break_minutes: number;
            /** Locked */
            locked: boolean;
        };
        /** CommandOption */
        CommandOption: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
        };
        /**
         * CommandPreview
         * @description A language command as a preview (architecture v3 section 33). Never a write: confirming means
         *     making `action` (with an Idempotency-Key). ready: show summary and confirm. needs_clarification:
         *     ask question, offering options. unsupported or unavailable: point to the form.
         */
        CommandPreview: {
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "needs_clarification" | "unsupported" | "unavailable";
            /** Intent */
            intent?: ("give_time_off" | "report_sick" | "generate_week" | "find_replacement") | null;
            /** Summary */
            summary: string;
            /** Question */
            question?: string | null;
            /** Options */
            options?: components["schemas"]["CommandOption"][];
            action?: components["schemas"]["ProposedCall"] | null;
            /** Affected Shift Count */
            affected_shift_count?: number | null;
        };
        /** CommandRequest */
        CommandRequest: {
            /**
             * Text
             * @description E.g. "Give Ravi Saturday off".
             */
            text: string;
            /**
             * Outlet Id
             * @description Defaults to the manager's outlet.
             */
            outlet_id?: string | null;
            /**
             * Employee Id
             * @description The answer to "Which Ravi?", sent with the same text.
             */
            employee_id?: string | null;
        };
        /**
         * ConflictItem
         * @description One business constraint in the diagnosed conflict set (architecture v4 section 17).
         */
        ConflictItem: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "minimum_coverage" | "no_overtime" | "rule" | "labour_cap";
            /**
             * Message
             * @description Deterministic text; safe to show.
             */
            message: string;
            /**
             * Relaxation
             * @description The business option this constraint offers if relaxed.
             */
            relaxation: string;
            /** Skill Id */
            skill_id?: string | null;
            /** Day */
            day?: string | null;
            /** Employee Id */
            employee_id?: string | null;
            /** Rule Id */
            rule_id?: string | null;
            /** Rule Type */
            rule_type?: string | null;
            /**
             * Minutes
             * @description no_overtime: the regular weekly minutes.
             */
            minutes?: number | null;
            /** Max Cost Paise */
            max_cost_paise?: number | null;
        };
        /** ConvertScenarioRequest */
        ConvertScenarioRequest: {
            /**
             * Candidate Id
             * Format: uuid
             * @description A candidate of this scenario's latest successful run.
             */
            candidate_id: string;
        };
        /** CoverageCell */
        CoverageCell: {
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /** Minimum Required */
            minimum_required: number;
            /** Preferred Required */
            preferred_required: number;
            /**
             * Scheduled
             * @description Staff productively on shift (breaks excluded).
             */
            scheduled: number;
        };
        /** CreateAvailabilityRequest */
        CreateAvailabilityRequest: {
            /**
             * Base Revision
             * @description The availability revision this change starts from.
             */
            base_revision: number;
            /**
             * Windows
             * @description The whole proposed weekly availability.
             */
            windows: components["schemas"]["AvailabilityWindow"][];
            /** Note */
            note?: string | null;
        };
        /** CreateDraftRequest */
        CreateDraftRequest: {
            /**
             * Base Version Id
             * @description The currently published version (null for an empty week). Stale -> 409.
             */
            base_version_id: string | null;
            /**
             * Copy From Version Id
             * @description Version whose shifts start the draft; defaults to base_version_id (empty when both are null).
             */
            copy_from_version_id?: string | null;
        };
        /** CreateProposalRequest */
        CreateProposalRequest: {
            /**
             * Draft Version Id
             * Format: uuid
             */
            draft_version_id: string;
            /**
             * Expected Revision
             * @description The draft revision the manager reviewed.
             */
            expected_revision: number;
        };
        /** CreateScenarioRequest */
        CreateScenarioRequest: {
            /** Title */
            title: string;
            /** Events */
            events?: components["schemas"]["ScenarioEventIn"][];
        };
        /**
         * CreateShiftRequest
         * @description open_shift_claim: take an open shift. giveaway: offer one of your shifts (to target_employee_id,
         *     or to every qualified colleague when omitted). swap: trade your shift for target_logical_shift_id;
         *     its holder must consent.
         */
        CreateShiftRequest: {
            /**
             * Type
             * @enum {string}
             */
            type: "open_shift_claim" | "giveaway" | "swap";
            /**
             * Logical Shift Id
             * Format: uuid
             * @description The open shift (claim) or your own shift (giveaway, swap).
             */
            logical_shift_id: string;
            /** Target Employee Id */
            target_employee_id?: string | null;
            /**
             * Target Logical Shift Id
             * @description swap only: the colleague's shift.
             */
            target_logical_shift_id?: string | null;
            /** Note */
            note?: string | null;
        };
        /**
         * DecisionTrace
         * @description What changed, what stayed, and the trade-off that produced the plan (architecture v4 section 18).
         */
        DecisionTrace: {
            /** Strategy */
            strategy: ("balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness") | ("least_disruption" | "lowest_cost" | "best_coverage");
            summary: components["schemas"]["PlanDelta"];
            /**
             * Counts
             * @description Every class, KEPT included.
             */
            counts: {
                [key: string]: number;
            };
            /**
             * Explained Shifts
             * @description Changed shifts with why/why-not facts.
             */
            explained_shifts: number;
            /**
             * Explanations Truncated
             * @description More changed shifts than were explained (limit 30).
             */
            explanations_truncated: boolean;
        };
        /**
         * DemoSession
         * @description Synthetic public demo only; private deployments never expose this endpoint.
         */
        DemoSession: {
            /**
             * Access Token
             * @description Send as `Authorization: Bearer <token>`.
             */
            access_token: string;
            /**
             * Token Type
             * @default bearer
             * @constant
             */
            token_type: "bearer";
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            me: components["schemas"]["Me"];
            /**
             * Sandbox Id
             * @description This visitor's private copy of the synthetic organization; send it back to switch persona. Changes are visible to nobody else and disappear at sandbox_expires_at.
             */
            sandbox_id?: string | null;
            /** Sandbox Expires At */
            sandbox_expires_at?: string | null;
        };
        /** DemoSessionRequest */
        DemoSessionRequest: {
            /**
             * Persona
             * @enum {string}
             */
            persona: "owner" | "manager" | "staff";
            /**
             * Sandbox Id
             * @description Switch persona inside an existing sandbox; omit to start a fresh one (B6.2).
             */
            sandbox_id?: string | null;
        };
        /** Disruption */
        Disruption: {
            /** Changed Shifts */
            changed_shifts: number;
            /** Added Shifts */
            added_shifts: number;
            /** Cross Outlet Moves */
            cross_outlet_moves: number;
            /** Open Shifts */
            open_shifts: number;
        };
        /**
         * EditPreview
         * @description What the draft would look like after the edits. Nothing is written; the server is the only
         *     authority on validity, cost and coverage.
         */
        EditPreview: {
            /**
             * Version Id
             * Format: uuid
             */
            version_id: string;
            /** Expected Revision */
            expected_revision: number;
            /** Shifts */
            shifts: components["schemas"]["Shift"][];
            /** Changes */
            changes: components["schemas"]["ShiftChange"][];
            metrics: components["schemas"]["Metrics"];
            validation: components["schemas"]["ValidationResult"];
        };
        /** EditRequest */
        EditRequest: {
            /**
             * Expected Revision
             * @description The draft revision the edits were made against.
             */
            expected_revision: number;
            /** Edits */
            edits: (components["schemas"]["AddShift"] | components["schemas"]["AddFromTemplate"] | components["schemas"]["UpdateShift"] | components["schemas"]["RemoveShift"] | components["schemas"]["SetLock"])[];
        };
        /** Employee */
        Employee: {
            /** Name */
            name: string;
            /**
             * Home Outlet Id
             * Format: uuid
             */
            home_outlet_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "inactive";
            hourly_rate: components["schemas"]["Money"];
            /** Skills */
            skills: components["schemas"]["EmployeeSkill"][];
            /** Tags */
            tags: string[];
            /**
             * Regular Weekly Minutes
             * @description Overtime threshold.
             */
            regular_weekly_minutes: number;
            /**
             * Max Weekly Minutes
             * @description Absolute cap; overtime permission never lifts it.
             */
            max_weekly_minutes: number;
            /** Preferred Weekly Minutes */
            preferred_weekly_minutes: number | null;
            /** Overtime Allowed */
            overtime_allowed: boolean;
            /** Cross Outlet Eligible */
            cross_outlet_eligible: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Revision
             * @description Send as base_revision when updating.
             */
            revision: number;
        };
        /** EmployeeCreate */
        EmployeeCreate: {
            /** Name */
            name: string;
            /**
             * Home Outlet Id
             * Format: uuid
             */
            home_outlet_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "inactive";
            hourly_rate: components["schemas"]["Money"];
            /** Skills */
            skills: components["schemas"]["EmployeeSkill"][];
            /** Tags */
            tags: string[];
            /**
             * Regular Weekly Minutes
             * @description Overtime threshold.
             */
            regular_weekly_minutes: number;
            /**
             * Max Weekly Minutes
             * @description Absolute cap; overtime permission never lifts it.
             */
            max_weekly_minutes: number;
            /** Preferred Weekly Minutes */
            preferred_weekly_minutes: number | null;
            /** Overtime Allowed */
            overtime_allowed: boolean;
            /** Cross Outlet Eligible */
            cross_outlet_eligible: boolean;
        };
        /** EmployeeList */
        EmployeeList: {
            /** Items */
            items: components["schemas"]["Employee"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** EmployeeSkill */
        EmployeeSkill: {
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /** Level */
            level: number;
        };
        /**
         * EmployeeUpdate
         * @description Partial update. Omit a field to leave it unchanged. Sending null for a field that cannot be
         *     null is rejected (422 validation_failed); only preferred_weekly_minutes accepts null, which
         *     clears it.
         */
        EmployeeUpdate: {
            /** Base Revision */
            base_revision: number;
            /** Name */
            name?: string | null;
            /** Home Outlet Id */
            home_outlet_id?: string | null;
            /** Status */
            status?: ("active" | "inactive") | null;
            hourly_rate?: components["schemas"]["Money"] | null;
            /** Skills */
            skills?: components["schemas"]["EmployeeSkill"][] | null;
            /** Tags */
            tags?: string[] | null;
            /** Regular Weekly Minutes */
            regular_weekly_minutes?: number | null;
            /** Max Weekly Minutes */
            max_weekly_minutes?: number | null;
            /** Preferred Weekly Minutes */
            preferred_weekly_minutes?: number | null;
            /** Overtime Allowed */
            overtime_allowed?: boolean | null;
            /** Cross Outlet Eligible */
            cross_outlet_eligible?: boolean | null;
        };
        /** ErrorBody */
        ErrorBody: {
            /**
             * Code
             * @enum {string}
             */
            code: "unauthenticated" | "permission_denied" | "not_found" | "validation_failed" | "stale_version" | "conflict" | "idempotency_conflict" | "run_in_progress" | "rate_limited" | "not_implemented" | "internal";
            /**
             * Message
             * @description Safe to show to the user.
             */
            message: string;
            /** Retryable */
            retryable: boolean;
            /**
             * Details
             * @description Code-specific structured facts, e.g. field errors or the current revision for stale_version.
             */
            details?: {
                [key: string]: unknown;
            };
            /**
             * Trace Id
             * @description Quote this when reporting a problem.
             */
            trace_id?: string | null;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ErrorBody"];
        };
        /**
         * EventStream
         * @description A server-sent event stream (architecture v4 section 49), shown decoded: each frame is
         *     `event:`/`id:`/`data:` lines; `: keepalive` comments arrive every 15 s while idle. An event is sent
         *     only when durable state changes; the stream ends with `end` (finished, or reconnect after 120 s).
         *     Authenticate with the Authorization header, so read it with fetch(), not EventSource; the GET
         *     endpoint remains the fallback.
         */
        EventStream: {
            /** Events */
            events: components["schemas"]["StreamEvent"][];
        };
        /** ExpandStaffingRequest */
        ExpandStaffingRequest: {
            /** Base Demand Revision */
            base_demand_revision: number;
            /**
             * Use Demand Bands
             * @description Let demand bands (orders/hour -> staff) override the template where the week has order counts.
             * @default false
             */
            use_demand_bands: boolean;
        };
        /** ExplanationFact */
        ExplanationFact: {
            /**
             * Code
             * @description incremental_cost, fairness_burden and disruption appear for the chosen person only. Unknown codes may be added; show their message.
             * @enum {string}
             */
            code: "skill" | "available" | "no_conflict" | "weekly_hours" | "travel" | "rules" | "incremental_cost" | "fairness_burden" | "disruption";
            /** Ok */
            ok: boolean;
            /**
             * Message
             * @description Deterministic text built from facts; safe to show.
             */
            message: string;
            /**
             * Facts
             * @description Blocking reasons carry provenance: rule_ids and/or absence_ids (v4 section 18).
             */
            facts?: {
                [key: string]: unknown;
            };
        };
        /**
         * FairnessComponents
         * @description Burden points by component (architecture v4 section 12). Last-minute and transfer burden are not
         *     part of policy 1.
         */
        FairnessComponents: {
            /** Policy Version */
            policy_version: number;
            /**
             * Closing
             * @description 3 per shift ending at 22:00 or later.
             */
            closing: number;
            /**
             * Weekend
             * @description 2 per Saturday or Sunday shift.
             */
            weekend: number;
            /**
             * Split
             * @description 2 per extra shift on the same day.
             */
            split: number;
            /**
             * Overtime
             * @description 1 per full hour beyond the regular week.
             */
            overtime: number;
        };
        /**
         * ForecastMetrics
         * @description Backtest: each of the last weeks forecast from the weeks before it, compared with what happened.
         */
        ForecastMetrics: {
            /** Model Version */
            model_version: string;
            /** Weeks Evaluated */
            weeks_evaluated: string[];
            /** Intervals */
            intervals: number;
            /**
             * Wape
             * @description Weighted absolute percentage error, 0-1.
             */
            wape: number;
            /**
             * Mae
             * @description Mean absolute error in orders per interval.
             */
            mae: number;
            /**
             * Bias
             * @description Positive = forecasts too high.
             */
            bias: number;
            /** Passed */
            passed: boolean;
            /** Thresholds */
            thresholds: {
                [key: string]: number;
            };
        };
        /** ForecastPoint */
        ForecastPoint: {
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /**
             * Predicted
             * @description Orders in this 30-minute interval.
             */
            predicted: number;
            /** Lower */
            lower: number;
            /** Upper */
            upper: number;
            /**
             * Samples
             * @description Past weeks behind the prediction.
             */
            samples: number;
        };
        /** ForecastRequest */
        ForecastRequest: {
            /**
             * Week Start
             * Format: date
             * @description The Monday to forecast; history before it is used.
             */
            week_start: string;
        };
        /**
         * ForecastRun
         * @description Advisory demand forecast (architecture v4 sections 21, 37). It never changes staffing by itself:
         *     when the backtest passes it produces a proposal a manager accepts or rejects.
         */
        ForecastRun: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /** Model Version */
            model_version: string;
            /**
             * Job State
             * @enum {string}
             */
            job_state: "queued" | "running" | "succeeded" | "failed";
            /**
             * Quality
             * @description failed: the backtest missed the gate; the forecast is shown but no proposal is made.
             */
            quality: ("passed" | "failed") | null;
            metrics: components["schemas"]["ForecastMetrics"] | null;
            /** Points */
            points: components["schemas"]["ForecastPoint"][];
            /** Proposal Id */
            proposal_id: string | null;
            error: components["schemas"]["ErrorBody"] | null;
            /**
             * Queued At
             * Format: date-time
             */
            queued_at: string;
            /** Finished At */
            finished_at: string | null;
            /** Poll After Ms */
            poll_after_ms: number | null;
        };
        /**
         * FreezeSpec
         * @description Protect commitments for one run (architecture v4 section 13): these published shifts are held
         *     exactly as they are. Nothing is stored as a lock; the next run starts unfrozen.
         */
        FreezeSpec: {
            /**
             * Shift Ids
             * @description Logical shift ids to pin.
             */
            shift_ids?: string[];
            /**
             * Employee Ids
             * @description Hold all of these people's shifts.
             */
            employee_ids?: string[];
            /**
             * Days
             * @description Hold every shift on these outlet-local days.
             */
            days?: string[];
        };
        /** GenerateRequest */
        GenerateRequest: {
            /**
             * Strategy
             * @default balanced
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness";
            /**
             * Base Version Id
             * @description Current published version the draft replaces; null for an empty week. Stale -> 409.
             */
            base_version_id?: string | null;
            /**
             * Time Limit Seconds
             * @default 10
             */
            time_limit_seconds: number;
            /** @description Regenerating over a published week: shifts to keep exactly. 409 conflict when current facts break a frozen shift (details.frozen_logical_shift_ids). */
            freeze?: components["schemas"]["FreezeSpec"] | null;
        };
        /** ImportJob */
        ImportJob: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @constant
             */
            kind: "employees";
            /**
             * Status
             * @description staged: every row is valid; commit it. invalid: fix the listed errors and upload again (nothing was written). committed: the employees exist. expired: staged over 24 hours ago.
             * @enum {string}
             */
            status: "staged" | "invalid" | "committed" | "expired";
            /** Filename */
            filename: string;
            /** Row Count */
            row_count: number;
            /**
             * Error Count
             * @description Rows with at least one error.
             */
            error_count: number;
            /**
             * File Errors
             * @description Problems with the file itself, e.g. its header.
             */
            file_errors: string[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Committed At */
            committed_at: string | null;
            /** Rows */
            rows: components["schemas"]["ImportRow"][];
        };
        /** ImportRow */
        ImportRow: {
            /**
             * Row Number
             * @description Line in the file; the header is line 1.
             */
            row_number: number;
            /** Name */
            name: string;
            /** Outlet Id */
            outlet_id: string | null;
            /** Errors */
            errors: components["schemas"]["ImportRowError"][];
            /**
             * Employee Id
             * @description Set once the import is committed.
             */
            employee_id: string | null;
        };
        /** ImportRowError */
        ImportRowError: {
            /**
             * Column
             * @description Template column, or * for the whole row.
             */
            column: string;
            /** Message */
            message: string;
        };
        /**
         * ImportTemplate
         * @description The fixed employee CSV template (architecture v3 section 19). No column mapping in the MVP.
         */
        ImportTemplate: {
            /** Columns */
            columns: string[];
            /**
             * Example
             * @description One valid data row.
             */
            example: string;
            /** Notes */
            notes: string[];
        };
        /** Infeasibility */
        Infeasibility: {
            /** Summary */
            summary: string;
            /** Shortages */
            shortages: components["schemas"]["Shortage"][];
            /**
             * Conflict Set
             * @description Business constraints that together leave no valid roster: CP-SAT's sufficient infeasible assumption set. A diagnostic set, not a claim of the smallest one. Facts, skills, safety caps and pins are never in it. Empty when the facts alone are infeasible.
             */
            conflict_set?: components["schemas"]["ConflictItem"][];
            /**
             * Options
             * @description In order: overtime, cross_outlet, reduced_minimum. Each was feasible on its own; none is claimed to be the smallest change. Overlap, availability, absences, mandatory skills, the absolute weekly cap and authorization boundaries are never relaxed.
             */
            options?: components["schemas"]["RelaxationOption"][];
        };
        /**
         * LabourExplanation
         * @description Why the labour model asks for this staffing: forecast orders -> orders per hour -> demand band.
         */
        LabourExplanation: {
            /** Forecast Orders */
            forecast_orders: number;
            /** Orders Per Hour */
            orders_per_hour: number;
            /** Band Min Orders */
            band_min_orders: number;
            /** Band Max Orders */
            band_max_orders: number | null;
        };
        /** Me */
        Me: {
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /**
             * Org Id
             * Format: uuid
             */
            org_id: string;
            /** Org Name */
            org_name: string;
            /** Display Name */
            display_name: string;
            /**
             * Role
             * @enum {string}
             */
            role: "owner" | "manager" | "staff";
            /**
             * Outlet Id
             * @description Set for managers and staff; null for owners.
             */
            outlet_id: string | null;
            /**
             * Employee Id
             * @description Set for staff.
             */
            employee_id: string | null;
            /**
             * Timezone
             * @description Organization default IANA timezone.
             */
            timezone: string;
            /**
             * Capabilities
             * @description What this caller may do. Use it to show or hide controls; the server still enforces every action.
             */
            capabilities: ("view_all_outlets" | "manage_employees" | "edit_demand" | "generate" | "publish" | "view_costs" | "approve_cross_outlet" | "view_own_schedule" | "report_own_absence")[];
        };
        /** MetricDelta */
        MetricDelta: {
            /**
             * Metric
             * @enum {string}
             */
            metric: "labour_cost" | "coverage_ratio" | "minimum_deficit_minutes" | "open_shifts";
            /**
             * Before
             * @description labour_cost in paise.
             */
            before: number | null;
            /** After */
            after: number | null;
            /**
             * Message
             * @description Deterministic text built from the numbers; safe to show.
             */
            message: string;
        };
        /** Metrics */
        Metrics: {
            /**
             * Coverage Ratio
             * @description sum(min(assigned, preferred) x minutes) / sum(preferred x minutes). null when there is no demand. Overstaffing never raises it.
             */
            coverage_ratio: number | null;
            /**
             * Minimum Deficit Minutes
             * @description Staff-minutes below the hard minimum.
             */
            minimum_deficit_minutes: number;
            /** Preferred Deficit Minutes */
            preferred_deficit_minutes: number;
            /** @description Estimated roster cost, not payroll. */
            labour_cost: components["schemas"]["Money"];
            overtime_cost: components["schemas"]["Money"];
            /** Overtime Minutes */
            overtime_minutes: number;
            /** Preference Match Ratio */
            preference_match_ratio: number | null;
            /** Open Shifts */
            open_shifts: number;
            /** Assigned Minutes */
            assigned_minutes: number;
            /**
             * Hours Preference Deviation Minutes
             * @description Hours-preference alignment: sum over employees with a preferred weekly total of |worked - preferred| minutes. Lower is better. Not a fairness measure. null when nobody states a preference, and in metrics stored before contract 3.4.
             */
            hours_preference_deviation_minutes?: number | null;
            /**
             * Fairness Burden Deviation
             * @description Fairness burden (v4 section 12): mean absolute deviation, across the outlet's staff, of burden points per 40 h over the last 8 published weeks plus this one. Points: closing shift 3, weekend 2, second shift in a day 2, overtime hour 1. Lower is fairer; null in metrics stored before 3.16.
             */
            fairness_burden_deviation?: number | null;
            /** @description This roster's burden points this week by component (history excluded), with the policy version. Compare two plans component by component. */
            fairness_components?: components["schemas"]["FairnessComponents"] | null;
        };
        /** Money */
        Money: {
            /** Amount Paise */
            amount_paise: number;
            /**
             * Currency
             * @default INR
             * @constant
             */
            currency: "INR";
        };
        /**
         * MyWeek
         * @description An employee's own published shifts across all outlets for one week.
         */
        MyWeek: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /**
             * Shifts
             * @description Only shifts from current published versions.
             */
            shifts: components["schemas"]["Shift"][];
            /**
             * Outlets
             * @description Outlets referenced by the shifts.
             */
            outlets: components["schemas"]["OutletRef"][];
            /**
             * Skills
             * @description Skills referenced by the shifts, for role labels.
             */
            skills: components["schemas"]["Skill"][];
            /**
             * Absences
             * @description The employee's own absences overlapping the week, any status (v3 section 20).
             */
            absences?: components["schemas"]["AbsenceMark"][];
        };
        /**
         * Notification
         * @description An in-app notification (architecture v3 section 40).
         */
        Notification: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Topic
             * @description schedule.published (your week), run.finished (options or a repair are ready), absence.reported, proposal.ready or proposal.stale.
             */
            topic: string;
            /**
             * Title
             * @description Deterministic text; safe to show.
             */
            title: string;
            /**
             * Payload
             * @description Ids to link to, e.g. schedule_id, version_id, run_id.
             */
            payload: {
                [key: string]: unknown;
            };
            /**
             * Delivered At
             * Format: date-time
             */
            delivered_at: string;
            /** Read At */
            read_at: string | null;
        };
        /** NotificationList */
        NotificationList: {
            /**
             * Items
             * @description Newest first, at most 100.
             */
            items: components["schemas"]["Notification"][];
        };
        /** OpenShift */
        OpenShift: {
            /**
             * Version Id
             * Format: uuid
             */
            version_id: string;
            shift: components["schemas"]["Shift"];
            /**
             * Reasons
             * @description Why you may take it: every check passed.
             */
            reasons: components["schemas"]["ExplanationFact"][];
        };
        /**
         * OpenShiftList
         * @description Only open shifts you are eligible for (architecture v4 section 28).
         */
        OpenShiftList: {
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /** Items */
            items: components["schemas"]["OpenShift"][];
        };
        /** OperatingWindow */
        OperatingWindow: {
            /**
             * Weekday
             * @description 0 = Monday ... 6 = Sunday
             */
            weekday: number;
            /**
             * Open Minute
             * @description Minutes from outlet-local midnight; values above 1440 continue past midnight
             */
            open_minute: number;
            /**
             * Close Minute
             * @description Minutes from outlet-local midnight; values above 1440 continue past midnight
             */
            close_minute: number;
        };
        /** OptimizationRun */
        OptimizationRun: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "generate" | "optimize" | "repair" | "scenario";
            /** Outlet Ids */
            outlet_ids: string[];
            /** Base Version Ids */
            base_version_ids: string[];
            /** Strategy */
            strategy: ("balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness") | ("least_disruption" | "lowest_cost" | "best_coverage");
            /**
             * Absence Id
             * @description Repair runs: the absence being repaired.
             */
            absence_id?: string | null;
            /**
             * Scenario Id
             * @description Scenario runs: hypothetical; their candidates cannot be selected.
             */
            scenario_id?: string | null;
            /**
             * Job State
             * @enum {string}
             */
            job_state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
            /**
             * Solver Status
             * @description Set once solving ends. UNKNOWN means no solution within the time limit; it does not prove infeasibility.
             */
            solver_status: ("OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "MODEL_INVALID" | "UNKNOWN") | null;
            /** Input Hash */
            input_hash: string;
            /**
             * Queued At
             * Format: date-time
             */
            queued_at: string;
            /** Started At */
            started_at: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Solver Wall Ms */
            solver_wall_ms: number | null;
            /**
             * Poll After Ms
             * @description Suggested polling delay while queued/running; null when terminal.
             */
            poll_after_ms: number | null;
            /** Candidates */
            candidates: components["schemas"]["Candidate"][];
            infeasibility: components["schemas"]["Infeasibility"] | null;
            /** @description Set when job_state is failed. */
            error: components["schemas"]["ErrorBody"] | null;
            /**
             * Repair Stages
             * @description Repair runs, once finished: the widening stages tried and why it widened.
             */
            repair_stages?: components["schemas"]["RepairStage"][];
            /**
             * Frozen Logical Shift Ids
             * @description The run's freeze set: shifts held exactly (v4 section 13).
             */
            frozen_logical_shift_ids?: string[];
            /** @description Generate runs that finished with plans; null for repairs and before. */
            portfolio?: components["schemas"]["PortfolioSummary"] | null;
            /**
             * Candidates Expired
             * @description Unselected candidates are removed 7 days after the run (retention); only selected ones remain, possibly none. Offer a new run instead of the old options.
             * @default false
             */
            candidates_expired: boolean;
        };
        /** Outlet */
        Outlet: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Slug */
            slug: string;
            /** Timezone */
            timezone: string;
            /** Operating Hours */
            operating_hours: components["schemas"]["OperatingWindow"][];
        };
        /** OutletList */
        OutletList: {
            /** Items */
            items: components["schemas"]["Outlet"][];
        };
        /** OutletRef */
        OutletRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Timezone */
            timezone: string;
        };
        /** PlanDelta */
        PlanDelta: {
            /**
             * Compared To
             * @description base_version when regenerating or repairing; on an empty week, other plans compare with the requested plan (rank 1), whose deltas are null.
             */
            compared_to: ("base_version" | "requested_plan") | null;
            /**
             * Cost Delta Paise
             * @description Labour plus overtime premium; negative = cheaper.
             */
            cost_delta_paise: number | null;
            /**
             * Preferred Gap Delta Minutes
             * @description Negative = better preferred coverage.
             */
            preferred_gap_delta_minutes: number | null;
            /**
             * Fairness Delta
             * @description Fairness burden deviation; negative = fairer.
             */
            fairness_delta: number | null;
            /** Overtime Minutes */
            overtime_minutes: number;
            /**
             * Cross Outlet Moves
             * @description Shifts worked away from the person's home outlet.
             */
            cross_outlet_moves: number;
            /**
             * Changed Commitments
             * @description MOVED_TIME + REASSIGNED + REMOVED + UNFILLED.
             */
            changed_commitments: number;
        };
        /** PortfolioDrop */
        PortfolioDrop: {
            /**
             * Strategy
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness";
            /**
             * Reason
             * @description duplicate: same assignments as `detail[0]`. guardrail: broke the guardrails named in `detail` (cost, overtime, coverage, disruption, fairness), measured against the requested plan. dominated: `detail[0]` is no worse on every displayed metric and better on one. limit: valid and distinct, but beyond the three plans shown.
             * @enum {string}
             */
            reason: "duplicate" | "guardrail" | "dominated" | "limit";
            /** Detail */
            detail: string[];
        };
        /**
         * PortfolioSummary
         * @description How the Candidate Portfolio chose what to show (architecture v4 section 16). The requested
         *     strategy's plan is always first; displayed metrics are total cost, preferred-coverage gap, overtime
         *     minutes, changed shifts (when there is a base) and fairness burden.
         */
        PortfolioSummary: {
            /**
             * Policy Version
             * @description Guardrail policy revision.
             */
            policy_version: number;
            /**
             * Considered
             * @description Strategies solved, requested first.
             */
            considered: ("balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness")[];
            /** Dropped */
            dropped: components["schemas"]["PortfolioDrop"][];
        };
        /** Proposal */
        Proposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /**
             * Draft Version Id
             * Format: uuid
             */
            draft_version_id: string;
            /** Draft Revision */
            draft_revision: number;
            /**
             * Base Version Id
             * @description The published version this plan replaces.
             */
            base_version_id: string | null;
            /**
             * Candidate Id
             * @description Set when the draft came from an optimization candidate.
             */
            candidate_id: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "approved" | "rejected" | "expired" | "stale" | "failed";
            /** @description What the manager agreed to; Changed is judged against it. */
            metrics_at_proposal: components["schemas"]["Metrics"];
            /**
             * Requested By User Id
             * Format: uuid
             */
            requested_by_user_id: string;
            /** Decided By User Id */
            decided_by_user_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided At */
            decided_at: string | null;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
        };
        /** ProposalChanges */
        ProposalChanges: {
            /** Added */
            added: number;
            /** Changed */
            changed: number;
            /** Removed */
            removed: number;
            /** Unchanged */
            unchanged: number;
            /**
             * Manual Kept
             * @description Manual overrides: never replaced by a forecast.
             */
            manual_kept: number;
        };
        /**
         * ProposalDecision
         * @description The publication transaction's answer (architecture v3 section 31). Always 200: each outcome is a
         *     normal business result, not an error.
         */
        ProposalDecision: {
            /**
             * Outcome
             * @description published: the new version is live. stale: someone published first or the draft changed; re-run against current_version_id. invalid: a current fact breaks the plan (violations); offer a repair. changed: still valid but metrics moved materially (deltas); approve again with acknowledge_changes to accept.
             * @enum {string}
             */
            outcome: "published" | "stale" | "invalid" | "changed";
            /** Message */
            message: string;
            proposal: components["schemas"]["Proposal"];
            published?: components["schemas"]["ScheduleVersionSummary"] | null;
            /** Superseded Version Id */
            superseded_version_id?: string | null;
            /**
             * Current Version Id
             * @description Set when stale.
             */
            current_version_id?: string | null;
            /**
             * Violations
             * @description Set when invalid.
             */
            violations?: components["schemas"]["Violation"][];
            /**
             * Deltas
             * @description Set when changed.
             */
            deltas?: components["schemas"]["MetricDelta"][];
        };
        /** ProposalList */
        ProposalList: {
            /**
             * Items
             * @description Newest first, at most 100.
             */
            items: components["schemas"]["Proposal"][];
        };
        /**
         * ProposedCall
         * @description The existing API call that carries out the command, made by the UI after the person confirms.
         */
        ProposedCall: {
            /** Operation Id */
            operation_id: string;
            /**
             * Method
             * @constant
             */
            method: "POST";
            /** Path */
            path: string;
            /** Body */
            body: {
                [key: string]: unknown;
            };
        };
        /** ProposedRequirement */
        ProposedRequirement: {
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /**
             * Interval End
             * Format: date-time
             */
            interval_end: string;
            /** Minimum */
            minimum: number;
            /** Preferred */
            preferred: number;
            /**
             * Source
             * @enum {string}
             */
            source: "template" | "forecast";
            /** @description forecast rows only. */
            explanation?: components["schemas"]["LabourExplanation"] | null;
        };
        /** PublishRequest */
        PublishRequest: {
            /**
             * Expected Base Version Id
             * @description The published version this draft replaces.
             */
            expected_base_version_id: string | null;
            /** Expected Revision */
            expected_revision: number;
        };
        /** PublishResult */
        PublishResult: {
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            published: components["schemas"]["ScheduleVersionSummary"];
            /** Superseded Version Id */
            superseded_version_id: string | null;
        };
        /** Recommendation */
        Recommendation: {
            /** Rank */
            rank: number;
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
            /**
             * Home Outlet Id
             * Format: uuid
             */
            home_outlet_id: string;
            /**
             * Disruption Class
             * @description Ranked in this order first: direct, then pushing into overtime, then another outlet.
             * @enum {string}
             */
            disruption_class: "direct" | "overtime" | "cross_outlet";
            /** @description Labour plus overtime premium, against leaving the shift open. */
            incremental_cost: components["schemas"]["Money"];
            /** Overtime Minutes Added */
            overtime_minutes_added: number;
            /**
             * Fairness Delta
             * @description Change in fairness burden deviation; negative = fairer.
             */
            fairness_delta: number | null;
            /** Weekly Minutes After */
            weekly_minutes_after: number;
            /**
             * Within Preferred Window
             * @description null: the person states no preferred windows.
             */
            within_preferred_window: boolean | null;
            /**
             * Reasons
             * @description Every eligibility check passed, plus cost, burden and disruption.
             */
            reasons: components["schemas"]["ExplanationFact"][];
            /** @description Apply to a draft with applyEdits to choose this person. */
            edit: components["schemas"]["UpdateShift"];
        };
        /** RelaxationEmployee */
        RelaxationEmployee: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
            /**
             * Home Outlet Id
             * Format: uuid
             */
            home_outlet_id: string;
            /**
             * Minutes
             * @description overtime: minutes beyond the regular week; cross_outlet: minutes worked.
             */
            minutes: number;
        };
        /**
         * RelaxationOption
         * @description A business option instead of a bare INFEASIBLE (architecture v3 section 13). It is a diagnosis
         *     found by re-solving with that one relaxation, not a schedule: apply it, then generate again.
         */
        RelaxationOption: {
            /**
             * Kind
             * @description overtime: let the named people work overtime (update their overtime permission). cross_outlet: borrow the named people from their outlets (owner). reduced_minimum: operate the listed intervals with fewer staff (lower the week's minimum_required).
             * @enum {string}
             */
            kind: "overtime" | "cross_outlet" | "reduced_minimum";
            /**
             * Summary
             * @description Deterministic text built from the facts; safe to show.
             */
            summary: string;
            /** Employees */
            employees?: components["schemas"]["RelaxationEmployee"][];
            /**
             * Shortages
             * @description reduced_minimum only.
             */
            shortages?: components["schemas"]["Shortage"][];
        };
        /** RemoveShift */
        RemoveShift: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "remove";
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
        };
        /** RepairRequest */
        RepairRequest: {
            /**
             * Absence Id
             * Format: uuid
             */
            absence_id: string;
            /**
             * Base Version Id
             * Format: uuid
             * @description The published version being repaired. Stale -> 409.
             */
            base_version_id: string;
            /**
             * Unlock Logical Shift Ids
             * @description Locked affected shifts the manager authorizes to change (decision 5).
             */
            unlock_logical_shift_ids?: string[];
            /**
             * Allow Cross Outlet
             * @description Owner only: let the repair borrow staff from other outlets (widening stage other_outlets). Managers get 403.
             * @default false
             */
            allow_cross_outlet: boolean;
            /** @description Shifts no stage may change (v4 section 13). 409 when the absence or another current fact breaks one of them. */
            freeze?: components["schemas"]["FreezeSpec"] | null;
            /**
             * Time Limit Seconds
             * @default 3
             */
            time_limit_seconds: number;
        };
        /**
         * RepairStage
         * @description One widening stage of a repair run (architecture v3 section 12), in the order tried.
         */
        RepairStage: {
            /**
             * Stage
             * @description impact: only the shifts the absence breaks; everything else frozen (v4 section 15). same_day: the affected days from the absence onward, home staff, no overtime. adjacent_shifts: plus the day either side. other_outlets: plus other outlets' staff (owner-authorized). overtime: overtime where contracts allow it.
             * @enum {string}
             */
            stage: "impact" | "same_day" | "adjacent_shifts" | "other_outlets" | "overtime";
            /**
             * Result
             * @description selected: the candidates come from this stage. insufficient: minimum staffing could not be kept, so the repair widened. skipped: see reason.
             * @enum {string}
             */
            result: "selected" | "insufficient" | "no_plan" | "skipped";
            /**
             * Reason
             * @description Why a stage was skipped: not authorized, or no wider than the last.
             */
            reason?: ("not_authorized" | "same_scope") | null;
            /**
             * Free Shifts
             * @description Published shifts this stage was allowed to change.
             */
            free_shifts: number;
            /**
             * Pool
             * @description Employees who could take them.
             */
            pool: number;
            /**
             * Minimum Shortfall Minutes
             * @description Best minimum-staffing shortfall found (staff-minutes).
             */
            minimum_shortfall_minutes?: number | null;
            /**
             * Released
             * @description What this stage was allowed to change.
             */
            released?: string | null;
            /**
             * Widened Because
             * @description Why the previous stage was not enough.
             */
            widened_because?: string | null;
        };
        /**
         * ReplacementRecommendations
         * @description Who can cover this shift (architecture v4 sections 11, 46). Read-only; nothing is written.
         *
         *     basis is a direct assignment: each person is checked as if they took the shift and nothing else
         *     changed. Someone blocked only by another of their shifts could become free if that shift moved; that
         *     is a repair run, never presented as a recommendation.
         */
        ReplacementRecommendations: {
            /**
             * Version Id
             * Format: uuid
             */
            version_id: string;
            /**
             * Version Status
             * @enum {string}
             */
            version_status: "draft" | "published" | "superseded" | "discarded";
            shift: components["schemas"]["Shift"];
            /**
             * Vacating Employee Id
             * @description Who holds the shift now; null = open.
             */
            vacating_employee_id: string | null;
            /**
             * Profile
             * @enum {string}
             */
            profile: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness";
            /**
             * Basis
             * @default direct_assignment
             * @constant
             */
            basis: "direct_assignment";
            /** Policy Version */
            policy_version: number;
            /**
             * Considered
             * @description Qualified people checked.
             */
            considered: number;
            /**
             * Eligible
             * @description Of those, people no rule blocks (recommendations is the top `limit`).
             */
            eligible: number;
            /** Recommendations */
            recommendations: components["schemas"]["Recommendation"][];
            /**
             * Rejected
             * @description Blocked people with the concrete rule (at most 10).
             */
            rejected: components["schemas"]["AlternativeFact"][];
        };
        /** ReplacementRequest */
        ReplacementRequest: {
            /**
             * Version Id
             * Format: uuid
             * @description The version the shift is in: published or a draft.
             */
            version_id: string;
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /**
             * Profile
             * @description Ranks eligible people the way the profile weighs cost, fairness and preferences.
             * @default balanced
             * @enum {string}
             */
            profile: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness";
            /**
             * Include Other Outlets
             * @description Owner only; managers get 403.
             * @default false
             */
            include_other_outlets: boolean;
            /**
             * Limit
             * @default 5
             */
            limit: number;
        };
        /** ReportAbsenceRequest */
        ReportAbsenceRequest: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "leave" | "sick" | "other";
            /**
             * Status
             * @description Managers may report confirmed absences; staff may only request for themselves.
             * @enum {string}
             */
            status: "requested" | "confirmed";
            /** Reason */
            reason?: string | null;
        };
        /** RestoreRequest */
        RestoreRequest: {
            /**
             * Expected Base Version Id
             * @description The currently published version.
             */
            expected_base_version_id: string | null;
        };
        /** RosterEmployee */
        RosterEmployee: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Home Outlet Id
             * Format: uuid
             */
            home_outlet_id: string;
            /** Skill Ids */
            skill_ids: string[];
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "inactive";
            /**
             * Scheduled Minutes
             * @description Paid minutes this week across all outlets' published versions.
             */
            scheduled_minutes: number;
            /** Regular Weekly Minutes */
            regular_weekly_minutes: number;
            /** Max Weekly Minutes */
            max_weekly_minutes: number;
        };
        /** RuleConflict */
        RuleConflict: {
            /**
             * Rule Id
             * Format: uuid
             */
            rule_id: string;
            /** Rule Name */
            rule_name: string;
            /**
             * Employees
             * @description Names of the people both rules apply to.
             */
            employees: string[];
            /**
             * Message
             * @description E.g. This conflicts with "Students must finish by 9 PM". ...
             */
            message: string;
            /** @description When one person is in both: the same rule scoped to them, overriding the existing rule. Offer it as 'Create an exception for <name>'; otherwise keep the existing rule. */
            suggested_exception: components["schemas"]["RuleDefinition"] | null;
        };
        /**
         * RuleDefinition
         * @description A scheduling rule (architecture v3 section 21). Precedence is by scope, never by number: a more
         *     specific rule replaces another only when it names it in overrides_rule_id.
         *
         *     parameters by rule_type: max_shift_end_time {latest_end_minute (0-1440, half-hour), weekdays
         *     [0=Monday..6]}; max_days_per_week {days (1-7)}.
         */
        RuleDefinition: {
            /**
             * Rule Type
             * @enum {string}
             */
            rule_type: "max_shift_end_time" | "max_days_per_week";
            /**
             * Scope Level
             * @enum {string}
             */
            scope_level: "organization" | "outlet" | "tag" | "employee";
            /**
             * Scope
             * @description {} for organization; {outlet_id}; {tag} (e.g. student); {employee_id}.
             */
            scope: {
                [key: string]: string;
            };
            /** Parameters */
            parameters: {
                [key: string]: unknown;
            };
            /**
             * Hard
             * @description Only hard rules are supported in the MVP.
             * @default true
             */
            hard: boolean;
            /**
             * Overrides Rule Id
             * @description The rule this one is an exception to.
             */
            overrides_rule_id?: string | null;
            /**
             * Source Text
             * @description How a person phrased it.
             */
            source_text?: string | null;
        };
        /** RuleEmployee */
        RuleEmployee: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
        };
        /** RuleImpact */
        RuleImpact: {
            /**
             * Employee Id
             * Format: uuid
             */
            employee_id: string;
            /** Name */
            name: string;
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Message */
            message: string;
        };
        /** RuleList */
        RuleList: {
            /** Items */
            items: components["schemas"]["SchedulingRule"][];
        };
        /**
         * RuleParse
         * @description A rule in words, run through the rule validation service. ready: preview is what createRule
         *     would save (send preview.rule). Unsupported rules are refused, never approximated.
         */
        RuleParse: {
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "needs_clarification" | "unsupported" | "unavailable";
            /** Message */
            message: string;
            preview?: components["schemas"]["RulePreview"] | null;
            /** Options */
            options?: components["schemas"]["CommandOption"][];
        };
        /** RuleParseRequest */
        RuleParseRequest: {
            /**
             * Text
             * @description E.g. "Students cannot work after 9 PM on weekdays".
             */
            text: string;
        };
        /**
         * RulePreview
         * @description What saving the rule would mean. Writes nothing.
         */
        RulePreview: {
            rule: components["schemas"]["RuleDefinition"];
            /**
             * Summary
             * @description Deterministic description, e.g. No shift ends after 21:00 on weekdays.
             */
            summary: string;
            /**
             * Valid
             * @description false when it conflicts with an active rule; saving would be 409.
             */
            valid: boolean;
            /** Affected */
            affected: components["schemas"]["RuleEmployee"][];
            /** Conflicts */
            conflicts: components["schemas"]["RuleConflict"][];
            /**
             * Impact
             * @description Upcoming published shifts this rule would break (at most 50). They stay published; the next generation or repair respects the rule.
             */
            impact: components["schemas"]["RuleImpact"][];
        };
        /**
         * Scenario
         * @description A what-if that never changes real facts. Run it, compare each candidate's trace (deltas against
         *     the base version, measured under the scenario) with `baseline`, then convert one candidate: it is
         *     re-checked against current facts and becomes a normal draft.
         */
        Scenario: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /** Title */
            title: string;
            /**
             * Base Version Id
             * @description The published version the scenario starts from.
             */
            base_version_id: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "open" | "converted" | "discarded" | "expired";
            /**
             * Created By User Id
             * Format: uuid
             */
            created_by_user_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Converted Version Id */
            converted_version_id: string | null;
            /** Events */
            events: components["schemas"]["ScenarioEvent"][];
            /** Latest Run Id */
            latest_run_id: string | null;
            /** @description From the latest run; null before the first. */
            baseline: components["schemas"]["ScenarioBaseline"] | null;
        };
        /**
         * ScenarioBaseline
         * @description The current plan as it would stand if the events happened: the "before" of the comparison.
         */
        ScenarioBaseline: {
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            metrics: components["schemas"]["Metrics"];
            /**
             * Hard Violations
             * @description Shifts the events would break (e.g. an absence).
             */
            hard_violations: number;
            /** Violation Codes */
            violation_codes: string[];
        };
        /** ScenarioEvent */
        ScenarioEvent: {
            /**
             * Type
             * @enum {string}
             */
            type: "demand_change" | "absence" | "outlet_closure" | "labour_cap" | "rule";
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Sequence
             * @description Events apply in this order.
             */
            sequence: number;
        };
        /**
         * ScenarioEventIn
         * @description One hypothetical event (architecture v4 section 23). Payloads by type:
         *
         *     - demand_change: {percent: -100..300, skill_id?, weekdays?: [0..6], start_minute?, end_minute?}
         *     - absence: {employee_id, start_at, end_at}
         *     - outlet_closure: {day: YYYY-MM-DD}
         *     - labour_cap: {max_cost_paise}
         *     - rule: {rule_type, parameters, employee_ids: [...]} (same rule types as createRule)
         *
         *     Other types are refused (422), never turned into free-form solver input.
         */
        ScenarioEventIn: {
            /**
             * Type
             * @enum {string}
             */
            type: "demand_change" | "absence" | "outlet_closure" | "labour_cap" | "rule";
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
        };
        /** ScenarioList */
        ScenarioList: {
            /** Items */
            items: components["schemas"]["Scenario"][];
        };
        /** ScenarioRunRequest */
        ScenarioRunRequest: {
            /**
             * Strategy
             * @default balanced
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage" | "stability" | "fairness";
            /**
             * Time Limit Seconds
             * @default 10
             */
            time_limit_seconds: number;
        };
        /** ScheduleVersion */
        ScheduleVersion: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /** Version Number */
            version_number: number;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "published" | "superseded" | "discarded";
            /**
             * Source
             * @enum {string}
             */
            source: "seed" | "manual" | "generate" | "optimize" | "repair" | "restore" | "import" | "scenario" | "request";
            /** Reason */
            reason: string;
            /** Base Version Id */
            base_version_id: string | null;
            /** Optimization Run Id */
            optimization_run_id: string | null;
            /**
             * Created By User Id
             * @description null = created by ShiftPilot.
             */
            created_by_user_id: string | null;
            /** Approved By User Id */
            approved_by_user_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Published At */
            published_at: string | null;
            /**
             * Revision
             * @description Bumped by every applied edit while the version is a draft; send it as expected_revision. Fixed once published.
             */
            revision: number;
            /** @description Stored when the draft was last saved and recomputed at publication, then frozen: what the version cost and covered when it went live. Cheap to list in history. null for versions saved before contract 3.1. ScheduleVersion.metrics is evaluated against current facts. */
            recorded_metrics?: components["schemas"]["Metrics"] | null;
            /** Input Hash */
            input_hash: string;
            /** Shifts */
            shifts: components["schemas"]["Shift"][];
            metrics: components["schemas"]["Metrics"];
            /** Coverage */
            coverage: components["schemas"]["CoverageCell"][];
            validation: components["schemas"]["ValidationResult"];
        };
        /** ScheduleVersionSummary */
        ScheduleVersionSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /** Version Number */
            version_number: number;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "published" | "superseded" | "discarded";
            /**
             * Source
             * @enum {string}
             */
            source: "seed" | "manual" | "generate" | "optimize" | "repair" | "restore" | "import" | "scenario" | "request";
            /** Reason */
            reason: string;
            /** Base Version Id */
            base_version_id: string | null;
            /** Optimization Run Id */
            optimization_run_id: string | null;
            /**
             * Created By User Id
             * @description null = created by ShiftPilot.
             */
            created_by_user_id: string | null;
            /** Approved By User Id */
            approved_by_user_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Published At */
            published_at: string | null;
            /**
             * Revision
             * @description Bumped by every applied edit while the version is a draft; send it as expected_revision. Fixed once published.
             */
            revision: number;
            /** @description Stored when the draft was last saved and recomputed at publication, then frozen: what the version cost and covered when it went live. Cheap to list in history. null for versions saved before contract 3.1. ScheduleVersion.metrics is evaluated against current facts. */
            recorded_metrics?: components["schemas"]["Metrics"] | null;
        };
        /** ScheduleWeek */
        ScheduleWeek: {
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             * @description Monday, outlet-local.
             */
            week_start: string;
            /** Timezone */
            timezone: string;
            /**
             * Schedule Id
             * @description null when nothing exists for this week yet.
             */
            schedule_id: string | null;
            /** @description Live published version, if any. */
            current_version: components["schemas"]["ScheduleVersion"] | null;
            /** Drafts */
            drafts: components["schemas"]["ScheduleVersionSummary"][];
            /**
             * Employees
             * @description Rows for the roster: active home-outlet employees plus anyone with a shift in current_version. An employee with no shift on a day is off that day.
             */
            employees: components["schemas"]["RosterEmployee"][];
            /**
             * Absences
             * @description Absences overlapping this week for listed employees.
             */
            absences: components["schemas"]["AbsenceMark"][];
        };
        /** SchedulingRule */
        SchedulingRule: {
            /**
             * Rule Type
             * @enum {string}
             */
            rule_type: "max_shift_end_time" | "max_days_per_week";
            /**
             * Scope Level
             * @enum {string}
             */
            scope_level: "organization" | "outlet" | "tag" | "employee";
            /**
             * Scope
             * @description {} for organization; {outlet_id}; {tag} (e.g. student); {employee_id}.
             */
            scope: {
                [key: string]: string;
            };
            /** Parameters */
            parameters: {
                [key: string]: unknown;
            };
            /**
             * Hard
             * @description Only hard rules are supported in the MVP.
             * @default true
             */
            hard: boolean;
            /**
             * Overrides Rule Id
             * @description The rule this one is an exception to.
             */
            overrides_rule_id?: string | null;
            /**
             * Source Text
             * @description How a person phrased it.
             */
            source_text?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Summary */
            summary: string;
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "active" | "archived";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** SetLock */
        SetLock: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "lock" | "unlock";
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /** Reason */
            reason?: string | null;
        };
        /** Shift */
        Shift: {
            /**
             * Id
             * Format: uuid
             * @description This version's row. Changes between versions.
             */
            id: string;
            /**
             * Logical Shift Id
             * Format: uuid
             * @description Stable identity across versions; key diffs on it.
             */
            logical_shift_id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Employee Id
             * @description null = open (unfilled) shift.
             */
            employee_id: string | null;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Break Start At */
            break_start_at: string | null;
            /** Break Minutes */
            break_minutes: number;
            /** Locked */
            locked: boolean;
            /** Lock Reason */
            lock_reason: string | null;
        };
        /** ShiftChange */
        ShiftChange: {
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /** Kinds */
            kinds: ("added" | "removed" | "reassigned" | "moved" | "resized" | "role_changed" | "lock_changed" | "break_changed")[];
            before: components["schemas"]["Shift"] | null;
            after: components["schemas"]["Shift"] | null;
        };
        /** ShiftExplanation */
        ShiftExplanation: {
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /**
             * Chosen Employee Id
             * @description null = the shift was left open.
             */
            chosen_employee_id: string | null;
            /**
             * Reasons
             * @description Facts about the chosen employee.
             */
            reasons: components["schemas"]["ExplanationFact"][];
            /**
             * Alternatives
             * @description Other qualified people (bounded list).
             */
            alternatives: components["schemas"]["AlternativeFact"][];
        };
        /** ShiftRequestList */
        ShiftRequestList: {
            /** Items */
            items: components["schemas"]["ShiftRequestView"][];
        };
        /**
         * ShiftRequestView
         * @description Lifecycle: open (waiting for a colleague) -> pending_manager -> approved | rejected. A manager's
         *     approval re-validates against current facts and publishes a new version through the normal gate;
         *     if the published week moved under the shifts it is stale, if current facts break it it is invalid
         *     (see violations). Requests expire when the shift starts.
         */
        ShiftRequestView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Type
             * @enum {string}
             */
            type: "open_shift_claim" | "giveaway" | "swap";
            /**
             * Status
             * @enum {string}
             */
            status: "open" | "pending_manager" | "approved" | "rejected" | "cancelled" | "expired" | "stale" | "invalid";
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /**
             * Base Version Id
             * Format: uuid
             */
            base_version_id: string;
            shift: components["schemas"]["Shift"];
            target_shift: components["schemas"]["Shift"] | null;
            /**
             * Requester Employee Id
             * Format: uuid
             */
            requester_employee_id: string;
            /** Target Employee Id */
            target_employee_id: string | null;
            /** Note */
            note: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Decided By User Id */
            decided_by_user_id: string | null;
            /** Decided At */
            decided_at: string | null;
            /**
             * Published Version Id
             * @description approved: the version that was published.
             */
            published_version_id: string | null;
            /**
             * Violations
             * @description invalid: what current facts break.
             */
            violations?: components["schemas"]["Violation"][];
        };
        /** ShiftTemplate */
        ShiftTemplate: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Skill Id
             * @description null: usable for any skill.
             */
            skill_id: string | null;
            /**
             * Start Minute
             * @description Outlet-local minutes from midnight.
             */
            start_minute: number;
            /** Duration Minutes */
            duration_minutes: number;
            /** Break Minutes */
            break_minutes: number;
            /**
             * Break Start Minute
             * @description Where the break starts, in minutes from shift start (the server's placement); null when the template has no break.
             */
            break_start_minute: number | null;
        };
        /** ShiftTemplateList */
        ShiftTemplateList: {
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Items
             * @description Active templates, by start time.
             */
            items: components["schemas"]["ShiftTemplate"][];
        };
        /** Shortage */
        Shortage: {
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /**
             * Interval End
             * Format: date-time
             */
            interval_end: string;
            /** Minimum Required */
            minimum_required: number;
            /**
             * Max Assignable
             * @description Upper bound of eligible staff for this interval.
             */
            max_assignable: number;
        };
        /** Skill */
        Skill: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /** SkillList */
        SkillList: {
            /** Items */
            items: components["schemas"]["Skill"][];
        };
        /** StaffingInterval */
        StaffingInterval: {
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /**
             * Interval End
             * Format: date-time
             */
            interval_end: string;
            /**
             * Minimum Required
             * @description Hard: a roster below this is infeasible.
             */
            minimum_required: number;
            /**
             * Preferred Required
             * @description Soft: shortfall is penalized.
             */
            preferred_required: number;
            /**
             * Source
             * @description template/band rows are regenerated by expandStaffingRequirements; manual rows are overrides that survive re-expansion.
             * @enum {string}
             */
            source: "template" | "band" | "manual" | "scenario" | "forecast";
        };
        /** StaffingProposal */
        StaffingProposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /**
             * Forecast Run Id
             * Format: uuid
             */
            forecast_run_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "accepted" | "rejected" | "stale";
            /** Base Demand Revision */
            base_demand_revision: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided By User Id */
            decided_by_user_id: string | null;
            /** Decided At */
            decided_at: string | null;
            /** @description Against the week's current requirements. */
            changes: components["schemas"]["ProposalChanges"];
            /** Rows */
            rows: components["schemas"]["ProposedRequirement"][];
        };
        /** StaffingRequirements */
        StaffingRequirements: {
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Week Start
             * Format: date
             */
            week_start: string;
            /**
             * Interval Minutes
             * @description Grid size, 30 by default.
             */
            interval_minutes: number;
            /** Demand Revision */
            demand_revision: number;
            /** Intervals */
            intervals: components["schemas"]["StaffingInterval"][];
        };
        /** StaffingRequirementsUpdate */
        StaffingRequirementsUpdate: {
            /** Base Demand Revision */
            base_demand_revision: number;
            /** Intervals */
            intervals: components["schemas"]["StaffingInterval"][];
        };
        /**
         * StaffingTemplateBlock
         * @description Default demand for one weekday, block and skill (e.g. Monday 12:00-15:00: 2 Grill, 3 preferred).
         */
        StaffingTemplateBlock: {
            /**
             * Weekday
             * @description Monday = 0.
             */
            weekday: number;
            /**
             * Start Minute
             * @description Outlet-local minutes from midnight.
             */
            start_minute: number;
            /** End Minute */
            end_minute: number;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
            /** Minimum Required */
            minimum_required: number;
            /** Preferred Required */
            preferred_required: number;
        };
        /** StaffingTemplateSet */
        StaffingTemplateSet: {
            /**
             * Outlet Id
             * Format: uuid
             */
            outlet_id: string;
            /**
             * Revision
             * @description 0 before any template was saved. Send it as base_revision.
             */
            revision: number;
            /**
             * Items
             * @description By weekday, skill and start.
             */
            items: components["schemas"]["StaffingTemplateBlock"][];
        };
        /** StaffingTemplateUpdate */
        StaffingTemplateUpdate: {
            /** Base Revision */
            base_revision: number;
            /**
             * Items
             * @description The whole set; blocks of one weekday and skill must not overlap.
             */
            items: components["schemas"]["StaffingTemplateBlock"][];
        };
        /** StageImportRequest */
        StageImportRequest: {
            /** Filename */
            filename: string;
            /**
             * Content
             * @description The CSV text (UTF-8), header row first.
             */
            content: string;
        };
        /** StreamEvent */
        StreamEvent: {
            /**
             * Event
             * @description run/forecast: the full resource as its GET returns it. version: {schedule_id, current_version_id}. end: {reason: finished | reconnect}.
             * @enum {string}
             */
            event: "run" | "forecast" | "version" | "end";
            /**
             * Id
             * @description Changes whenever the payload changes.
             */
            id?: string | null;
            /** Data */
            data: {
                [key: string]: unknown;
            };
        };
        /** TraceChange */
        TraceChange: {
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /**
             * Change
             * @description Never KEPT: kept shifts are only counted.
             * @enum {string}
             */
            change: "KEPT" | "MOVED_TIME" | "REASSIGNED" | "CREATED" | "REMOVED" | "UNFILLED";
            /**
             * Kinds
             * @description Finer diff kinds: added, removed, reassigned, moved, resized, ...
             */
            kinds: string[];
            /** Before Employee Id */
            before_employee_id: string | null;
            /** After Employee Id */
            after_employee_id: string | null;
        };
        /** UpdateAbsenceRequest */
        UpdateAbsenceRequest: {
            /**
             * Status
             * @enum {string}
             */
            status: "confirmed" | "rejected" | "cancelled";
        };
        /**
         * UpdateShift
         * @description Move, resize, reassign or change role. Omitted or null fields keep their value, except
         *     employee_id, where null unassigns. Remove a break with break_minutes 0.
         */
        UpdateShift: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "update";
            /**
             * Logical Shift Id
             * Format: uuid
             */
            logical_shift_id: string;
            /** Employee Id */
            employee_id?: string | null;
            /** Skill Id */
            skill_id?: string | null;
            /** Start At */
            start_at?: string | null;
            /** End At */
            end_at?: string | null;
            /** Break Start At */
            break_start_at?: string | null;
            /** Break Minutes */
            break_minutes?: number | null;
        };
        /** ValidationResult */
        ValidationResult: {
            /** Hard Violations */
            hard_violations: number;
            /** Soft Violations */
            soft_violations: number;
            /** Violations */
            violations: components["schemas"]["Violation"][];
        };
        /** VersionDiff */
        VersionDiff: {
            /**
             * From Version Id
             * Format: uuid
             */
            from_version_id: string;
            /**
             * To Version Id
             * Format: uuid
             */
            to_version_id: string;
            /** Changes */
            changes: components["schemas"]["ShiftChange"][];
            metrics_from: components["schemas"]["Metrics"];
            metrics_to: components["schemas"]["Metrics"];
        };
        /** VersionHistory */
        VersionHistory: {
            /**
             * Schedule Id
             * Format: uuid
             */
            schedule_id: string;
            /** Current Version Id */
            current_version_id: string | null;
            /**
             * Items
             * @description Newest first; drafts included.
             */
            items: components["schemas"]["ScheduleVersionSummary"][];
        };
        /** Violation */
        Violation: {
            /**
             * Code
             * @enum {string}
             */
            code: "unavailable" | "absent" | "missing_skill" | "overlap" | "insufficient_rest" | "travel_time" | "weekly_cap" | "overtime" | "minimum_coverage" | "preferred_coverage" | "locked_changed" | "outside_grid" | "outside_operating_hours" | "inactive_employee" | "rule";
            /**
             * Severity
             * @enum {string}
             */
            severity: "hard" | "soft";
            /**
             * Message
             * @description Deterministic text built from facts; safe to show.
             */
            message: string;
            /** Employee Id */
            employee_id: string | null;
            /** Logical Shift Ids */
            logical_shift_ids: string[];
            /**
             * Facts
             * @description Structured evidence, e.g. rest_minutes and required_rest_minutes.
             */
            facts: {
                [key: string]: unknown;
            };
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createDemoSession: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DemoSessionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DemoSession"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMe: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyWeek: {
        parameters: {
            query: {
                /** @description Monday of the week, outlet-local. */
                week_start: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MyWeek"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listOutlets: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OutletList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSkills: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listEmployees: {
        parameters: {
            query?: {
                /** @description Home outlet filter; required for managers' own outlet only. */
                outlet_id?: string | null;
                status?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EmployeeList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createEmployee: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmployeeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Employee"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getEmployee: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Employee"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    updateEmployee: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmployeeUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Employee"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getAvailability: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Availability"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    putAvailability: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                employee_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AvailabilityUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Availability"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getEmployeeImportTemplate: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportTemplate"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    stageEmployeeImport: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StageImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportJob"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getImport: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description An onboarding import. */
                import_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportJob"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    commitImport: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                /** @description An onboarding import. */
                import_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportJob"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listShiftTemplates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftTemplateList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStaffingTemplates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingTemplateSet"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    putStaffingTemplates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StaffingTemplateUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingTemplateSet"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    expandStaffingRequirements: {
        parameters: {
            query: {
                /** @description Monday of the week, outlet-local. */
                week_start: string;
            };
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpandStaffingRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingRequirements"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStaffingRequirements: {
        parameters: {
            query: {
                /** @description Monday of the week, outlet-local. */
                week_start: string;
            };
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingRequirements"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    putStaffingRequirements: {
        parameters: {
            query: {
                /** @description Monday of the week, outlet-local. */
                week_start: string;
            };
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StaffingRequirementsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingRequirements"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getScheduleWeek: {
        parameters: {
            query?: never;
            header?: {
                /** @description ETag from a previous response. */
                "If-None-Match"?: string | null;
            };
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    /** @description Derived from current_version_id; changes on every publication. */
                    ETag?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleWeek"];
                };
            };
            /** @description Not modified: the If-None-Match value is still current. No body. */
            304: {
                headers: {
                    /** @description Opaque validator. Send it back as If-None-Match to get 304 when nothing changed. */
                    ETag?: string;
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getScheduleVersion: {
        parameters: {
            query?: never;
            header?: {
                /** @description ETag from a previous response. */
                "If-None-Match"?: string | null;
            };
            path: {
                version_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    /** @description Opaque validator. Send it back as If-None-Match to get 304 when nothing changed. */
                    ETag?: string;
                    /** @description Always `private, no-cache`: shift content never changes, but status does (published later becomes superseded), so clients revalidate with If-None-Match and get 304 when nothing changed. */
                    "Cache-Control"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Not modified: the If-None-Match value is still current. No body. */
            304: {
                headers: {
                    /** @description Opaque validator. Send it back as If-None-Match to get 304 when nothing changed. */
                    ETag?: string;
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    generateSchedule: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OptimizationRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description stale_version (base changed), idempotency_conflict (key reused with other input) or run_in_progress (another run is active for this schedule; details.run_id is that run: attach to it and poll instead of showing an error). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description rate_limited: the organization's run cap is reached. */
            429: {
                headers: {
                    /** @description Seconds to wait before retrying. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getOptimizationRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OptimizationRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getOptimizationCandidate: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                candidate_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    selectOptimizationCandidate: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                candidate_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDraft: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateDraftRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewEdits: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EditPreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    applyEdits: {
        parameters: {
            query?: never;
            header?: {
                /** @description Recommended: with it a repeat returns the stored result, so a lost response can be retried safely; without it only revision fencing applies. */
                "Idempotency-Key"?: string | null;
            };
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    publishVersion: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublishResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listProposals: {
        parameters: {
            query: {
                /** @description The week (schedule) whose proposals to list. */
                schedule_id: string;
                /** @description Repeat to filter, e.g. status=pending. A pending proposal past expiry is expired. */
                status?: ("pending" | "approved" | "rejected" | "expired" | "stale" | "failed")[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createProposal: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateProposalRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description A schedule proposal. */
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveProposal: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                /** @description A schedule proposal. */
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApproveProposalRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalDecision"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    rejectProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description A schedule proposal. */
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    discardDraft: {
        parameters: {
            query?: never;
            header?: {
                /** @description Recommended: with it a repeat returns the stored result, so a lost response can be retried safely; without it only revision fencing applies. */
                "Idempotency-Key"?: string | null;
            };
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersionSummary"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listVersions: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionHistory"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    compareVersions: {
        parameters: {
            query: {
                /** @description The version to compare against. */
                with: string;
            };
            header?: never;
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionDiff"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    restoreVersion: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                /** @description A schedule version (draft, published or superseded). */
                version_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RestoreRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listAbsences: {
        parameters: {
            query?: {
                outlet_id?: string | null;
                from?: string | null;
                to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AbsenceList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reportAbsence: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReportAbsenceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AbsenceReport"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    parseCommand: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CommandRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandPreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    parseRule: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RuleParseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RuleParse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewRule: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RuleDefinition"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RulePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listRules: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RuleList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createRule: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RuleDefinition"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SchedulingRule"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    archiveRule: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SchedulingRule"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyNotifications: {
        parameters: {
            query?: {
                unread_only?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    markNotificationRead: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Notification"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyAbsences: {
        parameters: {
            query?: {
                from?: string | null;
                to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AbsenceList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    updateAbsence: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                absence_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateAbsenceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AbsenceReport"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    repairSchedule: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RepairRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OptimizationRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    /** @description Seconds to wait. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    recommendReplacements: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReplacementRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReplacementRecommendations"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createScenario: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateScenarioRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Scenario"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listScenarios: {
        parameters: {
            query?: {
                week_start?: string | null;
            };
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getScenario: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Scenario"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    addScenarioEvent: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioEventIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Scenario"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    runScenario: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioRunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OptimizationRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    /** @description Seconds to wait. */
                    "Retry-After"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    convertScenario: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConvertScenarioRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleVersion"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    discardScenario: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Scenario"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    requestForecast: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ForecastRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ForecastRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getForecastRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ForecastRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStaffingProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingProposal"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    acceptStaffingProposal: {
        parameters: {
            query?: never;
            header: {
                /** @description Unique per logical request; replays return the original result, a different body with the same key is 409. */
                "Idempotency-Key": string;
            };
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingRequirements"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    rejectStaffingProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffingProposal"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyOpenShifts: {
        parameters: {
            query: {
                week_start: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OpenShiftList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyShiftRequests: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createShiftRequest: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateShiftRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    acceptShiftRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    cancelShiftRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listShiftRequests: {
        parameters: {
            query?: {
                status?: ("open" | "pending_manager" | "approved" | "rejected" | "cancelled" | "expired" | "stale" | "invalid") | null;
            };
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveShiftRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    rejectShiftRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShiftRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getMyAvailabilityRequests: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createAvailabilityRequest: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateAvailabilityRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getAvailabilityRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    cancelAvailabilityRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listAvailabilityRequests: {
        parameters: {
            query?: {
                status?: ("pending" | "accepted" | "rejected" | "cancelled") | null;
            };
            header?: never;
            path: {
                outlet_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    acceptAvailabilityRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    rejectAvailabilityRequest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRequestView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    streamOptimizationRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description text/event-stream; see EventStream. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["EventStream"];
                };
            };
            /** @description Error envelope. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    streamForecastRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description text/event-stream; see EventStream. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["EventStream"];
                };
            };
            /** @description Error envelope. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    streamScheduleVersions: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                outlet_id: string;
                week_start: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description text/event-stream; see EventStream. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": components["schemas"]["EventStream"];
                };
            };
            /** @description Error envelope. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Error envelope. */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
