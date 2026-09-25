"""Human-facing Council Workflow Builder.

The UI configures exact cohort geometry and provider/model assignments, then
uses the shared Operator facade for governed approval and execution. It never
mints authority locally and never auto-approves.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from capt_ui.operator.council_workflow import (
    CohortWorkflow,
    CouncilWorkflow,
    donor_convergence_workflow,
)
from capt_ui.operator.runtime import Operator, OperatorError


def render_headless(workflow: CouncilWorkflow) -> str:
    workflow.validate()
    return json.dumps(workflow.to_record(), sort_keys=True, separators=(",", ":"))


def _defaults() -> tuple[str, str]:
    state = Path.home() / ".capt"
    return str(state / "runtime.sock"), str(state / "runtime.token")

def run_window(sock: str, token_file: str, target_root: str = "") -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    op = Operator(sock, token_file)
    op.connect()

    root = tk.Tk()
    root.title("CAPT Council Workflow Builder")
    root.geometry("1480x940")

    session: Dict[str, Any] = {}
    cohorts: Dict[str, CohortWorkflow] = {}

    general = ttk.LabelFrame(root, text="Council workflow", padding=8)
    general.pack(fill="x", padx=10, pady=8)

    fields = {}
    specs = (
        ("councilId", "Council ID", "council-human-workflow-r1"),
        ("missionId", "Mission ID", "m-human-workflow-r1"),
        ("targetRoot", "Target root", target_root or os.getcwd()),
        ("maxConcurrent", "Concurrent cohorts", "1"),
        ("contextBudget", "Context budget", "128000"),
        ("executionSeconds", "Execution seconds", "1800"),
    )
    for row, (key, label, default) in enumerate(specs):
        ttk.Label(general, text=label).grid(row=row // 3, column=(row % 3) * 2, sticky="w", padx=4, pady=3)
        var = tk.StringVar(value=default)
        fields[key] = var
        ttk.Entry(general, textvariable=var, width=34).grid(
            row=row // 3, column=(row % 3) * 2 + 1, sticky="ew", padx=4, pady=3
        )
    for col in (1, 3, 5):
        general.columnconfigure(col, weight=1)

    options = ttk.Frame(general)
    options.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(6, 0))
    file_mut = tk.BooleanVar(value=True)
    shell = tk.BooleanVar(value=True)
    verify = tk.BooleanVar(value=True)
    ttk.Checkbutton(options, text="File mutation", variable=file_mut).pack(side="left", padx=6)
    ttk.Checkbutton(options, text="Shell", variable=shell).pack(side="left", padx=6)
    ttk.Checkbutton(options, text="Human verification", variable=verify).pack(side="left", padx=6)
    ttk.Label(options, text="Network").pack(side="left", padx=(18, 4))
    network = tk.StringVar(value="remote_allowed")
    ttk.Combobox(
        options, textvariable=network, state="readonly", width=18,
        values=("remote_allowed", "local_only", "denied"),
    ).pack(side="left")
    body = ttk.Panedwindow(root, orient="vertical")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    cohort_frame = ttk.LabelFrame(body, text="Cohorts — one provider call per cohort", padding=8)
    body.add(cohort_frame, weight=3)
    columns = ("cohort", "provider", "model", "vessels", "configuration")
    cohort_tree = ttk.Treeview(cohort_frame, columns=columns, show="headings", height=9)
    widths = {"cohort": 150, "provider": 130, "model": 300, "vessels": 80, "configuration": 140}
    for col in columns:
        cohort_tree.heading(col, text=col.title())
        cohort_tree.column(col, width=widths[col], anchor="w")
    cohort_tree.pack(fill="both", expand=True)

    editor = ttk.Frame(cohort_frame)
    editor.pack(fill="x", pady=(8, 0))
    evars = {
        "cohort": tk.StringVar(value="c01"),
        "provider": tk.StringVar(value="openrouter"),
        "model": tk.StringVar(value=""),
        "vessels": tk.StringVar(value="11"),
        "configuration": tk.StringVar(value="default"),
    }
    for idx, (key, label) in enumerate((
        ("cohort", "Cohort"), ("provider", "Provider"), ("model", "Model"),
        ("vessels", "Vessels"), ("configuration", "Configuration"),
    )):
        ttk.Label(editor, text=label).grid(row=0, column=idx * 2, sticky="w", padx=3)
        ttk.Entry(editor, textvariable=evars[key], width=22).grid(
            row=0, column=idx * 2 + 1, sticky="ew", padx=3
        )
    objective = tk.Text(editor, height=4, wrap="word")
    ttk.Label(editor, text="Cohort objective").grid(row=1, column=0, sticky="nw", padx=3, pady=5)
    objective.grid(row=1, column=1, columnspan=9, sticky="ew", padx=3, pady=5)
    editor.columnconfigure(5, weight=1)

    approval_frame = ttk.LabelFrame(body, text="Governed approvals", padding=8)
    body.add(approval_frame, weight=2)
    approval_cols = ("cohort", "request", "state", "remaining", "expires")
    approval_tree = ttk.Treeview(approval_frame, columns=approval_cols, show="headings", height=7)
    for col, width in (("cohort", 150), ("request", 280), ("state", 110), ("remaining", 80), ("expires", 190)):
        approval_tree.heading(col, text=col.title())
        approval_tree.column(col, width=width, anchor="w")
    approval_tree.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="Configure a workflow. Requesting approval does not approve it.")
    ttk.Label(root, textvariable=status_var, padding=(10, 4)).pack(fill="x")

    def redraw_cohorts() -> None:
        for item in cohort_tree.get_children():
            cohort_tree.delete(item)
        for cohort in cohorts.values():
            cohort_tree.insert("", "end", iid=cohort.cohort_id, values=(
                cohort.cohort_id, cohort.provider, cohort.model,
                cohort.vessels_per_cohort, cohort.configuration_id,
            ))
    def upsert_cohort() -> None:
        try:
            item = CohortWorkflow(
                cohort_id=evars["cohort"].get().strip(),
                provider=evars["provider"].get().strip(),
                model=evars["model"].get().strip(),
                objective=objective.get("1.0", "end").strip(),
                vessels_per_cohort=int(evars["vessels"].get()),
                configuration_id=evars["configuration"].get().strip() or "default",
            ).validate()
        except Exception as exc:
            messagebox.showerror("Invalid cohort", str(exc))
            return
        cohorts[item.cohort_id] = item
        redraw_cohorts()

    def remove_cohort() -> None:
        for item in cohort_tree.selection():
            cohorts.pop(str(item), None)
        redraw_cohorts()

    def load_selected(_event=None) -> None:
        selected = cohort_tree.selection()
        if not selected:
            return
        item = cohorts[str(selected[0])]
        evars["cohort"].set(item.cohort_id)
        evars["provider"].set(item.provider)
        evars["model"].set(item.model)
        evars["vessels"].set(str(item.vessels_per_cohort))
        evars["configuration"].set(item.configuration_id)
        objective.delete("1.0", "end")
        objective.insert("1.0", item.objective)

    cohort_tree.bind("<<TreeviewSelect>>", load_selected)
    buttons = ttk.Frame(cohort_frame)
    buttons.pack(fill="x", pady=(6, 0))
    ttk.Button(buttons, text="Add / update cohort", command=upsert_cohort).pack(side="left")
    ttk.Button(buttons, text="Remove selected", command=remove_cohort).pack(side="left", padx=6)

    def build_workflow() -> CouncilWorkflow:
        return CouncilWorkflow(
            council_id=fields["councilId"].get().strip(),
            mission_id=fields["missionId"].get().strip(),
            target_root=fields["targetRoot"].get().strip(),
            cohorts=tuple(cohorts.values()),
            max_concurrent_cohorts=int(fields["maxConcurrent"].get()),
            requested_context_budget=int(fields["contextBudget"].get()),
            requested_execution_seconds=int(fields["executionSeconds"].get()),
            file_mutation_allowed=file_mut.get(),
            shell_access_allowed=shell.get(),
            human_verification_required=verify.get(),
            provider_network_policy=network.get(),
        ).validate()

    def apply_workflow(workflow: CouncilWorkflow) -> None:
        fields["councilId"].set(workflow.council_id)
        fields["missionId"].set(workflow.mission_id)
        fields["targetRoot"].set(workflow.target_root)
        fields["maxConcurrent"].set(str(workflow.max_concurrent_cohorts))
        fields["contextBudget"].set(str(workflow.requested_context_budget))
        fields["executionSeconds"].set(str(workflow.requested_execution_seconds))
        file_mut.set(workflow.file_mutation_allowed)
        shell.set(workflow.shell_access_allowed)
        verify.set(workflow.human_verification_required)
        network.set(workflow.provider_network_policy)
        cohorts.clear()
        cohorts.update((c.cohort_id, c) for c in workflow.cohorts)
        redraw_cohorts()

    def load_donor_template() -> None:
        try:
            apply_workflow(donor_convergence_workflow(fields["targetRoot"].get().strip()))
            status_var.set("Loaded exact donor template: 3 cohorts × 11 vessels, sequential.")
        except Exception as exc:
            messagebox.showerror("Template error", str(exc))

    ttk.Button(buttons, text="Load donor 3×11 template", command=load_donor_template).pack(side="right")

    draft = ttk.Frame(root)
    draft.pack(fill="x", padx=10, pady=(0, 6))

    def save_draft() -> None:
        try:
            workflow = build_workflow()
        except Exception as exc:
            messagebox.showerror("Invalid workflow", str(exc))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("CAPT workflow", "*.json"), ("JSON", "*.json")]
        )
        if path:
            Path(path).write_text(json.dumps(workflow.to_record(), indent=2) + "\n")
            status_var.set("Draft saved: " + path)
    def load_draft() -> None:
        path = filedialog.askopenfilename(filetypes=[("CAPT workflow", "*.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            workflow = CouncilWorkflow.from_mapping(json.loads(Path(path).read_text())).validate()
            apply_workflow(workflow)
            status_var.set("Draft loaded: " + path)
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    ttk.Button(draft, text="Save workflow draft", command=save_draft).pack(side="left")
    ttk.Button(draft, text="Load workflow draft", command=load_draft).pack(side="left", padx=6)

    def redraw_approvals(rows) -> None:
        for item in approval_tree.get_children():
            approval_tree.delete(item)
        for row in rows:
            approval_tree.insert("", "end", iid=row["requestId"], values=(
                row.get("cohortId"), row.get("requestId"), row.get("state"),
                row.get("remainingUses"), row.get("expiresAt"),
            ))

    def request_approvals() -> None:
        nonlocal session
        try:
            workflow = build_workflow()
            session = op.request_council_workflow(workflow)
            rows = op.council_workflow_status(session)
            redraw_approvals(rows)
            status_var.set(
                "Approval requests created. Human decision required before launch. "
                f"logical vessels={workflow.logical_vessels}"
            )
        except Exception as exc:
            messagebox.showerror("Approval request failed", str(exc))

    def refresh_approvals() -> None:
        if not session:
            return
        try:
            redraw_approvals(op.council_workflow_status(session))
        except Exception as exc:
            messagebox.showerror("Refresh failed", str(exc))

    def decide(decision: str) -> None:
        if not session:
            messagebox.showwarning("No session", "Request approvals first.")
            return
        label = "APPROVE" if decision == "approve" else "DENY"
        if not messagebox.askyesno(
            f"{label} Council workflow",
            f"{label} every currently requested cohort in this exact workflow?",
        ):
            return
        try:
            op.decide_council_workflow(session, decision, "Human decision from Council Workflow Builder.")
            refresh_approvals()
            status_var.set(f"Human decision recorded: {decision}.")
        except Exception as exc:
            messagebox.showerror("Decision failed", str(exc))
    def launch() -> None:
        if not session:
            messagebox.showwarning("No session", "Request approvals first.")
            return
        try:
            rows = op.council_workflow_status(session)
        except Exception as exc:
            messagebox.showerror("Status failed", str(exc))
            return
        if any(row.get("state") != "approved" for row in rows):
            messagebox.showwarning("Not approved", "Every cohort must be explicitly approved before launch.")
            redraw_approvals(rows)
            return
        if not messagebox.askyesno(
            "Launch governed Council",
            "Launch this exact approved Council through RuntimeService now?",
        ):
            return
        status_var.set("Council running… runtime receipts will remain authoritative.")

        def worker() -> None:
            try:
                receipt = op.run_council_workflow(session)
                root.after(0, lambda: status_var.set(
                    "Council finished: " + json.dumps(receipt.get("result") or {}, sort_keys=True)[:900]
                ))
            except Exception as exc:
                root.after(0, lambda: messagebox.showerror("Council run failed", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    controls = ttk.Frame(approval_frame)
    controls.pack(fill="x", pady=(6, 0))
    ttk.Button(controls, text="1. Request approvals", command=request_approvals).pack(side="left")
    ttk.Button(controls, text="2. Approve requested", command=lambda: decide("approve")).pack(side="left", padx=6)
    ttk.Button(controls, text="Deny requested", command=lambda: decide("deny")).pack(side="left")
    ttk.Button(controls, text="3. Launch approved Council", command=launch).pack(side="left", padx=18)
    ttk.Button(controls, text="Refresh", command=refresh_approvals).pack(side="right")

    def close() -> None:
        try:
            op.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    if target_root:
        try:
            apply_workflow(donor_convergence_workflow(target_root))
        except Exception:
            pass
    root.mainloop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CAPT human Council Workflow Builder")
    default_sock, default_token = _defaults()
    parser.add_argument("--sock", default=os.environ.get("CAPT_RUNTIME_SOCK", default_sock))
    parser.add_argument("--token-file", default=os.environ.get("CAPT_RUNTIME_TOKEN_FILE", default_token))
    parser.add_argument("--target-root", default="")
    parser.add_argument("--template", choices=("blank", "donor-convergence"), default="blank")
    parser.add_argument("--headless", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    target = args.target_root or os.getcwd()
    if args.headless:
        workflow = (
            donor_convergence_workflow(target)
            if args.template == "donor-convergence"
            else CouncilWorkflow(
                council_id="council-draft",
                mission_id="m-draft",
                target_root=target,
                cohorts=(CohortWorkflow("c01", "openrouter", "model", "Objective", 1),),
            ).validate()
        )
        print(render_headless(workflow))
        return 0
    run_window(args.sock, args.token_file, target if args.template == "donor-convergence" else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
