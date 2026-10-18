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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
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
             * @description Only confirmed absences make an overlapping shift invalid.
             * @enum {string}
             */
            status: "requested" | "confirmed";
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
            /**
             * Strategy
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage";
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
             * Draft Version Id
             * Format: uuid
             * @description Fetch with GET /v2/schedule-versions/{id}.
             */
            draft_version_id: string;
            metrics: components["schemas"]["Metrics"];
            /**
             * Changed Shifts
             * @description Logical shifts differing from the base version.
             */
            changed_shifts: number;
            /** @description Independent validator result. A candidate with hard violations is never returned. */
            validation: components["schemas"]["ValidationResult"];
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
        };
        /** DemoSessionRequest */
        DemoSessionRequest: {
            /**
             * Persona
             * @enum {string}
             */
            persona: "owner" | "manager" | "staff";
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
        /** GenerateRequest */
        GenerateRequest: {
            /**
             * Strategy
             * @default balanced
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage";
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
        };
        /** Infeasibility */
        Infeasibility: {
            /** Summary */
            summary: string;
            /** Shortages */
            shortages: components["schemas"]["Shortage"][];
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
            kind: "generate" | "optimize" | "repair";
            /** Outlet Ids */
            outlet_ids: string[];
            /** Base Version Ids */
            base_version_ids: string[];
            /**
             * Strategy
             * @enum {string}
             */
            strategy: "balanced" | "lowest_cost" | "staff_friendly" | "max_coverage";
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
            source: "seed" | "manual" | "generate" | "optimize" | "repair" | "restore" | "import";
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
            source: "seed" | "manual" | "generate" | "optimize" | "repair" | "restore" | "import";
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
             * @enum {string}
             */
            source: "band" | "manual" | "scenario";
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
        /** ValidationResult */
        ValidationResult: {
            /** Hard Violations */
            hard_violations: number;
            /** Soft Violations */
            soft_violations: number;
            /** Violations */
            violations: components["schemas"]["Violation"][];
        };
        /** Violation */
        Violation: {
            /**
             * Code
             * @enum {string}
             */
            code: "unavailable" | "absent" | "missing_skill" | "overlap" | "insufficient_rest" | "travel_time" | "weekly_cap" | "overtime" | "minimum_coverage" | "preferred_coverage" | "locked_changed" | "outside_grid" | "outside_operating_hours" | "inactive_employee";
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
                    /** @description `private, max-age=31536000, immutable` for published and superseded versions (they never change); `private, no-cache` for drafts. */
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
}
