# VARYN checkpoint 17L: User-facing three-role collaboration in Tk desktop

**Date:** 2026-11-04. **Branch:** feat/local-memory-prototype-20261103. **PR #1:** Draft; do not merge.
**Purpose:** Connect the 17K bounded analyst -> critic -> synthesizer collaboration engine to the actual VARYN Tkinter desktop, with explicit stage selection and review.

## What is implemented

The desktop now includes **Collaborate (3 roles)** alongside Send. The button opens a modal with three rows where the owner explicitly selects a provider and exact model ID for each role. Each defaults to **fake / fake-test** (offline, no AI model quality).

Clicking **Review and run 3 stages**:
1. Captures the typed task and the three model selections as an immutable request plan. Strict validation happens before any approval is requested.
2. If ANY stage selects a live developer-model API, VARYN requires the existing network permission checkbox and shows a **separate approval dialog for each external stage**. Each dialog names the exact role, provider and model, warns of possible API charges, and explicitly discloses transfer of the original task and bounded output of earlier model stages to the next provider. Rejecting any dialog aborts the entire plan without dispatch.
3. Creates a CollaborationEngine that shares the same in-memory request/token UsageBudget and provider registry already used by ordinary desktop chat. No hidden separate model-call budget is created.
4. Runs the reviewed plan in a background thread and routes its result back to the Tk main thread. The UI shows analyst, critic, synthesizer and a clearly labeled final synthesis. Send and Collaborate are disabled during a pending request.
5. Existing discard/close handling can hide a pending result but **cannot cancel a provider call already running or undo charges**. No retries, failover, automatic provider selection, or replay. No memory is uploaded by this feature.

The 17K engine remains strict on role order, stage budget, no direct official consumer-history access, and untrusted prior outputs. A separate review helper varies the permission question by each stage. Neither a mere network toggle nor a model-generated text value is accepted as individual stage authorization. This is UI-level approval, not authenticated OS identity or cryptographic proof of human consent.

## Verification

- tests/test_desktop_collaboration.py: 16 tests for offline-only action, network permission, exact per-stage live approval, prior-result sharing disclosure, invalid model-before-approval, full-plan refusal, budget shared with regular chat, controller live consent snapshot, sanitized errors and worker dispatch.
- tests/test_desktop_collaboration_tk.py: Windows-only graphical smoke that opens the real desktop and its configuration modal, invokes the real Tk button callbacks with three fake provider stages, then checks the visible transcript and session budget. No human mouse click or live provider API.
- Existing Windows Tk widget smoke and all 17K collaboration regressions remain mandatory.
- CI on both Windows and Ubuntu must pass from the final commit SHA; interim failed CI must be recorded, not ignored.

## How to try safely

On a Windows PC with Python and Tkinter installed, extract the inspected VARYN source package and launch the program in a **non-Administrator** session:

    py -3 -m varyn.desktop

Type a synthetic, non-sensitive task; select **Collaborate (3 roles)**, leave each provider at **fake**, and click **Review and run 3 stages**. The result should show separate fake-role labels in the transcript. The fake provider is deterministic placeholder text: it is NOT a working reasoning model and cannot demonstrate improvements in reasoning or creativity.

Real model stages require explicit API credentials and network permission, may incur provider charges, and forward earlier outputs to later providers. **Do not paste passwords, private documents, employer data or personal conversations into live tasks.** There is no true billing ceiling, hardware sandbox, active-use authorization, or independent physical-PC acceptance yet. Account login to consumer ChatGPT/Claude/Gemini apps is not part of this feature.

## Boundaries and next work

This completes the **desktop linkage** milestone for target 1. It does NOT establish measured multi-model quality, inter-app history sync, shared memory, cross-provider official app connectivity, unattended autonomous execution or persistent checkpoints.

Next priority: explicit project-scoped memory access with user-controlled retrieval and source labels, and deterministic side-by-side quality measurements against a single-model baseline. The user-selected **Option C**, automatic two-way history sync among the real consumer apps, remains blocked by separately verified provider authority, as documented in 17I's seven proof gates.
