<!-- Sync Impact Report -->
<!-- Version: 0.1.0 → 1.0.0 -->
<!-- Modified principles: All core principles replaced with new documentation, testing, and governance principles -->
<!-- Added sections: Documentation Standards, Testing Standards, Component Governance -->
<!-- Templates updated: plan.md, spec.md, tasks.md -->
<!-- TODO: Create base components documentation -->

# OA Component Constitution

## Core Principles

### I. Comprehensive Documentation (NON-NEGOTIABLE)
Every file MUST include a header with content and API brief description. Headers MUST be updated immediately when file content changes. This enables AI systems to understand file contents without reading entire files, ensuring rapid context comprehension and preventing code-requirement divergence.

### II. Architecture Visualization (MANDATORY)
After completing main business logic, MUST create detailed call flow diagrams mapping every API call (document location → function name). Generate "compressed view" at `.specify/specs/xxxx/research.md` as single source of truth for implementation reference.

### III. Real-First Testing (NON-NEGOTIABLE)
Tests MUST use real implementations whenever possible. Mock testing is PROHIBITED except for: external services with no test environment, performance bottlenecks, or systems under active development. Blocking points in real test implementation MUST be reported immediately for resolution.

### IV. Environment Discipline (MANDATORY)
Server application tests MUST start server script before execution. Python code execution MUST activate virtual environment using `uv` dependency management. No exceptions allowed for environment consistency.

### V. Base Component Governance (NON-NEGOTIABLE)
Existing base components MUST be documented and centrally registered. Private creation of additional base components is STRICTLY PROHIBITED. All modifications to base components require formal application and approval process.

### VI. Package Management Discipline (MANDATORY)
Python package management MUST use `uv` for dependency resolution, installation, and updates. Manual package management via pip is PROHIBITED without explicit justification.

## Additional Requirements

### Code Quality Standards
- All code MUST follow Python PEP 8 style guidelines
- Type hints are MANDATORY for all function signatures
- Docstrings are REQUIRED for all public interfaces
- Error handling MUST be comprehensive and specific
- Code complexity MUST be kept below 10 (McCabe metric)

### Testing Requirements
- Test coverage MUST exceed 80% for all business logic
- Integration tests MUST cover all API endpoints
- Performance tests MUST establish baseline metrics
- Security tests MUST include input validation and authentication flows

### User Experience Consistency
- UI components MUST follow established design system
- Error messages MUST be user-friendly and specific
- Navigation patterns MUST be consistent across the application
- Accessibility standards (WCAG 2.1 AA) MUST be met

### Performance Requirements
- API response times MUST be under 200ms p95 for standard operations
- Database queries MUST be optimized with appropriate indexing
- Memory usage MUST be monitored and optimized
- Caching strategies MUST be implemented for repeated operations

## Governance

### Amendment Process
1. Proposal: Submit amendment request with detailed rationale
2. Review: Core team evaluates impact and compliance
3. Approval: Requires 2/3 majority of technical leads
4. Implementation: Create migration plan with phased rollout
5. Documentation: Update all relevant templates and guidelines

### Compliance Requirements
- All pull requests MUST reference relevant constitution principles
- Code reviews MUST verify compliance with all standards
- Automated checks MUST validate documentation headers and test coverage
- Performance benchmarks MUST be established and tracked

### Quality Gates
- 100% of tests must pass before deployment
- Documentation headers must be present in all new files
- No new technical debt without explicit approval
- Regular architectural reviews (quarterly) for compliance

### Violation Process
- First offense: Warning and required correction
- Second offense: Feature freeze until compliance
- Third offense: Review by governance committee
- Willful violations: Project membership revocation

**Version**: 1.0.0 | **Ratified**: 2026-03-18 | **Last Amended**: 2026-03-18
